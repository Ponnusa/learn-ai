# 0020 — Fix: Whisper mis-detecting language, producing gibberish in an unrelated script

Date: 2026-10-13
Status: Accepted

## Context

Reported live, asking an English question about the Finnish story
("what is meant by 'metsä' in the story"): Whisper transcribed
"Браооооо, браоооо Сдеус" and "паспорт" — fluent-looking Cyrillic
text — for what was actually spoken English.

## Root cause

`OpenAIWhisperBackend.transcribe()` never passed a `language`
parameter, so Whisper auto-detects the spoken language from the audio
itself. Auto-detection is a classic failure point on a short or
slightly unclear clip, and more so right after a session where the
preceding content (the story, read aloud in Finnish) was in a
different language — the model can lock onto the wrong language
entirely and produce a coherent-looking transcription in a completely
unrelated script, not just a rough or empty one. This is a different
failure mode from the earlier "you" hallucination on near-silence
(decision 0016's wrong-device bug) — this is real speech, transcribed
confidently in the wrong language.

## Fix

- `SpeechRecognitionBackend.transcribe()`'s interface gained an
  optional `language: str | None = None` parameter (an ISO-639-1 code)
  forcing the expected spoken language instead of auto-detecting. A
  backend with no language-forcing capability of its own is free to
  ignore it.
- `OpenAIWhisperBackend` passes it through as Whisper's own `language`
  form field when given.
- `voice_loop_demo.py`'s capture helper now passes `language="en"`
  explicitly — hardcoded for now since English is this project's
  dev-first language (decision 0003's sequencing: English ships
  first, Finnish is verified and added before any pilot). Flagged
  honestly as needing to become a per-profile setting once Finnish is
  actually in play, not assumed English forever.

## Consequences

2 new unit tests (114 total passing): confirms `language` is omitted
from the request when not given (preserving auto-detect as the
default, not forcing English at the interface level), and that it's
passed through correctly when provided.

## Not yet done

Finnish-speaking children (or a bilingual household) using this demo
would currently get everything forced to English, which is wrong for
them — this is an explicitly accepted gap for the current dev-English-
first phase, not a claim this is solved for Finnish users. Revisit
once Finnish support work actually starts, per decision 0003/0004's
own stated sequencing.
