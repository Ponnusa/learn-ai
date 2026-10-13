"""Unit tests for companion_robot.safety.tool_validation."""
from companion_robot.safety.tool_validation import validate_tool_call

_ALLOWED_TOOLS = {
    "show_formula": {
        "type": "object",
        "properties": {"latex": {"type": "string"}},
        "required": ["latex"],
        "additionalProperties": False,
    },
}


def test_rejects_tool_not_in_allowlist():
    verdict = validate_tool_call("run_shell_command", {"cmd": "rm -rf /"}, _ALLOWED_TOOLS)
    assert verdict.allowed is False
    assert "not in the tool allowlist" in verdict.reason


def test_allows_valid_arguments_for_allowed_tool():
    verdict = validate_tool_call("show_formula", {"latex": "2+2=4"}, _ALLOWED_TOOLS)
    assert verdict.allowed is True


def test_rejects_missing_required_argument():
    verdict = validate_tool_call("show_formula", {}, _ALLOWED_TOOLS)
    assert verdict.allowed is False
    assert verdict.reason is not None


def test_rejects_unexpected_extra_argument():
    verdict = validate_tool_call(
        "show_formula", {"latex": "2+2=4", "extra": "sneaky"}, _ALLOWED_TOOLS
    )
    assert verdict.allowed is False


def test_rejects_wrong_argument_type():
    verdict = validate_tool_call("show_formula", {"latex": 1234}, _ALLOWED_TOOLS)
    assert verdict.allowed is False
