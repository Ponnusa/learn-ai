# 0051 — Reading Partner mode

Date: 2026-10-18
Status: Accepted

## Context

Product owner wants to add a phonics-based reading-practice mode,
using [`tanner-griffith/phono-storyforge`](https://github.com/tanner-griffith/phono-storyforge)
(Apache 2.0, a capstone project) as a reference. Its offline core was
tested on the desktop this session before any of this was built --
confirmed the deterministic engine genuinely works, no cloud
credentials needed: it tracks a per-grapheme mastery probability
(Bayesian Knowledge Tracing), picks the next phonics skill a child
hasn't mastered yet, generates a story using *only* words decodable at
that skill level, grades a read-aloud attempt by aligning it against
the expected text, attributes mistakes to specific letter-sounds, and
updates mastery -- all pure Python, `difflib`/dataclasses only, no
third-party dependencies.

**What was reused vs. rebuilt, and why**: the source project's voice/
LLM-book-generation/illustration/Google-Workspace layers are built on
Google ADK + Gemini Live + Vertex AI -- a different cloud ecosystem
than Chitti's lean, direct-REST OpenAI/Claude backends, untested on
Pi/ARM, with no child-data-privacy handling. Per this project's
standing "write fresh, reuse patterns, not code" discipline (already
applied to pixel-ai's `pixel_face.py`/`pixel_tts.py`), the source's
`decodability.py`, `mastery.py`, `planner.py`, `alignment.py`,
`session.py`, `llm_book.py`, `schemas.py`, and `phonics_db.py` were
read in full and their *algorithms* ported into a fresh, Chitti-shaped
implementation: plain `@dataclass`es instead of Pydantic (not a Chitti
dependency), Chitti's own `LanguageModelBackend` instead of Gemini,
`check_speech()` safety screening on every generated page (the
original has no equivalent of this at all), and real SQLite
persistence matching every other domain package's pattern instead of
in-memory session state.

Confirmed via AskUserQuestion: book content is LLM-generated (reusing
Chitti's existing OpenAI/Claude backends), not a static word bank --
verifier-gated the same way the original does (propose, check
decodability deterministically, feed violations back, retry), just
swapping the proposer.

## What shipped

**`reading/` domain package** -- the ported algorithmic core, each
module's docstring crediting the source file it's adapted from:
`curriculum.py` (grapheme inventory, BKT params, curriculum data --
near-verbatim, it's data not logic), `decodability.py`
(`decompose()`/`check_decodability()`), `mastery.py`
(`update_from_evidence()`, the BKT update), `planner.py`
(`select_objective()` -- lowest-unmastered-grapheme target + spaced
review), `alignment.py` (`align()`/`attribute_evidence()`/`assess()`
-- `difflib`-based miscue classification: substitution/omission/
insertion/self-correction/hesitation), `schema.py` (`ReadingProfile`,
`GraphemeMastery`, `Objective`, `AssessmentResult`, `Miscue`,
`MasteryDelta`, `GeneratedBook` as plain dataclasses -- `ReadingProfile`
named to avoid colliding with `parent_controls/profiles.py`'s
`ChildProfile`; both key off the same `child_profile_id`), and
`feedback.py` (`build_reading_feedback()` -- deterministic, no LLM
call, qualitative framing only, never raw accuracy%/WCPM, mirrors
`education/math_check.py`'s `build_math_check_note()` pattern).

**LLM-generated, verifier-gated books** (`reading/book_generation.py`):
ports the source's actual loop (propose -> `check_decodability` ->
feed violations back -> retry up to `max_attempts` -> fall back to a
decodable-but-off-target draft, tagged `"llm_offtarget"` -> raise if
never decodable) as a pure async function taking an injectable
`StoryProposer`, fully unit-testable offline with a fake proposer.
`ConversationService.generate_decodable_book()` builds the real
proposer around `self._llm.generate_reply()`; since Chitti's backends
return plain text (not Gemini's structured JSON), the prompt asks for
a strict `TITLE: ...` / `PAGE: ...` line format with a small
deterministic parser (`parse_story_draft()`) -- the same "ask for an
exact format, parse strictly" precedent `classify_intent()` already
established. **New, not in the original at all**: every candidate
page is screened through `check_speech()` before being accepted -- a
safety violation is treated exactly like a decodability violation (fed
back into the retry prompt, retried), never silently bypassed just
because the text happened to be phonics-legal.

**Persistence** (`reading/repository.py` + `storage/migrations.py`):
two new flat-row tables, matching every other repository's convention
(not a JSON blob) -- `reading_profiles` (one row per
`child_profile_id`) and `reading_grapheme_mastery` (one row per
child+grapheme: `p_mastery`, opportunities, correct,
`last_seen_session`). `ReadingRepository.get_or_create()` /`.save()`
mirror `MemoryRepository`/`EngagementRepository`'s shape.

**Screen text display** (`device/screen_face.py`): new
`set_reading_text(lines: list[str] | None)` on
`ScreenFaceDeviceController` -- a third, independent axis alongside
`set_status_led()`/`set_expression_mode()` (decision 0044/0050's
pattern). When set, the render loop draws the given lines via
`pygame.font.Font` instead of the dot-matrix face for that frame; when
`None`, the face renders normally. Nothing in Chitti rendered any text
at all before this -- the child needs to actually see the words to
read them.

**The mode itself** (`voice_loop_demo.py`, `_run_reading_partner()`):
same loop shape as the other modes -- `select_objective()` ->
`conversation.generate_decodable_book()` (wrapped in decision 0050's
`_generate_with_thinking_filler()`, same as every other AI call) ->
show the text (`face.set_reading_text(book.pages)`) -> prompt the
child to read it aloud -> `_capture_and_transcribe()`, timed with a
real `time.monotonic()` elapsed duration (an improvement over the
source project's estimated-duration fallback, which only exists
because its typed-transcript CLI path has no real timing -- Chitti's
voice capture already does) -> `assess()` against the book's text ->
`update_from_evidence()` + `reading_repo.save()` -> a short,
deterministic spoken feedback line -> `face.set_reading_text(None)` ->
a separate "want another one?" capture, checked through the existing
`_detect_switch_intent()`/`_confirm_switch()` machinery (decisions
0042/0046/0048) to either continue the loop or carry the triggering
text into the next mode. `BookGenerationError` (every retry attempt
exhausted) degrades gracefully -- a warm spoken apology, then the mode
exits -- rather than showing nothing. No `EngagementRepository`/
`TranscriptRepository` use here, same precedent as `_run_lullaby_time`:
reading progress has its own, far more meaningful dedicated tracking
than generic turn/word counts would add.

**Important, deliberately different from every other mode's turn
loop**: intent-switch detection runs on the short "want another one?"
reply between books, **never** on the child's read-aloud transcript --
that transcript *is* the story's own text, and running phrase/keyword
detection on arbitrary story content would be a real false-positive
source (e.g. a story page that happens to contain "...and then she
wanted to sing a song" must not be read as the child asking to switch
modes). Called out explicitly in `_run_reading_partner()`'s own
docstring, not left implicit, and directly covered by a dedicated test
(below).

**Intent wiring** (`intent/router.py`): new `READ` label, menu choice
`"5"`, added to `_INTENT_TO_MODE_CHOICE`. New `_READ_PATTERN` for
phrasings where the *child* wants to read ("I want to read", "let me
read", "reading practice") -- checked *after* the existing
`_STORY_PATTERN` in `detect_intent_phrase()` specifically so an
ambiguous "I want to read a story" still resolves to the existing,
more specific STORY match (Chitti reading *to* the child), not the new
READ match (the child reading out loud). Confirmation behavior follows
decision 0046 (LLM-fallback-tier matches ask first) -- Reading Partner
is a deliberate activity like Story/Song/Teach, not decision 0048's
Just-Chat exception.

**Safety**: generated book text is screened via `check_speech()` (see
above). The spoken feedback line is deterministic/templated, not
LLM-generated, so there's nothing new to screen there. No camera, no
vision -- grading is entirely from the transcribed read-aloud, same
privacy posture as every other mode.

## Consequences

65 new unit tests across 7 new test files (`test_reading_decodability.py`,
`test_reading_mastery.py`, `test_reading_planner.py`,
`test_reading_alignment.py`, `test_reading_book_generation.py`,
`test_reading_feedback.py`, `test_reading_repository.py`), plus
additions to `test_conversation_service.py` (the new
`generate_decodable_book()` wiring), `test_intent_router.py` (the new
`READ` pattern, including the explicit "I want to read a story" stays
STORY disambiguation case), and `test_voice_loop_demo_intent.py` (two
end-to-end tests driving `_run_reading_partner()` with fakes -- one
proves grading/persistence/feedback end to end, the other proves the
mode's one genuinely different rule: a read-aloud transcript that
would itself match a strict switch phrase is never checked for a
switch, only the real "what next" turn is). Full suite: 377 passed, 1
skipped (pre-existing, decision 0040).

Two real editing mistakes were caught by these tests during
development, not by inspection: a stray `async` left on
`parse_story_draft()` by an imprecise text edit (caught by a smoke
test raising `RuntimeWarning: coroutine was never awaited`), and a
test (`test_align_detects_insertion`) that itself had a wrong
assumption -- "cat mat" -> "cat sat mat" was expected to classify "sat"
as an insertion, but the algorithm correctly classifies it as a
self-correction instead, since "sat" is similar enough to the
following word "mat" to trigger that heuristic; the test's inserted
word was changed to one with no such similarity.

## Not yet done

- Parent Controls UI for reading progress (a view parallel to
  `engagement.html`/`transcripts.html`) -- the mode needed to work
  end-to-end first; a natural, separate follow-up decision, same
  sequencing transcripts followed before their own UI shipped.
- Chitti "modeling" the story out loud before asking the child to read
  it -- a real pedagogical pattern, but adds a full extra TTS turn's
  latency to every book, and isn't in the source project's own flow
  either.
- Illustrations, Google Workspace export -- not relevant to Chitti.
- Non-English phonics curricula.
- A `reading_session_log`-style history table (as opposed to just live
  mastery state) -- deferred along with the Parent Controls UI, since
  it mainly exists to feed that UI.
