"""Storage layer -- cross-cutting repository abstraction (spec section
10: SQLite first, with migrations and a repository abstraction). Used
by memory, reminders, and parent_controls rather than being a spec
service of its own. Nothing implemented yet -- companion_robot.memory.
schema defines what it will eventually persist.
"""
