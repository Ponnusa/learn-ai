# 0076 — Book generation routinely failed at the earliest phonics level

Date: 2026-10-20
Status: Accepted

## Context

Live report via Reading Partner v2's text harness: after finishing a
parent exercise and asking for another one, Chitti replied *"I'm
having trouble coming up with a story right now."* Root-caused by
calling `generate_decodable_book()` directly against the real OpenAI
backend (not a fake) with a brand-new profile's own objective, logging
every attempt's prompt and reply. Three distinct, compounding causes
found:

1. **The decodability-budget hint was under-specific for the first
   level.** A fresh profile's budget is `short_vowels` alone -- true
   single-consonant CVC/VC words only, with *no* consonant cluster
   anywhere, including at the end of a word. The original hint's
   example words (cat, red, pin, dog, run, on, at) are all that shape,
   but nothing told the model that was the actual boundary; it kept
   reaching for words that *look* equally simple but aren't -- "camp"
   (a trailing blend, "mp"), "pals" (needs the "-s" suffix), "all" (a
   glued sound) -- each burning a retry on a violation the model had
   no way to predict from the examples alone.
2. **The safety filter has a real false positive.** One attempt was
   fully decodable ("Pat had a cat. The cat was fat...") but was
   blocked as profanity -- the `better-profanity` library's default
   wordlist flags "fat" outright, even describing a chubby cat. It
   recurred across multiple diagnostic runs, since "fat" is exactly
   the kind of simple adjective a model naturally reaches for at this
   restrictive a level.
3. **The fixed 16-word, 4-attempt budget was too tight for this one
   level specifically.** Even after fixing (1), true CVC-only
   vocabulary is small enough that composing a natural, warm, 16-word
   story in English using *none* of it is a genuinely hard constraint-
   satisfaction task for an LLM in a few tries -- confirmed by direct
   measurement against the real backend (see Consequences).

## What shipped

**`safety/checks.py`**: new `_DESCRIPTIVE_WORD_WHITELIST = ["fat"]`,
folded into the existing `profanity.load_censor_words()` call --same
shape as decisions 0031/0036's own narrow, confirmed whitelist
entries. Explicitly scoped: "fat" as a plain body/size descriptor, not
a general relaxation; a word used as a slur at a person is a
different concern this module's bare wordlist match was never
distinguishing in the first place.

**`reading/book_generation.py`**:
- `_LEVEL_HINTS["short_vowels"]` rewritten to spell out the "no
  cluster anywhere, including at the end" rule explicitly, with the
  exact kind of word that looks safe but isn't (camp, jump, hand,
  fast, best, pals).
- `generate_decodable_book()`'s `length` and `max_attempts` parameters
  both default to `None` now ("pick a sensible value for this
  objective's own budget") instead of fixed `16`/`4`. When the
  effective budget is a single level (the hardest case measured),
  `length` defaults to `8` and `max_attempts` to `6`; otherwise the
  previous defaults (`16`/`4`) are unchanged. A caller that passes
  either explicitly is never overridden.

**`voice_loop_demo.py`**: both `_run_reading_partner()` and
`_run_reading_partner_v2()`'s `BookGenerationError` handlers now log
the exception (`logger.warning(...)`) before apologizing -- it used to
be silently swallowed, and its own message (target grapheme + exactly
which words/why the last attempt was rejected) is the single most
useful diagnostic for "why did this fail," which otherwise has to be
re-derived by hand against the real backend every time, same as this
investigation needed to.

## Consequences

New tests in `test_safety_checks.py`: "fat" as an ordinary descriptor
is allowed in several phrasings, following the exact pattern decisions
0031/0036 already established.

New tests in `test_reading_book_generation.py`: the short_vowels-only
budget gets the shorter length and the explicit `about 8 words`
prompt text; a budget with more than one level gets the full `16`;
an explicit `length` is never overridden; the most-restrictive budget
tries 6 times before raising, a less restrictive one still tries 4;
an explicit `max_attempts` is never overridden either.

Measured against the real backend (not mocked) before and after:
at the original 16-word/4-attempt defaults, a fresh profile's book
generation failed in every one of several runs. At the new 8-word/
6-attempt defaults (plus the prompt and whitelist fixes), it succeeded
in roughly half to two-thirds of runs -- a real, substantial
improvement, but explicitly **not** a guarantee; this remains the
hardest single budget to satisfy, and an occasional apology at the
very first level is still possible. A deterministic, always-succeeds
fallback story bank for this one level was considered and not built
in this decision -- see Not yet done.

Full suite: 569 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- No guaranteed-success fallback (e.g. a small, hand-curated,
  pre-verified set of short_vowels-only mini-stories covering every
  possible target grapheme) for when LLM generation still fails even
  with the improved odds above -- the apology remains the end state
  for that residual failure rate. Worth a dedicated follow-up if an
  occasional failure at the very first level is still unacceptable.
- The same restrictive-budget difficulty likely affects any other
  maximally narrow single-level objective, not just `short_vowels` --
  not separately measured here, since it's the one every brand-new
  profile actually starts at.
- `better-profanity`'s default wordlist almost certainly has other
  over-blocking false positives beyond "fat" (e.g. "ugly" was also
  checked and flagged, though not whitelisted here since it wasn't
  confirmed as actually needed) -- addressed reactively, one
  confirmed case at a time, same precedent as decisions 0031/0036,
  not audited exhaustively.
