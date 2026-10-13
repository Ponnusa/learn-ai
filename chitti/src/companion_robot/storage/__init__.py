"""Storage layer -- cross-cutting repository abstraction (spec section
10: SQLite first, with migrations and a repository abstraction). Used
by memory, reminders, and parent_controls rather than being a spec
service of its own.

sqlite.py: connect() -- a thin SQLite connection helper (row factory,
foreign keys on). migrations.py: run_migrations() -- idempotent
CREATE TABLE/INDEX statements, safe to re-run. companion_robot.memory.
repository is the first real consumer.
"""
