"""Lazy per-lint-run corpus scan shared by findability rules (#197).

One :class:`SearchContext` per ``run_lint`` call. The first rule that needs
pages triggers :func:`scan_corpus`; later rules reuse the same
:class:`~llmwiki.search.corpus.CorpusScan`. No module-level cache — lifetime
is bounded by the lint run that holds the options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from llmwiki.search.corpus import CorpusScan, scan_corpus


@dataclass
class SearchContext:
    """Vault-rooted scan holder. ``content_root`` is the vault root (parent of ``wiki/``)."""

    content_root: Path
    _scan: CorpusScan | None = field(default=None, init=False, repr=False)

    def corpus(self) -> CorpusScan:
        """Return the scan, running :func:`scan_corpus` at most once."""
        if self._scan is None:
            root = self.content_root.resolve()
            wiki = root / "wiki"
            roots: list[Path] = [wiki]
            sessions = root / "raw" / "sessions"
            if sessions.is_dir():
                roots.append(sessions)
            self._scan = scan_corpus(
                roots,
                content_root=root,
                cold_storage_root=wiki if wiki.is_dir() else None,
            )
        return self._scan
