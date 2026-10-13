# 0012 — Finnish benchmark: both backends measured

Date: 2026-10-13
Status: Accepted (data point recorded — not a final backend decision)

## Context

Decision 0011 recorded a partial run (OpenAI's key was truncated mid-
paste). A second, complete OpenAI key was provided — again pasted
directly into chat, same issue as before, logged in the same risk
register #17 rather than a new row. This record is the completed
comparison.

## Result

| | OpenAI (`gpt-4o-mini`) | Claude (`claude-haiku-4-5-20251001`) |
|---|---|---|
| Latency | 1.28s-2.14s | 1.15s-3.52s |
| Finnish fluency (first impression) | Reads naturally | Reads naturally |
| Teachable-Friend persona adherence | Flat — acknowledged the fact, asked nothing back | Strong — asked a genuine follow-up question on both relevant prompts |

Both backends stayed within or near the spec's ~1s first-response
target for short replies (greeting, maths), and both went well over it
for the story-generation request — expected given a short reply and a
multi-sentence story are different generation workloads, not
necessarily a backend-specific latency problem.

## What this is and isn't

This is a real first data point, not a final verdict:
- 4 prompts, one run each — no statistical confidence.
- Read by this agent, not a native Finnish speaker — fluency judgment
  is a first impression, not a confirmed assessment.
- Vendor child-directed-use policy (risk register #11) is a separate,
  still-unresolved gate that applies regardless of which backend wins
  on language quality — this benchmark doesn't touch that question at
  all.

**If forced to lean on this data point alone**: Claude's stronger
persona adherence matters more for Chitti's specific design (decision
0002's Teachable-Friend pivot) than OpenAI's modest latency edge on
short replies. But this is not being recorded as the backend decision
— that needs more runs, native-speaker review, and the policy check
above, per decision 0004's own stated criteria.

## Consequences

- Risk register #7 updated with the full comparison.
- Risk register #17 (credential exposure) updated to note the second
  key was also pasted directly, same issue as decision 0011 — no new
  row needed, same risk recurring.
