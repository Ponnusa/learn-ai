# 0037 — Everyday Companion: initiative, pacing, and language persistence

Date: 2026-10-16
Status: Accepted

## Context

A real transcript test of Everyday Companion (after decisions
0034-0036) surfaced one confirmed compliance gap and four genuinely
new, missing behaviors:

- **Compliance gap, not a missing instruction**: "don't end every
  turn with a question" (decision 0032's wording, reused here) was
  already in the prompt, but Chitti still frequently closed with
  "Want to try again?" / "What would you like to do next?" This is
  the same honest soft-limit already named in decision 0028 -- a
  prompt nudge isn't a guarantee.
- **No initiative**: when the child said "let's play an animal
  game," Chitti asked "you go first, or should I start?" instead of
  just starting -- an unnecessary clarifying question on an already-
  clear request.
- **No pacing guidance**: quick game turns got paragraph-length
  replies as often as genuine explanations did; nothing in the
  prompt distinguished "brief reaction" from "explain this properly."
- **Emotional support moved too fast**: "nobody played with me
  today" got empathy immediately followed by game/activity
  suggestions, without first leaving room for the child to say more.
- **Language switching only verified per-turn**: Finnish worked (even
  surprisingly well through a mangled transcription) and switching
  back to English worked, but nothing in the prompt said to *stay*
  in a language across turns rather than deciding fresh each time.

## Fix

Rather than rewriting `build_everyday_companion_prompt()` wholesale
(a full rewrite was proposed and declined -- this project's prompt
work has been additive, verified-against-real-transcripts fixes
since decision 0025, not replacements), five targeted additions:

1. A concrete before/after example next to the existing "vary your
   moves" instruction ("Yes! Lion! RROOAR!" vs. "Correct! Want to
   try again?") -- restating the same abstract rule a third time
   seemed less likely to help than a concrete contrast.
2. "If the child's request is already clear... just go ahead and
   start... only ask when you genuinely need something from them."
3. "Match how much you say to the moment" -- brief for game turns,
   a few sentences for everyday questions, more only on request.
4. "If the child shares something personal or upsetting, acknowledge
   it first and give them room to say more... don't rush straight
   into offering a game."
5. Extended the existing bilingual line: stay in the language
   switched to until the child switches back, use natural phrasing
   rather than word-for-word translation, and don't correct
   imperfect transcription unless asked to practice.

Also updated `docs/everyday_companion_test_checklist.md` with two
real results from this round of testing worth keeping as data
points: the spider question is now confirmed working live (decision
0036's fix), and the Finnish exchange worked better than the
checklist's own earlier cautious prediction -- even a mangled,
English-hint-forced transcription didn't stop the model from
recognizing and replying in fluent Finnish.

## Consequences

5 new unit tests (229 total passing) confirming each addition's
wording is present.

## Not yet done

None of these five additions are guarantees -- same honest limit as
every prompt-only fix this session. Language persistence and the
initiative behavior specifically need a live multi-turn conversation
to actually confirm, not just a prompt-content check; both are
flagged as such in the updated checklist rather than claimed as
settled. Mode-switching ("let's hear Barnaby's story") remains
deferred, tracked in memory, untouched by this decision.
