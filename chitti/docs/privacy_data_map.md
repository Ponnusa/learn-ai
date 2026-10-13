# Privacy data map — initial (Milestone 0)

Status: initial structure only. **No DPIA (Data Protection Impact
Assessment) has been performed.** Spec section 6 requires one to be
scoped before any child-facing pilot, with specialist privacy advice —
not something this document or a coding agent can complete alone.

## Memory categories and schema (spec section 6)

Five categories, none stored by default without explicit, per-category
handling:

1. **Conversation context** — temporary, in-memory only for the duration
   of a session. Never persisted as a durable memory record.
2. **Personal preferences** — optional, explicitly created (e.g. "favourite
   topic: dinosaurs"). Durable, reviewable, deletable.
3. **Reminders** — explicit tasks with date/time/expiry. Durable until
   expired or deleted.
4. **Learning state** — optional, created only when the feature is
   enabled by a parent.
5. **Daily summary** — created only when enabled and the applicable
   consent/controls are satisfied; not a default behavior.

Versioned record shape (implemented as a typed, logic-free dataclass in
`src/companion_robot/memory/` at this stage — see
`docs/decisions/0001-milestone-0-scope.md`):

| Field | Purpose |
|---|---|
| `id` | Stable identifier |
| `category` | One of the five categories above |
| `content` | The actual remembered fact/text |
| `created_at` / `updated_at` | Audit trail |
| `expires_at` | Enforces retention — `None` means indefinite, which should be rare and justified |
| `source` | Who/what created it (child, parent, system-inferred) — system-inferred memories need clear labeling since the spec requires *explicit* approval for memory creation |
| `consent_or_authorization_status` | Tracks whether the required consent/authorization for this specific record is in place |
| `retention_policy` | Which policy governs its expiry/deletion |
| `schema_version` | For safe migrations as the schema evolves |

## Data flows (to be filled in as backends are implemented)

| Data | Where it goes | Status |
|---|---|---|
| Raw audio | Not retained by default (spec section 2.1) | Policy decided; no implementation yet |
| Transcribed speech | Sent to whichever `LanguageModelBackend`/`SpeechToSpeechBackend` is selected | Backend undecided — see `architecture.md`'s comparison table; exact data recipient and residency to be documented here once chosen |
| Durable memories | Local SQLite only, at this stage | No cloud sync planned or built |
| Parent-control actions | Local only, at this stage | No remote admin surface built |

## Open items before any child-facing pilot (spec section 6)

- [ ] Legal basis for processing (consult specialist; likely consent from
  a parent/guardian for a child's data under GDPR + any Finnish-specific
  rules on the age of consent for information society services).
- [ ] Transparency information (privacy notice) for parents.
- [ ] Access controls for parent-facing data review/export/delete.
- [ ] Documented retention schedule per memory category.
- [ ] Formal DPIA screening decision (needed or not, and why).
- [ ] Confirmation of whether the chosen AI backend processes data inside
  or outside the EU, and under what terms.

None of these are resolved by this Milestone 0 pass — they're listed so
they aren't silently skipped later.
