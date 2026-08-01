"""Harvest entity/concept candidates from synthesized source pages (#90).

``synthesize`` writes ``wiki/sources/`` pages whose ``## Connections`` blocks
name the entities and concepts the LLM identified. Nothing materialized those
names, so the links dangle and the trusted layer stays empty.

Harvesting closes that loop deterministically: the extraction already happened
during synthesis, so this is a pass over ``wiki/sources/`` — never over
``raw/`` — and costs no synthesis calls.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from llmwiki.lint import WIKILINK_RE
from llmwiki.lint.rules.link_integrity import _norm_slug

#: Default significance threshold. Matches the Lint Workflow's definition of a
#: missing entity page ("mentioned in 3+ source pages") so the producer and the
#: checker that reports on it cannot disagree.
DEFAULT_MIN_REFS = 3


@dataclass(frozen=True)
class HarvestedTarget:
    """A wikilink target that cleared the significance threshold."""

    name: str
    #: Source pages that link to it, relative to ``wiki/``. Counted once per
    #: page — a page naming the target repeatedly still votes once.
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def refs(self) -> int:
        return len(self.sources)


def harvest_targets(
    wiki_dir: Path,
    *,
    min_refs: int = DEFAULT_MIN_REFS,
) -> list[HarvestedTarget]:
    """Return unresolved wikilink targets named by ``min_refs``+ source pages."""
    # A pending candidate does not resolve its own inbound links — if it did,
    # the first run would make every later run a no-op and evidence could
    # never be refreshed.
    candidates_root = wiki_dir / "candidates"
    resolved = {
        _norm_slug(p.stem)
        for p in wiki_dir.rglob("*.md")
        if not p.is_relative_to(candidates_root)
    }

    by_target: dict[str, set[str]] = defaultdict(set)
    sources_dir = wiki_dir / "sources"
    for page in sorted(sources_dir.rglob("*.md")):
        rel = page.relative_to(wiki_dir).as_posix()
        text = page.read_text(encoding="utf-8", errors="replace")
        # set() per page: repeated mentions in one document are one signal.
        for raw in set(WIKILINK_RE.findall(text)):
            name = raw.split("#")[0].strip()
            if name:
                by_target[name].add(rel)

    return [
        HarvestedTarget(name=name, sources=tuple(sorted(pages)))
        for name, pages in sorted(by_target.items())
        if len(pages) >= min_refs and _norm_slug(name) not in resolved
    ]


#: Maps harvested names to ``"entity"`` or ``"concept"``. Names it omits fall
#: back to an entity stub tagged ``unknown`` — misfiling is recoverable by a
#: reviewer, silently dropping a target is not.
Classifier = Callable[[list[str]], dict[str, str]]

_KIND_DIRS = {"entity": "entities", "concept": "concepts"}


_CONNECTIONS_HEADING = "## Connections"


def _preserved_body(path: Path, name: str) -> str:
    """Return an existing stub's prose — everything above ``## Connections``.

    Harvest owns the frontmatter and the evidence list; a reviewer owns
    everything between them. Re-running must refresh the first without
    touching the second.
    """
    if not path.is_file():
        return f"# {name}\n\n## Key Facts\n\n"
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("---\n"):
        _, _, text = text[4:].partition("\n---\n")
    body, sep, _ = text.partition(_CONNECTIONS_HEADING)
    return body.lstrip("\n") if sep else text.strip("\n") + "\n\n"


def _stub_text(
    target: HarvestedTarget,
    kind: str,
    *,
    today: str,
    body: str,
) -> str:
    """Render a candidate stub: frontmatter, reviewer prose, evidence."""
    slugs = [Path(rel).stem for rel in target.sources]
    evidence = "\n".join(f"- [[{slug}]]" for slug in slugs)
    entity_type = "entity_type: unknown\n" if kind == "entity" else ""
    sources = ", ".join(slugs)
    return (
        f"---\n"
        f'title: "{target.name}"\n'
        f"type: {kind}\n"
        f"status: candidate\n"
        f"{entity_type}"
        f"tags: []\n"
        f"sources: [{sources}]\n"
        f"last_updated: {today}\n"
        f"---\n\n"
        f"{body}"
        f"{_CONNECTIONS_HEADING}\n\n"
        f"Named by {target.refs} source page(s), which is the evidence that\n"
        f"justified this candidate:\n\n"
        f"{evidence}\n"
    )


def write_stubs(
    wiki_dir: Path,
    targets: Iterable[HarvestedTarget],
    *,
    classify: Classifier | None = None,
) -> list[Path]:
    """Write harvested targets as ``status: candidate`` stubs.

    Stubs land under ``wiki/candidates/`` only. Promotion into the trusted
    tree stays a human-or-agent decision via ``llmwiki candidates promote``.
    """
    targets = list(targets)
    kinds = classify([t.name for t in targets]) if classify else {}
    today = datetime.now(UTC).date().isoformat()

    written: list[Path] = []
    for target in targets:
        kind = kinds.get(target.name, "entity")
        subdir = _KIND_DIRS.get(kind, "entities")
        path = wiki_dir / "candidates" / subdir / f"{target.name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _preserved_body(path, target.name)
        path.write_text(
            _stub_text(target, kind, today=today, body=body), encoding="utf-8"
        )
        written.append(path)
    return written
