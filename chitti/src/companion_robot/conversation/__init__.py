"""Conversation Service (spec section 3.2.D) -- Milestone 3.

Owns age-appropriate response policy, conversation context, tool
invocation through a strict allowlist with schema-validated arguments,
and AI identity transparency. Every model-authored tool call must be
validated here before anything executes -- no tool ever accepts or
`exec()`s model-generated code (spec section 9; same reasoning given to
the user for the earlier pygame-animation-generation question).

Per decision 0002, this package also owns the two capabilities that
replaced the Education Engine's original scope -- neither has a
correctness state to validate, so they're persona/context patterns, not
a separate graded engine:
- Teachable-Friend: a curious-peer persona the child teaches, grounded in
  the protégé effect. The Safety layer still screens anything this
  persona is about to echo back.
- Story Companion: answers questions about a story grounded only in that
  story's own transcript (held as session-only conversation context),
  never general model knowledge.

Nothing implemented yet.
"""
