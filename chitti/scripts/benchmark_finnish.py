#!/usr/bin/env python
"""Runs the same Finnish-language prompts against both candidate
LanguageModelBackend implementations (decision 0004) and prints the
results side by side with per-call latency.

Deliberately does not attempt to auto-score Finnish fluency -- that
needs a Finnish speaker's judgment, not a guess from this script. What
this *does* measure objectively: whether each backend responds in
Finnish at all, and how long each call takes (feeding into the
first-response-latency question from decision 0004/0005).

Requires OPENAI_API_KEY and/or ANTHROPIC_API_KEY in chitti/.env --
missing either one just skips that backend's half of the run.
"""
import asyncio
import sys
import time

from companion_robot.voice.claude_backend import ClaudeLanguageModelBackend
from companion_robot.voice.openai_backend import OpenAILanguageModelBackend

_SYSTEM_PROMPT = (
    "You are Chitti, a friendly AI companion robot for a child. "
    "Respond naturally in Finnish, in short, age-appropriate sentences."
)

_PROMPTS = [
    "Hei Chitti! Mitä sinulle kuuluu?",
    "Voitko kertoa minulle lyhyen tarinan ketusta?",
    "Mikä on kahden plus kahden vastaus?",
    "Opetan sinulle jotain uutta: koirat osaavat haistaa hyvin. Mitä ajattelet siitä?",
]


async def _run_backend(name: str, backend) -> None:
    print(f"\n=== {name} ===")
    for prompt in _PROMPTS:
        start = time.monotonic()
        try:
            reply, model = await backend.generate_reply(
                [{"role": "user", "content": prompt}], _SYSTEM_PROMPT
            )
        except Exception as exc:
            print(f"[{prompt}]\n  ERROR: {exc}\n")
            continue
        elapsed = time.monotonic() - start
        print(f"[{prompt}]\n  -> ({model}, {elapsed:.2f}s) {reply}\n")


async def main() -> None:
    # Windows' console defaults to cp1252, which can't encode Finnish
    # diacritics reliably or any emoji a reply might contain -- crashes
    # with UnicodeEncodeError rather than just mis-rendering. Force
    # UTF-8 stdout so the actual replies print correctly regardless of
    # host console codepage.
    sys.stdout.reconfigure(encoding="utf-8")
    await _run_backend("OpenAI", OpenAILanguageModelBackend())
    await _run_backend("Claude", ClaudeLanguageModelBackend())
    print(
        "\nNote: this script only measures whether each backend replied in "
        "Finnish and how long it took. Judging actual fluency/quality needs "
        "a Finnish speaker reading the output above -- not automated here."
    )


if __name__ == "__main__":
    asyncio.run(main())
