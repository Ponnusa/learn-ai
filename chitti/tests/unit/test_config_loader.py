"""Unit tests for companion_robot.config.loader -- Milestone 1."""
import pytest

from companion_robot.config.loader import load_yaml_config, require_env


def test_require_env_raises_on_missing(monkeypatch):
    monkeypatch.delenv("CHITTI_TEST_VAR_XYZ", raising=False)
    with pytest.raises(RuntimeError, match="CHITTI_TEST_VAR_XYZ"):
        require_env("CHITTI_TEST_VAR_XYZ")


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("CHITTI_TEST_VAR_XYZ", "hello")
    assert require_env("CHITTI_TEST_VAR_XYZ") == "hello"


def test_load_yaml_config_reads_schema_version(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("schema_version: 1\nfoo: bar\n")
    data = load_yaml_config(config_file)
    assert data["schema_version"] == 1
    assert data["foo"] == "bar"


def test_load_yaml_config_rejects_missing_schema_version(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("foo: bar\n")
    with pytest.raises(RuntimeError, match="schema_version"):
        load_yaml_config(config_file)
