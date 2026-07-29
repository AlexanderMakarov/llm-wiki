"""Tests for adapter config validation (v1.0, #177)."""

from __future__ import annotations

from llmwiki.adapter_config import (
    ADAPTER_SCHEMAS,
    apply_defaults,
    enabled_adapters,
    is_adapter_enabled,
    validate_adapter_config,
    validate_all_adapters,
)

# ─── Schemas ───────────────────────────────────────────────────────────


def test_adapter_schemas_defined():
    assert set(ADAPTER_SCHEMAS.keys()) == {"web_clipper"}


def test_every_schema_has_required_fields():
    for _name, schema in ADAPTER_SCHEMAS.items():
        assert "required_if_enabled" in schema
        assert "defaults" in schema
        assert "types" in schema


# ─── validate_adapter_config ─────────────────────────────────────────


def test_disabled_adapter_always_valid():
    config = {"web_clipper": {"enabled": False}}
    errors = validate_adapter_config(config, "web_clipper")
    assert errors == []


def test_missing_section_valid():
    """No config for an adapter is treated as disabled."""
    errors = validate_adapter_config({}, "web_clipper")
    assert errors == []


def test_enabled_web_clipper_without_watch_dir():
    config = {"web_clipper": {"enabled": True}}
    errors = validate_adapter_config(config, "web_clipper")
    assert len(errors) == 1
    assert "watch_dir" in errors[0]


def test_fully_configured_web_clipper_valid():
    config = {
        "web_clipper": {
            "enabled": True,
            "watch_dir": "/some/path",
        }
    }
    errors = validate_adapter_config(config, "web_clipper")
    assert errors == []


def test_wrong_type_flagged():
    config = {
        "web_clipper": {
            "enabled": True,
            "watch_dir": "/some/path",
            "extensions": ".md",  # should be list
        }
    }
    errors = validate_adapter_config(config, "web_clipper")
    assert any("extensions" in e and "list" in e for e in errors)


def test_unknown_adapter():
    errors = validate_adapter_config({}, "bogus")
    assert len(errors) == 1
    assert "unknown adapter" in errors[0]


def test_non_dict_section_flagged():
    config = {"web_clipper": "not a dict"}
    errors = validate_adapter_config(config, "web_clipper")
    assert len(errors) == 1
    assert "JSON object" in errors[0]


# ─── is_adapter_enabled ───────────────────────────────────────────────


def test_is_enabled_true():
    assert is_adapter_enabled({"web_clipper": {"enabled": True}}, "web_clipper") is True


def test_is_enabled_false():
    assert is_adapter_enabled({"web_clipper": {"enabled": False}}, "web_clipper") is False


def test_is_enabled_missing():
    assert is_adapter_enabled({}, "web_clipper") is False


def test_is_enabled_non_dict():
    assert is_adapter_enabled({"web_clipper": "str"}, "web_clipper") is False


# ─── enabled_adapters ─────────────────────────────────────────────────


def test_enabled_adapters_empty():
    assert enabled_adapters({}) == []


def test_enabled_adapters_some():
    config = {
        "web_clipper": {"enabled": True},
    }
    result = enabled_adapters(config)
    assert set(result) == {"web_clipper"}


# ─── apply_defaults ───────────────────────────────────────────────────


def test_apply_defaults_fills_missing():
    config = {"web_clipper": {"enabled": True, "watch_dir": "/foo"}}
    result = apply_defaults(config, "web_clipper")
    assert result["extensions"] == [".md"]  # default applied
    assert result["auto_queue"] is True  # default applied


def test_apply_defaults_preserves_user_values():
    config = {"web_clipper": {"enabled": True, "extensions": [".txt"]}}
    result = apply_defaults(config, "web_clipper")
    assert result["extensions"] == [".txt"]  # not overwritten


def test_apply_defaults_unknown_adapter():
    result = apply_defaults({}, "unknown")
    assert result == {}


# ─── validate_all_adapters ────────────────────────────────────────────


def test_validate_all_returns_entries_for_every_adapter():
    result = validate_all_adapters({})
    assert set(result.keys()) == {"web_clipper"}
    assert all(errors == [] for errors in result.values())


def test_validate_all_flags_misconfigured():
    config = {
        "web_clipper": {"enabled": True},  # missing watch_dir
    }
    result = validate_all_adapters(config)
    assert result["web_clipper"]  # errors
