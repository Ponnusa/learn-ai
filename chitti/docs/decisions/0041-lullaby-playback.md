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
already has a real-hardware-tested `mpg123` subprocess pattern, same
reuse-a-proven-pattern approach decision 0040 used for
`pixel_face.py`. Two hard-won fixes carried forward:
1. `-b 2048` raises mpg123's output buffer -- the Pi 1's weak audio
   path underruns with the default tiny buffer.
2. `start_new_session=True` -- mpg123's interactive keyboard controls
   (pause/seek/quit) open `/dev/tty` directly to grab the controlling
   terminal, bypassing its own stdin entirely even with stdin
   redirected. That matters specifically for this project: push-to-
   talk depends on keyboard `input()`, which mpg123 could otherwise
   steal.

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

`voice_loop_demo.py`: new `_play_lullaby_file()` -- the mpg123
pattern above, as an async function that polls `proc.poll()` via
`asyncio.sleep()` rather than blocking on `proc.wait()`, specifically
so Ctrl-C during playback reaches a `finally: proc.terminate()` and
kills the still-running child. This matters because
`start_new_session=True` deliberately isolates mpg123 from the
terminal -- nothing else would stop it. New `_run_lullaby_time()`:
lists lullabies, lets the parent/child pick one (same picker pattern
as Story Companion's story list), sets
`face.set_status_led(DeviceState.SPEAKING)` for the duration. New menu
option 4 ("Lullaby time") in `main()`.

## Consequences

6 new unit tests (255 total passing, 1 skipped where noted in decision
0040). `test_lullaby_playback.py` mocks `subprocess.Popen` and
`asyncio.sleep` to prove the exact argv (including both hardware
fixes) and the terminate-on-interrupt behavior, without needing real
mpg123/audio hardware. `test_parent_controls_app.py` gained upload/
reject/delete tests using Flask's test client with an in-memory
multipart file, asserting both the DB row and the file on disk.

## Not yet done

Playlist/shuffle behavior, volume control, fade-out, an auto-stop
timer -- none requested, explicitly deferred rather than guessed at.
Not wired into transcripts/engagement by design (no conversational
turns to record). Manual end-to-end verification (a real MP3, real
mpg123, real speaker) is a Pi-only step -- this dev machine has neither
mpg123 nor real audio hardware, same caveat as every other real-audio
feature this project has shipped.
