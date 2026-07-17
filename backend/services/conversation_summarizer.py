"""
Conversation summariser — background task, never blocks a response.

What it does
------------
Once a conversation grows beyond COMPRESS_THRESHOLD messages, this service
compresses everything except the most recent KEEP_RECENT messages into a
compact prose summary and a structured topic map. Both are stored on the
conversations row and injected into future system prompts so the model
always has full context without ever hitting the token limit.

Trigger cadence
---------------
Called after every AI reply in chat.py. Does nothing until
total_msg_count >= COMPRESS_THRESHOLD, then fires whenever at least
NEW_MSG_TRIGGER new messages have accumulated since the last summary.
"""
import json
from database import get_db
from services.ai_router import openai_client, get_model

_SUMMARIZER_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish'}

KEEP_RECENT        = 6    # messages kept verbatim (3 user+assistant pairs)
COMPRESS_THRESHOLD = 10   # don't summarise until we have at least this many
NEW_MSG_TRIGGER    = 8    # re-summarise after this many new msgs since last run

_PROMPT = """\
You are an internal educational-AI assistant reviewing a student-tutor conversation.
Write a concise internal note (3-6 sentences) that captures:
1. Which topics have been explained and at what depth
2. How well the student appeared to understand each topic
3. Any confusions, gaps, or misconceptions that emerged

Then extract structured lists.

Return ONLY valid JSON — no markdown, no extra text:
{{
  "summary": "...",
  "topics_covered": ["topic1", "topic2"],
  "weak_areas": ["area where student struggled", "..."]
}}

CONVERSATION TO SUMMARISE:
{transcript}
"""


async def maybe_summarize(conversation_id: str, total_msg_count: int) -> None:
    """
    Entry point called from chat.py after every AI reply.
    Returns immediately if the threshold hasn't been reached.
    Never raises — errors are swallowed so they never affect the response.
    """
    if total_msg_count < COMPRESS_THRESHOLD:
        return

    try:
        async with get_db() as db:
            row = await db.fetchrow(
                "SELECT summarized_msg_count FROM conversations WHERE id = $1",
                conversation_id,
            )
        if not row:
            return

        already = row["summarized_msg_count"] or 0
        if (total_msg_count - already) < NEW_MSG_TRIGGER:
            return   # not enough new messages yet

        await _run(conversation_id, total_msg_count)

    except Exception:
        pass   # summariser never breaks anything


async def _run(conversation_id: str, total_msg_count: int) -> None:
    """Does the actual LLM call and DB write. Swallows all exceptions."""
    try:
        async with get_db() as db:
            all_msgs = await db.fetch("""
                SELECT role, content FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
            """, conversation_id)
            lang_val = await db.fetchval("""
                SELECT u.language FROM conversations c
                JOIN users u ON u.id = c.user_id
                WHERE c.id = $1
            """, conversation_id)

        if len(all_msgs) <= KEEP_RECENT:
            return

        # Compress everything except the most recent KEEP_RECENT messages.
        # Truncate each message so the prompt stays cheap.
        to_compress = all_msgs[:-KEEP_RECENT]
        transcript  = "\n".join(
            f"{m['role'].upper()}: {m['content'][:400]}"
            for m in to_compress
        )

        lang_note = ""
        if lang_val and lang_val in _SUMMARIZER_LANGUAGE_NAMES:
            lang_note = f"\n\nWrite the summary and topic lists in {_SUMMARIZER_LANGUAGE_NAMES[lang_val]}."

        resp = await openai_client.chat.completions.create(
            model=get_model("conversation_summary"),
            messages=[{"role": "user", "content": _PROMPT.format(transcript=transcript) + lang_note}],
            max_tokens=450,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        data    = json.loads(resp.choices[0].message.content)
        summary = (data.get("summary") or "").strip()
        covered = data.get("topics_covered") or []
        weak    = data.get("weak_areas") or []

        if not summary:
            return

        # summarized_msg_count tracks how many messages are compressed;
        # future calls know not to re-summarise until KEEP_RECENT more arrive.
        new_summarized_count = total_msg_count - KEEP_RECENT

        async with get_db() as db:
            await db.execute("""
                UPDATE conversations
                SET summary              = $1,
                    topics_covered       = $2::jsonb,
                    summarized_msg_count = $3
                WHERE id = $4
            """,
                summary,
                json.dumps({"covered": covered, "weak_areas": weak}),
                new_summarized_count,
                conversation_id,
            )

    except Exception:
        pass
