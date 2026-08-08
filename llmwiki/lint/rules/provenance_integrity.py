"""provenance_integrity — broken sources:/source_file: hops are errors (#122).

Report-only: guided repair belongs to ``doctor`` (#110).
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.lint import LintRule, register
from llmwiki.trace import TraceError, TraceHop, trace_page


def _has_provenance(meta: dict) -> bool:
    """True when the page records a downward provenance pointer."""
    sf = meta.get("source_file")
    if sf is not None and str(sf).strip().strip('"').strip("'"):
        return True
    sources = meta.get("sources")
    if sources is None:
        return False
    if isinstance(sources, list):
        return any(str(s).strip() for s in sources)
    return bool(str(sources).strip())


def _infer_vault(pages: dict) -> Path | None:
    """Resolve vault root from a ``load_pages`` path (…/vault/wiki/…)."""
    for page in pages.values():
        page_path = page.get("path")
        if not isinstance(page_path, Path):
            continue
        cur = page_path if page_path.is_dir() else page_path.parent
        for _ in range(8):
            if cur.name == "wiki":
                return cur.parent
            if cur == cur.parent:
                break
            cur = cur.parent
    return None


def _missing_message(hop: TraceHop) -> str:
    target = hop.location or hop.title or "(unknown)"
    if hop.role == "source":
        kind = "source summary"
    elif hop.role == "raw":
        kind = "raw file"
    else:
        kind = "provenance hop"
    return (
        f"missing {kind} '{target}' — "
        f"run doctor (#110) for guided repair"
    )


@register
class ProvenanceIntegrity(LintRule):
    """Broken ``sources:`` / ``source_file:`` hops are lint errors (#122).

    Walks each page that already carries provenance metadata via
    :func:`llmwiki.trace.trace_page`. Emits one ``error`` per missing hop.
    Pages without ``sources:`` / ``source_file:`` are skipped. Healing is
    out of scope here — see doctor (#110).
    """

    name = "provenance_integrity"
    severity = "error"

    def run(self, pages, *, llm_callback=None):
        del llm_callback  # unused — reserved / legacy kwarg
        issues: list[dict] = []
        if not pages:
            return issues

        vault = _infer_vault(pages)
        if vault is None:
            return issues

        for rel, page in pages.items():
            meta = page.get("meta") or {}
            if not _has_provenance(meta):
                continue
            path = page.get("path")
            if isinstance(path, Path):
                try:
                    locator = path.resolve().relative_to(vault.resolve()).as_posix()
                except ValueError:
                    locator = f"wiki/{rel.replace(chr(92), '/')}"
            else:
                locator = f"wiki/{rel.replace(chr(92), '/')}"
            try:
                result = trace_page(vault, locator)
            except TraceError:
                continue
            for hop in result.hops:
                if hop.status != "missing":
                    continue
                # Starting page is always resolvable when loaded via load_pages;
                # only downward hops (source / raw) are findings.
                if hop.role == "page":
                    continue
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": _missing_message(hop),
                })
        return issues
