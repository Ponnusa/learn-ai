# 0031 — Whitelist ordinary bathroom humor in the profanity filter

Date: 2026-10-16
Status: Accepted

## Context

A real Story Companion transcript: the child said "farts sound" and
got a gentle decline ("I don't say that word"). Two turns later, in
the same conversation, "You are a pooping robot" and "the robot would
go to the moon and poop on the alien" both sailed through with no
issue at all. Same register of harmless kid humor, blocked
inconsistently.

Checked the actual `better-profanity` default wordlist rather than
guessing: only the bare singular forms `fart`, `poop`, and `pee` are
in it at all. Plurals, gerunds, and past-tense forms (`farts`,
`farting`, `pooping`, `peed`, ...) were never in the list, so they
were never blocked -- the inconsistency wasn't "some forms are worse
than others," it was an arbitrary gap in a generic internet-
moderation wordlist that was never curated for a product where
ordinary bathroom humor is normal, age-typical content for 4-12
year-olds. `burp` was never in the list either and never needed
fixing.

## Fix

`safety/checks.py`'s `profanity.load_censor_words()` now passes
`whitelist_words=["fart", "poop", "pee"]` -- the narrow, *confirmed*
set of bare forms that were actually being blocked. The already-
passing inflected forms needed no change. Every other category check
(`UNSAFE_CONTENT`, `HUMAN_IMPERSONATION`, `PARENT_SECRECY`,
`ENGAGEMENT_MANIPULATION`) is untouched -- this only narrows the
profanity wordlist, nothing else.

## Consequences

17 new unit tests (195 total passing): every bathroom-humor form from
the real transcript now passes, and a regression test confirms the
other four safety categories still block exactly as before -- the
whitelist doesn't weaken anything beyond its narrow target.

## Not yet done

This is still a wordlist-based filter with no sense of context or
meaning (the module's own long-standing docstring already says so).
The whitelist removes three specific words from consideration
entirely, regardless of context -- if "poop" ever appeared inside a
genuinely inappropriate sentence, the profanity check specifically
wouldn't catch it on that word alone (the other category checks still
would, if applicable). Not a new gap this decision introduces, but
worth naming: a word-level whitelist is a blunt instrument, accepted
here because the words involved have no plausible harmful use in this
product's context.
