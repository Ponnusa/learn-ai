"""Safety layer (spec section 5).

Independent, tested application code that runs on every model response
before it's spoken or acted on -- not an extension of a personality
prompt. Supersedes pixel-ai/pixel_teaching_prompt.py's approach, which
puts equivalent behavior only in prompt text (see docs/risk_register.md
#1).

- checks.py: check_speech() screens any text Chitti is about to say
  (profanity, unsafe-content patterns, human impersonation, parent-
  secrecy, engagement manipulation) and decline_message() for a gentle
  refusal.
- tool_validation.py: validate_tool_call() enforces the tool allowlist
  + JSON-schema validation before companion_robot.conversation runs
  anything.

Deliberately NOT built here: detection of a child's own distress/abuse
disclosures in their speech -- a much higher-stakes problem needing
qualified child-safety input before even a placeholder is appropriate
(see checks.py's module docstring and docs/risk_register.md).
"""
