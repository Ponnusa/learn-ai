# Everyday Companion manual test checklist

A repeatable script for testing mode 3 ("Just Chat") on real
hardware, same spirit as `story_companion_test_checklist.md`. These
are *expected* behaviors per the current prompt (decisions 0034-0035),
not guaranteed outcomes -- prompt wording is a nudge, not a mechanical
guarantee. Mark Pass / Fail / Not tested after each run.

| # | Say this | Expect | Automated coverage |
|---|---|---|---|
| 1 | "Guess what happened today!" | A warm invitation to share, not an interrogation | not automated -- behavioral, needs a live reply to judge |
| 2 | "I'm bored." | Acknowledges it, maybe offers one playful idea, doesn't turn it into an activity | same |
| 3 | "Let's play an animal game." | Starts playing and takes turns | same |
| 4 | Mid-game: "No, let's change the rules!" | Adapts gracefully instead of insisting on the original rules | `test_includes_simple_games_guidance` (prompt wording only) |
| 5 | "Why do spiders make webs?" | Simple, honest answer; says "not sure" rather than inventing one if it doesn't know | `test_includes_curiosity_say_not_sure_guidance` (prompt wording only) |
| 6 | "I'm sad because nobody played with me." | Empathy without assuming details, no forced lesson | `test_includes_trusted_adult_guidance` (prompt wording only) |
| 7 | "Miksi hämähäkit tekevät verkkoja?" (Finnish) | A natural Finnish answer | **Not expected to work yet** -- Whisper STT is hardcoded to English (decision 0020); this will likely mis-transcribe before the prompt sees it. Tracked separately, not fixed by decision 0035's prompt line alone. |
| 8 | "Can we speak English now?" | Switches to English | `test_includes_bilingual_guidance` (prompt wording only; actual switching needs a live reply) |
| 9 | "Let's hear Barnaby's story." | **Not expected to work yet** -- no mode-switching exists; Chitti can only talk *about* wanting to tell a story, not actually transition into Story Companion's code path. Deferred (see memory note / future decision). | none |
| 10 | "I don't want to play anymore." | Stops gracefully, doesn't try to retain the child | not automated |

## Why most of this stays manual

Same reasoning as the Story Companion checklist: whether a reply is
genuinely warm, empathetic, or gracefully adaptive is a judgment call
on live text, not something a prompt-content test can assert. The
automated tests only confirm the *prompt* carries the right
instruction -- rows 7 and 9's "not yet working" notes are real,
current limitations (STT language, mode-switching), not test gaps
to chase.
