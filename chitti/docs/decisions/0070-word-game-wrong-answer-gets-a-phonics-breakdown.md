# 0070 — The word game's wrong-answer reveal now explains the sounds

Date: 2026-10-20
Status: Accepted

## Context

Live bug report, from a real Pi session log: the post-reading "missing
letters" bonus game (decision 0057) showed "FR_G" (the blanked word
"frog"), the child said "oh" (close to the blanked letter 'o', but not
the whole word), and Chitti just said *"Good try! The word is
'frog'. Let's keep going!"* -- handing over the answer with zero
phonics explanation. Product owner's direct complaint: *"it never
care to teach phonic... no information of phonics sound of 'o' and
others to explain it little bit carefully."*

Reading the code confirmed this is exactly as designed, just an
incomplete design: `word_game.py`'s own docstring says this game is
*"not part of the decoding-mastery assessment pipeline"* -- it was
built as a fun, separate bonus activity, deliberately apart from the
phoneme-accurate hint ladder (decision 0052/0064) that runs during the
*main* read-aloud. But that separation left this specific teaching
moment -- a wrong guess on a real word -- with nothing at all, while
the hint ladder two decisions ago (0064) already built exactly the
needed phonics apparatus (`hints.py`'s `blend_breakdown()` / sound-
example table) for the identical situation elsewhere in the same
session.

## What shipped

**`reading/hints.py`**: `_blend_breakdown()` renamed to public
`blend_breakdown()` -- no behavior change, just exposed so another
module can reuse the exact same phoneme-accurate breakdown instead of
a second, potentially-drifting copy.

**`reading/word_game.py`**: `incorrect_response()` now calls
`blend_breakdown()` and includes it in the reveal: *"Good try! The
word is 'frog' -- 'f' like in 'fish', 'r' like in 'run', 'o' like in
'dog', 'g' like in 'goat'. Let's keep going!"* -- still one line,
still moves straight on (this stays a fun bonus activity, not a second
hint ladder with retries), but now actually teaches something on a
miss instead of just stating the answer.

## Consequences

`test_word_game.py`: new `test_incorrect_response_includes_a_phonics_breakdown`
confirms the breakdown appears for "frog" (`'f' like in 'fish'`, `'o'
like in 'dog'`). The existing `test_incorrect_response_names_the_word`
still passes unchanged.

Full suite: 527 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- The word game itself still has no retry -- a miss is always a
  single reveal-and-move-on, same as before. Only the reveal's content
  changed, not the interaction shape (deliberately: this stays the
  "fun bonus," the hint ladder stays the one place with graduated
  retries).
