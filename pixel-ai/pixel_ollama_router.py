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

Also classifies everything else into one of three tiers for a
"basic" (free) user, once route() above has already ruled out the
zero-cost fast path: "learnx" (curriculum math/physics/chemistry --
LearnX's own specialized explanation logic is the right tool, not a
generic local/cloud model), "cloud" (general-knowledge/complex
questions a tiny local model handles poorly), or "llm" (the default --
casual chat, simple questions, follow-ups). Keyword/length heuristic
again, same known-limitation caveat -- this is a guess at difficulty,
not a measurement of it. A "premium" user instead gets routed through
the OpenAI Realtime pipeline directly, which decides its own LearnX
hand-off via tool-calling rather than this keyword classifier -- not
built yet, a separate and more involved piece of work (see README).

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


# Curriculum subject terms -- intentionally narrow/concrete (specific
# topics and operations, not broad words like "energy" or "force" that
# show up constantly in ordinary conversation and would misroute it).
_LEARNX_PATTERN = re.compile(
    r"\b(?:"
    r"solve|equation|formula|algebra|geometry|calculus|trigonometry|"
    r"derivative|integral|quadratic|polynomial|fraction|arithmetic|"
    r"velocity|acceleration|momentum|newton'?s law|physics|"
    r"chemistry|chemical reaction|molecules?|moles?|periodic table|"
    r"maths?\b"
    r")\b",
    re.IGNORECASE,
)
# Signals that a question wants real depth/breadth -- the kind of
# thing a 1.5-4B local model tends to handle poorly. Conservative on
# purpose: a false negative just means Ollama answers it (fine, just
# maybe not great); a false positive spends real cloud-API money on
# something Ollama could've handled.
_COMPLEX_PATTERN = re.compile(
    r"\b(explain in detail|write (?:a|an|me)|essay|analyz[es]|analyse|"
    r"compare and contrast|history of|summari[sz]e|code for|program that)\b",
    re.IGNORECASE,
)
_COMPLEX_WORD_COUNT = 25


def classify(text: str) -> str:
    """Decides which tier should handle `text`, once route() above has
    already ruled out the zero-cost fast path. Returns "learnx",
    "cloud", or "llm" (the default)."""
    if _LEARNX_PATTERN.search(text):
        return "learnx"
    if _COMPLEX_PATTERN.search(text) or len(text.split()) > _COMPLEX_WORD_COUNT:
        return "cloud"
    return "llm"


def log_routing(tier: str, question: str, reply: str, model: str | None = None) -> None:
    """One line per question: which brain, and which specific model
    within it, actually answered it ("llm" could be phi3:mini or
    whatever else is pulled; "cloud" could be whichever PIXEL_CLOUD_MODEL
    is set; "local"/"learnx" have no meaningful model name, left None).
    Always printed; best-effort appended to a JSONL file -- a logging
    failure must never block the conversation itself."""
    model_suffix = f" ({model})" if model else ""
    print(f"[router] {tier}{model_suffix} -> {question!r}")
    try:
        os.makedirs(os.path.dirname(_ROUTING_LOG_PATH), exist_ok=True)
        with open(_ROUTING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tier": tier,
                "model": model,
                "question": question,
                "reply": reply,
            }) + "\n")
    except OSError:
        logger.exception("failed to write routing log")
