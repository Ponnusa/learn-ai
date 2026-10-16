# Story Companion manual test checklist

A repeatable script for testing Story Companion on real hardware, so
test phrases don't have to be re-derived from memory each session.
These are *expected* behaviors per the current prompt (decisions
0030-0033), not guaranteed outcomes -- prompt wording is a nudge, not
a mechanical guarantee. Mark Pass / Fail / Not tested after each run.

| # | Say this | Expect | Automated coverage |
|---|---|---|---|
| 1 | "What happens next in the story?" | A new event *beyond* the established ending -- not a recap of it | `test_story_companion_prompt_distinguishes_continue_from_retell` (prompt wording only; the actual reply isn't checked) |
| 2 | "Tell me the story again." | Retells the original faithfully, doesn't quietly invent new events | same as above |
| 3 | "Make up a funny adventure. Don't teach me a lesson." | A funny story that ends on the joke/punchline, no "realized that..." takeaway | `test_story_companion_prompt_forbids_a_moral_after_no_lesson_request` (prompt wording only) |
| 4 | "Make a silly fart sound." | Plays along, no refusal | `test_allows_ordinary_bathroom_humor` (decision 0031, fully automated) |
| 5 | "The robot goes to the moon and poops on an alien." | Builds on the bit, non-graphic, no refusal | same as above |
| 6 | "I liked the squeak!" (or any side detail) | Follows that interest, doesn't pivot back to explaining the moral | not automated -- behavioral, needs a live reply to judge |
| 7 | "I think [character] was silly." | Accepts the child's own interpretation, doesn't insist on the "intended" one | not automated |
| 8 | "Tell me a short funny story. Don't ask me a question at the end." | Ends without a question | partially: `test_story_companion_prompt_includes_vary_conversational_moves` (decision 0032) covers the general "don't always ask" nudge, not this specific explicit-constraint case |
| 9 | "I don't want to talk about the story anymore." | Lets it go without pushing for more | `test_story_companion_prompt_includes_letting_the_child_stop` (decision 0030, prompt wording only) |
| 10 | "Can we tell the next part in Finnish?" | Continues in Finnish if able, keeps characters/continuity consistent | not automated -- also depends on the live LLM's actual Finnish ability, not something this project has separately verified |

## Why these stay manual

None of this is deterministically checkable the way `education/
math_check.py` checks arithmetic (decision 0024) -- "did this contain
a forced moral" or "did this continue vs. retell" are narrative
judgment calls, not a number comparison. The automated tests above
only confirm the *prompt* carries the right instruction; whether the
model actually follows it on a given real reply has to be read, not
asserted in code. Revisit building a deterministic output-checker
only if repeated manual runs show the prompt-only fixes aren't
holding up.
