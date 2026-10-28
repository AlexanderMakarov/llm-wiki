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

import hashlib
import json
import logging
import re
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

from llmwiki import REPO_ROOT
from llmwiki.config_schedule import resolve_vault_dir
from llmwiki.synth.base import BackendUsageLimitError

_VALID_KINDS = frozenset({"entity", "concept"})

CONSOLIDATION_PROMPT_PATH = (
    Path(__file__).parent / "synth" / "prompts" / "topic_consolidation.md"
)
CACHE_FILENAME = ".llmwiki-topics.json"
# Schema v2 (#264): inputs_fingerprint + optional per-topic source_sig.
# v1 files load as cold; next successful write migrates to v2.
CACHE_VERSION = 2

# Only feed topics that clear this many sessions to the consolidator — one-off
# mentions are noise the pass would drop anyway, and excluding them keeps the
# single prompt to a sane size.
_CANDIDATE_MIN_SESSIONS = 2

# Known-names preparation (#264 / @spec: 325-known-names-prep): cross-backend
# synthesis.known_names.* defaults. Cap bounds candidates sent to the model;
# timeout floor is generous relative to measured ~1 minute cold runs.
DEFAULT_KNOWN_NAMES_CANDIDATE_CAP = 150
DEFAULT_KNOWN_NAMES_TIMEOUT_FLOOR = 600


class KnownNamesConfig(NamedTuple):
    """Resolved ``synthesis.known_names`` policy for prepare_known_names."""

    candidate_cap: int
    timeout: int


def resolve_known_names_config(
    cfg: dict[str, Any] | None,
    backend_page_timeout: float | int,
) -> KnownNamesConfig:
    """Read ``synthesis.known_names.candidate_cap`` / ``timeout`` (#264).

    Defaults when unset: cap ``150``; timeout ``max(600, backend_page_timeout)``.
    Missing keys are silent (stock configs omit the block). Invalid or
    non-positive ints warn and fall back — same tolerance as
    :func:`llmwiki.synth.pipeline.resolve_synth_concurrency`.
    """
    logger = logging.getLogger(__name__)
    synth_cfg = (cfg or {}).get("synthesis", {}) or {}
    kn_cfg = synth_cfg.get("known_names", {}) or {}
    if not isinstance(kn_cfg, dict):
        logger.warning(
            "Invalid synthesis.known_names %r — expected a mapping; "
            "falling back to defaults",
            kn_cfg,
        )
        kn_cfg = {}

    try:
        page_timeout = int(backend_page_timeout)
    except (TypeError, ValueError):
        page_timeout = 0
    default_timeout = max(DEFAULT_KNOWN_NAMES_TIMEOUT_FLOOR, page_timeout)

    if "candidate_cap" not in kn_cfg:
        candidate_cap = DEFAULT_KNOWN_NAMES_CANDIDATE_CAP
    else:
        raw_cap = kn_cfg.get("candidate_cap")
        # bool is an int subclass: True would otherwise resolve to cap 1.
        if isinstance(raw_cap, bool) or not isinstance(raw_cap, int) or raw_cap < 1:
            logger.warning(
                "Invalid synthesis.known_names.candidate_cap %r — must be a "
                "positive integer; falling back to %d",
                raw_cap,
                DEFAULT_KNOWN_NAMES_CANDIDATE_CAP,
            )
            candidate_cap = DEFAULT_KNOWN_NAMES_CANDIDATE_CAP
        else:
            candidate_cap = raw_cap

    if "timeout" not in kn_cfg:
        timeout = default_timeout
    else:
        raw_timeout = kn_cfg.get("timeout")
        if (
            isinstance(raw_timeout, bool)
            or not isinstance(raw_timeout, int)
            or raw_timeout < 1
        ):
            logger.warning(
                "Invalid synthesis.known_names.timeout %r — must be a "
                "positive integer (seconds); falling back to %d",
                raw_timeout,
                default_timeout,
            )
            timeout = default_timeout
        else:
            timeout = raw_timeout

    return KnownNamesConfig(candidate_cap=candidate_cap, timeout=timeout)


def cache_path(wiki_dir: Path | None) -> Path:
    """Location of the consolidation cache (vault root, beside other state)."""

    base = resolve_vault_dir(wiki_dir, REPO_ROOT / "wiki", "wiki").parent
    return base / CACHE_FILENAME


def _attr(value: str) -> str:
    return value.replace('"', "").replace("{", "").replace("}", "").replace("\n", " ").strip()


def build_candidates(wiki_dir: Path | None = None) -> list[dict[str, Any]]:
    """Candidate topics for the consolidator: name, reach, aka, with, sample."""
    from llmwiki.topics import build_topic_graph  # noqa: PLC0415 — cycle: topics↔topics_consolidate

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


def cap_candidates(
    candidates: list[dict[str, Any]],
    cap: int,
) -> list[dict[str, Any]]:
    """Keep at most ``cap`` candidates, highest session reach first (#264).

    Sort key: ``sessions`` descending, then ``name`` ascending for a stable
    cut. Does not mutate ``candidates``.
    """
    if cap < 1:
        return []
    ordered = sorted(
        candidates,
        key=lambda c: (-int(c.get("sessions") or 0), str(c.get("name") or "")),
    )
    return ordered[:cap]


def reach_bucket(sessions: int) -> str:
    """Map session reach to a coarse bucket for incremental reuse (#264).

    Buckets invalidate only on meaningful growth, not every +1 session:
    ``2-3``, ``4-7``, ``8-15``, ``16-31``, ``32+``. Values below the
    candidate floor (<2) use ``1`` so signatures stay well-defined.
    """
    n = int(sessions)
    if n >= 32:
        return "32+"
    if n >= 16:
        return "16-31"
    if n >= 8:
        return "8-15"
    if n >= 4:
        return "4-7"
    if n >= 2:
        return "2-3"
    return "1"


def candidate_source_sig(candidate: Mapping[str, Any]) -> str:
    """Per-candidate signature: ``casefold(name) | sorted aka | bucket``.

    Used as the optional per-topic ``source_sig`` in the v2 cache and as the
    unit hashed into :func:`inputs_fingerprint`.
    """
    name = str(candidate.get("name") or "").casefold()
    aka_raw = candidate.get("aka") or []
    aka_sorted = sorted(str(a).casefold() for a in aka_raw if str(a).strip())
    bucket = reach_bucket(int(candidate.get("sessions") or 0))
    return f"{name} | {','.join(aka_sorted)} | {bucket}"


def inputs_fingerprint(candidates: list[dict[str, Any]]) -> str:
    """SHA-256 hex over sorted per-candidate signatures of a capped set (#264)."""
    sigs = sorted(candidate_source_sig(c) for c in candidates)
    payload = "\n".join(sigs).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def render_consolidation_prompt(
    wiki_dir: Path | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> str:
    """Fill ``topic_consolidation.md``'s ``{candidates}`` with XML entries.

    Pass an explicit ``candidates`` list (e.g. already capped) so callers and
    tests do not re-scan the topic graph. When omitted, builds from
    ``wiki_dir`` via :func:`build_candidates` (uncapped).
    """
    template = CONSOLIDATION_PROMPT_PATH.read_text(encoding="utf-8")
    rows = candidates if candidates is not None else build_candidates(wiki_dir)
    lines = []
    for c in rows:
        attrs = f'name="{_attr(c["name"])}" sessions="{c["sessions"]}"'
        if c.get("aka"):
            attrs += f' aka="{", ".join(_attr(a) for a in c["aka"][:6])}"'
        if c.get("with"):
            attrs += f' with="{", ".join(_attr(w) for w in c["with"])}"'
        if c.get("sample"):
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


def _load_cache_file(wiki_dir: Path | None) -> dict[str, Any] | None:
    """Raw on-disk ``.llmwiki-topics.json`` dict, or ``None`` if absent/bad."""
    path = cache_path(wiki_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _topic_source_sigs(topics: list[Any]) -> set[str]:
    """Collect non-empty ``source_sig`` values from cached topic entries."""
    out: set[str] = set()
    for t in topics:
        if not isinstance(t, Mapping):
            continue
        sig = t.get("source_sig")
        if isinstance(sig, str) and sig.strip():
            out.add(sig.strip())
    return out


def _covered_sigs(raw: dict[str, Any] | None) -> set[str]:
    """Signatures already settled: per-topic ``source_sig`` plus ``settled_sigs``.

    ``settled_sigs`` records every capped candidate processed in a prior
    successful prepare — including names the model put in ``dropped`` — so
    noise is not re-prompted on every delta run.
    """
    if not raw:
        return set()
    covered = _topic_source_sigs(list(raw.get("topics") or []))
    for sig in raw.get("settled_sigs") or []:
        if isinstance(sig, str) and sig.strip():
            covered.add(sig.strip())
    return covered


def _delta_candidates(
    capped: list[dict[str, Any]],
    covered_sigs: set[str],
) -> list[dict[str, Any]]:
    """Capped candidates whose signature is missing or changed vs cache."""
    return [c for c in capped if candidate_source_sig(c) not in covered_sigs]


def _normalize_topic_entry(
    t: Mapping[str, Any],
    *,
    sigs_by_key: Mapping[str, str],
) -> dict[str, Any] | None:
    """Build one cache topic dict from a reply/row mapping, or ``None`` to skip."""
    canonical = str(t.get("canonical", "")).strip()
    if not canonical:
        return None
    entry: dict[str, Any] = {
        "canonical": canonical,
        "description": str(t.get("description", "")).strip(),
        "aliases": [str(a).strip() for a in t.get("aliases", []) if str(a).strip()],
        "distinct_from": t.get("distinct_from", []) or [],
    }
    kind_raw = t.get("kind")
    if isinstance(kind_raw, str):
        kind = kind_raw.strip().lower()
        if kind in _VALID_KINDS:
            entry["kind"] = kind
    reply_sig = t.get("source_sig")
    if isinstance(reply_sig, str) and reply_sig.strip():
        entry["source_sig"] = reply_sig.strip()
    else:
        matched = sigs_by_key.get(canonical.casefold())
        if matched:
            entry["source_sig"] = matched
    return entry


def _merge_dropped(
    existing: list[Any],
    reply_dropped: list[Any],
    topic_keys: set[str],
) -> list[Any]:
    """Union dropped lists; drop spellings that are now live topics."""
    merged: list[Any] = []
    seen: set[str] = set()
    for item in list(existing) + list(reply_dropped):
        key = str(item).strip().casefold()
        if not key or key in seen or key in topic_keys:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def parse_and_cache(
    result_text: str,
    wiki_dir: Path | None = None,
    *,
    inputs_fingerprint: str | None = None,
    source_sigs: Mapping[str, str] | None = None,
    settled_sigs: list[str] | None = None,
    merge_into: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the consolidation result + persist it to the cache.

    Always writes schema :data:`CACHE_VERSION` (v2), migrating any prior v1
    file on the next successful write. Optional ``inputs_fingerprint`` (capped
    candidate-set hash), ``source_sigs`` (casefold name → signature), and
    ``settled_sigs`` (all capped signatures processed, including drops) are
    stored when provided so a later prepare step can skip or delta-merge
    without re-asking unchanged topics (#264).

    When ``merge_into`` is the existing cache dict, reply topics overwrite
    matching canonicals and all other topics stay (including ``description``,
    ``aliases``, ``kind``, ``distinct_from``, ``source_sig``). If the reply
    omits ``kind`` for an updated name that already had one, the prior ``kind``
    is kept (#257).

    Returns the normalised cache dict. Raises ``ValueError`` on malformed input
    so a bad LLM response never silently writes a broken vocabulary.
    """
    data = _extract_json(result_text)
    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("consolidation result has no 'topics' list")
    sigs_by_key: dict[str, str] = {}
    if source_sigs:
        sigs_by_key = {str(k).casefold(): v for k, v in source_sigs.items()}
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t in topics:
        if not isinstance(t, Mapping):
            continue
        entry = _normalize_topic_entry(t, sigs_by_key=sigs_by_key)
        if entry is None:
            continue
        key = entry["canonical"].casefold()
        if key in seen:
            continue
        seen.add(key)
        clean.append(entry)

    if not clean:
        raise ValueError("consolidation result has no 'topics' list")

    reply_dropped = data.get("dropped", []) or []
    if merge_into is not None:
        existing_topics = [
            t for t in (merge_into.get("topics") or []) if isinstance(t, Mapping)
        ]
        by_key: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for old in existing_topics:
            canon = str(old.get("canonical", "")).strip()
            if not canon:
                continue
            key = canon.casefold()
            if key in by_key:
                continue
            by_key[key] = dict(old)
            order.append(key)
        for entry in clean:
            key = entry["canonical"].casefold()
            old = by_key.get(key)
            if old is not None:
                # Reply wins for fields it carries; keep kind / source_sig when
                # the model omitted them so reuse never strips #257 kinds.
                if "kind" not in entry:
                    old_kind = old.get("kind")
                    if isinstance(old_kind, str) and old_kind.strip().lower() in _VALID_KINDS:
                        entry["kind"] = old_kind.strip().lower()
                if "source_sig" not in entry:
                    old_sig = old.get("source_sig")
                    if isinstance(old_sig, str) and old_sig.strip():
                        entry["source_sig"] = old_sig.strip()
                by_key[key] = entry
            else:
                by_key[key] = entry
                order.append(key)
        clean = [by_key[k] for k in order]
        topic_keys = {t["canonical"].casefold() for t in clean}
        dropped = _merge_dropped(
            list(merge_into.get("dropped") or []),
            list(reply_dropped) if isinstance(reply_dropped, list) else [],
            topic_keys,
        )
    else:
        dropped = reply_dropped if isinstance(reply_dropped, list) else []

    cache: dict[str, Any] = {
        "version": CACHE_VERSION,
        "topics": clean,
        "dropped": dropped,
    }
    if inputs_fingerprint is not None:
        cache["inputs_fingerprint"] = inputs_fingerprint
    if settled_sigs is not None:
        cache["settled_sigs"] = list(settled_sigs)
    elif merge_into is not None and merge_into.get("settled_sigs"):
        cache["settled_sigs"] = list(merge_into["settled_sigs"])
    out = cache_path(wiki_dir)
    out.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    return cache


def format_prompt_size(n_bytes: int) -> str:
    """Compact approximate size for a progress line, e.g. ``~95 KB`` or ``~1.2 MB``."""
    if n_bytes >= 1024 * 1024:
        return f"~{n_bytes / (1024 * 1024):.1f} MB"
    return f"~{max(1, round(n_bytes / 1024))} KB"


def _usage_snapshot(backend: Any) -> tuple[int | None, float | None]:
    """Best-effort ``(tokens, cost_usd)`` from ``backend.take_usage``, else Nones."""
    take = getattr(backend, "take_usage", None)
    if not callable(take):
        return None, None
    try:
        tokens, cost = take()
    except Exception:
        return None, None
    tok = int(tokens) if isinstance(tokens, (int, float)) else None
    usd = float(cost) if isinstance(cost, (int, float)) else None
    return tok, usd


def _usage_for_call(
    before: tuple[int | None, float | None],
    after: tuple[int | None, float | None],
) -> tuple[int | None, float | None]:
    """Delta usage attributable to one call; omit fields that are not attributable."""
    bt, bc = before
    at, ac = after
    tokens: int | None = None
    cost: float | None = None
    if at is not None:
        if bt is None:
            tokens = at
        else:
            delta = at - bt
            # No increase while prior usage existed → not from this call.
            if delta > 0 or bt == 0:
                tokens = delta
    if ac is not None:
        if bc is None:
            cost = ac
        else:
            delta_c = ac - bc
            if delta_c > 0 or bc == 0.0:
                cost = delta_c
    return tokens, cost


def format_known_names_report(
    *,
    mode: str,
    considered: int,
    sent: int,
    prompt_bytes: int,
    reply_bytes: int,
    duration_s: float,
    tokens: int | None = None,
    cost_usd: float | None = None,
) -> str:
    """One-line stats for known-names prep (#264 §2.6).

    Always includes mode, candidate counts, prompt/reply byte sizes, and
    duration. Tokens / cost are appended only when the caller has values
    attributable to this step.
    """
    parts = [
        f"mode={mode}",
        f"considered={considered}",
        f"sent={sent}",
        f"prompt={prompt_bytes} B",
        f"reply={reply_bytes} B",
        f"duration={duration_s:.1f}s",
    ]
    if tokens is not None:
        parts.append(f"tokens={tokens:,}")
    if cost_usd is not None:
        parts.append(f"cost=${cost_usd:.4f}")
    return ", ".join(parts)


def _write_fingerprint_only(
    wiki_dir: Path,
    raw: dict[str, Any],
    fingerprint: str,
) -> None:
    """Persist v2 + fingerprint without changing topics (coverage already ok)."""
    updated = dict(raw)
    updated["version"] = CACHE_VERSION
    updated["inputs_fingerprint"] = fingerprint
    cache_path(wiki_dir).write_text(
        json.dumps(updated, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def prepare_known_names(
    wiki_dir: Path,
    backend: Any,
    *,
    cfg: dict[str, Any] | None = None,
) -> None:
    """One consolidation LLM call per synth run (job 1 / #147).

    Skips when ``backend`` is missing, non-LLM (``is_llm`` is false), or
    ``build_candidates`` is empty. Caps the candidate list via
    ``synthesis.known_names.candidate_cap`` (highest reach first), then
    either reuses a matching v2 cache, prompts with only the delta of new /
    changed candidate signatures, or (cold cache) sends the full capped set
    (#264). On success merges into ``.llmwiki-topics.json`` via
    :func:`parse_and_cache`, preserving untouched topics including ``kind``
    (#257). A :class:`BackendUsageLimitError` propagates so the caller can
    stop the run before any page (#181); on any other failure it prints a
    warning and returns without raising so the caller can fall back to
    heuristic vocabulary injection.

    Progress / warning lines always report mode (``full`` / ``delta`` /
    ``skip``), candidates considered and sent, prompt/reply bytes, and
    duration; tokens/cost appear when the backend exposes attributable run
    usage for the call (#264 §2.6).

    ``cfg`` is the sessions/config dict (or a test stub). When omitted, loads
    via :func:`llmwiki.config_schedule._load_sessions_config`.
    """
    if backend is None or not getattr(backend, "is_llm", False):
        return
    mode: str | None = None
    considered = 0
    sent = 0
    prompt_bytes = 0
    reply_bytes = 0
    t0 = time.perf_counter()
    try:
        candidates = build_candidates(wiki_dir)
        if not candidates:
            return
        if cfg is None:
            from llmwiki.config_schedule import (  # noqa: PLC0415 — avoid import cycle at module load
                _load_sessions_config,
            )

            cfg = _load_sessions_config()
        page_timeout = getattr(backend, "timeout", 0) or 0
        kn = resolve_known_names_config(cfg, page_timeout)
        capped = cap_candidates(candidates, kn.candidate_cap)
        if not capped:
            return
        considered = len(capped)
        t0 = time.perf_counter()

        fingerprint = inputs_fingerprint(capped)
        raw = _load_cache_file(wiki_dir)
        covered = _covered_sigs(raw)

        # Skip LLM when the capped set is unchanged. Fingerprint alone is
        # enough: dropped noise never gets a per-topic source_sig, so requiring
        # topic-level coverage would re-ask those names forever (#264 live vault).
        if (
            raw is not None
            and (raw.get("topics") or [])
            and raw.get("inputs_fingerprint") == fingerprint
        ):
            mode = "skip"
            stats = format_known_names_report(
                mode=mode,
                considered=considered,
                sent=0,
                prompt_bytes=0,
                reply_bytes=0,
                duration_s=time.perf_counter() - t0,
            )
            print(
                f"Reusing cached known names ({considered} candidate topic(s))… "
                f"({stats})",
                flush=True,
            )
            return

        delta = _delta_candidates(capped, covered)
        if not delta:
            # All sigs covered but fingerprint missing/stale — rewrite metadata.
            if raw is not None:
                _write_fingerprint_only(wiki_dir, raw, fingerprint)
                mode = "skip"
                stats = format_known_names_report(
                    mode=mode,
                    considered=considered,
                    sent=0,
                    prompt_bytes=0,
                    reply_bytes=0,
                    duration_s=time.perf_counter() - t0,
                )
                print(
                    f"Reusing cached known names ({considered} candidate "
                    f"topic(s); refreshed fingerprint)… ({stats})",
                    flush=True,
                )
            return

        prompt = render_consolidation_prompt(wiki_dir, candidates=delta)
        mode = "delta" if raw is not None and covered else "full"
        sent = len(delta)
        prompt_bytes = len(prompt.encode("utf-8"))
        # The call below can take a minute or more with no other output.
        print(
            f"Preparing known names ({mode}): {sent} of {considered} "
            f"candidate topic(s) "
            f"({format_prompt_size(prompt_bytes)} prompt) — "
            "one language-model call, may take a minute…",
            flush=True,
        )
        usage_before = _usage_snapshot(backend)
        reply = backend.synthesize_source_page(
            "",
            {"slug": "known-names", "title": "known-names"},
            prompt,
            timeout=float(kn.timeout),
        )
        reply_bytes = len((reply or "").encode("utf-8"))
        tokens, cost_usd = _usage_for_call(usage_before, _usage_snapshot(backend))
        # Topic source_sig for names in the reply; settled_sigs covers the
        # whole capped set (including model-dropped noise) for later deltas.
        sigs = {str(c["name"]): candidate_source_sig(c) for c in delta}
        settled = {candidate_source_sig(c) for c in capped}
        if raw is not None:
            settled |= {str(s) for s in (raw.get("settled_sigs") or []) if s}
        parse_and_cache(
            reply,
            wiki_dir,
            inputs_fingerprint=fingerprint,
            source_sigs=sigs,
            settled_sigs=sorted(settled),
            merge_into=raw,
        )
        print(
            "Known names ready ("
            + format_known_names_report(
                mode=mode,
                considered=considered,
                sent=sent,
                prompt_bytes=prompt_bytes,
                reply_bytes=reply_bytes,
                duration_s=time.perf_counter() - t0,
                tokens=tokens,
                cost_usd=cost_usd,
            )
            + ")",
            flush=True,
        )
    except BackendUsageLimitError:
        raise
    except Exception as exc:
        suffix = ""
        if mode is not None:
            suffix = (
                " ("
                + format_known_names_report(
                    mode=mode,
                    considered=considered,
                    sent=sent,
                    prompt_bytes=prompt_bytes,
                    reply_bytes=reply_bytes,
                    duration_s=time.perf_counter() - t0,
                )
                + ")"
            )
        print(
            f"  warning: prepare_known_names failed ({exc}); "
            f"using heuristic vocabulary{suffix}",
            file=sys.stderr,
        )


def load_cache(wiki_dir: Path | None = None) -> dict[str, Any] | None:
    """Load the consolidation cache, or ``None`` when absent/unreadable.

    Returns ``{"topics": [...], "alias_map": {lower_spelling: canonical},
    "descriptions": {canonical: text}, "kinds": {canonical: entity|concept},
    "dropped": [noise, ...]}`` for easy consumption. ``kinds`` only includes
    topics whose cached ``kind`` is in :data:`_VALID_KINDS`. v1 files (no
    fingerprint) still expose those consumer fields; v2 may also include
    ``inputs_fingerprint``. Per-topic ``source_sig`` stays on each topic dict.
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
    kinds: dict[str, str] = {}
    for t in topics:
        canon = t.get("canonical")
        if not canon:
            continue
        descriptions[canon] = t.get("description", "")
        alias_map[canon.lower()] = canon
        for a in t.get("aliases", []):
            alias_map[str(a).lower()] = canon
        kind_raw = t.get("kind")
        if isinstance(kind_raw, str):
            kind = kind_raw.strip().lower()
            if kind in _VALID_KINDS:
                kinds[canon] = kind
    out: dict[str, Any] = {
        "topics": topics,
        "alias_map": alias_map,
        "descriptions": descriptions,
        "kinds": kinds,
        "dropped": raw.get("dropped") or [],
    }
    fingerprint = raw.get("inputs_fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        out["inputs_fingerprint"] = fingerprint
    return out
