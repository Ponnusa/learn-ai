# 0110 — Route Chitti's OpenAI calls through Azure OpenAI

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback, correcting a misdirected earlier change: "why did u
change in the learnx backend.. i wanted that to be in chiiti all
these changes." The earlier request ("open ai is not working, can we
use it via https://animlearneuopenai.openai.azure.com/... our manim
video generation in leanrx uses this for voice") had specifically
named "leanrx" (learnx)'s manim pipeline, which is why that work
landed in `learnai/backend/` instead -- confirmed on a follow-up
question that Chitti was the actually-intended target, with the
backend change reverted (`backend/.env`'s `USE_AZURE_OPENAI`/Azure
vars removed; it's gitignored, so nothing to revert in git itself).

Chitti is a separate codebase with its own OpenAI usage, unrelated to
the backend's: `voice/openai_backend.py` (chat), `voice/stt_openai.py`
(Whisper), `voice/tts_openai.py` (TTS) -- all raw `requests`-based
HTTP calls (decision 0049's own connection-reuse rationale), not the
official `openai` SDK the backend uses. No Azure routing existed here
at all before this.

## What shipped

**`config/loader.py`**: new `use_azure_openai() -> bool` (reads
`USE_AZURE_OPENAI`) and `openai_request(path, model) -> (url, headers,
effective_model)` -- the one shared place that decides, for any
OpenAI-shaped REST call, whether to hit `api.openai.com` directly
(bearer token, model name as sent) or Azure OpenAI (deployment name
in the URL path, `api-version` query param, `api-key` header instead
of bearer). `_AZURE_DEPLOYMENT_MAP` (`whisper-1` -> `whisper`, `tts-1`
-> `tts`) mirrors `learnai/backend/services/ai_router.py`'s own
`_AZURE_MODEL_MAP` -- confirmed against the real Azure resource
(Sweden Central) that those are indeed the deployment names there, not
reinvented blind.

**`voice/openai_backend.py`, `voice/stt_openai.py`,
`voice/tts_openai.py`**: each now calls `openai_request()` to get its
URL/headers/model instead of its own hardcoded `_API_URL` constant and
`Authorization: Bearer` header. No change to any of these files'
public behavior when `USE_AZURE_OPENAI` is unset (still unset by
default) -- confirmed by the full existing test suite for all three
passing unchanged.

**`.env` / `.env.example`**: `USE_AZURE_OPENAI=true` plus the
endpoint/key/API version added to the real (gitignored) `.env`;
`.env.example` documents the four new optional variables, same style
as its existing entries.

Verified against the real Azure resource, not just mocked tests: ran
`OpenAILanguageModelBackend.generate_reply()`,
`OpenAITTSBackend.synthesize()`, and
`OpenAIWhisperBackend.transcribe()` directly against it --
chat replied correctly (`model='gpt-4o-mini'`), TTS returned real PCM
audio, and Whisper transcribed that same audio back correctly.

## Consequences

Six new tests in `test_config_loader.py` (`use_azure_openai()`'s
truthy/falsy parsing; `openai_request()`'s direct-OpenAI default,
Azure routing, the whisper/tts deployment-name mapping, and endpoint
trailing-slash handling). One new integration test in each of
`test_openai_backend.py`, `test_stt_openai_backend.py`, and
`test_tts_openai_backend.py` confirming each backend actually calls
through to `openai_request()` rather than its own old hardcoded URL.

Full suite: 711 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The backend (`learnai/backend/`) change from the earlier,
misdirected attempt was reverted -- if Azure OpenAI routing is wanted
there too (it already has its own, separate, SDK-based
implementation in `services/ai_router.py`/`services/manim.py`, just
not currently turned on), that's a distinct, already-built-but-unused
switch, not something this decision touches.
