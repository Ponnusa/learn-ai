"""Memory Service (spec section 3.2.E, 6).

schema.py: the typed, versioned MemoryRecord shape (Milestone 0).
repository.py: MemoryRepository -- SQLite-backed create/get/list/
update/delete/purge_expired, scoped per child_profile_id, refusing to
ever persist conversation_context. Supersedes pixel-ai/pixel_memory.py's
flat Markdown upsert/append file, which had no consent, retention,
expiry, deletion, or multi-child scoping. See docs/architecture.md's
"Memory Service" section for what's kept conceptually vs. rebuilt.

Not yet built: wiring this into a real conversation loop (waits for
companion_robot.conversation) or a parent-controls review/delete UI.
"""
