"""Candidate approval workflow (v1.1.0 · #51).

New entity/concept pages created by `/wiki-ingest` land in
``wiki/candidates/`` first with ``status: candidate`` frontmatter.
A human then runs `/wiki-candidates` (or `/candidates.html` / ``candidates apply``)
to promote, merge, or discard each one. Promoted pages move into
``wiki/entities/`` or ``wiki/concepts/``. Discarded candidates are archived
under ``wiki/archive/candidates/`` for audit.

Rationale: hallucinated entities ("CompanyX" that doesn't exist) should
not land in the trusted wiki layer without human review.

Public API:
  - ``list_candidates(wiki_dir)`` → list of Candidate dicts
  - ``promote(slug, wiki_dir, dest)`` → move candidate into trusted area
  - ``flip_and_promote(slug, wiki_dir)`` → flip entity↔concept then promote (#97)
  - ``fill_key_facts_from_evidence(text, wiki_dir, name=…)`` → enrich empty Key Facts
  - ``rewrite_key_facts(slug, wiki_dir, synthesizer=…)`` → rewrite Key Facts on a trusted page
  - ``strip_harvest_merge_sections(text)`` → drop pasted harvest-stub merge blocks
  - ``merge(slug, wiki_dir, into_slug)`` → fold candidate into an existing page
    (trusted or another pending stub of the same kind)
  - ``discard(slug, wiki_dir, reason)`` → move to archive/
  - ``stale_candidates(wiki_dir, threshold_days=30)`` → list pages flagged stale
  - ``is_candidate(page_path)`` → bool

Design choices:
  - Separate ``candidates/`` mirror tree (vs status field only) so the
    build step can cleanly exclude them from the public site by default.
  - ``## Connections`` links from candidates stay as-is when promoted;
    callers run `llmwiki lint` afterward to catch any stale pointers.
  - Discard is non-destructive: pages move to ``wiki/archive/candidates/``
    with a timestamped reason file so you can recover them later.
  - Promote fills an empty ``## Key Facts`` from harvest evidence (#103);
    non-empty reviewer facts are never overwritten on promote. Use
    ``rewrite_key_facts`` to replace machine-assembled bullets on a page
    that is already trusted.
"""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from llmwiki._system_pages import ARCHIVE_FOLDER
from llmwiki.reindex import reindex_wiki
from llmwiki.synth.base import BaseSynthesizer

# ─── constants ─────────────────────────────────────────────────────────

CANDIDATES_DIR_NAME = "candidates"
# This module is cold storage's only writer; `_system_pages.ARCHIVE_FOLDER` is
# what every reader recognises. One constant, so renaming the folder cannot
# leave the readers looking somewhere else.
ARCHIVE_DIR_NAME = ARCHIVE_FOLDER
ARCHIVED_CANDIDATES_SUBDIR = "candidates"

# Subfolders mirrored under wiki/candidates/
MIRRORED_SUBDIRS = ["entities", "concepts", "sources", "syntheses"]

# Entity ↔ concept flip map for review (#97). Only these two kinds flip.
_FLIP_KIND = {"entities": "concepts", "concepts": "entities"}
_TYPE_FOR_KIND = {"entities": "entity", "concepts": "concept"}

# Default staleness threshold (days)
DEFAULT_STALE_DAYS = 30

# Cap attributable Key Facts bullets written on promote (#103).
_MAX_KEY_FACTS = 5
_KEY_FACT_CLIP = 160

# Evidence digest budget: how much of the sources the model gets to read.
_MAX_EVIDENCE_SOURCES = 12
_MAX_MENTION_LINES = 4
_EVIDENCE_LINE_CLIP = 300

KEY_FACTS_PROMPT_PATH = Path(__file__).parent / "synth" / "prompts" / "key_facts.md"


class KeyFactsBackendError(RuntimeError):
    """Raised when Key Facts need writing but no LLM backend can write them.

    Promote refuses rather than degrading to string-slicing: a Key Facts
    section assembled by regex reads like prose but states whatever happened
    to sit near a wikilink, which is worse than an empty section because
    nothing downstream can tell the two apart.
    """

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_WIKILINK_TARGET_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


# ─── types ─────────────────────────────────────────────────────────────

class Candidate(TypedDict):
    """Info about one candidate page waiting for review."""

    slug: str              # bare filename stem (e.g. "NewEntity")
    rel_path: str          # path relative to wiki/ (e.g. "candidates/entities/NewEntity.md")
    abs_path: Path         # absolute path to the file
    kind: str              # "entities" | "concepts" | "sources" | "syntheses"
    title: str             # frontmatter title
    created: str | None # frontmatter created/last_updated date (YYYY-MM-DD)
    age_days: int          # days since `created`
    body_preview: str      # first 200 chars of body


# ─── helpers ───────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (meta_dict, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out, m.group(2)


def _age_days(date_str: str | None, *, now: datetime | None = None) -> int:
    """Compute days between ``date_str`` (YYYY-MM-DD) and now."""
    if not date_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return 0
    ref = now or datetime.now(UTC)
    return max(0, (ref - dt).days)


def is_candidate(page_path: Path) -> bool:
    """True if the path is inside wiki/candidates/ subtree."""
    parts = page_path.parts
    return CANDIDATES_DIR_NAME in parts


def candidates_dir(wiki_dir: Path) -> Path:
    """Return wiki/candidates/ (creates parent if needed)."""
    return wiki_dir / CANDIDATES_DIR_NAME


def archive_dir(wiki_dir: Path) -> Path:
    """Return wiki/archive/candidates/."""
    return wiki_dir / ARCHIVE_DIR_NAME / ARCHIVED_CANDIDATES_SUBDIR


# ─── public API ────────────────────────────────────────────────────────


def list_candidates(
    wiki_dir: Path,
    *,
    now: datetime | None = None,
) -> list[Candidate]:
    """Walk wiki/candidates/ and return one entry per pending page."""
    root = candidates_dir(wiki_dir)
    if not root.is_dir():
        return []

    out: list[Candidate] = []
    for sub in MIRRORED_SUBDIRS:
        sub_dir = root / sub
        if not sub_dir.is_dir():
            continue
        for path in sorted(sub_dir.glob("*.md")):
            if path.name == "_context.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = _parse_frontmatter(text)
            created = meta.get("last_updated") or meta.get("date")
            out.append({
                "slug": path.stem,
                "rel_path": str(path.relative_to(wiki_dir)),
                "abs_path": path,
                "kind": sub,
                "title": meta.get("title", path.stem),
                "created": created,
                "age_days": _age_days(created, now=now),
                "body_preview": body.strip()[:200],
            })
    return out


def _count_trusted_pages(wiki_dir: Path, kind: str) -> int:
    """Count ``*.md`` pages under ``wiki/<kind>/`` (skip ``_context.md``)."""
    root = wiki_dir / kind
    if not root.is_dir():
        return 0
    return sum(
        1
        for path in root.glob("*.md")
        if path.is_file() and path.name != "_context.md"
    )


def candidate_review_summary(
    wiki_dir: Path,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
    now: datetime | None = None,
) -> dict[str, object]:
    """Counts for the Home / Analytics review-gate widgets (#84).

    Pending stubs live under ``wiki/candidates/`` until promote / merge /
    discard. Stale uses the same threshold as ``stale_candidates`` / the
    ``stale_candidates`` lint rule (default 30 days). Trusted
    ``entities`` / ``concepts`` counts are vault-wide final-layer sizes
    (not partitioned by agent, and not the same as raw session rows).
    """
    items = list_candidates(wiki_dir, now=now)
    by_kind: dict[str, int] = {}
    for cand in items:
        by_kind[cand["kind"]] = by_kind.get(cand["kind"], 0) + 1
    stale = stale_candidates(wiki_dir, threshold_days=stale_days, now=now)
    return {
        "to_review": len(items),
        "to_review_by_kind": by_kind,
        "to_review_stale": len(stale),
        "stale_days": int(stale_days),
        "trusted_entities": _count_trusted_pages(wiki_dir, "entities"),
        "trusted_concepts": _count_trusted_pages(wiki_dir, "concepts"),
    }


def apply_review_summary_to_pipeline(
    pipeline: dict[str, object] | None,
    wiki_dir: Path,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
    now: datetime | None = None,
) -> dict[str, object]:
    """Merge review counts into a ``synth.pipeline`` dict (mutates a copy)."""
    out: dict[str, object] = dict(pipeline or {})
    stages = list(out.get("stages") or ["raw", "synthesized"])  # type: ignore[arg-type]
    if "to_review" not in stages:
        stages.append("to_review")
    out["stages"] = stages
    out.update(candidate_review_summary(wiki_dir, stale_days=stale_days, now=now))
    return out


def _reconcile_catalog(wiki_dir: Path) -> None:
    """Keep ``wiki/index.md`` in sync after candidate consume actions (#101).

    Promote / merge / discard change which pages exist under ``candidates/``
    and the trusted trees; idle sync/synth must not be required to clean up.
    Failures are swallowed — catalog drift is recoverable on the next
    successful reconcile, and must not undo a completed promote/discard.
    """
    try:
        reindex_wiki(wiki_dir)
    except (OSError, ValueError, RuntimeError):
        pass


# ─── Key Facts from evidence (#103) ────────────────────────────────────


def parse_sources_field(raw: str | list[object] | None) -> list[str]:
    """Parse a frontmatter ``sources:`` value into ordered slugs.

    Accepts the string forms used by this module's local frontmatter parser
    (``[a, b]`` or bare ``a, b``) and the list form returned by the canonical
    :func:`llmwiki._frontmatter.parse_frontmatter` parser.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(part).strip() for part in raw if str(part).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [
        part.strip().strip('"').strip("'")
        for part in text.split(",")
        if part.strip().strip('"').strip("'")
    ]


# Backward-compatible private alias (#122 promote for trace / lint reuse).
_parse_sources_field = parse_sources_field


def _section_span(body: str, heading: str) -> tuple[int, int] | None:
    """Return ``(content_start, content_end)`` for ``## <heading>``, if present."""
    for match in _HEADING_RE.finditer(body):
        if match.group(1).strip().lower() != heading.lower():
            continue
        start = match.end()
        next_h = _HEADING_RE.search(body, start)
        end = next_h.start() if next_h else len(body)
        return start, end
    return None


def _section_has_substantive_content(section: str) -> bool:
    """True when Key Facts (or similar) already has bullets or prose."""
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "*", "+")):
            if stripped.lstrip("-*+ ").strip():
                return True
            continue
        if not stripped.startswith("#"):
            return True
    return False


def _key_facts_needs_fill(body: str) -> bool:
    """True when ``## Key Facts`` is missing or empty (heading only)."""
    span = _section_span(body, "Key Facts")
    if span is None:
        return True
    start, end = span
    return not _section_has_substantive_content(body[start:end])


def resolve_source_page(wiki_dir: Path, slug: str) -> Path | None:
    """Locate ``wiki/sources/**/<slug>.md`` (flat or nested)."""
    sources = wiki_dir / "sources"
    if not sources.is_dir() or not slug:
        return None
    direct = sources / f"{slug}.md"
    if direct.is_file():
        return direct
    matches = sorted(sources.rglob(f"{slug}.md"))
    return matches[0] if matches else None


# Backward-compatible private alias (#122 promote for trace / lint reuse).
_resolve_source_page = resolve_source_page


def _evidence_source_slugs(
    meta: dict[str, str],
    body: str,
    wiki_dir: Path,
) -> list[str]:
    """Evidence sources from frontmatter ``sources:`` and Connections links."""
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(slug: str) -> None:
        key = slug.casefold()
        if not slug or key in seen:
            return
        seen.add(key)
        ordered.append(slug)

    for slug in _parse_sources_field(meta.get("sources", "")):
        _add(slug)

    span = _section_span(body, "Connections")
    if span is not None:
        start, end = span
        for raw in _WIKILINK_TARGET_RE.findall(body[start:end]):
            name = raw.split("#", 1)[0].strip()
            if _resolve_source_page(wiki_dir, name) is not None:
                _add(name)
    return ordered


def _clip_fact(text: str, limit: int = _KEY_FACT_CLIP) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip(".,;: ") + "…"


def _mention_lines(body: str, name: str) -> list[str]:
    """Every line naming ``[[Name]]``, in document order.

    A source usually names an entity more than once, and the line that
    actually *describes* it is rarely the first — a session summary tends to
    mention it in passing before the Connections section states what it is.
    Handing the model every mention lets it pick; handing it only the first
    guarantees passing mentions win.
    """
    if not name:
        return []
    pattern = re.compile(
        rf"\[\[{re.escape(name)}(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]",
        re.IGNORECASE,
    )
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in body.splitlines():
        if not pattern.search(raw_line):
            continue
        cleaned = re.sub(r"^[-*+]\s+", "", raw_line.strip()).strip()
        if not cleaned or cleaned in seen:
            continue
        # A line that is nothing but wikilinks and punctuation — a bare
        # Connections bullet — states no fact, so it is not evidence.
        if not re.sub(r"[^\w]", "", _WIKILINK_TARGET_RE.sub("", cleaned)):
            continue
        seen.add(cleaned)
        lines.append(_clip_fact(cleaned, _EVIDENCE_LINE_CLIP))
        if len(lines) >= _MAX_MENTION_LINES:
            break
    return lines


def _source_evidence(path: Path, name: str, slug: str) -> str | None:
    """One source's contribution to the evidence digest, or None if silent."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta, body = _parse_frontmatter(text)
    lines = _mention_lines(body, name)
    if not lines:
        return None
    title = (meta.get("title") or slug).strip().strip('"')
    quoted = "\n".join(f"  > {line}" for line in lines)
    return f"- [[{slug}]] — {title}\n{quoted}"


def _evidence_digest(wiki_dir: Path, slugs: list[str], name: str) -> str:
    """Assemble the evidence block the model writes Key Facts from."""
    blocks: list[str] = []
    for slug in slugs:
        path = _resolve_source_page(wiki_dir, slug)
        if path is None:
            continue
        block = _source_evidence(path, name, slug)
        if block is None:
            continue
        blocks.append(block)
        if len(blocks) >= _MAX_EVIDENCE_SOURCES:
            break
    return "\n".join(blocks)


def _bullets_from_completion(completion: str) -> list[str]:
    """Keep the model's bullet lines, drop any preamble or trailing chatter."""
    bullets: list[str] = []
    for raw_line in (completion or "").splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith(("-", "*", "+")):
            continue
        fact = stripped.lstrip("-*+ ").strip()
        if not fact:
            continue
        bullets.append(fact)
        if len(bullets) >= _MAX_KEY_FACTS:
            break
    return bullets


def _key_facts_prompt_template(wiki_dir: Path) -> str:
    """Load ``prompts/key_facts.md``, preferring the vault's own override."""
    override = wiki_dir / "prompts" / "key_facts.md"
    if override.is_file():
        return override.read_text(encoding="utf-8")
    return KEY_FACTS_PROMPT_PATH.read_text(encoding="utf-8")


def _inject_key_facts(body: str, bullets: list[str]) -> str:
    """Write ``## Key Facts`` bullets, replacing an empty section if present."""
    block = "## Key Facts\n\n" + "\n".join(f"- {b}" for b in bullets) + "\n"
    for match in _HEADING_RE.finditer(body):
        if match.group(1).strip().lower() != "key facts":
            continue
        start = match.start()
        content_start = match.end()
        next_h = _HEADING_RE.search(body, content_start)
        end = next_h.start() if next_h else len(body)
        return body[:start] + block + "\n" + body[end:].lstrip("\n")
    conn = re.search(r"^## Connections\b", body, re.MULTILINE)
    if conn:
        return body[: conn.start()] + block + "\n" + body[conn.start() :]
    return body.rstrip() + "\n\n" + block + "\n"


_HARVEST_BOILERPLATE_RE = re.compile(
    r"Named by \d+ source page\(s\).*?justified this candidate:",
    re.DOTALL,
)

#: Inner headings inside a pasted harvest stub under ``## Candidate merge``.
_STUB_INNER_HEADINGS = frozenset({"key facts", "connections"})


def _clear_key_facts_content(body: str) -> str:
    """Empty an existing ``## Key Facts`` section so a rewrite can refill it."""
    span = _section_span(body, "Key Facts")
    if span is None:
        return body
    start, end = span
    for match in _HEADING_RE.finditer(body):
        if match.group(1).strip().lower() == "key facts":
            return body[: match.end()] + "\n\n" + body[end:].lstrip("\n")
    return body


def fill_key_facts_from_evidence(
    text: str,
    wiki_dir: Path,
    *,
    name: str | None = None,
    synthesizer: BaseSynthesizer | None = None,
    force: bool = False,
) -> str:
    """Fill an empty ``## Key Facts`` from harvest evidence sources (#103).

    Resolves ``sources:`` frontmatter and Connections wikilinks that point at
    ``wiki/sources/`` pages, collects every line where they name the page, and
    asks ``synthesizer`` to write declarative facts from that evidence.

    Non-empty Key Facts are left untouched unless ``force=True`` (rewrite path
    for pages promoted by the earlier regex assembler). A page whose sources
    never say anything about it is left alone too: there is nothing to write
    from.

    Raises ``KeyFactsBackendError`` when evidence exists but ``synthesizer``
    is missing, unavailable, or not LLM-backed.
    """
    meta, body = _parse_frontmatter(text)
    page_name = (name or meta.get("title") or "").strip().strip('"')
    if not page_name:
        return text
    if force:
        body = _clear_key_facts_content(body)
    elif not _key_facts_needs_fill(body):
        return text

    slugs = _evidence_source_slugs(meta, body, wiki_dir)
    evidence = _evidence_digest(wiki_dir, slugs, page_name)
    if not evidence:
        if not force:
            return text
        fm_match = FRONTMATTER_RE.match(text)
        if fm_match:
            return f"---\n{fm_match.group(1)}\n---\n{body}"
        return body

    if synthesizer is None or not getattr(synthesizer, "is_llm", False):
        raise KeyFactsBackendError(
            f"{page_name}: writing Key Facts needs an LLM backend — set "
            'synthesis.backend to "claude" or "ollama" in config.json'
        )
    if not synthesizer.is_available():
        raise KeyFactsBackendError(
            f"{page_name}: synthesis backend {synthesizer.name} is not available"
        )

    completion = synthesizer.synthesize_key_facts(
        evidence,
        {"title": page_name, "type": meta.get("type", "entity")},
        _key_facts_prompt_template(wiki_dir),
    )
    bullets = _bullets_from_completion(completion)
    if not bullets:
        raise KeyFactsBackendError(
            f"{page_name}: {synthesizer.name} returned no usable Key Facts"
        )

    new_body = _inject_key_facts(body, bullets)
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        return f"---\n{fm_match.group(1)}\n---\n{new_body}"
    return new_body


def promote(
    slug: str,
    wiki_dir: Path,
    *,
    kind: str | None = None,
    dest_kind: str | None = None,
    synthesizer: BaseSynthesizer | None = None,
) -> Path:
    """Move ``wiki/candidates/<kind>/<slug>.md`` → ``wiki/<dest>/<slug>.md``.

    If ``kind`` is omitted, infers from where the candidate lives. ``dest_kind``
    defaults to that same folder (plain promote). Pass the opposite kind for
    flip-and-promote (#97). Rewrites ``status: candidate`` → ``reviewed`` and
    aligns ``type:`` with the destination folder. Has ``synthesizer`` write an
    empty ``## Key Facts`` from evidence sources (#103). Reconciles
    ``wiki/index.md`` afterward (#101).

    Returns the new (promoted) path. Raises FileNotFoundError if the
    candidate does not exist, ``ValueError`` if ``dest_kind`` is invalid, or
    ``KeyFactsBackendError`` when the page needs Key Facts and no LLM backend
    is configured.
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    inferred_kind = candidate.parent.name
    target_kind = dest_kind or inferred_kind
    if target_kind not in MIRRORED_SUBDIRS:
        raise ValueError(f"invalid dest_kind: {target_kind!r}")
    target_dir = wiki_dir / target_kind
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / candidate.name
    if target.is_file():
        raise FileExistsError(f"trusted page already exists: {target}")

    text = candidate.read_text(encoding="utf-8")
    text = _rewrite_status(text, old="candidate", new="reviewed")
    if target_kind != inferred_kind:
        text = _rewrite_type(
            text, new=_TYPE_FOR_KIND.get(target_kind, target_kind.rstrip("s"))
        )
    text = fill_key_facts_from_evidence(
        text, wiki_dir, name=candidate.stem, synthesizer=synthesizer
    )
    target.write_text(text, encoding="utf-8")
    candidate.unlink()
    _reconcile_catalog(wiki_dir)
    return target


def flip_and_promote(
    slug: str,
    wiki_dir: Path,
    *,
    kind: str | None = None,
    synthesizer: BaseSynthesizer | None = None,
) -> Path:
    """Promote into the opposite trusted folder (entity↔concept) (#97).

    Only ``entities`` and ``concepts`` candidates flip. Raises ValueError for
    other kinds. Equivalent to ``promote(..., dest_kind=<opposite>)``.
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    inferred_kind = candidate.parent.name
    dest = _FLIP_KIND.get(inferred_kind)
    if dest is None:
        raise ValueError(
            f"cannot flip kind {inferred_kind!r} — only entities↔concepts"
        )
    return promote(
        slug,
        wiki_dir,
        kind=inferred_kind,
        dest_kind=dest,
        synthesizer=synthesizer,
    )


# ─── merge helpers (#103) ──────────────────────────────────────────────


def _split_frontmatter_text(text: str) -> tuple[str, str]:
    """Split raw page text into (frontmatter-with-delimiters, body)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return "", text
    return f"---\n{match.group(1)}\n---\n", match.group(2)


def strip_harvest_merge_sections(text: str) -> str:
    """Remove ``## Candidate merge`` blocks that are pasted harvest stubs.

    Pre-#103 ``merge`` appended the whole stub (second H1, empty Key Facts,
    "Named by N source page(s)…" boilerplate). Those blocks are not reviewer
    prose — drop them. Merges that carry real reviewer writing are kept.
    """
    fm, body = _split_frontmatter_text(text)
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return text
    remove: list[tuple[int, int]] = []
    i = 0
    while i < len(matches):
        heading = matches[i].group(1).strip()
        if not heading.lower().startswith("candidate merge"):
            i += 1
            continue
        start = matches[i].start()
        j = i + 1
        while (
            j < len(matches)
            and matches[j].group(1).strip().lower() in _STUB_INNER_HEADINGS
        ):
            j += 1
        end = matches[j].start() if j < len(matches) else len(body)
        section = body[start:end]
        if _HARVEST_BOILERPLATE_RE.search(section):
            remove.append((start, end))
        i = max(j, i + 1)
    if not remove:
        return text
    out = body
    for start, end in reversed(remove):
        out = out[:start].rstrip() + "\n\n" + out[end:].lstrip("\n")
    return fm + out


def _find_trusted_page(
    slug: str,
    wiki_dir: Path,
    kind: str | None,
) -> Path:
    """Locate ``wiki/<kind>/<slug>.md`` (entities/concepts by default)."""
    subs = [kind] if kind else ["entities", "concepts"]
    for sub in subs:
        path = wiki_dir / sub / f"{slug}.md"
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"trusted page not found: {slug!r} under {wiki_dir}"
        + (f" (kind={kind})" if kind else " (entities|concepts)")
    )


def rewrite_key_facts(
    slug: str,
    wiki_dir: Path,
    *,
    kind: str | None = None,
    synthesizer: BaseSynthesizer | None = None,
    strip_merges: bool = True,
) -> Path:
    """Rewrite ``## Key Facts`` on an already-trusted entity/concept page (#103).

    Promote only fills empty Key Facts on the way out of ``candidates/``.
    Pages promoted by the earlier regex assembler still carry clipped
    fragments; this is the recovery path — force-fill from evidence via the
    LLM backend, and optionally drop pasted harvest-stub ``## Candidate
    merge`` blocks left by the old merge behaviour.
    """
    path = _find_trusted_page(slug, wiki_dir, kind)
    text = path.read_text(encoding="utf-8")
    if strip_merges:
        text = strip_harvest_merge_sections(text)
    text = fill_key_facts_from_evidence(
        text,
        wiki_dir,
        name=path.stem,
        synthesizer=synthesizer,
        force=True,
    )
    path.write_text(text, encoding="utf-8")
    return path


def _reviewer_prose(body: str) -> str:
    """Whatever a human wrote into a candidate, minus harvest scaffolding.

    Empty for a harvest stub: its H1, empty Key Facts, boilerplate sentence
    and evidence link list are all machine-generated and belong to the
    target page's own sections, not to a pasted block.
    """
    text = re.sub(r"^#\s+.*$", "", body, count=1, flags=re.MULTILINE)
    for heading in ("Key Facts", "Connections"):
        span = _section_span(text, heading)
        if span is None:
            continue
        start, end = span
        section = text[start:end]
        if heading == "Connections":
            section = _HARVEST_BOILERPLATE_RE.sub("", section)
            section = re.sub(r"^\s*[-*+]\s*\[\[[^\]]+\]\]\s*$", "", section,
                             flags=re.MULTILINE)
        if _section_has_substantive_content(section):
            continue
        heading_start = text.rfind("## ", 0, start)
        text = text[:heading_start] + text[end:]
    return text.strip()


def _union_sources_frontmatter(text: str, slugs: list[str]) -> str:
    """Add ``slugs`` to the page's ``sources:`` frontmatter list."""
    if not slugs:
        return text
    meta, _ = _parse_frontmatter(text)
    existing = _parse_sources_field(meta.get("sources", ""))
    seen = {s.casefold() for s in existing}
    merged = existing + [s for s in slugs if s.casefold() not in seen]
    if merged == existing:
        return text
    line = f"sources: [{', '.join(merged)}]"
    if "sources" in meta:
        return re.sub(r"^sources:.*$", line, text, count=1, flags=re.MULTILINE)
    head, body = _split_frontmatter_text(text)
    if not head:
        return text
    return head.replace("\n---\n", f"\n{line}\n---\n", 1) + body


def _union_connections(body: str, slugs: list[str]) -> str:
    """Append missing ``[[slug]]`` bullets to the ``## Connections`` list."""
    if not slugs:
        return body
    span = _section_span(body, "Connections")
    if span is None:
        return body.rstrip() + "\n\n## Connections\n\n" + "\n".join(
            f"- [[{s}]]" for s in slugs
        ) + "\n"
    start, end = span
    section = body[start:end]
    present = {t.split("#", 1)[0].strip().casefold()
               for t in _WIKILINK_TARGET_RE.findall(section)}
    missing = [s for s in slugs if s.casefold() not in present]
    if not missing:
        return body
    addition = "\n".join(f"- [[{s}]]" for s in missing)
    return body[:end].rstrip() + "\n" + addition + "\n" + body[end:]


def _record_alias(body: str, alias: str, source_count: int, today: str) -> str:
    """Note the merged-away name under ``## Aliases``."""
    entry = f"- {alias} — merged {today} ({source_count} source pages)"
    span = _section_span(body, "Aliases")
    if span is None:
        return body.rstrip() + f"\n\n## Aliases\n\n{entry}\n"
    _, end = span
    return body[:end].rstrip() + f"\n{entry}\n" + body[end:]


def merge(
    slug: str,
    wiki_dir: Path,
    *,
    into_slug: str,
    kind: str | None = None,
) -> Path:
    """Fold the candidate into ``<into_slug>.md``, then archive the candidate.

    Target resolution (#97): prefer a trusted page at
    ``wiki/<kind>/<into_slug>.md``; otherwise accept another pending stub at
    ``wiki/candidates/<kind>/<into_slug>.md`` (same-table merge).

    A harvest stub carries no prose worth keeping — only the evidence that
    justified it — so its sources are unioned into the target's ``sources:``
    frontmatter and ``## Connections`` list and it is recorded under
    ``## Aliases``. Pasting the stub verbatim instead would nest a second
    H1, a second empty Key Facts, and a link list the page's own Connections
    section never learns about.

    A candidate a reviewer actually wrote in still gets its prose appended
    under ``## Candidate merge — <date>``.

    Reconciles ``wiki/index.md`` afterward (#101).

    Returns the path of the target page. Raises FileNotFoundError if either
    page is missing. Raises ValueError if merging a stub into itself.
    """
    if slug == into_slug:
        raise ValueError("cannot merge a candidate into itself")

    candidate = _find_candidate(slug, wiki_dir, kind)
    inferred_kind = candidate.parent.name
    trusted = wiki_dir / inferred_kind / f"{into_slug}.md"
    pending = wiki_dir / CANDIDATES_DIR_NAME / inferred_kind / f"{into_slug}.md"
    if trusted.is_file():
        target = trusted
    elif pending.is_file():
        target = pending
    else:
        raise FileNotFoundError(
            f"merge target not found: {into_slug!r} under "
            f"{inferred_kind}/ or candidates/{inferred_kind}/"
        )

    candidate_text = candidate.read_text(encoding="utf-8")
    candidate_meta, candidate_body = _parse_frontmatter(candidate_text)
    evidence = _evidence_source_slugs(candidate_meta, candidate_body, wiki_dir)
    prose = _reviewer_prose(candidate_body)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    merged = _union_sources_frontmatter(target.read_text(encoding="utf-8"), evidence)
    meta_text, body = _split_frontmatter_text(merged)
    body = _union_connections(body, evidence)
    body = _record_alias(body, slug, len(evidence), today)
    if prose:
        body = (
            body.rstrip() +
            f"\n\n## Candidate merge — {today}\n\n" +
            f"Merged from `{candidate.relative_to(wiki_dir)}`:\n\n" +
            prose + "\n"
        )
    target.write_text(meta_text + body, encoding="utf-8")

    # Discard candidate by moving it to archive with a merge-reason file
    _archive_candidate(candidate, wiki_dir, reason=f"merged into {into_slug}")
    _reconcile_catalog(wiki_dir)
    return target


def discard(
    slug: str,
    wiki_dir: Path,
    *,
    reason: str = "",
    kind: str | None = None,
) -> Path:
    """Move the candidate to ``wiki/archive/candidates/<timestamp>/<slug>.md``
    with an adjacent ``<slug>.reason.txt`` capturing why.

    Reconciles ``wiki/index.md`` afterward (#101).

    Returns the archived path.
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    path = _archive_candidate(candidate, wiki_dir, reason=reason)
    _reconcile_catalog(wiki_dir)
    return path


def stale_candidates(
    wiki_dir: Path,
    *,
    threshold_days: int = DEFAULT_STALE_DAYS,
    now: datetime | None = None,
) -> list[Candidate]:
    """Return candidates older than ``threshold_days``."""
    return [
        c for c in list_candidates(wiki_dir, now=now)
        if c["age_days"] >= threshold_days
    ]


# ─── internals ─────────────────────────────────────────────────────────


def _find_candidate(
    slug: str,
    wiki_dir: Path,
    kind: str | None,
) -> Path:
    """Locate ``<slug>.md`` under wiki/candidates/, optionally filtered by kind."""
    root = candidates_dir(wiki_dir)
    subs = [kind] if kind else MIRRORED_SUBDIRS
    for sub in subs:
        path = root / sub / f"{slug}.md"
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"candidate not found: {slug!r} under {root}"
        + (f" (kind={kind})" if kind else "")
    )


def _rewrite_status(text: str, *, old: str, new: str) -> str:
    """Replace ``status: <old>`` with ``status: <new>`` in frontmatter."""
    pattern = re.compile(
        rf"^(status:\s*){re.escape(old)}(\s*)$",
        re.MULTILINE,
    )
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{new}\g<2>", text)
    # Add status line to frontmatter if missing
    m = FRONTMATTER_RE.match(text)
    if m:
        new_fm = m.group(1) + f"\nstatus: {new}"
        return f"---\n{new_fm}\n---\n{m.group(2)}"
    return text


def _rewrite_type(text: str, *, new: str) -> str:
    """Replace or insert frontmatter ``type:`` for flip-and-promote (#97)."""
    pattern = re.compile(r"^(type:\s*)\S+(\s*)$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{new}\g<2>", text, count=1)
    m = FRONTMATTER_RE.match(text)
    if m:
        new_fm = m.group(1) + f"\ntype: {new}"
        return f"---\n{new_fm}\n---\n{m.group(2)}"
    return text


def _archive_candidate(
    candidate: Path,
    wiki_dir: Path,
    *,
    reason: str,
) -> Path:
    """Move candidate into archive with reason file."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    dest_dir = archive_dir(wiki_dir) / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / candidate.name
    shutil.move(str(candidate), str(dest))

    if reason:
        reason_file = dest.with_suffix(".reason.txt")
        reason_file.write_text(
            f"Discarded at: {datetime.now(UTC).isoformat()}\n"
            f"Reason: {reason}\n"
            f"Original path: candidates/{candidate.parent.name}/{candidate.name}\n",
            encoding="utf-8",
        )
    return dest
