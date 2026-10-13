"""Education Engine (spec section 3.2.F, 7) -- NOT being built for the MVP.

Superseded by decision 0002 (docs/decisions/0002-teachable-friend-story-
companion-and-parent-ui.md): the deterministic, graded activity this
package was meant to own is replaced by Teachable-Friend and Story
Companion, both owned by companion_robot.conversation instead -- neither
has a correctness state to validate, so there's nothing for this package
to do. Kept as an empty package in case a graded activity is
reintroduced later; nothing is planned against it today.
"""
