"""Verbal-communication engagement tracking (decision 0023).

Behavioral telemetry only -- turn count and word count per session,
written once at session end. Deliberately not a correctness or
proficiency evaluator: the goal is helping a child (especially one
hesitant to speak) build speaking confidence, not grading what they
say. No LLM is involved in computing or interpreting these numbers,
and nothing here is ever spoken back to the child as a score.

schema.py: EngagementSession, EngagementMode.
repository.py: EngagementRepository -- create/list_for_child/
latest_for_child.
"""
