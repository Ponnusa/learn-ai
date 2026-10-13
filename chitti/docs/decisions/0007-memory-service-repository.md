# 0007 — Memory Service: SQLite-backed repository

Date: 2026-10-13
Status: Accepted

## Context

Second real feature after the Safety layer (decision 0006), per the
agreed build order. Hardware- and backend-independent, so fully
testable today against an in-memory SQLite database.

## What was built

- `storage/sqlite.py`: `connect()` — thin SQLite connection helper (row
  factory, foreign keys on).
- `storage/migrations.py`: `run_migrations()` — idempotent `memory_records`
  table + index creation, safe to re-run.
- `memory/repository.py`: `MemoryRepository` — `create`, `get`,
  `list_for_child`, `update_content`, `update_consent`, `delete`,
  `purge_expired`. Enforces three invariants beyond what the dataclass
  alone guarantees:
  1. `create()` raises if `category == CONVERSATION_CONTEXT` — turns the
     schema's documented "must never be persisted" rule into an actual
     enforced check, not just a comment.
  2. Every read/update/delete is scoped by `child_profile_id` in the SQL
     itself (`WHERE id = ? AND child_profile_id = ?`) — a record from
     one child's profile can never be fetched, edited, or deleted using
     another child's profile id.
  3. `get()`/`list_for_child()` exclude already-expired records without
     needing `purge_expired()` to have run first — "expired" behaves
     like "deleted" for every normal read.
- 10 new unit tests (41 total passing), including explicit cross-profile
  isolation checks and an expiry test proving records are hidden before
  any purge runs, plus a separate purge test proving only expired rows
  are actually removed.

## Consequences

- Risk register #4 updated from "schema stubbed only" to "mitigated in
  code," with the same caveat as decisions 0006: not yet wired into a
  real conversation loop or a parent-controls review/delete UI, since
  neither exists yet.

## Not yet done

- Wiring this into `conversation/` (next build steps: LLM backend +
  Finnish benchmark, then conversation logic) or a parent-controls UI
  for memory review/export/deletion (Milestone 5).
- Migration versioning beyond "create the table if missing" — fine for
  schema_version 1; revisit once a real schema change is needed.
