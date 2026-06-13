"""
Chat router — conversation management + AI responses.
Subject detection runs in parallel with main AI call (asyncio.gather).
Profile update runs in background after every 5 messages.
"""
import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from database import get_db
from services.ai_router import openai_client, get_model
from services.subject_detector import detect_subject
from services.prompt_builder import build_chat_prompt, inject_conversation_context, CHAT_SYSTEM_PROMPT
from services.profile_updater import update_student_profile
from services.conversation_summarizer import maybe_summarize
from services.tier_config import get_limit
from services.scoring import score_signal

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _noop() -> dict:
    """No-op coroutine — replaces the removed asyncio.coroutine() in Python 3.11+."""
    return {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    image_url: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    language: str = "en"


class ConversationCreateRequest(BaseModel):
    user_id: str | None = None
    session_id: str | None = None


@router.post("/conversations")
async def create_conversation(req: ConversationCreateRequest):
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO conversations (user_id, session_id)
            VALUES ($1, $2) RETURNING id, created_at
        """, req.user_id, req.session_id)
    return {"conversation_id": str(row["id"]), "created_at": row["created_at"]}


@router.get("/conversations")
async def list_conversations(user_id: str | None = None, session_id: str | None = None):
    async with get_db() as db:
        if user_id:
            rows = await db.fetch("""
                SELECT c.id, c.title, c.subject, c.subtopic,
                       c.study_set_id, c.created_at, c.updated_at,
                       ss.title AS study_set_title
                FROM conversations c
                LEFT JOIN study_sets ss ON ss.id = c.study_set_id
                WHERE c.user_id = $1
                ORDER BY c.updated_at DESC LIMIT 50
            """, user_id)
        elif session_id:
            rows = await db.fetch("""
                SELECT c.id, c.title, c.subject, c.subtopic,
                       c.study_set_id, c.created_at, c.updated_at,
                       ss.title AS study_set_title
                FROM conversations c
                LEFT JOIN study_sets ss ON ss.id = c.study_set_id
                WHERE c.session_id = $1
                ORDER BY c.updated_at DESC LIMIT 20
            """, session_id)
        else:
            return []
    return [dict(r) for r in rows]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, role, content, content_type, metadata, created_at
            FROM messages WHERE conversation_id = $1
            ORDER BY created_at ASC
        """, conversation_id)
    # asyncpg returns JSONB columns as raw strings — parse them so the
    # frontend receives proper JSON objects (not escaped string literals)
    result = []
    for r in rows:
        meta = r["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        result.append({
            "id":           str(r["id"]),
            "role":         r["role"],
            "content":      r["content"],
            "content_type": r["content_type"],
            "metadata":     meta or {},
            "created_at":   r["created_at"].isoformat() if r["created_at"] else None,
        })
    return result


@router.post("/send")
async def send_message(req: ChatRequest, bg: BackgroundTasks):
    """
    Main chat endpoint.
    1. Check credits
    2. Ensure conversation exists
    3. Save user message
    4. Run AI response + subject detection in parallel
    5. Save AI reply
    6. Update conversation title/subject if first message
    7. Trigger profile update in background every 5 messages
    """
    # ── 1. Credit check ──────────────────────────────────────────────────────
    await _check_message_credit(req.user_id, req.session_id)

    async with get_db() as db:
        # ── 2. Ensure conversation exists ────────────────────────────────────
        conv_id = req.conversation_id
        if not conv_id:
            row = await db.fetchrow("""
                INSERT INTO conversations (user_id, session_id)
                VALUES ($1, $2) RETURNING id
            """, req.user_id, req.session_id)
            conv_id = str(row["id"])

        # Get conversation context (including rolling summary + topic map)
        conv = await db.fetchrow("""
            SELECT subject, subtopic, title,
                   summary, topics_covered, summarized_msg_count
            FROM conversations WHERE id = $1
        """, conv_id)
        is_first_message = (conv["title"] is None)
        subject          = conv["subject"] if conv else None
        conv_summary     = conv["summary"] if conv else None
        topics_covered   = conv["topics_covered"] if conv else None

        # Keep last 6 messages verbatim; older content lives in conv_summary.
        # (12 → 6 because the summary already carries all earlier context.)
        history = await db.fetch("""
            SELECT role, content FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC LIMIT 6
        """, conv_id)
        history = list(reversed(history))

        # Fetch diagram knowledge models for this conversation (for AI context)
        diagram_rows = await db.fetch("""
            SELECT concept, knowledge_model, spec FROM educational_images
            WHERE conversation_id = $1 AND status = 'ready'
            ORDER BY created_at ASC LIMIT 5
        """, conv_id)

        # ── 3. Save user message ─────────────────────────────────────────────
        content_type = "image_url" if req.image_url else "text"
        await db.execute("""
            INSERT INTO messages (conversation_id, role, content, content_type)
            VALUES ($1, 'user', $2, $3)
        """, conv_id, req.message, content_type)

        # Increment session counter
        if req.session_id:
            await db.execute("""
                UPDATE anonymous_sessions SET msg_count = msg_count + 1 WHERE id = $1
            """, req.session_id)

    # ── 4. Build system prompt + detect subject in parallel ──────────────────
    system_prompt_task = build_chat_prompt(req.user_id, subject, req.language)
    subject_task = (
        detect_subject(text=req.message, image_url=req.image_url)
        if is_first_message or not subject
        else _noop()
    )

    system_prompt, subject_data = await asyncio.gather(
        system_prompt_task,
        subject_task,
        return_exceptions=True,
    )
    if isinstance(system_prompt, Exception):
        system_prompt = CHAT_SYSTEM_PROMPT
    if isinstance(subject_data, Exception):
        subject_data = {}

    # Inject rolling summary + topic map so the model never re-explains covered ground
    system_prompt = inject_conversation_context(system_prompt, conv_summary, topics_covered)

    # Append diagram knowledge context so AI can answer questions about generated images
    if diagram_rows:
        diagram_lines = []
        for d in diagram_rows:
            km   = d["knowledge_model"] or {}
            spec = d["spec"] or {}
            goal         = km.get("learning_goal") or spec.get("key_relationships", "")
            entities     = km.get("entities") or []
            mechanisms   = km.get("mechanisms") or []
            misconceptions = km.get("common_misconceptions") or []
            must_show    = km.get("must_show") or spec.get("visual_elements") or []

            line = f'- Diagram: "{d["concept"]}"'
            if goal:        line += f'\n  Learning goal: {goal}'
            if must_show:   line += f'\n  Shows: {", ".join(must_show[:6])}'
            if entities:    line += f'\n  Entities: {", ".join(entities[:5])}'
            if mechanisms:  line += f'\n  Mechanisms: {", ".join(mechanisms[:4])}'
            if misconceptions:
                line += f'\n  Common misconceptions: {", ".join(misconceptions[:2])}'
            diagram_lines.append(line)

        system_prompt = (
            system_prompt
            + "\n\n[DIAGRAMS IN THIS CONVERSATION]\n"
            "The student has generated the following educational diagrams. "
            "Use this knowledge to answer questions about the diagrams — "
            "you cannot see the images but know exactly what they represent:\n\n"
            + "\n\n".join(diagram_lines)
            + "\n[END DIAGRAMS]"
        )

    # ── 5. Call AI (GPT-4o or GPT-4o with vision) ────────────────────────────
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})

    if req.image_url:
        user_content = [
            {"type": "image_url", "image_url": {"url": req.image_url}},
            {"type": "text", "text": req.message},
        ]
    else:
        user_content = req.message
    messages.append({"role": "user", "content": user_content})

    task = "chat_response_vision" if req.image_url else "chat_response"
    ai_resp = await openai_client.chat.completions.create(
        model=get_model(task),
        messages=messages,
        max_tokens=2048,
        temperature=0.7,
    )
    reply_text = ai_resp.choices[0].message.content

    # ── 6. Generate suggestion chips (background-ish, fast) ──────────────────
    chips = await _generate_chips(reply_text, req.language)

    # ── 7. Save AI reply + update conversation ───────────────────────────────
    async with get_db() as db:
        msg_row = await db.fetchrow("""
            INSERT INTO messages (conversation_id, role, content, metadata)
            VALUES ($1, 'assistant', $2, $3::jsonb) RETURNING id, created_at
        """, conv_id, reply_text, json.dumps({"chips": chips, "subject": subject_data}))

        msg_count_row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = $1", conv_id
        )
        msg_count = msg_count_row["cnt"]

        # Update conversation subject + title on first message
        if is_first_message and subject_data.get("subject"):
            title = await _generate_title(req.message, req.language)
            await db.execute("""
                UPDATE conversations
                SET subject = $1, subtopic = $2, subject_confidence = $3,
                    title = $4, updated_at = NOW()
                WHERE id = $5
            """, subject_data.get("subject"), subject_data.get("subtopic"),
                subject_data.get("confidence"), title, conv_id)
        else:
            await db.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1", conv_id
            )

    # ── 8. Conversation summariser (background) — runs whenever enough new
    #        messages have accumulated; updates rolling summary + topic map.
    bg.add_task(maybe_summarize, conv_id, msg_count)

    # ── 9. Profile update every 5 messages (background) ──────────────────────
    if req.user_id and msg_count % 5 == 0:
        bg.add_task(
            update_student_profile,
            req.user_id, conv_id, subject_data.get("subject", "General")
        )

    return {
        "conversation_id": conv_id,
        "message_id": str(msg_row["id"]),
        "reply": reply_text,
        "chips": chips,
        "subject": subject_data,
    }


async def _check_message_credit(user_id: str | None, session_id: str | None):
    async with get_db() as db:
        if user_id:
            user = await db.fetchrow("SELECT tier FROM users WHERE id = $1", user_id)
            tier = user["tier"] if user else "free"
            limit = await get_limit(tier, "messages_daily")
            if limit == -1:
                return
            count = await db.fetchval("""
                SELECT COUNT(*) FROM usage_events
                WHERE user_id = $1 AND event_type = 'message_sent'
                AND created_at > NOW() - INTERVAL '1 day'
            """, user_id)
            if count >= limit:
                raise HTTPException(status_code=429, detail="Daily message limit reached")
            await db.execute("""
                INSERT INTO usage_events (user_id, event_type) VALUES ($1, 'message_sent')
            """, user_id)
        elif session_id:
            row = await db.fetchrow(
                "SELECT msg_count FROM anonymous_sessions WHERE id = $1", session_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            limit = await get_limit("anonymous", "messages_total")
            if row["msg_count"] >= limit:
                raise HTTPException(status_code=429, detail="session_limit_reached")


async def _generate_chips(reply: str, language: str) -> list[str]:
    """
    Generate 3 topic-specific follow-up suggestion chips.
    Mix of: deeper questions, real-world examples, common mistake checks.
    Each must be ≤9 words and specific to the content — not generic.
    """
    try:
        resp = await openai_client.chat.completions.create(
            model=get_model("suggestion_chips"),
            messages=[{
                "role": "user",
                "content": (
                    "Generate exactly 3 short follow-up prompts a student would naturally say "
                    "after reading this explanation. Rules:\n"
                    "- Each prompt ≤9 words\n"
                    "- Be SPECIFIC: mention actual concepts, formulas, or terms from the text\n"
                    "- Mix: one deeper question, one example/application request, one common-mistake check\n"
                    "- Do NOT use generic phrases like 'explain more' or 'tell me more'\n"
                    f"- Language: {language}\n"
                    "Return JSON: {\"suggestions\": [\"...\", \"...\", \"...\"]}\n\n"
                    f"{reply[:700]}"
                ),
            }],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        chips = data.get("suggestions") or data.get("chips") or []
        return [c for c in chips if isinstance(c, str) and c.strip()][:3]
    except Exception:
        return []


async def _generate_title(message: str, language: str) -> str:
    """Generate a short conversation title from the first message."""
    try:
        resp = await openai_client.chat.completions.create(
            model=get_model("title_generation"),
            messages=[{
                "role": "user",
                "content": f"Generate a short title (max 5 words) for a conversation starting with: {message[:200]}. Return plain text only.",
            }],
            max_tokens=20,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception:
        return message[:40]
