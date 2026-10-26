# 0120 — Word-family practice drops its own phonics breakdown and sound clips too

Date: 2026-10-26

Status: Accepted

## Context

Pointed at again from a real session log: a word-family practice round
("map, tap, gap, cap") got a wrong word reacted to with "Good try! The
word is 'cap' -- 'c' like in 'cat', 'a' like in 'cat', 'p' like in
'pig'. Let's keep going!" plus a real phonics-sound-clip playback.

Decisions 0116 and 0118 already removed phonics teaching from the hint
ladder and the missing-letters word game, respectively -- decision
0118 explicitly called out `_run_word_family_practice()`'s own
wrong-word reinforcement as the one remaining real-clip playback left
anywhere, and scoped it out at the time since it wasn't raised as
something to change in that round. It's now being raised: the overall
direction is no phonics teaching anywhere in the reading flow, and
this was the last holdout.

## What shipped

**`voice_loop_demo.py`'s `_run_word_family_practice()`**: a missed
family word's reaction is now the same plain, simplified line used
everywhere else since decision 0116 -- `That's okay! The word is
"X". Let's keep going!` -- instead of `word_game.py`'s
`incorrect_response()` (hints.py's grapheme-by-grapheme
`blend_breakdown()`). The real phonics-sound-clip playback
(`_play_real_phonics_sounds()`, decision 0091) is gone entirely. The
word's own screen spotlight (unrelated to phonics -- just showing
which word is being corrected) is unchanged.

**Dead code removed**, since this was their last caller: `word_game.py`'s
`incorrect_response()`/`_INCORRECT_TEMPLATE` and its `blend_breakdown`
import; `hints.py`'s `blend_breakdown()`/`_sound_example()`;
`voice_loop_demo.py`'s `_play_real_phonics_sounds()` and its
`get_clip_bytes` import. `hints.py`'s `_SOUND_EXAMPLES` dict stays --
`test_reading_phonics_audio.py` still validates `reading/phonics_audio.py`'s
own clip inventory against it, independent of `blend_breakdown()`.
`reading/phonics_audio.py` itself is untouched -- still used by the
standalone `scripts/phonics_explorer.py` test tool, unrelated to this
app's own reading flow.

## Consequences

Updated `test_voice_loop_demo_intent.py`'s
`test_word_family_practice_only_corrects_the_missed_word_not_every_word()`
to expect the new plain reaction text, assert no "like in" phonics
breakdown appears, and assert no real (non-placeholder) audio clip
plays. Removed `test_word_game.py`'s two `incorrect_response()` tests
(the function no longer exists).

Full suite: 713 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

Nothing in the reading flow is known to still teach phonics or play a
recorded sound clip in the child-facing correction/reaction path.
