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
_DIR_KINDS = {v: k for k, v in _KIND_DIRS.items()}

#: Asks for one line per name. Deliberately batched: cost must scale with the
#: candidate count (a few dozen short strings), never with the corpus.
_CLASSIFY_PROMPT = """\
Classify each name below as either an entity or a concept.

An entity is a concrete, nameable thing: a person, company, product, tool,
library, service, or project. A concept is an idea, method, pattern,
framework, or practice.

Answer with one line per name, formatted exactly as:

    <name>: entity
    <name>: concept

Do not add commentary. Names to classify:

{body}
"""


def classify_names(names: list[str], backend) -> dict[str, str]:
    """Ask ``backend`` to sort ``names`` into entities and concepts.

    Best-effort by contract. An unreachable backend, a refusal, or unparseable
    output all yield ``{}`` — callers fall back to an ``unknown`` entity stub.
    Harvesting must never be blocked by classification, because the vault that
    most needs harvesting is the one whose backend has nothing left to do.
    """
    if backend is None or not names:
        return {}
    try:
        if not backend.is_available():
            return {}
        reply = backend.synthesize_source_page(
            "\n".join(names),
            {"slug": "candidate-classification"},
            _CLASSIFY_PROMPT,
        )
    except Exception:  # noqa: BLE001 - a classifier failure must not abort
        return {}

    wanted = {name.lower(): name for name in names}
    kinds: dict[str, str] = {}
    for line in (reply or "").splitlines():
        raw_name, sep, raw_kind = line.rpartition(":")
        if not sep:
            continue
        kind = raw_kind.strip().lower()
        # Only names we asked about: a backend that invents targets must not
        # be able to smuggle them past the threshold check.
        original = wanted.get(raw_name.strip().lower())
        if original is not None and kind in _KIND_DIRS:
            kinds[original] = kind
    return kinds


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
        # A stub the reviewer already refiled keeps its folder. Re-classifying
        # every run would fight the human the queue exists to serve.
        subdir = _existing_subdir(wiki_dir, target.name)
        if subdir is None:
            subdir = _KIND_DIRS.get(kinds.get(target.name, "entity"), "entities")
        kind = _DIR_KINDS.get(subdir, "entity")
        path = wiki_dir / "candidates" / subdir / f"{target.name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _preserved_body(path, target.name)
        path.write_text(
            _stub_text(target, kind, today=today, body=body), encoding="utf-8"
        )
        written.append(path)
    return written


def _existing_subdir(wiki_dir: Path, name: str) -> str | None:
    """Return the candidates subfolder already holding ``name``, if any."""
    for subdir in _KIND_DIRS.values():
        if (wiki_dir / "candidates" / subdir / f"{name}.md").is_file():
            return subdir
    return None


#: Thresholds shown alongside the chosen one, so an operator can see the shape
#: of their own backlog instead of guessing at a number.
_REPORTED_THRESHOLDS = (10, 5, 3, 2, 1)


def summarize_backlog(
    wiki_dir: Path,
    *,
    min_refs: int = DEFAULT_MIN_REFS,
) -> dict:
    """Describe the candidate backlog without writing anything.

    ``--estimate`` has two lists to preview: sources still to synthesize, and
    candidates still to generate. Reporting a single count at one threshold
    hides whether that threshold was a sensible choice, so this returns the
    distribution across neighbouring values too.
    """
    if not (wiki_dir / "sources").is_dir():
        return {
            "min_refs": min_refs,
            "candidates": 0,
            "broken_targets": 0,
            "broken_links": 0,
            "covered_links": 0,
            "distribution": dict.fromkeys(_REPORTED_THRESHOLDS, 0),
        }

    every = harvest_targets(wiki_dir, min_refs=1)
    selected = [t for t in every if t.refs >= min_refs]
    total_links = sum(t.refs for t in every)
    return {
        "min_refs": min_refs,
        "candidates": len(selected),
        "broken_targets": len(every),
        "broken_links": total_links,
        "covered_links": sum(t.refs for t in selected),
        "distribution": {
            n: sum(1 for t in every if t.refs >= n) for n in _REPORTED_THRESHOLDS
        },
    }
