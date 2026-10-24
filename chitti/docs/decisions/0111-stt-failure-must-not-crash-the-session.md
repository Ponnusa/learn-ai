# 0111 — A transcription failure must not crash the whole session

Date: 2026-10-25
Status: Accepted

## Context

Direct feedback: real console output from a live Reading Partner
session, pasted in full. It showed the Azure OpenAI `whisper`
deployment (decision 0110) returning 429 Too Many Requests --
first repeatedly during word-highlight modeling (decision 0098's
`transcribe_with_word_timestamps()`, once per sentence Chitti models
aloud), which degraded gracefully exactly as designed (that call is
already wrapped in try/except, logged as "word-timestamp lookup
failed", and the read-aloud continued without a highlight). But the
*same* 429, the next time it hit the plain `transcribe()` call inside
`_capture_and_transcribe()`, was a completely unhandled exception --
it propagated all the way up through `main()` and killed the entire
process. The whole companion robot went down over one bad turn.

Two separate issues, both real:

1. **An Azure quota problem, not a code bug**: Azure OpenAI
   deployments typically start with a much lower default TPM/RPM
   quota than direct OpenAI's own per-account limits. Decision 0098
   adds real volume (one Whisper call per sentence modeled), so the
   `whisper` deployment is the one most likely to hit this. Not
   something this decision's code can fix -- raising that
   deployment's (and `tts`'s/`gpt-4o-mini`'s, as sessions grow) quota
   in Azure AI Foundry is a user action item, not a code change.
2. **A real robustness bug, independent of which provider or quota
   is involved**: `_capture_and_transcribe()` had no error handling
   at all around `stt.transcribe()`. ANY transient failure there --
   a rate limit, a network blip, a provider outage -- took down the
   entire session instead of just failing that one turn.

## What shipped

**`voice_loop_demo.py`**: `_capture_and_transcribe()`'s call to
`stt.transcribe()` is now wrapped in try/except. On failure, it logs
(`logger.exception`, same convention `_speak_with_timed_highlight()`
already uses for this exact same API) and returns `""` instead of
raising. Deliberately reuses the EXISTING empty-transcript handling
every one of this function's ~20 callers already has ("(nothing
heard, try again)", looping back to prompt again) -- no new recovery
path invented, the already-correct one just now also covers an API
failure, not only literal silence.

**Test-isolation bug found and fixed along the way**: running the
full suite for the first time after decision 0110 set a real
`USE_AZURE_OPENAI=true` in `chitti/.env` (for live verification)
revealed that `config/loader.py`'s own `load_dotenv()`, which runs at
*import* time, loads that real value into every test process too --
silently flipping pre-existing tests in `test_openai_backend.py`,
`test_stt_openai_backend.py`, and `test_tts_openai_backend.py` that
assumed direct-OpenAI behavior (URL, bearer auth) over to Azure
routing instead, since those tests never anticipated this env var
existing at all. Fixed with one `autouse=True` fixture per file,
`monkeypatch.delenv("USE_AZURE_OPENAI", raising=False)`, so each
file's tests are no longer at the mercy of whatever happens to be in
the real `.env` on whichever machine runs them.

## Consequences

Two new tests in `test_voice_loop_demo_capture_error_handling.py`
(an STT failure returns `""` instead of raising; a successful
transcription still returns the real text unchanged). Three new
autouse fixtures (one per affected backend test file) fixing the
real test-isolation bug described above.

Full suite: 713 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The Azure `whisper` deployment's own quota is not something this
decision touches -- raising it (and watching `tts`/`gpt-4o-mini` as
session length grows) is a pending action item in Azure AI Foundry,
outside this codebase. If 429s keep recurring even after a quota
raise, a retry-with-backoff specifically for 429 (as opposed to this
decision's blanket "any failure -> nothing heard") would be a
natural, separable follow-up.
