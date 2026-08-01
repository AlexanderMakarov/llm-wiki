"""Harvest entity/concept candidates from synthesized source pages (#90).

``synthesize`` writes ``wiki/sources/`` pages whose ``## Connections`` blocks
name the entities and concepts the LLM identified. Nothing materialized those
names, so the links dangle and the trusted layer stays empty.

Harvesting closes that loop deterministically: the extraction already happened
during synthesis, so this is a pass over ``wiki/sources/`` — never over
``raw/`` — and costs no synthesis calls.
"""

from __future__ import annotations

import sys
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


#: Names per classification call. One prompt listing every harvested name
#: would, at a low ``--min-refs`` on a large vault, ask for hundreds of output
#: lines — and a reply truncated at the limit loses the tail silently. Chunking
#: bounds each call while keeping total cost proportional to the candidate
#: count rather than the corpus.
DEFAULT_CLASSIFY_BATCH = 100


def classify_names(
    names: list[str],
    backend,
    *,
    batch_size: int = DEFAULT_CLASSIFY_BATCH,
    retry_missing: bool = True,
) -> dict[str, str]:
    """Ask ``backend`` to sort ``names`` into entities and concepts.

    Returns only names the backend classified as ``entity`` or ``concept``.
    Omitted / unparseable names are absent from the result — callers decide
    whether to fail closed (``run_harvest`` default) or file as ``unknown``
    (``--allow-unclassified``).

    When ``retry_missing`` is true (default), names absent from the first
    reply get one small follow-up call before giving up (#90). Truncation and
    flaky backends often omit a short tail; a second pass recovers those
    without teaching ``unknown`` as the happy path.
    """
    if backend is None or not names:
        return {}
    try:
        if not backend.is_available():
            return {}
    except Exception:  # noqa: BLE001 - treat a broken probe as unavailable
        return {}

    kinds: dict[str, str] = {}
    kinds.update(_classify_chunks(names, backend, batch_size=batch_size))
    if retry_missing:
        missing = [name for name in names if name not in kinds]
        if missing:
            kinds.update(_classify_chunks(missing, backend, batch_size=batch_size))
    return kinds


def _classify_chunks(
    names: list[str],
    backend,
    *,
    batch_size: int,
) -> dict[str, str]:
    """One pass of batched classify calls; skips chunks that raise."""
    kinds: dict[str, str] = {}
    size = max(1, batch_size)
    for start in range(0, len(names), size):
        chunk = names[start : start + size]
        try:
            reply = backend.synthesize_source_page(
                "\n".join(chunk),
                {"slug": "candidate-classification"},
                _CLASSIFY_PROMPT,
            )
        except Exception:  # noqa: BLE001 - one bad chunk must not lose the rest
            continue
        kinds.update(_parse_classification(reply, chunk))
    return kinds


def _parse_classification(reply: str | None, asked: list[str]) -> dict[str, str]:
    """Extract ``name: kind`` lines, keeping only names we asked about."""
    wanted = {name.lower(): name for name in asked}
    kinds: dict[str, str] = {}
    for line in (reply or "").splitlines():
        raw_name, sep, raw_kind = line.rpartition(":")
        if not sep:
            continue
        kind = raw_kind.strip().lower()
        # A backend that invents targets must not be able to smuggle them
        # past the threshold check.
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
    # A stub that already exists keeps its folder — the reviewer may have
    # refiled it, and that decision outranks the model's. Resolve those first
    # so classification is only asked about genuinely new names: re-runs
    # otherwise pay for an answer they then discard.
    filed = {t.name: _existing_subdir(wiki_dir, t.name) for t in targets}
    unfiled = [name for name, subdir in filed.items() if subdir is None]
    kinds = classify(unfiled) if classify else {}
    today = datetime.now(UTC).date().isoformat()

    written: list[Path] = []
    for target in targets:
        subdir = filed[target.name]
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


def unfiled_names(wiki_dir: Path, targets: Iterable[HarvestedTarget]) -> list[str]:
    """Names with no candidate stub yet — the only ones worth classifying.

    A stub that exists has a settled folder (the reviewer may have refiled it),
    so callers can both skip paying to re-decide it and avoid failing a re-run
    over a question that was already answered.
    """
    return [t.name for t in targets if _existing_subdir(wiki_dir, t.name) is None]


def run_harvest(
    wiki_dir: Path,
    *,
    min_refs: int = DEFAULT_MIN_REFS,
    allow_unclassified: bool = False,
    backend=None,
    require_sources: bool = True,
) -> int:
    """Harvest + write candidates. Returns a process-style exit code (0/1/2).

    Shared by ``llmwiki synth`` and ``all --with-synth`` so both paths agree
    on classification refusal and messaging (#90).

    ``require_sources=False`` treats a missing ``wiki/sources/`` as an empty
    harvest (exit 0) — used when harvest follows a sources pass that wrote
    nothing on a fresh vault. ``--candidates-only`` keeps ``require_sources``
    True so an operator who asked for harvest gets a clear error.
    """
    sources_dir = wiki_dir / "sources"
    if not sources_dir.is_dir():
        if require_sources:
            print(
                f"error: no synthesized sources to harvest at {sources_dir}",
                file=sys.stderr,
            )
            return 2
        print("Candidates: 0 stub(s) (no wiki/sources/ yet)")
        return 0

    targets = harvest_targets(wiki_dir, min_refs=min_refs)
    pending = unfiled_names(wiki_dir, targets)
    kinds = classify_names(pending, backend)
    missing = [name for name in pending if name not in kinds]

    if missing and not allow_unclassified:
        backend_name = getattr(backend, "name", "none")
        print(
            f"error: {len(missing)} of {len(pending)} new target(s) could not "
            f"be classified as entity or concept after retry "
            f"(backend: {backend_name}). "
            "Nothing was written. Fix the backend and re-run, or pass "
            "--allow-unclassified to file them as entity_type: unknown for "
            "review.",
            file=sys.stderr,
        )
        print(
            f"  unclassified: {', '.join(missing[:10])}"
            f"{' …' if len(missing) > 10 else ''}",
            file=sys.stderr,
        )
        return 1

    written = write_stubs(wiki_dir, targets, classify=lambda _names: kinds)
    print(
        f"Candidates: {len(written)} stub(s) at --min-refs {min_refs} "
        f"→ {wiki_dir / 'candidates'}"
    )
    unknown = sum(
        1
        for p in written
        if "entity_type: unknown" in p.read_text(encoding="utf-8", errors="replace")
    )
    if unknown:
        print(
            f"  ! {unknown} of {len(written)} candidate(s) are filed as "
            "entity_type: unknown — re-file them during review",
            file=sys.stderr,
        )
    if written:
        print("  review with: llmwiki candidates list")
    return 0
