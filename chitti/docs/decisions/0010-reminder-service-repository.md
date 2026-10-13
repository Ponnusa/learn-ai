# 0010 — Reminder Service: SQLite-backed repository, DST-correct recurrence

Date: 2026-10-13
Status: Accepted

## Context

Fifth real feature, built while the live Finnish benchmark is still
pending `.env` setup. Chosen because it's Milestone 3 scope (spec
section 8) and fully independent of both the hardware and AI-backend
blockers.

## What was built

- `reminders/schema.py`: `ReminderRecord`, `ReminderSource`,
  `Recurrence` (daily/weekly). `is_alarm` folds alarms into this same
  schema per decision 0002, rather than a separate service.
- `reminders/repository.py`: `ReminderRepository` — `create`, `get`,
  `list_for_child`, `update_text`, `set_enabled`, `delete`, plus the
  two methods a scheduler loop actually needs: `due_reminders(now)` and
  `mark_fired(id, child_profile_id, fired_at)`. One-time reminders
  disable themselves after firing (spec's "expiration"); recurring ones
  advance to their next occurrence and stay enabled.
- `storage/migrations.py`: added the `reminders` table.
- 10 new unit tests (63 total passing).

## A real bug the DST test caught

Spec section 8 explicitly requires handling daylight-saving changes.
The first version of `create()`/`_row_to_record()` stored
`scheduled_at.isoformat()` directly — which bakes in the UTC offset
*at that instant* (e.g. `+02:00`) and discards which IANA zone it came
from. `datetime.fromisoformat()` on reload parses that back as a fixed
offset, not `zoneinfo.ZoneInfo("Europe/Helsinki")`. A unit test
constructing a daily 8am Europe/Helsinki reminder and firing it across
the real March 2026 spring-forward transition caught this immediately:
the "next occurrence" came back at the *wrong* UTC instant, because the
stale +02:00 offset was being reused instead of correctly resolving to
+03:00 for the post-transition date.

**Fix**: store the naive wall-clock time and the zone key (`Europe/
Helsinki`, or a fixed-offset string like `+02:00` for non-IANA tzinfo)
in two separate columns, and reconstruct a real `ZoneInfo` on every
load. This also surfaced a second, related issue: `due_reminders()`'s
original SQL-level `WHERE scheduled_at <= ?` string comparison stopped
being meaningful once `scheduled_at` was naive — fixed by filtering in
Python against reconstructed aware datetimes instead, which is correct
regardless of how many different zones different reminders use.

Separately: `zoneinfo.ZoneInfo` requires the `tzdata` package on
Windows (no system IANA database) — added as an explicit dependency so
this works consistently across dev machines and the eventual Pi
target, rather than relying on Raspberry Pi OS happening to ship it.

## Consequences

- This is exactly the kind of finding `/code-review` or careful testing
  is supposed to catch before it reaches production — recorded here in
  full rather than quietly fixed, since the reasoning (why naive
  timedelta math on a reloaded "aware" datetime is wrong) is worth
  keeping for whoever touches this code next.

## Not yet done

- The actual scheduler loop polling `due_reminders()` and triggering
  playback — waits for real audio I/O (Milestone 2 hardware).
- Natural-language date/time parsing with ambiguity confirmation (spec
  section 8) — a conversation-level concern, not built here.
- Device-restart persistence depends on the caller using a real SQLite
  file path in production, not `:memory:` — an app.py wiring concern
  for later, not enforced by the repository itself.
