"""Conversation Service (spec section 3.2.D) -- Milestone 3.

Owns age-appropriate response policy, conversation context, tool
invocation through a strict allowlist with schema-validated arguments,
and AI identity transparency. Every model-authored tool call must be
validated here before anything executes -- no tool ever accepts or
`exec()`s model-generated code (spec section 9; same reasoning given to
the user for the earlier pygame-animation-generation question). Nothing
implemented yet.
"""
