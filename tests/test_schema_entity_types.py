"""The entity-type taxonomy is gone; `entity_kind` is not (#102).

`entity_type` and `entity_kind` are one character apart. The taxonomy
was removed, while `entity_kind: ai-model` still drives the model index
and info-cards — these tests pin both halves of that distinction.
"""

from __future__ import annotations

import llmwiki.schema as schema
from llmwiki.schema import ENTITY_KIND_AI_MODEL, is_model_entity, parse_model_profile


def test_entity_type_taxonomy_is_gone():
    assert not hasattr(schema, "ENTITY_TYPES")
    assert not hasattr(schema, "validate_entity_type")


def test_entity_kind_ai_model_survives():
    assert ENTITY_KIND_AI_MODEL == "ai-model"


def test_is_model_entity_still_recognises_model_pages():
    assert is_model_entity({"type": "entity", "entity_kind": "ai-model"})
    assert not is_model_entity({"type": "entity", "entity_kind": "tool"})


def test_is_model_entity_ignores_entity_type():
    """A leftover `entity_type` value must not affect model detection."""
    assert is_model_entity(
        {"type": "entity", "entity_kind": "ai-model", "entity_type": "banana"}
    )


def test_parse_model_profile_still_parses():
    profile, warnings = parse_model_profile({
        "title": "Test Model",
        "provider": "ACME",
        "model": '{"context_window": 200000}',
    })
    assert profile["title"] == "Test Model"
    assert profile["provider"] == "ACME"
    assert profile["model"]["context_window"] == 200000
    assert warnings == []
