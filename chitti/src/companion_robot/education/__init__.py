"""Education Engine (spec section 3.2.F, 7) -- mostly NOT built for the
MVP. Superseded by decision 0002
(docs/decisions/0002-teachable-friend-story-companion-and-parent-ui.md):
the deterministic, graded activity this package was meant to own is
replaced by Teachable-Friend and Story Companion, owned by
companion_robot.conversation instead.

math_check.py (decision 0024) is the one deliberate exception: simple
addition has a real, cheap-to-verify answer, unlike grammar or
pronunciation, so it's worth a small deterministic checker even though
no broader graded engine exists. Everything else spec section 7
describes (a full curriculum, proficiency tracking across subjects)
remains explicitly not built.
"""
