# Compliance strategy — tracking, not an assessment

Status: every item below is **not yet assessed**. This file exists to
make sure nothing on the spec's list (section 14) is silently forgotten,
not to claim any of it has been evaluated. Regulatory classification is
explicitly an open task for qualified specialists, per the spec — a
coding agent does not determine legal compliance.

| Area | Spec reference | Status | Notes |
|---|---|---|---|
| EU toy-safety classification | Section 14 | Not yet assessed | Depends on final product classification as a toy or not |
| EN 71 standards / EN IEC 62115 | Section 14 | Not yet assessed | Applicable editions/scope not yet determined |
| Radio Equipment Directive + radio/EMC | Section 14 | Not yet assessed | Depends on final hardware (wireless modules, etc.) |
| RoHS / environmental | Section 14 | Not yet assessed | Depends on final hardware/BOM |
| GDPR + Finnish data-protection law | Section 14 | Not yet assessed | See `privacy_data_map.md` for the data-side groundwork; legal basis still needs specialist review |
| Cyber Resilience Act | Section 14 | Not yet assessed | Applicable dates/obligations not yet reviewed against this product's timeline |
| EU AI Act, incl. Article 50 transparency | Section 14 | Not yet assessed | Transparency obligations apply from 2 August 2026 — relevant given a conversational AI product; needs explicit review before that date regardless of launch timing |
| Battery/charger/electrical/labelling | Section 14 | Not yet assessed | Depends on final hardware (no battery subsystem decided yet) |
| Consumer protection / product liability / accessibility / language | Section 14 | Not yet assessed | — |
| EU Toy Safety Regulation (EU) 2025/2509 | Section 14 | Noted | Scheduled to apply from 1 August 2030, with some provisions earlier — track against actual launch date, don't assume it's irrelevant just because the date is distant |

## Regulatory register maintenance

Recheck every row before: (a) any child-facing pilot, (b) any commercial
launch milestone, (c) at least annually given how much of this is dated
(AI Act Article 50, Toy Safety Regulation phase-in). Record the date of
each recheck here.

| Date checked | Checked by | Outcome |
|---|---|---|
| — | — | Not yet performed |

## Official starting points (from the spec)

- Toy safety: https://single-market-economy.ec.europa.eu/sectors/toys/toy-safety_en
- Toy Safety Regulation: https://eur-lex.europa.eu/eli/reg/2025/2509/oj
- AI Act transparency: https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act
- Finnish Safety and Chemicals Agency: https://tukes.fi/en
- Finnish Data Protection Ombudsman: https://tietosuoja.fi/en/home

**No software architecture or checklist alone establishes compliance.**
Confirm actual requirements with the relevant authorities, a testing
laboratory, and legal/privacy specialists before any pilot or commercial
claim.
