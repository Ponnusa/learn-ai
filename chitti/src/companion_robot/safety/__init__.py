"""Safety layer (spec section 5) -- Milestone 3.

Must be independent, tested application code that runs on every model
response before it's spoken or acted on -- not an extension of a
personality prompt. Supersedes pixel-ai/pixel_teaching_prompt.py's
approach, which puts equivalent behavior only in prompt text (see
docs/risk_register.md #1). Nothing implemented yet.
"""
