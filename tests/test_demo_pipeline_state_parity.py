"""Demo Home Pipeline state matches wiki coverage (#255).

@spec: 255-demo-pipeline-parity
@layer: unit
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki import build as build_mod
from llmwiki.synth.pipeline import _load_state, refresh_synth_pending, source_synth_is_done
from llmwiki.synth.state_backfill import (
    backfill_synth_state_from_wiki_pages,
    is_shipped_demo_vault,
)


def test_is_shipped_demo_vault_true_for_repo_demo(tmp_path: Path, monkeypatch) -> None:
    demo = tmp_path / "demo"
    demo.mkdir()
    monkeypatch.setattr(
        "llmwiki.synth.state_backfill.SHIPPED_DEMO_VAULT",
        demo,
    )
    assert is_shipped_demo_vault(demo) is True
    assert is_shipped_demo_vault(tmp_path / "other") is False


def test_backfill_stamps_mtime_when_wiki_page_covers_raw(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    raw_doc = vault / "raw" / "docs" / "guides" / "hello.md"
    raw_doc.parent.mkdir(parents=True)
    raw_doc.write_text("---\ntitle: Hello\nproject: guides\n---\n\nBody.\n", encoding="utf-8")
    wiki_page = vault / "wiki" / "sources" / "guides" / "hello.md"
    wiki_page.parent.mkdir(parents=True)
    wiki_page.write_text(
        "---\ntitle: Hello\ntype: source\n---\n\n## Summary\nDone.\n\n## Connections\n",
        encoding="utf-8",
    )
    state_path = vault / "llmwiki-state.json"
    rel = "docs::guides/hello.md"
    stale_mtime = 1.0
    state_path.write_text(
        json.dumps({"synth": {"files": {rel: stale_mtime}}}),
        encoding="utf-8",
    )
    raw_doc.touch()
    current = float(raw_doc.stat().st_mtime)
    assert current > stale_mtime + 1

    upserts, errors = backfill_synth_state_from_wiki_pages(vault=vault, dry_run=False)
    assert errors == []
    assert upserts == 1

    files = _load_state(state_path)
    assert source_synth_is_done(rel, files, current) is True


def test_demo_reconcile_refreshes_pipeline_after_stale_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shipped-demo reconcile must refresh pending/pipeline, not only ``synth.files``."""
    vault = tmp_path / "shipped-demo"
    vault.mkdir()
    (vault / "raw" / "sessions").mkdir(parents=True)
    raw_doc = vault / "raw" / "docs" / "guides" / "hello.md"
    raw_doc.parent.mkdir(parents=True, exist_ok=True)
    raw_doc.write_text("---\ntitle: Hello\nproject: guides\n---\n\nBody.\n", encoding="utf-8")
    wiki_page = vault / "wiki" / "sources" / "guides" / "hello.md"
    wiki_page.parent.mkdir(parents=True)
    wiki_page.write_text(
        "---\ntitle: Hello\ntype: source\n---\n\n## Summary\nDone.\n\n## Connections\n",
        encoding="utf-8",
    )
    rel = "docs::guides/hello.md"
    raw_doc.touch()
    stale_pipeline = {
        "stages": ["raw", "synthesized"],
        "rows": [
            {
                "css": "agent-docs",
                "id": "documents",
                "kind": "docs",
                "label": "Documents",
                "next_usd": 9.0,
                "on_disk": 1,
                "pending": 1,
                "raw": 1,
                "synthesized": 0,
            }
        ],
    }
    (vault / "llmwiki-state.json").write_text(
        json.dumps(
            {
                "synth": {
                    "files": {rel: 1.0},
                    "pending_total": 1,
                    "pending": [{"rel": rel, "is_doc": True, "project": "guides"}],
                    "pipeline": stale_pipeline,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("llmwiki.synth.state_backfill.SHIPPED_DEMO_VAULT", vault)
    monkeypatch.setattr(build_mod, "is_shipped_demo_vault", lambda root: root == vault)

    build_mod._reconcile_shipped_demo_synth_state(
        content_root=vault,
        raw_dir=vault / "raw",
        wiki_sources=vault / "wiki" / "sources",
    )

    after = json.loads((vault / "llmwiki-state.json").read_text(encoding="utf-8"))
    assert after["synth"]["pending_total"] == 0
    docs_row = next(
        r for r in after["synth"]["pipeline"]["rows"] if r.get("kind") == "docs"
    )
    assert docs_row["pending"] == 0
    assert docs_row["synthesized"] == 1


def test_build_reconcile_skips_non_shipped_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backfill_calls: list[Path] = []
    refresh_calls: list[Path] = []

    def _fake_backfill(*, vault: Path, dry_run: bool = False) -> tuple[int, list[str]]:
        backfill_calls.append(vault)
        return 0, []

    def _fake_refresh(**kwargs: object) -> dict[str, object]:
        refresh_calls.append(kwargs["state_file"])  # type: ignore[index]
        return {}

    monkeypatch.setattr(build_mod, "backfill_synth_state_from_wiki_pages", _fake_backfill)
    monkeypatch.setattr(build_mod, "refresh_synth_pending", _fake_refresh)
    monkeypatch.setattr(build_mod, "is_shipped_demo_vault", lambda root: False)
    build_mod._reconcile_shipped_demo_synth_state(
        content_root=tmp_path / "demo",
        raw_dir=tmp_path / "demo" / "raw",
        wiki_sources=tmp_path / "demo" / "wiki" / "sources",
    )
    assert backfill_calls == []
    assert refresh_calls == []


def test_refresh_pending_pending_docs_drop_after_backfill(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    raw_doc = vault / "raw" / "docs" / "guides" / "hello.md"
    raw_doc.parent.mkdir(parents=True)
    raw_doc.write_text("---\ntitle: Hello\nproject: guides\n---\n\nBody.\n", encoding="utf-8")
    wiki_page = vault / "wiki" / "sources" / "guides" / "hello.md"
    wiki_page.parent.mkdir(parents=True)
    wiki_page.write_text(
        "---\ntitle: Hello\ntype: source\n---\n\n## Summary\nDone.\n\n## Connections\n",
        encoding="utf-8",
    )
    rel = "docs::guides/hello.md"
    stale_mtime = 1.0
    (vault / "llmwiki-state.json").write_text(
        json.dumps({"synth": {"files": {rel: stale_mtime}}}),
        encoding="utf-8",
    )
    raw_doc.touch()

    refresh_synth_pending(
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "llmwiki-state.json",
    )
    before = json.loads((vault / "llmwiki-state.json").read_text(encoding="utf-8"))
    assert before["synth"]["pending_total"] >= 1

    backfill_synth_state_from_wiki_pages(vault=vault, dry_run=False)
    refresh_synth_pending(
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "llmwiki-state.json",
    )
    after = json.loads((vault / "llmwiki-state.json").read_text(encoding="utf-8"))
    assert after["synth"]["pending_total"] == 0
