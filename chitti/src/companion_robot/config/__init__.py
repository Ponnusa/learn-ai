"""Config validation (spec section 9: validated configuration files and
environment-based secrets) -- extends pixel-ai/config.py's fail-fast
_require() pattern. No real required variables exist yet since no AI
backend has been chosen (see docs/architecture.md); loader.py's
require_env() is ready for Milestone 1+ to start using.
"""
