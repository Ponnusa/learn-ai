"""Tool-call allowlist + schema validation (spec section 9). Never
executes anything itself -- just says yes/no, so companion_robot.
conversation can refuse a tool call before any handler runs.

This is the same reasoning already given when the product owner asked
whether an LLM could write pygame animation code on the fly: no tool
here ever accepts or `exec()`s model-authored code. Every capability is
a fixed, pre-registered function with a typed, validated argument
schema -- the model can only pick from the allowlist and fill in
already-defined parameters, never author new behavior.
"""
from dataclasses import dataclass

import jsonschema


@dataclass
class ToolCallVerdict:
    allowed: bool
    reason: str | None = None


def validate_tool_call(
    tool_name: str, arguments: dict, allowed_tools: dict[str, dict]
) -> ToolCallVerdict:
    """allowed_tools maps a registered tool name to the JSON schema its
    arguments must satisfy. A tool name not in this mapping is refused
    outright -- there is no fallback, default, or wildcard tool."""
    schema = allowed_tools.get(tool_name)
    if schema is None:
        return ToolCallVerdict(
            allowed=False, reason=f"{tool_name!r} is not in the tool allowlist"
        )

    try:
        jsonschema.validate(instance=arguments, schema=schema)
    except jsonschema.ValidationError as exc:
        return ToolCallVerdict(
            allowed=False, reason=f"arguments failed schema validation: {exc.message}"
        )

    return ToolCallVerdict(allowed=True)
