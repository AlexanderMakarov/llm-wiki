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
  - ``discard(slug, wiki_dir, reason, redirect=None)`` → move to archive/,
    then unlink (or retarget to ``redirect``) every ``[[link]]`` to it
  - ``DiscardBatch(wiki_dir)`` → one wiki scan and one rewrite pass shared by
    a run of discards, instead of two passes each
  - ``discarded_names(wiki_dir)`` → names a reviewer dismissed for good
  - ``merged_intents(wiki_dir)`` → merged-away name → the target its reason
    file recorded, for a survivor that no longer answers to the name
  - ``candidate_filename(name)`` → the flat, path-safe stub filename for a name
  - ``stale_candidates(wiki_dir, threshold_days=30)`` → list pages flagged stale
  - ``is_candidate(page_path)`` → bool

Design choices:
  - Separate ``candidates/`` mirror tree (vs status field only) so the
    build step can cleanly exclude them from the public site by default.
  - ``## Connections`` links from candidates stay as-is when promoted;
    callers run `llmwiki lint` afterward to catch any stale pointers.
  - Discard is non-destructive: pages move to ``wiki/archive/candidates/``
    with a timestamped reason file so you can recover them later. Links to a
    discarded name are rewritten to plain text (or to the ``redirect`` page,
    which records the name under ``## Aliases``) so nothing keeps pointing
    into cold storage (#282).
  - Promote fills an empty ``## Key Facts`` from ``fact:`` lines on cited
    source pages (#147); non-empty reviewer facts are never overwritten.
    Use ``rewrite_key_facts`` (LLM, opt-in) to replace bullets on a page
    that is already trusted.
"""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from llmwiki._system_pages import ARCHIVE_FOLDER, is_archived_path
from llmwiki.reindex import reindex_wiki
from llmwiki.source_topics import parse_source_topics
from llmwiki.synth.base import BaseSynthesizer
from llmwiki.wikilinks import (
    format_alias_bullet,
    norm_page_key,
    parse_page_aliases,
    rewrite_wikilinks,
)

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
    """Raised when ``rewrite_key_facts`` needs an LLM backend and lacks one.

    Promote fills empty Key Facts from source topic ``fact:`` lines offline
    (#147) and never raises this. The opt-in rewrite CLI still requires a
    real backend rather than clipping prose near a wikilink.
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


#: Characters no stub filename may carry: path separators (``A/B`` would
#: become a folder), Windows-reserved punctuation, and control characters.
_UNSAFE_FILENAME_RE = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

#: Device names Windows refuses as a filename whatever the extension.
_RESERVED_STEM_RE = re.compile(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", re.IGNORECASE)


def candidate_filename(name: str) -> str:
    """Return the flat ``<stem>.md`` filename a candidate named ``name`` uses.

    Every path-unsafe character becomes ``-``, and leading dots plus trailing
    dots and spaces are dropped, so a stub never lands in a subfolder, as a
    hidden file, or under a name Windows cannot open. A stem Windows reserves
    for a device (``CON``, ``LPT1``, …) gains a trailing ``-``. The name itself
    is kept verbatim in the stub's frontmatter ``title``. The mapping is
    idempotent — a stem it produced maps to itself — so a slug read back off
    disk locates the same file, and :func:`llmwiki.wikilinks.norm_page_key`
    folds ``[[A/B thing]]`` onto the ``A-B thing`` stem.
    """
    stem = _UNSAFE_FILENAME_RE.sub("-", name).strip().lstrip(". ").rstrip(". ")
    if not stem:
        return "candidate.md"
    if _RESERVED_STEM_RE.fullmatch(stem):
        stem = f"{stem}-"
    return f"{stem}.md"


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


def _topic_fact_bullets(
    wiki_dir: Path,
    slugs: list[str],
    page_name: str,
) -> list[str]:
    """Key Facts lines from ``fact:`` bullets on evidence source pages (#147).

    Each fact is suffixed with `` [[source-slug]]``. Order follows ``slugs``,
    then topic order within each page. Does not clip mention lines.
    """
    bullets: list[str] = []
    for slug in slugs:
        path = _resolve_source_page(wiki_dir, slug)
        if path is None:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for record in parse_source_topics(text):
            if record.name != page_name:
                continue
            for fact in record.facts:
                cleaned = fact.strip()
                if cleaned:
                    bullets.append(f"{cleaned} [[{slug}]]")
    return bullets


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
_HARVEST_BOILERPLATE_SHORT_RE = re.compile(
    r"Named by \d+ source page\(s\):\s*\n+(?:- \[\[[^\]]+\]\]\s*\n)+",
)


def _harvest_boilerplate_block(slugs: list[str]) -> str:
    """Evidence sentence + link list, matching ``candidates_harvest._stub_text``."""
    evidence = "\n".join(f"- [[{s}]]" for s in slugs)
    return (
        f"Named by {len(slugs)} source page(s), which is the evidence that\n"
        f"justified this candidate:\n\n"
        f"{evidence}\n"
    )


def _refresh_harvest_boilerplate(body: str, slugs: list[str]) -> str:
    """Rewrite harvest evidence boilerplate when its count or list is stale."""
    if not slugs or not re.search(r"Named by \d+ source page\(s\)", body):
        return body
    if _HARVEST_BOILERPLATE_RE.search(body):
        return _HARVEST_BOILERPLATE_RE.sub(_harvest_boilerplate_block(slugs), body, count=1)
    if _HARVEST_BOILERPLATE_SHORT_RE.search(body):
        short_block = (
            f"Named by {len(slugs)} source page(s):\n\n"
            + "\n".join(f"- [[{s}]]" for s in slugs)
            + "\n"
        )
        return _HARVEST_BOILERPLATE_SHORT_RE.sub(short_block, body, count=1)
    return body

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
    """Fill an empty ``## Key Facts`` from cited source pages (#147 / #103).

    Resolves ``sources:`` frontmatter and Connections wikilinks that point at
    ``wiki/sources/`` pages. When ``synthesizer`` is missing or not LLM-backed
    (the promote path), concatenates nested ``fact:`` lines from
    :func:`llmwiki.source_topics.parse_source_topics` on those pages, each
    suffixed `` [[slug]]``. If no facts are found, returns ``text`` unchanged
    and never raises.

    When ``synthesizer.is_llm`` (``rewrite_key_facts`` / ``force=True``), asks
    the backend to write declarative facts from a mention digest and raises
    ``KeyFactsBackendError`` if the backend is missing, unavailable, or
    returns no bullets.

    Non-empty Key Facts are left untouched unless ``force=True``.
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
    use_llm = synthesizer is not None and getattr(synthesizer, "is_llm", False)

    if not use_llm:
        if force:
            raise KeyFactsBackendError(
                f"{page_name}: rewriting Key Facts needs an LLM backend — set "
                'synthesis.backend to "claude" or "ollama" in config.json'
            )
        bullets = _topic_fact_bullets(wiki_dir, slugs, page_name)
        if not bullets:
            return text
        new_body = _inject_key_facts(body, bullets)
        fm_match = FRONTMATTER_RE.match(text)
        if fm_match:
            return f"---\n{fm_match.group(1)}\n---\n{new_body}"
        return new_body

    evidence = _evidence_digest(wiki_dir, slugs, page_name)
    if not evidence:
        if not force:
            return text
        fm_match = FRONTMATTER_RE.match(text)
        if fm_match:
            return f"---\n{fm_match.group(1)}\n---\n{body}"
        return body

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
    aligns ``type:`` with the destination folder. Fills an empty ``## Key
    Facts`` from source topic ``fact:`` lines offline (#147) — never calls
    ``synthesize_key_facts`` and never raises ``KeyFactsBackendError``.
    ``synthesizer`` is accepted for API compatibility with callers that still
    pass a backend; it is unused. Reconciles ``wiki/index.md`` afterward
    (#101).

    Returns the new (promoted) path. Raises FileNotFoundError if the
    candidate does not exist, or ``ValueError`` if ``dest_kind`` is invalid.
    """
    del synthesizer  # promote fills Key Facts offline (#147)
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
    text = fill_key_facts_from_evidence(text, wiki_dir, name=candidate.stem)
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
    """Locate ``wiki/<kind>/<slug>.md`` (entities/concepts by default).

    Same slug handling as the pending-stub lookup: sanitized, exact filename
    first, then a unique ``norm_page_key`` fold of the folder's filenames.
    """
    subs = [kind] if kind else ["entities", "concepts"]
    return _resolve_page_file(
        slug,
        wiki_dir,
        subs,
        label="trusted page",
        not_found=(
            f"trusted page not found: {slug!r} under {wiki_dir}"
            + (f" (kind={kind})" if kind else " (entities|concepts)")
        ),
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

    Promote fills empty Key Facts offline from source topic ``fact:`` lines
    (#147). This opt-in CLI force-fills via an LLM backend (and optionally
    drops pasted harvest-stub ``## Candidate merge`` blocks left by the old
    merge behaviour). Requires a real synthesizer — Dummy/None raise
    ``KeyFactsBackendError``.
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


def _record_alias(
    body: str, alias: str, source_count: int, today: str, *, verb: str = "merged",
) -> str:
    """Note the merged-away (or redirected) name under ``## Aliases``."""
    entry = format_alias_bullet(alias, f"{verb} {today} ({source_count} source pages)")
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
    target = _resolve_page_file(
        into_slug,
        wiki_dir,
        [inferred_kind, f"{CANDIDATES_DIR_NAME}/{inferred_kind}"],
        label="merge target",
        not_found=(
            f"merge target not found: {into_slug!r} under "
            f"{inferred_kind}/ or candidates/{inferred_kind}/"
        ),
    )
    if target == candidate:
        raise ValueError("cannot merge a candidate into itself")

    candidate_text = candidate.read_text(encoding="utf-8")
    candidate_meta, candidate_body = _parse_frontmatter(candidate_text)
    evidence = _evidence_source_slugs(candidate_meta, candidate_body, wiki_dir)
    prose = _reviewer_prose(candidate_body)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    merged = _union_sources_frontmatter(target.read_text(encoding="utf-8"), evidence)
    meta_text, body = _split_frontmatter_text(merged)
    body = _union_connections(body, evidence)
    merged_meta, _ = _parse_frontmatter(meta_text + "\n")
    all_evidence = _evidence_source_slugs(merged_meta, body, wiki_dir)
    body = _refresh_harvest_boilerplate(body, all_evidence)
    body = _record_alias(
        body, candidate_meta.get("title") or slug, len(evidence), today,
    )
    if prose:
        body = (
            body.rstrip() +
            f"\n\n## Candidate merge — {today}\n\n" +
            f"Merged from `{candidate.relative_to(wiki_dir)}`:\n\n" +
            prose + "\n"
        )
    target.write_text(meta_text + body, encoding="utf-8")

    # Discard candidate by moving it to archive with a merge-reason file
    _archive_candidate(candidate, wiki_dir, reason=_format_merge_reason(into_slug))
    _reconcile_catalog(wiki_dir)
    return target


@dataclass
class DiscardResult:
    """What :func:`discard` did: where the stub went and which links it fixed.

    The link counts are filled in when the rewrite runs — at return time for
    a lone discard, at :meth:`DiscardBatch.flush` for a batched one.
    """

    path: Path
    #: The candidate's name — its frontmatter ``title``, else its stem.
    name: str
    #: Stem of the page links now point at, or ``None`` when they were unlinked.
    redirect: str | None = None
    links_rewritten: int = 0
    #: Pages whose links were rewritten, relative to ``wiki/``.
    pages_changed: list[str] = field(default_factory=list)
    #: ``<page>: <error>`` for every page that could not be read and was left
    #: alone. Shared with the other results of the same :class:`DiscardBatch`.
    skipped: list[str] = field(default_factory=list)


@dataclass
class DiscardBatch:
    """Shared wiki state for a run of :func:`discard` calls (#282).

    A lone discard walks every live page twice — once to see whether another
    page already answers to the name, once to rewrite that name's links — so
    a review batch of N discards costs 2N full reads. A batch reads the live
    pages once, keeps that index current as stubs are archived and aliases
    recorded, and collects the rewrites so :meth:`flush` applies them all in
    one further pass. Each result's counts are filled in by that flush.
    """

    wiki_dir: Path
    #: ``<page>: <error>`` for every page the passes could not read.
    errors: list[str] = field(default_factory=list)
    #: ``norm_page_key`` → the live pages answering to it.
    owners: dict[str, list[Path]] = field(init=False)
    _pending: dict[str, str | None] = field(init=False, default_factory=dict)
    _results: dict[str, list[DiscardResult]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.owners = _live_page_owners(self.wiki_dir, errors=self.errors)

    def retire(self, path: Path) -> None:
        """Drop a page that just left the live set, such as an archived stub."""
        for key, paths in list(self.owners.items()):
            kept = [p for p in paths if p != path]
            if kept:
                self.owners[key] = kept
            else:
                del self.owners[key]

    def record_name(self, name: str, page: Path) -> None:
        """Note that ``page`` now answers to ``name`` too, via a new alias."""
        key = norm_page_key(name)
        if key and page not in self.owners.setdefault(key, []):
            self.owners[key].append(page)

    def defer(self, key: str, replacement: str | None, result: DiscardResult) -> None:
        """Collect one discard's rewrite into the shared pass."""
        if self._pending.get(key, replacement) != replacement:
            self.flush()
        self._pending[key] = replacement
        self._results.setdefault(key, []).append(result)

    def flush(self) -> None:
        """Apply every collected rewrite in one pass and fill in the counts."""
        if not self._pending:
            return
        pending, results = self._pending, self._results
        self._pending, self._results = {}, {}
        rewrite = rewrite_links_in_wiki(self.wiki_dir, pending, errors=self.errors)
        for key, rows in results.items():
            for result in rows:
                result.links_rewritten = rewrite.counts.get(key, 0)
                result.pages_changed = list(rewrite.pages_by_key.get(key, ()))


def discard(
    slug: str,
    wiki_dir: Path,
    *,
    reason: str = "",
    kind: str | None = None,
    redirect: str | None = None,
    batch: DiscardBatch | None = None,
) -> DiscardResult:
    """Move the candidate to ``wiki/archive/candidates/<timestamp>/<slug>.md``
    with an adjacent ``<slug>.reason.txt`` capturing why, then fix its links.

    Every ``[[link]]`` to the candidate's name outside ``wiki/archive/``
    (case/punctuation-insensitive) becomes plain text — its label, else the
    name as written — so the discard leaves no link into cold storage (#282).
    With ``redirect``, the links point at that existing live page instead,
    keep their visible text, and the name is recorded under the page's
    ``## Aliases`` so later links to it resolve there too. Links are left
    alone when another live page or alias already answers to the name.

    ``batch`` shares one live-page index and one rewrite pass across several
    discards; the result's link counts are filled in by
    :meth:`DiscardBatch.flush`.

    Raises ``FileNotFoundError`` when the candidate or the redirect page is
    missing and ``ValueError`` when the redirect is ambiguous, names the
    candidate itself, or when another live page already answers to the
    discarded name — all before anything moves, since recording the alias
    anyway would leave two live pages claiming one name. Reconciles
    ``wiki/index.md`` afterward (#101).
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    meta, body = _parse_frontmatter(candidate.read_text(encoding="utf-8"))
    name = meta.get("title") or candidate.stem
    source_count = len(_evidence_source_slugs(meta, body, wiki_dir))
    target = find_live_page(wiki_dir, redirect) if redirect else None
    if target is not None and norm_page_key(target.stem) == norm_page_key(name):
        raise ValueError(f"cannot redirect {name!r} to itself")

    skipped = batch.errors if batch is not None else []
    key = norm_page_key(name)
    owners = (
        batch.owners if batch is not None
        else _live_page_owners(wiki_dir, errors=skipped)
    )
    # The stub is still live here, so it answers to its own name: ignore it.
    resolvers = [page for page in owners.get(key, ()) if page != candidate]
    if target is not None:
        claimed = next((page for page in resolvers if page != target), None)
        if claimed is not None:
            raise ValueError(
                f"cannot redirect {name!r} to {target.stem!r}: "
                f"{claimed.relative_to(wiki_dir).as_posix()} already answers to "
                f"that name"
            )

    path = _archive_candidate(
        candidate, wiki_dir, reason=reason,
        redirect=target.stem if target is not None else None,
    )
    if batch is not None:
        batch.retire(candidate)
    result = DiscardResult(
        path=path,
        name=name,
        redirect=target.stem if target is not None else None,
        skipped=skipped,
    )
    if target is not None:
        record_redirect_alias(target, name, source_count=source_count)
        if batch is not None:
            batch.record_name(name, target)
    if key and not resolvers:
        replacement = target.stem if target is not None else None
        if batch is not None:
            batch.defer(key, replacement, result)
        else:
            rewrite = rewrite_links_in_wiki(
                wiki_dir, {key: replacement}, errors=skipped,
            )
            result.links_rewritten = sum(rewrite.counts.values())
            result.pages_changed = rewrite.pages
    _reconcile_catalog(wiki_dir)
    return result


def _iter_live_markdown(wiki_dir: Path) -> list[Path]:
    """Every ``*.md`` under ``wiki/`` outside cold storage, sorted."""
    if not wiki_dir.is_dir():
        return []
    return [
        path for path in sorted(wiki_dir.rglob("*.md"))
        if path.is_file() and not is_archived_path(path.relative_to(wiki_dir).parts)
    ]


def _note_skip(
    errors: list[str] | None, wiki_dir: Path, path: Path, exc: Exception,
) -> None:
    """Record a page a pass could not read, so no caller skips it silently.

    One entry per page however many passes trip over it.
    """
    if errors is None:
        return
    try:
        rel = path.relative_to(wiki_dir).as_posix()
    except ValueError:
        rel = str(path)
    entry = f"{rel}: {exc}"
    if entry not in errors:
        errors.append(entry)


def _live_page_owners(
    wiki_dir: Path, *, errors: list[str] | None = None,
) -> dict[str, list[Path]]:
    """``norm_page_key`` → the live pages answering to it: stems + aliases.

    Pending candidates count — their names are still under review. A page
    that cannot be read still owns its stem; only its aliases are lost, and
    the failure is appended to ``errors``.
    """
    owners: dict[str, list[Path]] = defaultdict(list)
    for path in _iter_live_markdown(wiki_dir):
        names = [path.stem]
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _note_skip(errors, wiki_dir, path, exc)
        else:
            names.extend(parse_page_aliases(text))
        for name in names:
            key = norm_page_key(name)
            if key and path not in owners[key]:
                owners[key].append(path)
    owners.pop("", None)
    return dict(owners)


def _live_page_keys(wiki_dir: Path, *, errors: list[str] | None = None) -> set[str]:
    """``norm_page_key`` of every name a live page answers to: stems + aliases."""
    return set(_live_page_owners(wiki_dir, errors=errors))


def archived_candidate_names(
    wiki_dir: Path, *, errors: list[str] | None = None,
) -> dict[str, str]:
    """``norm_page_key -> name`` for every stub under ``wiki/archive/candidates/``.

    The name is the stub's frontmatter ``title``, else its stem. Merged and
    discarded stubs alike: this is the dismissal ledger harvest consults.
    A stub that cannot be read is appended to ``errors`` instead of being
    dropped without a word.
    """
    root = archive_dir(wiki_dir)
    names: dict[str, str] = {}
    if not root.is_dir():
        return names
    for path in sorted(root.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _note_skip(errors, wiki_dir, path, exc)
            continue
        meta, _ = _parse_frontmatter(text)
        name = meta.get("title") or path.stem
        key = norm_page_key(name)
        if key:
            names.setdefault(key, name)
    return names


def discarded_names(
    wiki_dir: Path,
    *,
    live_keys: Collection[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, str]:
    """``norm_page_key -> name`` for candidates a reviewer discarded for good.

    Archived stubs whose name no live page answers to — neither by stem nor
    under ``## Aliases``. Merged and redirected names are excluded: they
    resolve through the alias the survivor page records. Shared by the topic
    vocabulary and ``migrate discarded-topic-links`` so both agree on what
    was dismissed (#282). ``live_keys`` lets a caller that already scanned
    the wiki pass its stem/alias keys instead of re-reading every page, and
    ``errors`` collects the pages neither pass could read.
    """
    live = (
        set(live_keys) if live_keys is not None
        else _live_page_keys(wiki_dir, errors=errors)
    )
    return {
        key: name
        for key, name in archived_candidate_names(wiki_dir, errors=errors).items()
        if key not in live
    }


def merged_intents(
    wiki_dir: Path, *, errors: list[str] | None = None,
) -> dict[str, str]:
    """``norm_page_key -> recorded target`` for archived candidates a merge folded.

    Reads back the reason :func:`merge` wrote beside the stub, through the
    same formatter, so the reviewer's intent survives even when the survivor
    page was later renamed or re-filed and no longer answers to the
    merged-away name. Merges made before survivors recorded an ``## Aliases``
    entry have nothing else left to go on. ``migrate discarded-topic-links``
    uses this to tell a merge apart from a dismissal (#282). A stub that
    cannot be read is appended to ``errors`` instead of being dropped without
    a word.
    """
    root = archive_dir(wiki_dir)
    intents: dict[str, str] = {}
    if not root.is_dir():
        return intents
    for path in sorted(root.rglob("*.md")):
        reason_file = _reason_file(path)
        if not reason_file.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            reason = reason_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _note_skip(errors, wiki_dir, path, exc)
            continue
        target = _parse_merge_reason(
            _reason_field_value(reason, _REASON_FIELD_REASON)
        )
        if not target:
            continue
        meta, _ = _parse_frontmatter(text)
        key = norm_page_key(meta.get("title") or path.stem)
        if key:
            intents.setdefault(key, target)
    return intents


@dataclass(frozen=True)
class LinkRewrite:
    """What one :func:`rewrite_links_in_wiki` pass changed."""

    #: Links rewritten per ``norm_page_key``.
    counts: dict[str, int]
    #: Every page changed, relative to ``wiki/``, in walk order.
    pages: list[str]
    #: The pages changed for each key, so a batched caller can report per row.
    pages_by_key: dict[str, list[str]]


def rewrite_links_in_wiki(
    wiki_dir: Path,
    targets: Mapping[str, str | None],
    *,
    dry_run: bool = False,
    errors: list[str] | None = None,
) -> LinkRewrite:
    """Apply :func:`llmwiki.wikilinks.rewrite_wikilinks` to every live page.

    Walks ``wiki/**/*.md`` outside ``wiki/archive/`` — pending candidates
    included, so their evidence lists stop naming a dismissed page too. Each
    page is rewritten as itself, so a link retargeted at the page it already
    sits on becomes plain text instead of a self-link. ``dry_run`` counts
    without writing, and a page that cannot be read is appended to ``errors``
    rather than skipped without a word.
    """
    totals: dict[str, int] = defaultdict(int)
    changed: list[str] = []
    by_key: dict[str, list[str]] = defaultdict(list)
    if not targets:
        return LinkRewrite(counts={}, pages=changed, pages_by_key={})
    for path in _iter_live_markdown(wiki_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _note_skip(errors, wiki_dir, path, exc)
            continue
        new_text, counts = rewrite_wikilinks(text, targets, self_stem=path.stem)
        if not counts or new_text == text:
            continue
        if not dry_run:
            path.write_text(new_text, encoding="utf-8")
        rel = path.relative_to(wiki_dir).as_posix()
        for key, n in counts.items():
            totals[key] += n
            by_key[key].append(rel)
        changed.append(rel)
    return LinkRewrite(
        counts=dict(totals), pages=changed, pages_by_key=dict(by_key),
    )


def rewrite_links_to(
    wiki_dir: Path,
    targets: Mapping[str, str | None],
    *,
    dry_run: bool = False,
    errors: list[str] | None = None,
) -> tuple[dict[str, int], list[str]]:
    """``(links rewritten per key, pages changed)`` of one rewrite pass.

    Thin view over :func:`rewrite_links_in_wiki` for callers that report a
    whole pass rather than per key.
    """
    rewrite = rewrite_links_in_wiki(
        wiki_dir, targets, dry_run=dry_run, errors=errors,
    )
    return rewrite.counts, rewrite.pages


def redirect_target_pages(wiki_dir: Path) -> list[Path]:
    """Every page a redirect may land on, in walk order.

    Live means outside ``wiki/candidates/`` and ``wiki/archive/``: a redirect
    must land on a page that is staying, and a ``_``-prefixed folder-context
    stub is not a page. Shared by :func:`find_live_page` and the redirect
    suggestions of ``migrate discarded-topic-links`` so both offer the same
    set of pages.
    """
    candidates_root = candidates_dir(wiki_dir)
    return [
        path for path in _iter_live_markdown(wiki_dir)
        if not path.is_relative_to(candidates_root)
        and not path.name.startswith("_")
    ]


def find_live_page(wiki_dir: Path, name: str) -> Path:
    """Locate the existing live page a redirect names.

    Searches :func:`redirect_target_pages`: exact stem first, then a unique
    ``norm_page_key`` match. Raises ``FileNotFoundError`` when nothing
    matches and ``ValueError`` when the folded name is ambiguous.
    """
    return _resolve_page_file(
        name.strip(),
        wiki_dir,
        (),
        pool=redirect_target_pages(wiki_dir),
        label="redirect target",
        not_found=(
            f"redirect target not found: {name!r} is not an existing page under "
            f"{wiki_dir} (candidates and archive do not count)"
        ),
    )


def record_redirect_alias(
    page: Path, name: str, *, source_count: int, dry_run: bool = False,
) -> bool:
    """List ``name`` under ``page``'s ``## Aliases`` unless it already is.

    Uses the same ``## Aliases`` bullet as ``merge`` so
    :func:`llmwiki.wikilinks.build_page_alias_map` resolves the name to
    ``page``. ``source_count`` is the number of source pages that backed the
    redirected name, computed by the caller before any links were rewritten.
    Returns whether the page changed (or would, under ``dry_run``).
    """
    text = page.read_text(encoding="utf-8")
    key = norm_page_key(name)
    if any(norm_page_key(alias) == key for alias in parse_page_aliases(text)):
        return False
    if not dry_run:
        meta_text, body = _split_frontmatter_text(text)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        body = _record_alias(body, name, source_count, today, verb="redirected")
        page.write_text(meta_text + body, encoding="utf-8")
    return True


def archived_candidate_source_count(wiki_dir: Path, key: str) -> int:
    """Evidence-source count for the archived stub answering to ``key``.

    Mirrors what :func:`merge` counts under ``## Aliases`` — the discarded
    candidate's own evidence sources — so a migrated ``--redirect`` records
    the same total a live ``discard --redirect`` would.
    """
    root = archive_dir(wiki_dir)
    if not root.is_dir():
        return 0
    for path in sorted(root.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        name = meta.get("title") or path.stem
        if norm_page_key(name) == key:
            return len(_evidence_source_slugs(meta, body, wiki_dir))
    return 0


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


def _contained(path: Path, root: Path) -> Path:
    """Return ``path`` once it is known to sit inside ``root``.

    Backstop for every reviewer-supplied slug: a name that walks out of the
    vault (``../../elsewhere``) is refused instead of read or written.
    """
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes {root}: {path}")
    return path


def _resolve_page_file(
    slug: str,
    wiki_dir: Path,
    subdirs: Sequence[str],
    *,
    pool: Iterable[Path] | None = None,
    label: str,
    not_found: str,
) -> Path:
    """Resolve a reviewer-supplied ``slug`` to one markdown page under ``wiki_dir``.

    The one slug→path resolver every ``candidates`` action shares: the stub
    lookup, the trusted-page lookup, the ``merge --into`` target, and the
    ``discard --redirect`` target. ``slug`` is sanitized through
    :func:`candidate_filename`, so a name carrying a path separator can only
    ever name a file inside the searched folders, and the returned path is
    checked against ``wiki_dir`` as a backstop.

    ``subdirs`` are the folders under ``wiki_dir`` to search, in priority
    order. Pass ``pool`` to search a ready-made set of pages instead (a
    whole-tree walk, say); ``subdirs`` is then empty and unused.

    An exact filename match wins. Failing that, a unique
    :func:`llmwiki.wikilinks.norm_page_key` fold of the searched filenames
    resolves, so a differently-cased or differently-punctuated slug still
    finds its page. ``_``-prefixed files are folder-context stubs, not pages,
    and never resolve. ``label`` names the thing being looked up in the
    ambiguity message; ``not_found`` is raised verbatim as
    ``FileNotFoundError``.
    """
    if not slug.strip():
        raise FileNotFoundError(not_found)
    filename = candidate_filename(slug)
    key = norm_page_key(slug)
    folded: list[Path] = []
    if pool is None:
        for sub in subdirs:
            path = wiki_dir / sub / filename
            if path.is_file() and not path.name.startswith("_"):
                return _contained(path, wiki_dir)
        if key:
            for sub in subdirs:
                sub_dir = wiki_dir / sub
                if not sub_dir.is_dir():
                    continue
                for path in sorted(sub_dir.glob("*.md")):
                    if path.name.startswith("_"):
                        continue
                    if norm_page_key(path.stem) == key:
                        folded.append(path)
    else:
        for path in pool:
            if path.name == filename:
                return _contained(path, wiki_dir)
            if key and norm_page_key(path.stem) == key:
                folded.append(path)
    if len(folded) == 1:
        return _contained(folded[0], wiki_dir)
    if folded:
        found = ", ".join(p.relative_to(wiki_dir).as_posix() for p in folded)
        raise ValueError(f"{label} {slug!r} is ambiguous: {found}")
    raise FileNotFoundError(not_found)


def _find_candidate(
    slug: str,
    wiki_dir: Path,
    kind: str | None,
) -> Path:
    """Locate a pending stub under wiki/candidates/, optionally filtered by kind.

    Exact filename match wins first. Failing that, falls back to a unique
    :func:`llmwiki.wikilinks.norm_page_key` fold of pending stub filenames, so
    a case or punctuation variant of the stub's name (``Junk`` for a stub
    written ``JUNK.md``, or a sanitized ``/`` in the name) still resolves.
    Raises ``ValueError`` when the fold matches more than one pending stub.
    """
    subs = [kind] if kind else MIRRORED_SUBDIRS
    return _resolve_page_file(
        slug,
        wiki_dir,
        [f"{CANDIDATES_DIR_NAME}/{sub}" for sub in subs],
        label="candidate",
        not_found=(
            f"candidate not found: {slug!r} under {candidates_dir(wiki_dir)}"
            + (f" (kind={kind})" if kind else "")
        ),
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


#: Field label of the reason file line that says why a candidate was archived.
_REASON_FIELD_REASON = "Reason"

#: What :func:`merge` records as its reason, ahead of the target it folded the
#: candidate into. The only thing that tells a merge apart from a free-text
#: dismissal once the stub is in cold storage.
_MERGE_REASON_PREFIX = "merged into "


def _reason_file(archived: Path) -> Path:
    """The reason file that belongs beside an archived candidate stub."""
    return archived.with_suffix(".reason.txt")


def _reason_field(label: str, value: object) -> str:
    """One ``<label>: <value>`` line of an archived candidate's reason file."""
    return f"{label}: {value}"


def _reason_field_value(text: str, label: str) -> str:
    """Value ``label`` carries in a reason file, ``""`` when it carries none.

    Reads the line :func:`_reason_field` writes, through the same formatter,
    so no caller has to restate the file's layout.
    """
    prefix = _reason_field(label, "")
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _format_merge_reason(into_slug: str) -> str:
    """The reason :func:`merge` records for the candidate it folded away."""
    return f"{_MERGE_REASON_PREFIX}{into_slug}"


def _parse_merge_reason(reason: str) -> str:
    """Target in a :func:`_format_merge_reason` reason, ``""`` when it is not one."""
    if not reason.startswith(_MERGE_REASON_PREFIX):
        return ""
    return reason[len(_MERGE_REASON_PREFIX):].strip()


def _archive_candidate(
    candidate: Path,
    wiki_dir: Path,
    *,
    reason: str,
    redirect: str | None = None,
) -> Path:
    """Move candidate into archive with reason file.

    The reason file is written whenever there is a reason or a redirect.
    """
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    dest_dir = archive_dir(wiki_dir) / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    original = candidate.relative_to(wiki_dir).as_posix()
    dest = dest_dir / candidate.name
    shutil.move(str(candidate), str(dest))

    if reason or redirect:
        reason_file = _reason_file(dest)
        lines = [
            _reason_field("Discarded at", datetime.now(UTC).isoformat()),
            _reason_field(_REASON_FIELD_REASON, reason),
            _reason_field("Original path", original),
        ]
        if redirect:
            lines.append(_reason_field("Redirected to", redirect))
        reason_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
