"""Reading Partner mode (decision 0051): phonics-based reading practice.

Adapts (not vendors) the deterministic algorithmic core of
tanner-griffith/phono-storyforge (github.com/tanner-griffith/
phono-storyforge, Apache License 2.0) -- a closed-loop adaptive reading
tutor built for a Google/Kaggle "Agents for Good" capstone. Tested its
offline engine directly before porting anything: it genuinely works
with zero cloud credentials, tracks per-grapheme mastery with Bayesian
Knowledge Tracing, picks the next phonics skill a child hasn't
mastered, and grades a read-aloud by aligning it against the expected
text -- all pure Python (`difflib` + dataclasses), no dependencies.

What's ported vs. rebuilt, deliberately (same "write fresh, reuse
patterns, not code" discipline this project already applied to
pixel-ai's pixel_face.py/pixel_tts.py):
- Ported near-verbatim (the algorithms themselves, translated from the
  source's Pydantic models to plain dataclasses to match every other
  Chitti schema): curriculum.py's grapheme/BKT data, decodability.py's
  word-decomposition and decodability check, mastery.py's BKT update,
  planner.py's objective selection, alignment.py's miscue grading.
  None of this needed any change beyond the dataclass translation --
  it's deterministic, dependency-free, and hardware-agnostic.
- Rebuilt, not ported: book generation. The source uses Google ADK +
  Gemini Live + Vertex AI, a different cloud ecosystem than Chitti's
  lean, direct-REST OpenAI/Claude backends, untested on Pi/ARM, with
  no child-data-privacy handling. book_generation.py keeps the same
  verifier-gated propose/check/retry *pattern* but calls Chitti's own
  LanguageModelBackend, and -- something the original has no
  equivalent of at all -- screens every generated page through
  safety/checks.py's check_speech() before accepting it.
- Not ported at all: illustrations (Vertex AI images) and Google
  Workspace export (Docs/Drive/Gmail) -- no camera/printer/Workspace
  use case on this device.

repository.py persists per-child mastery state (reading_profiles +
reading_grapheme_mastery tables), scoped by child_profile_id like
every other domain package here.
"""
