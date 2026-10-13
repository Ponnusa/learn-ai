"""Structured logging setup (spec sections 2.1, 9: logging that
excludes raw audio and unnecessary personal data by default).

Deliberately minimal at Milestone 1: there's no audio or child speech
flowing through the app yet, so there's nothing to redact in practice.
This function controls formatting only -- every call site is still
responsible for never logging raw audio bytes or a verbatim child
transcript, same as pixel-ai's own PIXEL_AUDIO_LOG_DIR opt-in pattern
for anything that would need to be an explicit, flagged exception.
"""
import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
