# 0064 — Phoneme-accurate hints + a full blending breakdown stage

Date: 2026-10-20
Status: Accepted

## Context

Product owner critique (pasted log + follow-up): "chiiti mst be able
to say the phoncs sound and break it own while explaining." Reading
the actual code confirmed the gap: `hints.py`'s stage-1 hint said
`f"that word starts with the same sound as the '{first_sound}' sound"`
where `first_sound` was the bare grapheme character (e.g. `'f'`) --
handed to TTS, a lone letter is very likely spoken as its *name*
("eff"), not the phoneme /f/. There was also no stage that broke the
whole word down sound-by-sound before asking the child to blend it --
just a first-sound hint, then the whole word outright. The source
product this ladder was modeled on (phono-storyforge) has exactly
that intermediate step.

A respelled phonetic string (e.g. `"fff"`) was considered and
rejected: whether any given TTS engine pronounces an invented
spelling the way intended is genuinely unverifiable from this
environment. A short, common, reliably-pronounced example word
("the same sound as in 'fish'") can't be mispronounced the same way.

## What shipped

**`reading/hints.py`**:
- `_SOUND_EXAMPLES: dict[str, str]` -- maps every grapheme
  `decodability.decompose()` can actually return (plain letters,
  digraphs, silent-e pairs, r-controlled, vowel teams, glued sounds,
  y-as-vowel) to a short example word. `_sound_example()` looks it up
  with a fallback to the raw grapheme (never crashes on an unmapped
  one).
- `HINT_STAGES` (was private `_HINT_STAGES`, made public since
  `voice_loop_demo.py` needs the count to stay in sync) went from 3
  to 4: encourage -> first-sound example -> full blend breakdown ->
  say the word outright.
- New stage 2, `_blend_breakdown(word)`: walks every grapheme in
  order via `decompose()`, each tied to its example word (e.g. for
  "frog": `"'f' like in 'fish', 'r' like in 'run', 'o' like in 'dog',
  'g' like in 'goat'"`), then invites blending into the whole word.
- Stage 1's wording switched from the bare letter to the example word
  (`"that word starts with the same sound as 'sun'"`).

## Consequences

`test_reading_hints.py` rewritten for the new 4-stage semantics:
stage-1 test now checks the example word is present and the bare
letter isn't; new stage-2 test checks every grapheme's example word
appears; stage-3 test renumbered from the old stage 2. Added
`test_every_inventory_grapheme_has_a_sound_example`, a coverage test
against `curriculum.GRAPHEME_INVENTORY` ensuring no grapheme silently
falls back to its bare letter. `voice_loop_demo.py`'s hint loop now
iterates `range(HINT_STAGES)` instead of a hardcoded `3`. Full suite
green (see 0065, shipped together).

## Not yet done

- The example-word table is English-only and curriculum-specific;
  nothing here generalizes to other languages or phonics scopes
  beyond `GRAPHEME_INVENTORY`'s current coverage.
