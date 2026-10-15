# 0024 — Deterministic addition-fact check for Teachable-Friend

Date: 2026-10-15
Status: Accepted

## Context

A series of math-dialogue sample conversations surfaced the same
structural issue flagged in the earlier correctness-architecture
discussion: for Chitti to react genuinely to "one plus one is two,"
or gently guide a wrong "2+2=3" the way a hand-written example did
("Let's count together: one, two apples, then three, four..."), the
model has to privately know which one is actually true. We decided
*against* building a correctness evaluator for English/Finnish (no
deterministic evaluator exists; a real research project). Simple
addition is the opposite case: `a + b == c` has one real answer and
is trivial to check in a few lines of app code.

**Central design principle, carried over from decision 0023's "never
spoken as a score" instinct**: the child must never feel tested. The
verified fact is plumbing the model uses, not something the child is
graded against -- their own explanation keeps driving the
conversation, and a wrong claimed sum is guided through gently
(building on what they already said), never flatly marked wrong.

## What this is, and isn't

- **Is**: a pure-function regex check (`education/math_check.py`'s
  `extract_addition_claim()`) for a complete claim the child states in
  one utterance ("one plus one is two", "2+2=5", "four plus two is
  six"). When found, the verified result (correct or not, plus the
  actual correct sum) is appended to `TEACHABLE_FRIEND_SYSTEM_PROMPT`
  for that one turn via `build_math_check_note()` -- the model still
  chooses every word, it just isn't trusted to privately judge the
  arithmetic itself.
- **Isn't**: a broader graded engine. `education/` stays mostly
  unbuilt (superseded by decision 0002); this is the one deliberate
  exception, because unlike grammar or pronunciation, addition has a
  cheap, unambiguous answer.

## Scope and known gaps

- Only a complete, self-stated claim is recognized -- covers "child
  teaches Chitti a math fact" directly. A bare reply to a challenge
  *Chitti* itself posed (just "five." with no restated operands) isn't
  covered; that needs app-owned, cross-turn challenge-number tracking,
  a bigger feature deliberately not built here.
- Numbers 0-20 as digits or single words; multi-word numbers ("twenty
  two") aren't recognized. Found live in testing: a naive version of
  the regex silently mis-parsed "twenty two plus one is twenty three"
  by matching only the trailing word ("two")of the compound number,
  producing a wrong but confident-looking result (2+1=20) instead of
  recognizing the gap. Fixed by checking the word immediately before/
  after the matched tokens for another word-number, and returning
  `None` (falls through to an ordinary conversational turn) rather
  than guessing.
- Only addition; subtraction/multiplication/etc. aren't recognized.

## Consequences

11 new unit tests (137 total passing): the extractor's digit/word
forms, case-insensitivity, correct/incorrect sums, the multi-word-
number false-match fix, and `ConversationService.teachable_friend_
reply()`'s prompt-injection with and without a `math_check` result.
