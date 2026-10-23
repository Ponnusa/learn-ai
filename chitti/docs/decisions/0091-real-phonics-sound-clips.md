# 0091 — Real recorded phonics sounds, not just "letter as in word"

Date: 2026-10-23
Status: Accepted

## Context

Direct feedback: when spelling/sounding out a missed word, Chitti
says things like `'p' like in 'pig', 'a' like in 'cat', 't' like in
'top'` -- a proxy (an example word that happens to start with the
sound), not the real phoneme. *"I think it must be more like
phonetics, rather than like this."*

Checked what's actually feasible with Chitti's current pipeline
before picking an approach: `voice/tts_openai.py`'s `OpenAITTSBackend`
sends plain text to OpenAI's `/v1/audio/speech` endpoint -- no SSML,
no phoneme tags, confirmed directly in the request payload. Spelling
out a phonetic respelling ("puh", "ah") was already rejected once
before (decision 0064) for the same reason: no way to verify in
advance how any given TTS voice will pronounce it. Presented three
real options (tighten the existing proxy-word approach, switch TTS
providers for SSML phoneme support, or pre-recorded real sound clips)
-- the product owner picked pre-recorded clips, then pointed at
`github.com/minormending/learn-letters`'s `audio/` folder (a
44-phoneme UK chart set) as a source, and confirmed they hold the
rights to use those specific recordings.

That repo has no LICENSE file and describes the audio only as "from
the public-use phoneme set supplied with the project" (no named
source, no citable terms) -- flagged this plainly before using
anything from it. Proceeded only on the product owner's own explicit
representation that they hold the rights, not on the repo's own
unclear description.

## What shipped

**`src/companion_robot/reading/phonics_sounds/*.wav`** (50 files):
the source MP3s converted once to 24kHz mono 16-bit PCM WAV --
matching `audio/real.py`'s `RealAudioTransport.play()` contract
exactly, so they play through the same pipeline every TTS reply
already uses, no new playback mechanism needed.

**`reading/phonics_audio.py`** (new module): `get_clip_bytes(grapheme)
-> bytes | None`, reading and caching each WAV's raw PCM frames
(via Python's `wave` module -- found live that assuming a fixed
44-byte header, as some WAV tooling does, silently sliced into real
audio data here, since ffmpeg's actual header on these files is 78
bytes). Returns `None` for any grapheme not covered.

**Not every grapheme is covered** -- 18 of Chitti's 68
`_SOUND_EXAMPLES` keys have no real single-phoneme clip to map to and
are explicitly listed in `DEFERRED_GRAPHEMES` with why, not just
silently missing: `q`/`x`/`qu` (consonant blends, not single
phonemes), `wh`/`ph`/`au`/`aw` (not in the source set at all), `y`
(the source clip is the consonant /j/ "yes"; Chitti's "y" is
y-as-vowel "my" -- a different sound, not a safe substitute), `u_e`
(the closest available clip is /u:/ "moon", not u_e's actual /ju:/
"cube" -- close enough to risk teaching it wrong), and the nine
`glued_sounds` rime chunks (`all`/`ang`/`ing`/`ong`/`ung`/`ank`/`ink`/
`onk`/`unk` -- multi-phoneme chunks, not single sounds this source
has clips for).

**`voice_loop_demo.py`**: new `_play_real_phonics_sounds(audio, word)`
plays every covered grapheme's real clip, in order, silently skipping
deferred ones. Wired in as reinforcement, additive to the existing
spoken text (nothing removed, nothing rephrased, zero risk to the
~600 tests already asserting exact hint/feedback text):
- The hint ladder's stage 1 (first-sound hint) now also plays the
  first grapheme's real clip right after saying "...like in 'pig'."
- Stage 2 (full blend breakdown) plays every covered grapheme's clip
  in sequence, right after the spoken breakdown.
- Both `incorrect_response()` call sites (the word game, and
  word-family practice) play the missed word's covered graphemes'
  clips right after the spoken "Good try! The word is..." line.

## Consequences

New tests: `test_reading_phonics_audio.py` -- a covered grapheme
returns valid, cached, even-length PCM; a deferred/unknown grapheme
returns `None`; every key in `hints.py`'s `_SOUND_EXAMPLES` is either
covered or explicitly in `DEFERRED_GRAPHEMES` (never silently
missing). `test_voice_loop_demo_intent.py`: a wrong word-game answer
plays exactly the real clips for "bunny"'s covered graphemes (b/u/n,
not "y") -- `_FakeAudio` extended to record what it's asked to play,
since it was previously a pure no-op.

Full suite: 613 passed (3 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The 18 deferred graphemes still speak the existing "like in 'word'"
proxy text only, same as before this decision -- the product owner's
own request was to note these for later generation, not block on
them now. When that happens (most likely via Chitti's own
OpenAI TTS, synthesized once and spot-checked, per the
generate-and-verify approach discussed and not yet built), the same
`get_clip_bytes()`/`DEFERRED_GRAPHEMES` structure in
`phonics_audio.py` is exactly where those clips would slot in --
nothing about this design needs to change to add them.
