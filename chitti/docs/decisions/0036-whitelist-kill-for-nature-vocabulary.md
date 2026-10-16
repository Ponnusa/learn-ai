# 0036 — Whitelist "kill" for ordinary nature/food-chain vocabulary

Date: 2026-10-16
Status: Accepted

## Context

A real Everyday Companion transcript: "Why do spiders make webs?"
got a flat profanity decline ("I don't say that word"), right in the
middle of a conversation otherwise working well (graceful rule
changes mid-game, genuine empathy for sadness, a fluent Finnish
reply, switching back to English on request).

Root-caused rather than guessed at: the decline message is
specifically PROFANITY's, and testing candidate words a model would
naturally use answering that question found the culprit -- **"kill"**
is in the base `better-profanity` wordlist. Any honest answer about
predators or food chains ("webs help them trap and kill insects for
food") legitimately needs that word, and curiosity questions about
nature ("why do spiders make webs," "how do lions hunt," "why do
sharks attack") are exactly what Everyday Companion (decision 0034)
exists to answer.

## Fix

`safety/checks.py`'s whitelist (decision 0031's bathroom-humor set)
gained a second, separately-named set: `_NATURE_VOCABULARY_WHITELIST
= ["kill"]`. Verified this doesn't weaken anything: `"kill
yourself"`/`"kill your self"` is still caught independently by
`_UNSAFE_CONTENT_PATTERNS` (a separate regex that doesn't depend on
the profanity wordlist at all), now correctly categorized as
`UNSAFE_CONTENT` rather than the less-precise `PROFANITY` it
happened to fall under before.

## Consequences

5 new unit tests (220 total passing): plain "kill" and nature-context
sentences now pass, and a regression guard confirms self-harm
language is still blocked -- just reclassified to the more accurate
category.

## Not yet done

Same caveat as decision 0031: this is a word-level whitelist with no
sense of context. If "kill" ever appeared inside a genuinely
inappropriate sentence that didn't also match `_UNSAFE_CONTENT_
PATTERNS` or another category, the profanity check specifically
wouldn't catch it on that word alone. Accepted here because "kill" in
isolation, outside the dedicated self-harm/violence patterns, has no
plausible harmful reading in this product's context -- the same
judgment call decision 0031 already made for bathroom humor.
