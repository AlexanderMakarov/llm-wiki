"""source_file index: correctness + O(1) lookups vs N full scans (#122)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import trace
from llmwiki._frontmatter import parse_frontmatter
from llmwiki.trace import build_source_file_index, find_wiki_source_for_raw


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _naive_find_wiki_source_for_raw(vault: Path, raw_rel: str) -> Path | None:
    """Reference full scan (pre-index behaviour) for correctness checks."""
    vault_root = vault.expanduser().resolve()
    target = raw_rel.replace("\\", "/").strip().lstrip("/")
    if not target or ".." in Path(target).parts:
        return None
    sources_dir = vault_root / "wiki" / "sources"
    if not sources_dir.is_dir():
        return None
    for path in sorted(sources_dir.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        try:
            meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        value = meta.get("source_file")
        if value is None or isinstance(value, list | dict):
            claimed = ""
        else:
            claimed = str(value).strip().strip('"').strip("'")
        claimed = claimed.replace("\\", "/").lstrip("/")
        if claimed == target:
            return path.resolve()
    return None


@pytest.fixture(autouse=True)
def _clear_source_file_index_cache():
    trace._SOURCE_FILE_INDEX_CACHE.clear()
    yield
    trace._SOURCE_FILE_INDEX_CACHE.clear()


def _vault_with_n_sources(tmp_path: Path, n: int) -> Path:
    vault = tmp_path / "vault"
    for i in range(n):
        raw_name = f"2026-01-01T12-{i:02d}-demo-s{i:03d}.md"
        raw_rel = f"raw/sessions/{raw_name}"
        _write(vault / raw_rel, f"---\ntitle: raw-{i}\n---\n\nbody\n")
        _write(
            vault / "wiki" / "sources" / f"s{i:03d}.md",
            (
                f'---\ntitle: "Source {i}"\ntype: source\n'
                f"project: demo\nsource_file: {raw_rel}\n---\n\n## Summary\n"
            ),
        )
    return vault


def test_index_lookup_matches_full_scan(tmp_path: Path):
    vault = _vault_with_n_sources(tmp_path, 12)
    index = build_source_file_index(vault)
    assert len(index) == 12
    for i in range(12):
        raw_rel = f"raw/sessions/2026-01-01T12-{i:02d}-demo-s{i:03d}.md"
        via_index = find_wiki_source_for_raw(vault, raw_rel, index=index)
        via_scan = _naive_find_wiki_source_for_raw(vault, raw_rel)
        assert via_index is not None
        assert via_scan is not None
        assert via_index.resolve() == via_scan.resolve()
        assert index[raw_rel].resolve() == via_scan.resolve()
    assert find_wiki_source_for_raw(vault, "raw/sessions/missing.md", index=index) is None


def test_one_index_then_n_lookups_far_cheaper_than_n_scans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    n = 50
    vault = _vault_with_n_sources(tmp_path, n)
    raw_rels = [
        f"raw/sessions/2026-01-01T12-{i:02d}-demo-s{i:03d}.md" for i in range(n)
    ]

    source_reads: list[Path] = []
    orig_read_text = Path.read_text

    def counting_read_text(self: Path, *args, **kwargs):
        # Count wiki source frontmatter reads only (not raw transcript bodies).
        try:
            parts = self.resolve().parts
        except OSError:
            parts = self.parts
        if (
            self.suffix == ".md"
            and "wiki" in parts
            and "sources" in parts
            and not self.name.startswith("_")
        ):
            source_reads.append(self)
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    # Baseline: N independent cold finds (each rebuilds a full index).
    source_reads.clear()
    for raw_rel in raw_rels:
        trace._SOURCE_FILE_INDEX_CACHE.clear()
        found = find_wiki_source_for_raw(vault, raw_rel)
        assert found is not None
    cold_reads = len(source_reads)

    # Fixed path: one index build, then N lookups with that index.
    source_reads.clear()
    trace._SOURCE_FILE_INDEX_CACHE.clear()
    index = build_source_file_index(vault)
    index_build_reads = len(source_reads)
    source_reads.clear()
    for raw_rel in raw_rels:
        found = find_wiki_source_for_raw(vault, raw_rel, index=index)
        assert found is not None
    lookup_reads = len(source_reads)

    assert index_build_reads == n
    assert lookup_reads == 0
    # N cold rebuilds each scan all N sources → ~n² reads.
    assert cold_reads >= n * n
    assert cold_reads >= index_build_reads * n
