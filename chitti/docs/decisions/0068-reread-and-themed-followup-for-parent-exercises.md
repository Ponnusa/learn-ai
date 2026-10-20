# 0068 — Re-reading a finished parent exercise, and a themed LLM follow-up

Date: 2026-10-20
Status: Accepted

## Context

Product owner, in a new follow-up after the 0064-0067 roadmap shipped:
*"after parents upload doc is read, then using the inference llm model
should be able to provide more sources auto build stories or
sentences for child to learn, age appropriate.. also after read the
parents doc, i shoud be able to go back the read the same. now after
being read its removed from our reading list."* Reading the actual
code confirmed the gap named in that last sentence: `reading_exercises.py`'s
`mark_consumed()` is called by `_run_reading_partner()` as soon as an
exercise is picked up, and `next_pending_for_child()` only ever
returns unconsumed rows -- so once read, an exercise was gone from
Reading Partner's own serving logic for good (still visible, marked
"Read", in the parent dashboard's list, but never offered to the
child again), and nothing ever built on it afterward.

Two clarifying questions were asked before implementing, since both
had more than one reasonable shape:
1. How should "go back and read the same" be triggered? Chose
   **voice-offered each session** (Reading Partner itself offers it)
   over a parent-dashboard button, since it needs no UI change and
   works straight from voice.
2. What should the LLM auto-build afterward? Chose **same theme/
   vocabulary, new sentences** -- a follow-up story reusing the parent
   doc's own topic/words -- over just falling back to the normal
   adaptive generator untouched.

## What shipped

Both gated behind the same `CHITTI_ENABLE_READING_EXERCISES=1` flag
decision 0063 already established for the whole exercises feature.

**Re-read offer** (`voice_loop_demo.py`): with no NEW exercise waiting
and the offer not already made this call, Reading Partner checks
`reading_exercises.list_for_child()` for anything already consumed
(excluding one *this same call* just finished, so a child isn't asked
to re-read something they finished thirty seconds ago) and offers the
most recently finished one by title: *"Would you like to read 'X'
again, or try something new?"* -- same `is_affirmative()` gate as
every other optional activity. Accepting re-serves that exact
exercise's content verbatim, same as a fresh read (sentence-by-
sentence per decision 0067, hint ladder, mastery update, all
unchanged). Asked at most once per `_run_reading_partner()` call, not
after every book, so a long multi-book session isn't re-asked the same
thing repeatedly.

**Themed follow-up** (`book_generation.py` / `conversation/service.py`
/ `voice_loop_demo.py`): `generate_decodable_book()` and
`ConversationService.generate_decodable_book()` both gained an optional
`source_passage: str | None` parameter. When given, `_build_prompt()`'s
opening instruction asks the writer to build a companion story reusing
the given passage's own topic and some of its vocabulary, instead of
the child's generic stored `interest` -- reusing the exact same
verifier-gated loop (decodability + safety retries), not a separate
generation path. `_run_reading_partner()` remembers a freshly-finished
exercise's text in a call-scoped `followup_source_text` the moment it's
picked up, and spends it on the very next generated book (if the child
wants one) -- consumed whether or not that generation attempt succeeds,
so it fires exactly once per exercise, never repeatedly. A re-read
(as opposed to a fresh exercise) does NOT set this -- revisiting
something already read isn't new content to build a follow-up from.

## Consequences

New tests in `test_reading_book_generation.py`:
`generate_decodable_book()` themes on `source_passage` when given
(and ignores `interest` in that case), and falls back to `interest`
when it isn't given.

New test in `test_conversation_service.py`:
`generate_decodable_book(..., source_passage=...)` passes the text
through into the actual prompt sent to the LLM.

New tests in `test_voice_loop_demo_intent.py`: a second, separate
`_run_reading_partner()` call offers and (on accepting) re-serves a
previously-finished exercise verbatim; declining falls back to normal
generation; and finishing a fresh exercise, then wanting another book,
produces a follow-up book whose generation prompt contains the
exercise's own text (verified via the actual `generate_reply` call
args, not just spoken output). The two new book-generation tests use a
retry-tolerant fake LLM (a function, not a fixed reply list) rather
than guessing how many on-target retry attempts
`generate_decodable_book()`'s own loop will take -- same reasoning an
existing switch-detection test already uses for capture counts.

All 43 pre-existing Reading Partner tests pass unchanged -- none of
them have more than one book per session or any pre-existing consumed
exercise, so the new branches never activate for them.

Full suite: 525 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- No parent-dashboard "read again" button was added (the other option
  from the clarifying question) -- voice-only for now, per the chosen
  answer.
- If a child finishes an exercise, re-reads a DIFFERENT, older
  finished exercise, and then wants another book, that re-read does
  not trigger a themed follow-up (only a fresh exercise does, by
  design) -- the follow-up only ever themes on the most recently
  *freshly* finished exercise, which could occasionally be a few books
  back by the time the child gets to it if they decline several
  "another one?" prompts in different directions first. Not expected
  to matter in practice (`followup_source_text` is spent on the very
  next book), but worth knowing if it ever looks surprising in a real
  session log.
- The re-read offer only ever surfaces the single most recently
  finished exercise, never lets the child pick among several finished
  ones by voice -- a reasonable v1 scope, not a technical ceiling.
