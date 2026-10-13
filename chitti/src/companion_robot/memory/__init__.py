"""Memory Service (spec section 3.2.E, 6) -- Milestone 3.

Typed, versioned record schema only at Milestone 0 (schema.py). No
storage, review, deletion, or retention logic exists yet -- supersedes
pixel-ai/pixel_memory.py's flat Markdown upsert/append file, which has
none of those either. See docs/architecture.md's "Memory Service"
section for what's kept conceptually vs. rebuilt.
"""
