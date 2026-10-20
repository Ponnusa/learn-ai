# 0073 — Word family: real-word check, and a corrected onset-rime split

Date: 2026-10-20
Status: Accepted

## Context

Live bug report: using the new text-only harness (decision 0072), the
word-family activity (decision 0066) offered to practice more words
like "frog" -- and then asked the child to read "prog", "brog", and
"srog" in turn. None of those are real English words. Product owner,
flagging it directly: *"are these really words?"*

Traced to two compounding causes, both root-caused and fixed here:

1. **The onset-rime split was linguistically wrong for blend-initial
   words.** `extract_rime()` treated only a word's single *first*
   grapheme as the onset -- for "frog" (f-r-o-g), that gave rime
   "rog", a pattern essentially no other real English word shares.
   Asked to find real words matching an all-but-impossible pattern,
   the LLM invented some instead of admitting none exist. The standard
   linguistic definition splits onset and rime at the first *vowel*:
   "frog"'s onset is the full blend "fr", its rime is "og" -- which
   has many real matches (dog, fog, hog, jog, log, clog, ...).
2. **Nothing checked real-word-ness at all.** Even with a correct
   rime, `verify_family_word()` only ever checked phonics *structure*
   (exact rime match + decodable) -- "prog"/"brog"/"srog" are all
   structurally valid under the old definition (and, not entirely
   coincidentally, still phonics-decodable CVC-with-blend shapes under
   the new one too), so the verifier wrongly waved every one of them
   through. Decision 0066's own stated discipline ("deterministically
   verify, don't trust the model's say-so") was only half-implemented.

## What shipped

**`reading/word_family.py`**:
- New `_rime_graphemes()`: the onset is everything before the first
  vowel-kind grapheme (one consonant, or a full blend) -- rime is that
  vowel onward. `None` if there's no vowel to anchor on, or the word
  starts with one (e.g. "at" -- nothing meaningful to treat as a
  separate onset). `extract_rime()` and `verify_family_word()` both
  now go through this one shared function, so the target rime and
  every candidate's own rime are always computed the exact same way
  -- previously `verify_family_word()` hardcoded its own "skip the
  first grapheme" logic independently of `extract_rime()`'s, which
  would have silently drifted out of sync with this fix if only one
  side were corrected.
- New `_COMMON_ENGLISH_WORDS`: an originally-assembled (not copied
  from any single external wordlist or corpus) set of common, simple,
  real English words covering the classic phonogram/word-family
  groups used throughout early-reading pedagogy. Checked and rejected
  two well-known candidate external wordlists before writing this:
  Google's n-gram-derived common-word lists explicitly discourage
  commercial use without separately licensing the underlying corpus
  from the Linguistic Data Consortium -- not a risk worth taking on a
  commercial child-safety product. `verify_family_word()` now also
  requires membership in this set. Deliberately not exhaustive -- a
  real, decodable word missing from it is simply dropped (the same
  "fails a check -> drop, don't retry" shape every other verifier in
  this package already follows), never an error. A missing real word
  is an acceptable false negative; a word invented by an LLM is not an
  acceptable false positive.

## Consequences

`test_word_family.py`: `test_extract_rime_rime_is_every_grapheme_after_the_first`
replaced with `test_extract_rime_splits_on_a_full_blend_not_just_the_first_letter`
(frog -> "fr"/"og", not "f"/"rog"); new
`test_extract_rime_returns_none_when_the_word_starts_with_the_vowel_itself`
("at"); new `test_verify_family_word_rejects_invented_non_words_sharing_a_real_rime`
(the exact reported bug: prog/brog/srog against frog's corrected "og"
rime, all rejected) and `test_verify_family_word_accepts_real_words_sharing_frogs_corrected_rime`
(dog/log, accepted). Every other existing `word_family.py`/
`generate_word_family()`/Reading Partner test continues to pass
unchanged -- "mat"/"cat"/"sat"/"bat" are all single-consonant-onset
words, so the corrected split gives the identical rime ("at") the old
one did; "chat"'s onset is already one digraph grapheme ("ch"), not
two separate consonant graphemes, so its split is unaffected too.

Full suite: 532 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- `_COMMON_ENGLISH_WORDS` is a few hundred words covering the most
  common phonogram families, not a comprehensive dictionary -- a
  legitimate but less common real word will sometimes be dropped
  rather than offered. Acceptable per the false-negative-over-false-
  positive reasoning above, but worth knowing if the word-family
  activity ever seems to generate suspiciously few candidates for a
  word with an unusual rime.
- No change to `build_family_prompt()`'s wording itself -- the fix is
  entirely in verification; the prompt still just asks for "simple,
  real English words," same as before.
