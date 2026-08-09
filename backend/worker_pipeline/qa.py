"""
Generic generate -> critique -> retry loop.

Ported from learnai/backend/services/educational_image.py's generate_with_critic()
pattern (Claude plan -> gpt-image-1 generate -> GPT-4o vision critic -> one
retry with correction feedback). Kept generic over the actual generator/critic
functions so image_renderer.py (and any future video QA) share one retry
policy instead of two copies of the same loop.
"""
import logging
from typing import Callable, Tuple

logger = logging.getLogger(__name__)

CRITIC_THRESHOLD = 85
MAX_GEN_ATTEMPTS = 2


def run_with_critic(
    generate_fn: Callable[[str], bytes],
    critic_fn: Callable[[bytes], dict],
    max_attempts: int = MAX_GEN_ATTEMPTS,
    threshold: int = CRITIC_THRESHOLD,
) -> Tuple[bytes, dict]:
    """
    generate_fn(correction_feedback) -> raw asset bytes
    critic_fn(asset_bytes) -> {"score": int, "issues": [...], "correction_prompt": str, ...}

    Returns (final_bytes, final_critic_report) — report always has "attempt" set.

    Never raises on a low final score: the caller decides whether a low-scoring
    result is acceptable to ship (matches educational_image.py — it ships the
    best attempt rather than failing the whole segment over one bad critic
    call). If critic_fn itself fails and can't produce a score, treat that as
    "don't force a retry" rather than as a rejection.
    """
    feedback = ""
    result_bytes = b""
    report: dict = {}

    for attempt in range(1, max_attempts + 1):
        result_bytes = generate_fn(feedback)
        report = critic_fn(result_bytes)
        report["attempt"] = attempt

        score = report.get("score", threshold)
        if score >= threshold or attempt >= max_attempts:
            if attempt > 1:
                logger.info(f"[qa] accepted after {attempt} attempts, score={score}")
            break

        feedback = report.get("correction_prompt", "")
        logger.info(f"[qa] score={score} < {threshold} — retrying with critic feedback")

    return result_bytes, report
