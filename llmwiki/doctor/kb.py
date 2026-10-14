"""Load and validate the bundled heal knowledge base (``heal_kb.json``)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from llmwiki.doctor.models import Finding, FixTier

#: Keys that must never appear in the catalog — failures are deleted, not archived.
_FORBIDDEN_ENTRY_KEYS = frozenset({"retired", "deprecated", "superseded_by"})

#: Prefix for regex patterns in ``patterns[]`` (stdlib ``re.search``).
_REGEX_PREFIX = "re:"

#: Absolute / home-ish paths collapsed during fingerprinting.
_ABS_PATH_RE = re.compile(
    r"(?:(?:/home|/Users|/var|/tmp|/mnt|/opt|/usr|/etc)/[^\s\"']+)"
    r"|(?:[A-Za-z]:\\[^\s\"']+)"
)
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9_.:/-]+")

_REQUIRED_TOP_KEYS = frozenset({"version", "areas", "entries", "unknown_templates"})
_REQUIRED_ENTRY_KEYS = frozenset(
    {
        "id",
        "area",
        "patterns",
        "message",
        "fix",
        "actionable",
        "severity",
        "tier",
        "runner",
    }
)
_VALID_AREAS = frozenset("ABCDEFGHIJKLMNO")
_VALID_TIERS = frozenset({"safe", "dangerous", "guided"})
_VALID_SEVERITIES = frozenset({"error", "warning", "info"})


class HealKBError(ValueError):
    """Raised when the bundled catalog is missing or fails schema checks."""


@dataclass(frozen=True)
class HealKB:
    """In-memory view of ``heal_kb.json``."""

    version: int
    areas: dict[str, dict[str, str]]
    entries: list[dict[str, Any]]
    unknown_templates: dict[str, str]
    matcher: dict[str, Any]
    _by_id: dict[str, dict[str, Any]]

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Return the catalog entry for ``entry_id``, or ``None``."""
        return self._by_id.get(entry_id)

    def list_areas(self) -> dict[str, dict[str, str]]:
        """Return area letter → ``{title, summary}`` (copy)."""
        return {k: dict(v) for k, v in self.areas.items()}

    def entries_for_area(self, area: str) -> list[dict[str, Any]]:
        """Return all entries whose ``area`` matches (catalog order)."""
        return [e for e in self.entries if e.get("area") == area]


def _reject_forbidden_keys(obj: Any, *, where: str) -> None:
    if isinstance(obj, dict):
        bad = _FORBIDDEN_ENTRY_KEYS & obj.keys()
        if bad:
            raise HealKBError(
                f"heal_kb.json {where}: forbidden key(s) {sorted(bad)}; "
                "delete obsolete entries instead of marking them retired/deprecated"
            )
        for key, value in obj.items():
            _reject_forbidden_keys(value, where=f"{where}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _reject_forbidden_keys(item, where=f"{where}[{i}]")


def _validate_entry(entry: dict[str, Any], *, index: int) -> None:
    missing = _REQUIRED_ENTRY_KEYS - entry.keys()
    if missing:
        raise HealKBError(f"entries[{index}]: missing required keys {sorted(missing)}")
    eid = entry["id"]
    if not isinstance(eid, str) or not eid.strip():
        raise HealKBError(f"entries[{index}]: id must be a non-empty string")
    area = entry["area"]
    if area not in _VALID_AREAS:
        raise HealKBError(f"entries[{index}] ({eid}): area must be A–O, got {area!r}")
    if not isinstance(entry["patterns"], list) or not all(
        isinstance(p, str) for p in entry["patterns"]
    ):
        raise HealKBError(f"entries[{index}] ({eid}): patterns must be a list of strings")
    for key in ("message", "fix"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise HealKBError(f"entries[{index}] ({eid}): {key} must be a non-empty string")
    if not isinstance(entry["actionable"], bool):
        raise HealKBError(f"entries[{index}] ({eid}): actionable must be a bool")
    if entry["severity"] not in _VALID_SEVERITIES:
        raise HealKBError(
            f"entries[{index}] ({eid}): severity must be one of {sorted(_VALID_SEVERITIES)}"
        )
    if entry["tier"] not in _VALID_TIERS:
        raise HealKBError(
            f"entries[{index}] ({eid}): tier must be one of {sorted(_VALID_TIERS)}"
        )
    runner = entry["runner"]
    if runner is not None and not isinstance(runner, str):
        raise HealKBError(f"entries[{index}] ({eid}): runner must be a string or null")
    if entry["actionable"] and not str(entry["fix"]).strip():
        raise HealKBError(f"entries[{index}] ({eid}): actionable entries require fix text")
    if entry["tier"] == "guided" and runner is not None:
        raise HealKBError(
            f"entries[{index}] ({eid}): guided tier must have runner null"
        )
    if entry["tier"] in {"safe", "dangerous"} and runner is None:
        raise HealKBError(
            f"entries[{index}] ({eid}): {entry['tier']} tier requires a non-null runner "
            "(use guided + null when the operator must act by hand)"
        )


def validate_catalog(raw: dict[str, Any]) -> HealKB:
    """Validate a parsed catalog dict and return a :class:`HealKB`."""
    if not isinstance(raw, dict):
        raise HealKBError("heal_kb.json root must be an object")
    _reject_forbidden_keys(raw, where="root")
    missing = _REQUIRED_TOP_KEYS - raw.keys()
    if missing:
        raise HealKBError(f"heal_kb.json missing top-level keys: {sorted(missing)}")
    version = raw["version"]
    if not isinstance(version, int) or version < 1:
        raise HealKBError("version must be a positive int")
    areas = raw["areas"]
    if not isinstance(areas, dict):
        raise HealKBError("areas must be an object")
    for letter in sorted(_VALID_AREAS):
        if letter not in areas:
            raise HealKBError(f"areas missing letter {letter}")
        meta = areas[letter]
        if not isinstance(meta, dict):
            raise HealKBError(f"areas.{letter} must be an object")
        for field in ("title", "summary"):
            if field not in meta or not isinstance(meta[field], str) or not meta[field].strip():
                raise HealKBError(f"areas.{letter}.{field} must be a non-empty string")
    entries = raw["entries"]
    if not isinstance(entries, list) or not entries:
        raise HealKBError("entries must be a non-empty list")
    by_id: dict[str, dict[str, Any]] = {}
    covered: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise HealKBError(f"entries[{i}] must be an object")
        _validate_entry(entry, index=i)
        eid = entry["id"]
        if eid in by_id:
            raise HealKBError(f"duplicate entry id: {eid}")
        by_id[eid] = entry
        covered.add(entry["area"])
    missing_areas = sorted(_VALID_AREAS - covered)
    if missing_areas:
        raise HealKBError(
            f"every area A–O needs ≥1 entry; missing entries for: {missing_areas}"
        )
    templates = raw["unknown_templates"]
    if not isinstance(templates, dict):
        raise HealKBError("unknown_templates must be an object")
    for key in ("issue_body", "ai_prompt"):
        if key not in templates or not isinstance(templates[key], str):
            raise HealKBError(f"unknown_templates.{key} must be a string")
    matcher = raw.get("matcher") or {}
    if not isinstance(matcher, dict):
        raise HealKBError("matcher must be an object when present")
    return HealKB(
        version=version,
        areas={k: {"title": v["title"], "summary": v["summary"]} for k, v in areas.items()},
        entries=list(entries),
        unknown_templates={
            "issue_body": templates["issue_body"],
            "ai_prompt": templates["ai_prompt"],
        },
        matcher=dict(matcher),
        _by_id=by_id,
    )


def _read_bundled_json() -> dict[str, Any]:
    try:
        text = (
            resources.files("llmwiki.doctor")
            .joinpath("heal_kb.json")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, OSError, TypeError) as exc:
        raise HealKBError(f"cannot load bundled heal_kb.json: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HealKBError(f"heal_kb.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise HealKBError("heal_kb.json root must be an object")
    return data


@lru_cache(maxsize=1)
def load_heal_kb() -> HealKB:
    """Load and validate the package-bundled heal catalog."""
    return validate_catalog(_read_bundled_json())


def get_entry(entry_id: str) -> dict[str, Any] | None:
    """Convenience: ``load_heal_kb().get(entry_id)``."""
    return load_heal_kb().get(entry_id)


def list_areas() -> dict[str, dict[str, str]]:
    """Convenience: ``load_heal_kb().list_areas()``."""
    return load_heal_kb().list_areas()


def fingerprint(text: str) -> str:
    """Normalize a pasted symptom for matching (no semantic/embedding step).

    Casefold, strip ANSI/quotes noise, collapse whitespace, redact absolute
    paths and long hex/uuids to placeholders.
    """
    cleaned = _ANSI_RE.sub("", text or "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("`", " ").replace('"', " ").replace("'", " ")
    cleaned = _ABS_PATH_RE.sub("<path>", cleaned)
    cleaned = _UUID_RE.sub("<uuid>", cleaned)
    cleaned = _LONG_HEX_RE.sub("<hex>", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip().casefold()
    return cleaned


def _tokens(text: str, stopwords: set[str]) -> set[str]:
    return {
        tok
        for tok in _TOKEN_RE.findall(text.casefold())
        if len(tok) > 2 and tok not in stopwords
    }


def _pattern_hits(fingerprint_text: str, pattern: str) -> bool:
    """True when ``pattern`` matches ``fingerprint_text`` (literal or ``re:``)."""
    if not pattern:
        return False
    if pattern.startswith(_REGEX_PREFIX):
        expr = pattern[len(_REGEX_PREFIX) :]
        try:
            return re.search(expr, fingerprint_text, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return pattern.casefold() in fingerprint_text


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass(frozen=True)
class MatchResult:
    """Outcome of :func:`match_symptom`."""

    entry: dict[str, Any] | None
    method: str  # "id" | "pattern" | "lexical" | "none"
    score: float = 1.0


def match_symptom(text: str, kb: HealKB | None = None) -> MatchResult:
    """Resolve a pasted symptom against the catalog (Path 2 in the tech spec).

    Order: stable id / structured hook → pattern list (catalog order) →
    high-threshold lexical fallback. Never invents a runner on a weak score.
    """
    catalog = kb or load_heal_kb()
    fp = fingerprint(text)
    if not fp:
        return MatchResult(entry=None, method="none", score=0.0)

    # Exact / structured hooks: catalog id or rule=<name> tokens.
    for entry in catalog.entries:
        eid = str(entry["id"])
        if eid.casefold() in fp or f"id={eid.casefold()}" in fp:
            return MatchResult(entry=entry, method="id", score=1.0)
    rule_match = re.search(r"\brule=([a-z0-9_:-]+)", fp)
    if rule_match:
        rule = rule_match.group(1)
        for entry in catalog.entries:
            eid = str(entry["id"])
            if eid == f"lint.{rule}" or eid == f"lint:{rule}" or rule in eid:
                return MatchResult(entry=entry, method="id", score=1.0)
            for pat in entry.get("patterns") or []:
                if isinstance(pat, str) and (
                    f"rule={rule}" in pat.casefold() or f"lint:{rule}" in pat.casefold()
                ):
                    return MatchResult(entry=entry, method="id", score=1.0)

    for entry in catalog.entries:
        for pat in entry.get("patterns") or []:
            if isinstance(pat, str) and _pattern_hits(fp, pat):
                return MatchResult(entry=entry, method="pattern", score=1.0)

    stopwords = {
        str(s).casefold()
        for s in (catalog.matcher.get("stopwords") or [])
        if isinstance(s, str)
    }
    min_score = float(catalog.matcher.get("min_lexical_score") or 0.45)
    query_tokens = _tokens(fp, stopwords)
    best: tuple[float, dict[str, Any]] | None = None
    for entry in catalog.entries:
        corpus_parts = [str(entry.get("message") or "")]
        corpus_parts.extend(
            str(p) for p in (entry.get("patterns") or []) if isinstance(p, str)
        )
        corpus_tokens = _tokens(" ".join(corpus_parts), stopwords)
        score = _jaccard(query_tokens, corpus_tokens)
        if score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, entry)
    if best is not None:
        return MatchResult(entry=best[1], method="lexical", score=best[0])
    return MatchResult(entry=None, method="none", score=0.0)


def finding_from_entry(
    entry: dict[str, Any], *, message: str | None = None
) -> Finding:
    """Build a :class:`~llmwiki.doctor.models.Finding` from a catalog row."""
    tier_raw = str(entry.get("tier") or "guided")
    try:
        tier = FixTier(tier_raw)
    except ValueError:
        tier = FixTier.GUIDED
    return Finding(
        id=str(entry["id"]),
        area=str(entry["area"]),
        message=message if message is not None else str(entry["message"]),
        fix=str(entry.get("fix") or ""),
        actionable=bool(entry.get("actionable")),
        severity=str(entry.get("severity") or "info"),
        tier=tier,
        runner=entry.get("runner"),
    )
