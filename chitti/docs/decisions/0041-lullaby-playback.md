# 0041 — Lullaby/MP3 playback

Date: 2026-10-17
Status: Accepted

## Context

Product-owner idea: let a parent upload an MP3 (e.g. a lullaby) for
Chitti to play back. Confirmed as a **separate** menu option in
`voice_loop_demo.py`, not folded into any conversation mode and not
tangled with the separately-deferred intent-detection/mode-switching
work -- this is simple playback, not a conversation: no LLM, no STT,
no transcript/engagement recording (those all assume conversational
turns, and there are none here).

Two genuinely new capabilities this needed:
1. **File upload** in Parent Controls -- no existing route handled
   `request.files`; `stories.py`/`stories.html` only ever handled text
   via a textarea.
2. **MP3 playback** -- `audio/real.py`'s `RealAudioTransport` only
   plays raw PCM (TTS output); MP3 needs a decoder.

**Adapted, not copied, from a proven reference**: `pixel-ai/pixel_tts.py`
has a real-hardware-tested `mpg123` subprocess pattern, same reuse-a-
proven-pattern approach decision 0040 used for `pixel_face.py`. Its
`start_new_session=True` fix (mpg123's interactive keyboard controls
open `/dev/tty` directly, bypassing stdin redirection -- a problem
here specifically because push-to-talk depends on keyboard `input()`)
is carried forward as cheap insurance even in the decode-only mode
this decision ended up shipping -- see the addendum below for why
`pixel_tts.py`'s pattern of letting mpg123 own real-time ALSA playback
directly turned out *not* to transfer to this project as-is.

## What shipped

New `lullabies/` domain package (`schema.py`'s `LullabyRecord`,
`repository.py`'s `LullabyRepository`), modeled on
`parent_controls/stories.py`'s exact shape but **deliberately
simpler**: no stored filename. The audio file's path on disk is always
derived from the record's own `id` (`data/lullabies/{id}.mp3`), never
from the parent-supplied filename -- this sidesteps path-traversal and
filename-collision risk entirely rather than needing to sanitize
anything. New `lullabies` table via the usual
`storage/migrations.py` pattern.

`parent_controls/app.py`: new `/lullabies` GET+POST route (mirrors
`/stories`) and `/lullabies/<id>/delete`. `create_app()` now takes a
`lullabies_dir` parameter and sets `MAX_CONTENT_LENGTH` to 20MB --
Flask returns 413 automatically past that, a cheap guard against a
huge accidental upload on a Pi with limited storage. Upload validation
is just a non-empty title and a `.mp3`-suffixed filename -- same
authorizing-adult trust model as risk register #14 (no story content
moderation either), now noted there as covering audio too. New
`templates/lullabies.html` (multipart form), linked from `dashboard.html`.

`voice_loop_demo.py`: new `_decode_mp3_to_pcm()` (mpg123 as a pure
decoder -- see the addendum for why) and `_play_lullaby_file()`, which
hands the decoded PCM to `audio.play()`, the same already-open
`RealAudioTransport` pipeline every TTS reply uses. New
`_run_lullaby_time()`: lists lullabies, lets the parent/child pick one
(same picker pattern as Story Companion's story list), sets
`face.set_status_led(DeviceState.SPEAKING)` for the duration, and calls
`audio.stop_playback()` if Ctrl-C/cancellation arrives mid-song. New
menu option 4 ("Lullaby time") in `main()`.

## Consequences

5 new unit tests (254 total passing, 1 skipped where noted in decision
0040). `test_lullaby_playback.py` mocks `subprocess.run` to prove
`_decode_mp3_to_pcm`'s argv, and uses a fake `audio.play()` to prove
`_play_lullaby_file` hands off the decoded PCM through it rather than
ever letting mpg123 open an ALSA device itself. `test_parent_controls_app.py`
gained upload/reject/delete tests using Flask's test client with an
in-memory multipart file, asserting both the DB row and the file on
disk.

## Addendum (2026-10-17): no sound on real hardware -- three attempts

Found live: an uploaded lullaby produced no sound at all on the Pi,
even though TTS replies played fine through the same speaker.

**First attempt (wrong diagnosis)**: assumed the same device-routing
bug class decision 0016 fixed for `aplay`/`arecord` -- that ALSA's
`"default"` device doesn't route to the actual speaker on this
hardware -- and forced mpg123's ALSA module plus the exact
`PLAYBACK_DEVICE` `audio/real.py` resolves for `aplay -D` (`-o alsa -a
<device>`). This made things *worse*: a single audio "thud" and an
immediate exit, no song at all.

**Second attempt (right test, incomplete conclusion)**: ran
`mpg123 -v data/lullabies/*.mp3` directly on the Pi with no device
flags at all -- it played correctly, so reverted to mpg123's own
default device (matching `pixel-ai/pixel_tts.py`'s original pattern).
Still silent inside the actual demo, even though the identical
command, and even `setsid mpg123 ... </dev/null 2>/dev/null` (matching
every flag `_play_lullaby_file` actually used, including
`start_new_session=True`), played fine standalone every time.

**Root cause, found by checking what else was running**: `ps aux`
during a real demo session, at the mode-selection prompt (before even
choosing the lullaby), showed `audio/real.py`'s persistent `aplay -D
plughw:2,0 ...` process already alive -- spawned by the very first TTS
reply (e.g. the session's "welcome back" greeting) and deliberately
kept open for the rest of the session (decision 0016 addendum 4, to
avoid the device's "wake up" latency on every reply). ALSA hardware
devices (`plughw:X,Y`) only allow one exclusive owner. mpg123 trying
to open that *same* device for real-time playback while `aplay`
already held it failed -- silently, since nothing was listening for an
error: the demo suppresses mpg123's stderr, and the standalone manual
tests never hit this because nothing else was holding the device open
at the time.

**Actual fix**: stop letting mpg123 touch the audio device at all.
`_decode_mp3_to_pcm()` now runs it in decode-only mode (`-s`, write raw
PCM to stdout) -- no ALSA device opened by mpg123 whatsoever.
`_play_lullaby_file()` then hands the decoded PCM to the *same*
`audio.play()` every TTS reply already uses, i.e. the one already-open
`RealAudioTransport` pipeline. One ALSA client for the entire session,
never two fighting over the same hardware device. `--mono -r
PLAYBACK_SAMPLE_RATE` on the decode matches the fixed 16-bit-mono
format `RealAudioTransport.play()` assumes; mpg123 resamples/downmixes
as needed regardless of the uploaded file's real format.
`_run_lullaby_time()` also now calls `audio.stop_playback()` on
Ctrl-C/cancellation, since the "Ctrl-C to stop" promise needs an
explicit stop now that playback is a single long buffer already handed
to the persistent `aplay` process, not a process `_play_lullaby_file`
owns directly. Tests rewritten to match: `_decode_mp3_to_pcm`'s argv
and `_play_lullaby_file`'s hand-off into a fake `audio.play()`.

**Lesson for next time**: a command that works standalone doesn't
prove the subprocess wrapper is fine -- it proves the *device* is
available at that moment. Any new ALSA-touching subprocess at this
project needs to be checked against whatever else might already be
holding the hardware device for the session, not just tested in
isolation.

## Not yet done

Playlist/shuffle behavior, volume control, fade-out, an auto-stop
timer -- none requested, explicitly deferred rather than guessed at.
Not wired into transcripts/engagement by design (no conversational
turns to record). Manual end-to-end verification (a real MP3, real
mpg123, real speaker) is a Pi-only step -- this dev machine has neither
mpg123 nor real audio hardware, same caveat as every other real-audio
feature this project has shipped.
