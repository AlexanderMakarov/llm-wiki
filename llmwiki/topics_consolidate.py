"""Topic consolidation pass (#54).

A one-time (or occasional) LLM migration that turns the noisy auto-extracted
topic list into a clean controlled vocabulary: it merges duplicates, drops
incidental noise, and writes a one-line **description** per canonical topic.

The expensive part is a *single* LLM call over the topic *names* (~hundreds),
not the 940 session bodies — so it costs a tiny fraction of a full re-synth.
Its output is cached (autonomously, no hand-editing) and consumed by:

* the topic graph + pages (apply the merge-map — zero further tokens), and
* the regular synth prompt (inject lean ``name`` + ``description`` entries).

Two prompts now live in ``synth/prompts/``: ``source_page.md`` (regular,
per-session) and ``topic_consolidation.md`` (this dedup/migration pass) — the
latter doubles as a reusable template for future vocabulary migrations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

CONSOLIDATION_PROMPT_PATH = (
    Path(__file__).parent / "synth" / "prompts" / "topic_consolidation.md"
)
CACHE_FILENAME = ".llmwiki-topics.json"

# Only feed topics that clear this many sessions to the consolidator — one-off
# mentions are noise the pass would drop anyway, and excluding them keeps the
# single prompt to a sane size.
_CANDIDATE_MIN_SESSIONS = 2


def cache_path(wiki_dir: Path | None) -> Path:
    """Location of the consolidation cache (vault root, beside other state)."""
    from llmwiki.graph import WIKI_DIR

    base = (wiki_dir or WIKI_DIR).parent
    return base / CACHE_FILENAME


def _attr(value: str) -> str:
    return value.replace('"', "").replace("{", "").replace("}", "").replace("\n", " ").strip()


def build_candidates(wiki_dir: Path | None = None) -> list[dict[str, Any]]:
    """Candidate topics for the consolidator: name, reach, aka, with, sample."""
    from llmwiki.topics import build_topic_graph

    g = build_topic_graph(wiki_dir, min_sessions=_CANDIDATE_MIN_SESSIONS)
    sessions = g.get("sessions", {})
    related: dict[str, list[tuple[int, str]]] = {}
    for e in g.get("edges", []):
        related.setdefault(e["source"], []).append((e["weight"], e["target"]))
        related.setdefault(e["target"], []).append((e["weight"], e["source"]))

    out: list[dict[str, Any]] = []
    for n in g.get("nodes", []):
        rel = [r[1] for r in sorted(related.get(n["id"], []), reverse=True)[:4]]
        sample = ""
        for slug in n.get("sessions", []):
            title = (sessions.get(slug) or {}).get("title")
            if title:
                sample = title
                break
        out.append({
            "name": n["id"],
            "sessions": n.get("session_count", 0),
            "aka": [a for a in n.get("aliases", []) if a != n["id"]],
            "with": rel,
            "sample": sample,
        })
    return out


def render_consolidation_prompt(wiki_dir: Path | None = None) -> str:
    """Fill ``topic_consolidation.md``'s ``{candidates}`` with XML entries."""
    template = CONSOLIDATION_PROMPT_PATH.read_text(encoding="utf-8")
    lines = []
    for c in build_candidates(wiki_dir):
        attrs = f'name="{_attr(c["name"])}" sessions="{c["sessions"]}"'
        if c["aka"]:
            attrs += f' aka="{", ".join(_attr(a) for a in c["aka"][:6])}"'
        if c["with"]:
            attrs += f' with="{", ".join(_attr(w) for w in c["with"])}"'
        if c["sample"]:
            attrs += f' sample="{_attr(c["sample"])[:80]}"'
        lines.append(f"  <candidate {attrs} />")
    return template.replace("{candidates}", "\n".join(lines))


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the model's JSON output, tolerating ```json fences / stray prose."""
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
    if fence:
        s = fence.group(1)
    else:
        # Fall back to the outermost { ... } span.
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end > start:
            s = s[start:end + 1]
    return json.loads(s)


def parse_and_cache(result_text: str, wiki_dir: Path | None = None) -> dict[str, Any]:
    """Validate the consolidation result + persist it to the cache.

    Returns the normalised cache dict. Raises ``ValueError`` on malformed input
    so a bad LLM response never silently writes a broken vocabulary.
    """
    data = _extract_json(result_text)
    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("consolidation result has no 'topics' list")
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t in topics:
        canonical = str(t.get("canonical", "")).strip()
        if not canonical or canonical.lower() in seen:
            continue
        seen.add(canonical.lower())
        clean.append({
            "canonical": canonical,
            "description": str(t.get("description", "")).strip(),
            "aliases": [str(a).strip() for a in t.get("aliases", []) if str(a).strip()],
            "distinct_from": t.get("distinct_from", []) or [],
        })
    cache = {"version": 1, "topics": clean, "dropped": data.get("dropped", []) or []}
    out = cache_path(wiki_dir)
    out.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    return cache


def load_cache(wiki_dir: Path | None = None) -> Optional[dict[str, Any]]:
    """Load the consolidation cache, or ``None`` when absent/unreadable.

    Returns ``{"topics": [...], "alias_map": {lower_spelling: canonical},
    "descriptions": {canonical: text}, "dropped": [noise, ...]}`` for easy
    consumption.
    """
    p = cache_path(wiki_dir)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    topics = raw.get("topics") or []
    alias_map: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    for t in topics:
        canon = t.get("canonical")
        if not canon:
            continue
        descriptions[canon] = t.get("description", "")
        alias_map[canon.lower()] = canon
        for a in t.get("aliases", []):
            alias_map[str(a).lower()] = canon
    return {
        "topics": topics,
        "alias_map": alias_map,
        "descriptions": descriptions,
        "dropped": raw.get("dropped") or [],
    }
