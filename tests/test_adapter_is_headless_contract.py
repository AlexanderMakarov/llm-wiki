"""Contract: every registered adapter defines ``is_headless_session`` (#180)."""

from __future__ import annotations

from llmwiki.adapters import REGISTRY, discover_all


def test_every_registered_adapter_defines_is_headless_session() -> None:
    discover_all()
    missing: list[str] = []
    for name, cls in REGISTRY.items():
        if "is_headless_session" not in cls.__dict__:
            missing.append(f"{name} ({cls.__name__})")
    assert not missing, (
        "every REGISTRY adapter must define is_headless_session on the class "
        f"(not only inherit BaseAdapter default); missing: {missing}"
    )
