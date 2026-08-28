"""Harvest entity/concept candidates from synthesized source pages (#90).

``synthesize`` writes ``wiki/sources/`` pages whose ``## Connections`` blocks
name the entities and concepts the LLM identified. Nothing materialized those
names, so the links dangle and the trusted layer stays empty.

Harvesting closes that loop deterministically: kind, description, and facts are
read from source topic bullets via :mod:`llmwiki.source_topics` — a pass over
``wiki/sources/`` only, never ``raw/``, and with no classification LLM call.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from llmwiki.lint.rules.link_integrity import _norm_slug
from llmwiki.reindex import reindex_wiki
from llmwiki.source_topics import TopicRecord, parse_source_topics
from llmwiki.vault_settings import DEFAULT_MIN_REFS
from llmwiki.wikilinks import count_source_refs

# ``DEFAULT_MIN_REFS`` is re-exported from :mod:`llmwiki.vault_settings` so
# existing importers (``cli.py``, ``pipeline.py``) keep reading it here while
# :mod:`llmwiki.lint` reads the same definition from vault_settings — a lint
# import of this module would be a cycle, since ``_norm_slug`` above comes out
# of the lint package (#150).


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


class SourceReadError(OSError):
    """One or more ``wiki/sources/`` pages could not be read.

    Carries every failing page so a caller can report the whole set at once
    instead of surfacing whichever page happened to be walked first.
    """

    def __init__(self, failures: Iterable[tuple[str, str]]) -> None:
        self.failures: list[tuple[str, str]] = list(failures)
        detail = "; ".join(f"{rel} ({reason})" for rel, reason in self.failures)
        super().__init__(f"unreadable source page(s): {detail}")


def harvest_targets(
    wiki_dir: Path,
    *,
    min_refs: int = DEFAULT_MIN_REFS,
) -> list[HarvestedTarget]:
    """Return unresolved wikilink targets named by ``min_refs``+ source pages.

    Raises :class:`SourceReadError` when any page under ``wiki/sources/``
    cannot be read: a partial scan would under-count evidence and silently
    drop targets below the threshold.
    """
    # A pending candidate does not resolve its own inbound links — if it did,
    # the first run would make every later run a no-op and evidence could
    # never be refreshed.
    #
    # `wiki/archive/**` IS scanned here, deliberately, and this is the one
    # place that reads it (#140). Everywhere else archive/ is cold storage
    # because it holds pages a reviewer dismissed as noise — a tool name, an
    # example, a term repeated by accident. Here it plays its second role:
    # the dismissal ledger. The archived stub is the only record that the
    # term was ever judged, so an archived slug must keep counting as
    # resolved. Route this through `is_archived_path` and every dismissed
    # term is re-proposed on the next synth, and on every synth after —
    # permanently, because discarding it again changes nothing.
    candidates_root = wiki_dir / "candidates"
    resolved = {
        _norm_slug(p.stem)
        for p in wiki_dir.rglob("*.md")
        if not p.is_relative_to(candidates_root)
    }

    texts_by_rel: dict[str, str] = {}
    unreadable: list[tuple[str, str]] = []
    sources_dir = wiki_dir / "sources"
    for page in sorted(sources_dir.rglob("*.md")):
        rel = page.relative_to(wiki_dir).as_posix()
        try:
            texts_by_rel[rel] = page.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            unreadable.append((rel, exc.strerror or str(exc)))

    if unreadable:
        raise SourceReadError(unreadable)

    # Counting is shared with ``link_integrity`` (#150); resolution is not, and
    # deliberately so — see the note above on candidates/ and archive/.
    by_target = count_source_refs(texts_by_rel)

    return [
        HarvestedTarget(name=name, sources=tuple(sorted(pages)))
        for name, pages in sorted(by_target.items())
        if len(pages) >= min_refs and _norm_slug(name) not in resolved
    ]


#: Maps harvested names to ``"entity"`` or ``"concept"``. A classifier must
#: answer for every name it is given: ``write_stubs`` refuses to guess on its
#: behalf, because a misfiled stub looks identical to a reviewed one.
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
    check_available: bool = True,
) -> dict[str, str]:
    """Ask ``backend`` to sort ``names`` into entities and concepts.

    Returns only names the backend classified as ``entity`` or ``concept``.
    Omitted / unparseable names are absent from the result, and an
    unavailable backend yields an empty mapping — the two look alike here, so
    callers that need to tell them apart probe availability themselves (see
    ``run_harvest``).

    ``check_available=False`` skips the availability probe. A probe can shell
    out or make a network round-trip, so a caller that has just run one passes
    its answer in rather than paying for a second — and a backend that dies
    between two probes cannot be misreported as answering incompletely.

    When ``retry_missing`` is true (default), names absent from the first
    reply get one small follow-up call before giving up (#90). Truncation and
    flaky backends often omit a short tail; a second pass recovers those.
    """
    if backend is None or not names:
        return {}
    if check_available and not _backend_is_reachable(backend):
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


def _topic_records_for_target(
    wiki_dir: Path, target: HarvestedTarget
) -> list[tuple[str, TopicRecord]]:
    """``(source-slug, TopicRecord)`` for citing sources in sorted slug order."""
    matched: list[tuple[str, TopicRecord]] = []
    for rel in target.sources:
        slug = Path(rel).stem
        try:
            text = (wiki_dir / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for record in parse_source_topics(text):
            if record.name == target.name:
                matched.append((slug, record))
    return matched


def _majority_kind(wiki_dir: Path, target: HarvestedTarget) -> str:
    """Entity vs concept from citing source topic bullets; tie → first usable."""
    entity = 0
    concept = 0
    first: str | None = None
    for _slug, record in _topic_records_for_target(wiki_dir, target):
        if record.kind not in _KIND_DIRS:
            continue
        if first is None:
            first = record.kind
        if record.kind == "entity":
            entity += 1
        elif record.kind == "concept":
            concept += 1
    if entity > concept:
        return "entity"
    if concept > entity:
        return "concept"
    if first is not None:
        return first
    return "entity"


def _kinds_from_source_topics(
    wiki_dir: Path, targets: Iterable[HarvestedTarget]
) -> dict[str, str]:
    """Map each target name to its majority kind from source topic bullets."""
    return {t.name: _majority_kind(wiki_dir, t) for t in targets}


def _new_stub_body(wiki_dir: Path, target: HarvestedTarget) -> str:
    """Build H1 + optional description + Key Facts from source topic bullets."""
    description = ""
    fact_lines: list[str] = []
    for slug, record in _topic_records_for_target(wiki_dir, target):
        if not description and record.description.strip():
            description = record.description.strip()
        for fact in record.facts:
            text = fact.strip()
            if text:
                fact_lines.append(f"- {text} [[{slug}]]")

    parts = [f"# {target.name}\n\n"]
    if description:
        parts.append(f"{description}\n\n")
    parts.append("## Key Facts\n\n")
    if fact_lines:
        parts.append("\n".join(fact_lines) + "\n\n")
    return "".join(parts)


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
    sources = ", ".join(slugs)
    return (
        f"---\n"
        f'title: "{target.name}"\n'
        f"type: {kind}\n"
        f"status: candidate\n"
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

    ``classify=None`` is the explicit no-classifier mode: every new name is
    filed as an entity. Supplying a ``classify`` asserts that it decides, so a
    name it leaves out raises :class:`ValueError` rather than being guessed —
    a guessed stub is indistinguishable from a classified one on disk.

    New stubs get description and Key Facts from source topic bullets; an
    existing stub keeps prose above ``## Connections`` via
    :func:`_preserved_body`.
    """
    targets = list(targets)
    # A stub that already exists keeps its folder — the reviewer may have
    # refiled it, and that decision outranks the model's. Resolve those first
    # so classification is only asked about genuinely new names: re-runs
    # otherwise pay for an answer they then discard.
    filed = {t.name: _existing_subdir(wiki_dir, t.name) for t in targets}
    unfiled = [name for name, subdir in filed.items() if subdir is None]
    kinds: dict[str, str] = {}
    if classify is not None:
        kinds = classify(unfiled)
        unclassified = [n for n in unfiled if kinds.get(n) not in _KIND_DIRS]
        if unclassified:
            raise ValueError(
                "classifier returned no entity/concept kind for "
                f"{len(unclassified)} name(s): {', '.join(unclassified)}"
            )
    today = datetime.now(UTC).date().isoformat()

    written: list[Path] = []
    for target in targets:
        subdir = filed[target.name]
        if subdir is None:
            subdir = _KIND_DIRS.get(kinds.get(target.name, "entity"), "entities")
        kind = _DIR_KINDS.get(subdir, "entity")
        path = wiki_dir / "candidates" / subdir / f"{target.name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            body = _preserved_body(path, target.name)
        else:
            body = _new_stub_body(wiki_dir, target)
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

    Returns harvestable-stub counts for ``wiki/sources/`` as it exists now —
    a pre-run snapshot, not a forecast of what the next synthesize will
    harvest. Reporting a single count at one threshold hides whether that
    threshold was a sensible choice, so this returns the distribution across
    neighbouring values too.
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


def _backend_is_reachable(backend) -> bool:
    """Probe ``backend`` the way ``classify_names`` does, but report the answer.

    ``classify_names`` returns an empty mapping both for an unreachable
    backend and for a reply it could not parse. Callers that still use the
    LLM classifier probe availability separately so they can tell the two
    apart.
    """
    if backend is None:
        return False
    try:
        return bool(backend.is_available())
    except Exception:  # noqa: BLE001 - a broken probe is an unreachable backend
        return False


def run_harvest(
    wiki_dir: Path,
    *,
    min_refs: int = DEFAULT_MIN_REFS,
    backend=None,
    require_sources: bool = True,
) -> int:
    """Harvest + write candidates. Returns a process-style exit code (0/1/2).

    Shared by ``llmwiki synth`` and ``all`` so both paths agree on messaging (#90 / #147).

    Kind, description, and Key Facts come from source topic bullets
    (:func:`llmwiki.source_topics.parse_source_topics`). ``backend`` is
    accepted for call-site compatibility and ignored for classification.

    ``require_sources=False`` treats a missing ``wiki/sources/`` as an empty
    harvest (exit 0) — used when harvest follows a sources pass that wrote
    nothing on a fresh vault. ``--candidates-only`` keeps ``require_sources``
    True so an operator who asked for harvest gets a clear error.
    """
    del backend  # retained on the signature; classification is topic-based
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

    try:
        targets = harvest_targets(wiki_dir, min_refs=min_refs)
    except SourceReadError as exc:
        print(
            f"error: {len(exc.failures)} source page(s) under {sources_dir} "
            "could not be read, so the evidence behind every candidate is "
            "incomplete. Nothing was written. Fix the permissions or remove "
            "the unreadable page(s), then re-run.",
            file=sys.stderr,
        )
        for rel, reason in exc.failures[:10]:
            print(f"  unreadable: {rel} ({reason})", file=sys.stderr)
        return 2

    kinds = _kinds_from_source_topics(wiki_dir, targets)
    written = write_stubs(
        wiki_dir,
        targets,
        classify=lambda names: {n: kinds.get(n, "entity") for n in names},
    )
    print(
        f"Candidates: {len(written)} stub(s) at --min-refs {min_refs} "
        f"→ {wiki_dir / 'candidates'}"
    )
    if written:
        # List new stubs under ## Candidates (and drop stale bullets) (#101).
        try:
            reindex_wiki(wiki_dir)
        except (OSError, ValueError, RuntimeError):
            pass
        print("  review with: llmwiki candidates list")
    return 0
