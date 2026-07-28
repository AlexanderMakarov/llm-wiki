"""stub_source_pages — flag machine-generated filler in wiki/sources (#24)."""

from __future__ import annotations

from llmwiki.lint import LintRule, register
from llmwiki.synth.pipeline import _is_stub_page


@register
class StubSourcePages(LintRule):
    """Flag stub / sentinel pages under ``wiki/sources/`` (#24).

    A source page whose body is an agent-delegate pending sentinel
    (``<!-- llmwiki-pending: … -->``) or the dummy backend's canned
    ``Auto-synthesized from session`` body renders on the site as if it
    were a summary while carrying no synthesis. This rule walks the wiki
    from the page side and reports every such page, including the ones
    backlog discovery cannot reach — it iterates raw files and asks whether
    each source is synthesized, so it never visits:

      - a stub whose raw source file is gone (pruned, deleted, renamed),
      - a stub superseded by a real page filed under a different name
        (``discover_stub_source_keys()`` drops that source from the backlog
        so the real page wins, leaving the stub behind),
      - a stub with no ``source_file:`` frontmatter key to match on
        *and* no live raw source deriving to its path (either alone
        still reaches the stub, so both must hold — overlapping the
        pruned/renamed-raw case above).
    """

    name = "stub_source_pages"
    severity = "warning"

    _SOURCES_PREFIX = "sources/"

    def run(self, pages, *, llm_callback=None):

        issues = []
        for rel, page in pages.items():
            rel_posix = rel.replace("\\", "/")
            if not rel_posix.startswith(self._SOURCES_PREFIX):
                continue
            if not _is_stub_page(page["body"]):
                continue
            issues.append({
                "rule": self.name,
                "severity": self.severity,
                "page": rel,
                "message": (
                    "source page is machine-generated filler (pending sentinel "
                    "or dummy stub) — re-run `llmwiki synthesize` with a real "
                    "backend (claude / ollama) to fill it"
                ),
            })
        return issues
