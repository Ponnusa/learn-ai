"""Sentence-by-sentence reading with a persistent position (decision
0067). Deterministic boundary splitting, no NLP -- this product's own
generated/parent-provided content is already short, simple sentences,
so sentence-ending punctuation followed by whitespace (or the end of
the text) is a reliable enough boundary without an abbreviation-aware
parser.
"""
import hashlib
import re

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_sentences(text: str) -> list[str]:
    """Splits `text` into its sentences, trimmed, empties dropped. A
    passage with no terminal punctuation at all comes back as one
    whole sentence, not zero."""
    stripped = text.strip()
    if not stripped:
        return []
    return [s.strip() for s in _SENTENCE_BOUNDARY_RE.split(stripped) if s.strip()]


def passage_key(text: str) -> str:
    """A stable id for a passage's own text -- used as
    ReadingProfile.current_passage_key so a resumed parent-uploaded
    exercise (same text, same key) can pick back up mid-passage while
    a freshly-generated book (different text each time) always starts
    a new key, never confused with an unrelated passage that happens
    to start at the same sentence index."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]
