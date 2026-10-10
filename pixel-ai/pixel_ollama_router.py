"""Deterministic fast-path routing for pixel_ollama_voice.py.

Standalone, new file -- same non-interfering pattern as the other
pixel_*.py modules. Compared against mayukh4/pibot_local_agent's
router.py: that project uses Ollama's structured tool-calling (plus a
keyword fallback for when the model doesn't emit one) to route between
several API-backed tools (weather, news, jokes) and a cloud model. We
don't have those API keys wired up here, and don't want this mode's
"zero cost" story to quietly grow a cloud fallback, so this is scoped
down to what's actually useful right now: answering trivial things
(time/date, "how are you feeling") instantly from real Python/OS data,
with ZERO Ollama call at all, before anything reaches the LLM.
Everything else still goes through Ollama exactly as before -- this is
a fast path in front of _stream_ollama_reply(), not a replacement for it.

Keyword matching only, not Ollama's structured tool-calling -- reliable
regardless of which model is pulled (phi3:mini's tool-calling is less
consistent than Qwen2.5's), and simple enough that the structured-tool-
call machinery pibot_local_agent needs for multi-argument tools
(weather's location, news' category) would be overkill for these two
zero-argument ones. Same pattern as pixel_memory.py's
detect_rename_request()/detect_goodbye(): a pattern list, not real
language understanding, so some phrasings will still fall through to
Ollama instead of being caught here -- that's fine, Ollama still
answers them correctly, just without the latency/cost savings.

Also detects video requests (the only LearnX call left anywhere in
this pipeline -- see detect_video_request()) and classifies everything
else into one of two tiers for a "basic" (free) user, once route()
above has already ruled out the zero-cost fast path: "direct_api"
(curriculum math/physics/chemistry, or general-knowledge/complex
questions a tiny local model handles poorly -- both go to
pixel_direct_llm.py now, not LearnX's chat backend, since routing
regular Q&A through LearnX would mean two network hops -- Pixel to
LearnX to OpenAI and back -- instead of one) or "llm" (the default --
casual chat, simple questions, follow-ups). Keyword/length heuristic
again, same known-limitation caveat -- this is a guess at difficulty,
not a measurement of it. A "premium" user instead gets routed through
the OpenAI Realtime pipeline directly, which has its own
`generate_video` tool for the same video intent instead of this
keyword classifier (see pixel_openai_voice_semantic.py).

Logs which tier actually answered each question -- printed to console
always, and appended to a gitignored JSONL file for later review.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_ROUTING_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "persona", "routing_log.jsonl"
)

_TIME_PATTERN = re.compile(
    r"\b(what time|what'?s the time|current time|what day is it|"
    r"what'?s the date|what date|today'?s date)\b",
    re.IGNORECASE,
)
_STATUS_PATTERN = re.compile(
    r"\b(system status|how are you (?:feeling|doing)|your temperature|"
    r"cpu temp|health check|how'?s your health)\b",
    re.IGNORECASE,
)


def _get_current_time() -> str:
    return f"It's {time.strftime('%A, %B %d, %Y at %I:%M %p')}."


def _read_cpu_temp_c() -> float | None:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def _read_uptime_hours() -> float | None:
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
        return seconds / 3600.0
    except (OSError, ValueError, IndexError):
        return None


def _read_mem_percent_used() -> float | None:
    try:
        with open("/proc/meminfo") as f:
            fields = {line.split(":")[0]: int(line.split()[1]) for line in f}
        total = fields["MemTotal"]
        available = fields["MemAvailable"]
        return (total - available) / total * 100.0
    except (OSError, KeyError, ValueError, IndexError):
        return None


def _get_system_status() -> str:
    """Real stats read straight from /proc and /sys -- same files
    pibot_local_agent's system_tool.py reads, no library needed. All
    three are Linux-only (fine on the Pi) and individually optional --
    missing one (e.g. no thermal zone on this board) just skips that
    part of the sentence instead of failing the whole reply."""
    parts = []
    temp = _read_cpu_temp_c()
    if temp is not None:
        parts.append(f"my CPU's at {temp:.0f} degrees Celsius")
    mem = _read_mem_percent_used()
    if mem is not None:
        parts.append(f"using about {mem:.0f} percent of my memory")
    uptime = _read_uptime_hours()
    if uptime is not None:
        parts.append(f"been running for {uptime:.1f} hours")
    if not parts:
        return "I can't check my system stats on this device, but otherwise I'm doing great!"
    return "I'm doing well! " + ", ".join(parts) + "."


def route(text: str) -> str | None:
    """Returns a deterministic reply if `text` matches a known
    zero-LLM-call case, else None -- caller should fall through to the
    normal Ollama chat flow in that case."""
    if _TIME_PATTERN.search(text):
        return _get_current_time()
    if _STATUS_PATTERN.search(text):
        return _get_system_status()
    return None


# Video intent -- checked before classify() below, since a video
# request is a separate action (calls pixel_brain.request_video(), the
# only LearnX call left anywhere in this pipeline) rather than a Q&A
# tier at all.
_VIDEO_PATTERN = re.compile(
    r"\b(show me a video|make (?:me )?a video|create a video|"
    r"can you (?:make|create|show) (?:me )?an? (?:video|animation)|"
    r"animate|animation of|visuali[sz]e)\b",
    re.IGNORECASE,
)


def detect_video_request(text: str) -> bool:
    """True if `text` sounds like the student wants a video/animation."""
    return bool(_VIDEO_PATTERN.search(text))


# Curriculum subject terms -- intentionally narrow/concrete (specific
# topics and operations, not broad words like "energy" or "force" that
# show up constantly in ordinary conversation and would misroute it) --
# plus general depth/breadth signals a 1.5-4B local model tends to
# handle poorly. Both now mean the same thing: this needs the direct
# OpenAI tier (pixel_direct_llm.py), not LearnX's chat backend, which
# would cost an extra network hop for no benefit since LearnX's own
# chat_response already just calls OpenAI itself (checked in
# backend/services/ai_router.py). Conservative on purpose: a false
# negative just means Ollama answers it (fine, just maybe not great);
# a false positive spends real API money on something Ollama could've
# handled.
_DIRECT_API_PATTERN = re.compile(
    r"\b(?:"
    r"solve|equation|formula|algebra|geometry|calculus|trigonometry|"
    r"derivative|integral|quadratic|polynomial|fraction|arithmetic|"
    r"velocity|acceleration|momentum|newton'?s law|physics|"
    r"chemistry|chemical reaction|molecules?|moles?|periodic table|maths?|"
    r"explain in detail|write (?:a|an|me)|essay|analyz[es]|analyse|"
    r"compare and contrast|history of|summari[sz]e|code for|program that"
    r")\b",
    re.IGNORECASE,
)
_DIRECT_API_WORD_COUNT = 25


def classify(text: str) -> str:
    """Decides which tier should handle `text`, once route() above has
    already ruled out the zero-cost fast path and detect_video_request()
    has ruled out a video action. Returns "direct_api" or "llm" (the
    default)."""
    if _DIRECT_API_PATTERN.search(text) or len(text.split()) > _DIRECT_API_WORD_COUNT:
        return "direct_api"
    return "llm"


def log_routing(
    tier: str, question: str, reply: str,
    model: str | None = None, depth: str | None = None,
) -> None:
    """One line per question: which brain, which specific model within
    it, and (for the direct-API tier) whether the student wanted a
    quick answer or a real explanation -- see
    pixel_teaching_prompt.py's [[DEPTH:...]] marker. This is what lets
    student behavior be reviewed later from the raw log, not just
    assumed. Always printed; best-effort appended to a JSONL file -- a
    logging failure must never block the conversation itself."""
    suffix = f" ({model})" if model else ""
    if depth:
        suffix += f" [{depth}]"
    print(f"[router] {tier}{suffix} -> {question!r}")
    try:
        os.makedirs(os.path.dirname(_ROUTING_LOG_PATH), exist_ok=True)
        with open(_ROUTING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tier": tier,
                "model": model,
                "depth": depth,
                "question": question,
                "reply": reply,
            }) + "\n")
    except OSError:
        logger.exception("failed to write routing log")
