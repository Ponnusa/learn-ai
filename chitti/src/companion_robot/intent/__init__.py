"""Hybrid mode-switch intent detection (decision 0042): lets a child
say "tell me a story" or "play a song" mid-conversation and actually
switch Chitti into that mode, instead of Chitti only being able to
talk *about* it.

router.py: pure, deterministic functions only -- no LLM/IO, same
"deterministic, returns None rather than guessing" spirit as
education/math_check.py. The LLM fallback for phrasing the
deterministic patterns miss lives on ConversationService
(conversation/service.py's classify_intent()), not here, since all of
this project's LLM-prompting already lives there.
"""
