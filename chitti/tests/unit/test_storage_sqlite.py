"""Unit tests for companion_robot.storage.sqlite.connect() -- the
check_same_thread=False + LockingConnection fix from decision 0014's
real-server smoke test.
"""
import threading

from companion_robot.storage.sqlite import connect


def test_connection_usable_from_a_different_thread_than_it_was_created_in():
    """Reproduces the exact bug found running the Parent Controls web
    UI for real: Flask's dev server handles different requests on
    different threads, but the connection is created once up front.
    Plain sqlite3.connect() raises ProgrammingError in this scenario --
    this is the regression test for the fix."""
    conn = connect(":memory:")  # created on the test's own thread

    results = {}

    def _use_from_other_thread():
        try:
            conn.execute("SELECT 1").fetchone()
            results["ok"] = True
        except Exception as exc:  # pragma: no cover - failure path
            results["error"] = exc

    thread = threading.Thread(target=_use_from_other_thread)
    thread.start()
    thread.join()

    assert results.get("ok") is True
    assert "error" not in results


def test_execute_and_commit_still_work_normally():
    conn = connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.execute("INSERT INTO t (id) VALUES (1)")
    conn.commit()

    row = conn.execute("SELECT id FROM t").fetchone()
    assert row["id"] == 1


def test_concurrent_single_statement_updates_from_multiple_threads_do_not_corrupt_state():
    """Each execute() call is atomic under the lock -- proven here with
    a single-statement increment (UPDATE ... SET value = value + 1),
    the realistic pattern this codebase's repositories actually use.
    A separate, non-atomic read-then-write across two execute() calls
    would still race (classic lost-update), but that's an application-
    level transaction concern, not something a per-call lock claims to
    solve -- not tested here since nothing in this codebase does that.
    """
    conn = connect(":memory:")
    conn.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, value INTEGER)")
    conn.execute("INSERT INTO counter (id, value) VALUES (1, 0)")
    conn.commit()

    def _increment_many_times():
        for _ in range(50):
            conn.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
            conn.commit()

    threads = [threading.Thread(target=_increment_many_times) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = conn.execute("SELECT value FROM counter WHERE id = 1").fetchone()["value"]
    assert final == 200
