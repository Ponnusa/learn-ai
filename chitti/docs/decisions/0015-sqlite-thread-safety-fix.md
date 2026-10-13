# 0015 — SQLite connection thread-safety fix, found running the real server

Date: 2026-10-13
Status: Accepted

## Context

Preparing to test the Parent Controls web UI (decision 0014) on the
real Pi 1 B+ hardware, the same way Milestone 1 and Milestone 1's
dependencies were tested there. Before handing over test instructions,
this agent ran the actual Flask server locally (not just the test
client used for all 78 of decision 0014's unit tests) and hit a real
bug immediately.

## The bug

`curl http://127.0.0.1:5000/` returned `500`, with the server log
showing:

```
sqlite3.ProgrammingError: SQLite objects created in a thread can only
be used in that same thread. The object was created in thread id
16500 and this is thread id 7328.
```

Flask's dev server handles different requests on different threads;
`main()` opens the SQLite connection once, before the server starts,
on the main thread. Every subsequent request on a different thread
hit this. **This never showed up in decision 0014's 78 unit tests**
because Flask's test client runs synchronously in a single thread —
exactly the scenario the real server doesn't match. A clear example of
why "all tests pass" and "actually works" aren't the same claim.

## The fix, and a second bug found fixing the first one

`storage/sqlite.py`'s `connect()` now passes `check_same_thread=False`
and wraps the connection in `LockingConnection`, which serializes every
`execute()` call with a `threading.Lock`.

The first version of `LockingConnection` only held the lock around the
`execute()` call itself, not the subsequent `.fetchone()`/`.fetchall()`
a caller runs afterward — a regression test simulating concurrent
requests (`test_concurrent_access_from_multiple_threads_does_not_corrupt_state`)
caught this immediately: a thread's `.fetchone()` call returned `None`
for a row that should always exist, because another thread's statement
on the same underlying connection interfered with the first cursor's
unconsumed result set in the gap between lock release and the
unprotected fetch. Fixed by having `execute()` eagerly fetch all rows
*while still holding the lock*, returning a `_MaterializedResult` that
needs no further connection access — closing the actual race instead
of just moving it.

That test also needed its own fix: it used a read-then-write pattern
(`SELECT` then `UPDATE` as two separate `execute()` calls) to simulate
concurrent increments, which is a classic lost-update race regardless
of connection-level locking — a per-call lock was never going to make
that sequence atomic. Rewritten to use a single atomic statement
(`UPDATE counter SET value = value + 1`), the realistic pattern every
repository in this codebase actually uses, which the fix does protect
correctly (verified: 200 increments across 4 threads land on exactly
200, not fewer).

## Scope of the fix, stated honestly

`check_same_thread=False` + a Python-level lock is a deliberate, scoped
tradeoff for Chitti's actual usage pattern — one local device, one
admin, low-frequency requests — not a general solution for heavy
concurrent access. SQLite's own file-level locking already serializes
writes safely underneath this; the fix just stops Python's sqlite3
module from refusing cross-thread use outright, and the lock prevents
two threads' statements from interleaving mid-execute.

## Consequences

- 3 new regression tests (81 total passing) in
  `tests/unit/test_storage_sqlite.py`.
- Every existing repository (`memory/`, `reminders/`,
  `parent_controls/profiles.py`/`stories.py`/`auth.py`) benefits from
  this fix automatically — they all go through `storage.sqlite.connect()`.
- Re-ran the real server manually after the fix: 5 concurrent requests
  to `/setup`, all `200`, no errors in the log.

## Not yet done

- This was found and fixed on the dev sandbox, not yet re-verified on
  the Pi 1 B+ hardware — that's the next step.
