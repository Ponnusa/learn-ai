"""
Chat router — conversation management + AI responses.
Subject detection runs in parallel with main AI call (asyncio.gather).
Profile update runs in background after every 5 messages.
"""
import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, Response
from pydantic import BaseModel
from database import get_db
from services.ai_router import openai_client, get_model
from services.subject_detector import detect_subject
from services.prompt_builder import build_chat_prompt, inject_conversation_context, CHAT_SYSTEM_PROMPT
from services.profile_updater import update_student_profile
from services.conversation_summarizer import maybe_summarize
from services.credits import check_message_credit
from services.chips import generate_chips

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
                  AND (c.conversation_type = 'chat' OR c.conversation_type IS NULL)
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
                  AND (c.conversation_type = 'chat' OR c.conversation_type IS NULL)
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


@router.post("/debug-prompt")
async def debug_prompt(req: ChatRequest):
    """
    DEV — returns the exact system prompt + message history that would be
    sent to the AI for this request, without calling the AI or charging credit.
    """
    conv_id      = req.conversation_id
    subject      = None
    conv_summary = None
    topics_covered = None
    history: list = []

    if conv_id:
        async with get_db() as db:
            conv = await db.fetchrow("""
                SELECT subject, summary, topics_covered
                FROM conversations WHERE id = $1
            """, conv_id)
            if conv:
                subject        = conv["subject"]
                conv_summary   = conv["summary"]
                topics_covered = conv["topics_covered"]

            rows = await db.fetch("""
                SELECT role, content FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at DESC LIMIT 6
            """, conv_id)
            history = list(reversed(rows))

    system_prompt = await build_chat_prompt(req.user_id, subject, req.language)
    system_prompt = inject_conversation_context(system_prompt, conv_summary, topics_covered)

    task   = "chat_response_vision" if req.image_url else "chat_response"
    model  = get_model(task)
    msgs   = [{"role": h["role"], "content": h["content"]} for h in history]

    return {
        "model":               model,
        "system_prompt":       system_prompt,
        "system_prompt_chars": len(system_prompt),
        "history":             msgs,
        "history_count":       len(msgs),
        "conversation_id":     conv_id,
        "subject":             subject,
    }


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
    await check_message_credit(req.user_id, req.session_id)

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
        user_meta = json.dumps({"image_url": req.image_url}) if req.image_url else None
        await db.execute("""
            INSERT INTO messages (conversation_id, role, content, content_type, metadata)
            VALUES ($1, 'user', $2, $3, $4)
        """, conv_id, req.message, content_type, user_meta)

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
    chips = await generate_chips(reply_text, req.language)

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


_TITLE_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish'}

async def _generate_title(message: str, language: str) -> str:
    """Generate a short conversation title from the first message."""
    try:
        lang_note = ""
        if language in _TITLE_LANGUAGE_NAMES:
            lang_note = f" Write the title in {_TITLE_LANGUAGE_NAMES[language]}."
        resp = await openai_client.chat.completions.create(
            model=get_model("title_generation"),
            messages=[{
                "role": "user",
                "content": f"Generate a short title (max 5 words) for a conversation starting with: {message[:200]}. Return plain text only.{lang_note}",
            }],
            max_tokens=20,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception:
        return message[:40]


_TTS_LANG_NAMES = {'en': 'English', 'fi': 'Finnish', 'sv': 'Swedish'}

_TTS_SYSTEM = (
    "Convert this educational text to a clean spoken script in {lang}. "
    "Rules: remove all LaTeX delimiters and commands ($, $$, \\[, \\], \\ce{{}}, etc.); "
    "write formulas as spoken words (e.g. C_2H_4 becomes C 2 H 4, x^2 becomes x squared, "
    "\\frac{{a}}{{b}} becomes a over b); "
    "remove all markdown symbols (**, __, #, backticks, bullet dashes); "
    "convert bullet lists to natural flowing sentences; "
    "keep all educational content intact. "
    "Output plain prose only — no symbols, no formatting marks."
)


@router.get("/messages/{message_id}/audio")
async def get_message_audio(message_id: str, language: str = "en"):
    """Return cached audio for a chat message, generating and saving it on first call.

    First call:  GPT-4o-mini cleans LaTeX/markdown to spoken prose,
                 tts-1 (nova) converts to audio, saved to messages.audio_data.
    Subsequent:  read audio_data from DB directly — no AI calls.
    """
    from fastapi import HTTPException as _HTTPException
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT audio_data, content FROM messages WHERE id = $1::uuid",
            message_id,
        )
    if not row:
        raise _HTTPException(404, "Message not found")

    if row["audio_data"]:
        return Response(
            content=bytes(row["audio_data"]),
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    lang_name = _TTS_LANG_NAMES.get(language, "English")

    clean_resp = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _TTS_SYSTEM.format(lang=lang_name)},
            {"role": "user", "content": row["content"][:3000]},
        ],
        max_tokens=800,
        temperature=0.3,
    )
    spoken = clean_resp.choices[0].message.content.strip()

    audio_resp = await openai_client.audio.speech.create(
        model="tts-1", voice="nova", input=spoken[:4096],
    )
    audio_bytes = audio_resp.content

    async with get_db() as db:
        await db.execute(
            "UPDATE messages SET audio_data = $1, audio_script = $2 WHERE id = $3::uuid",
            audio_bytes, spoken, message_id,
        )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
