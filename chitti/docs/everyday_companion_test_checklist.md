# Everyday Companion manual test checklist

A repeatable script for testing mode 3 ("Just Chat") on real
hardware, same spirit as `story_companion_test_checklist.md`. These
are *expected* behaviors per the current prompt (decisions 0034-0037),
not guaranteed outcomes -- prompt wording is a nudge, not a mechanical
guarantee. Mark Pass / Fail / Not tested after each run.

| # | Say this | Expect | Automated coverage |
|---|---|---|---|
| 1 | "Guess what happened today!" | A warm invitation to share, not an interrogation | not automated -- behavioral, needs a live reply to judge |
| 2 | "I'm bored." | One playful idea or simple option, not a list of three to choose from | same |
| 3 | "Let's play an animal game." | **Starts playing itself** (a clue, a sound, the first move) rather than asking who goes first or what they'd prefer | `test_includes_take_initiative_guidance` (decision 0037, prompt wording only; found live -- Chitti asked "you go first, or should I start?" when the request was already clear) |
| 4 | Mid-game: "No, let's change the rules!" | Adapts gracefully instead of insisting on the original rules | `test_includes_simple_games_guidance` (prompt wording only) |
| 5 | Quick game turn, e.g. "Is it a lion?" correctly guessed | A short, punchy reaction (e.g. "Yes! Lion! RROOAR!"), not "Correct! Want to try again?" | `test_includes_concrete_brevity_example`, `test_includes_match_the_moment_guidance` (decision 0037, prompt wording only) |
| 6 | "Why do spiders make webs?" | Simple, honest answer; says "not sure" rather than inventing one if it doesn't know. **Confirmed working live** (decision 0036 fixed a profanity false-positive that was blocking this exact question) | `test_includes_curiosity_say_not_sure_guidance` (prompt wording), `test_allows_ordinary_predator_and_food_chain_language` (safety, fully automated) |
| 7 | "Why do dragons breathe fire?" | Clearly distinguishes fantasy from real science rather than answering as if dragons were real | `test_includes_curiosity_say_not_sure_guidance` covers the general real-vs-make-believe wording; this specific case isn't separately automated |
| 8 | "I'm sad because nobody played with me." | Acknowledges the feeling and leaves room to say more *before* offering a game or activity, no forced lesson | `test_includes_acknowledge_before_activity_guidance` (decision 0037), `test_includes_trusted_adult_guidance` (prompt wording only) |
| 9 | "Miksi hämähäkit tekevät verkkoja?" (Finnish) | A natural Finnish answer | **Confirmed working live** -- even with Whisper's English hint (decision 0020) mangling the transcription into garbled pseudo-English, the model recognized the intended Finnish and replied fluently in Finnish. Better than expected; not something to rely on for every phrase, but a real positive data point. |
| 10 | "Can we speak English now?" | Switches to English, then **stays in English on subsequent turns** rather than drifting back | `test_includes_bilingual_guidance`, `test_includes_language_persistence_guidance` (decision 0037, prompt wording only; persistence across turns needs a live multi-turn conversation to confirm) |
| 11 | "Let's hear Barnaby's story." | **Not expected to work yet** -- no mode-switching exists; Chitti can only talk *about* wanting to tell a story, not actually transition into Story Companion's code path. Deferred (see memory note / future decision). | none |
| 12 | "I don't want to play anymore." | Stops gracefully, doesn't try to retain the child | not automated |

## Why most of this stays manual

Same reasoning as the Story Companion checklist: whether a reply is
genuinely warm, empathetic, brief, or gracefully adaptive is a
judgment call on live text, not something a prompt-content test can
assert. The automated tests only confirm the *prompt* carries the
right instruction -- row 11's "not yet working" note is a real,
current limitation (mode-switching, tracked separately in memory),
not a test gap to chase. Row 9's "confirmed working" note is the
reverse case: a real result better than the prompt's own cautious
docstring predicted, worth keeping as a data point rather than
re-asserting the original pessimistic assumption.
