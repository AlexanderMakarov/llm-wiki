"""Anonymize symptoms and build unknown-assist drafts (R5)."""

from __future__ import annotations

import platform
import re
import sys
from typing import Any

from llmwiki import __version__
from llmwiki.docs_pages import github_blob_url
from llmwiki.doctor.kb import fingerprint, load_heal_kb

#: Home / absolute path shapes → ``<path>`` (never emit vault roots).
_HOME_RE = re.compile(
    r"(?:/home|/Users)/[^\s\"'/\]]+(?:/[^\s\"']*)?"
    r"|(?:/mnt|/var|/opt|/tmp)/[^\s\"']+"
    r"|(?:[A-Za-z]:\\[^\s\"']+)"
)
_USER_SEG_RE = re.compile(r"\b(?:USER|username)=[^\s\"']+", re.IGNORECASE)
_HOST_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def heal_kb_github_url() -> str:
    """Public blob URL for the bundled heal catalog (wheel/Homebrew safe)."""
    return f"{github_blob_url()}/llmwiki/doctor/heal_kb.json"


def agents_md_github_url() -> str:
    """Public blob URL for repo ``AGENTS.md``."""
    return f"{github_blob_url()}/AGENTS.md"


def redact_symptom(text: str) -> str:
    """Redact paths/usernames/hostnames from a pasted symptom for sharing."""
    cleaned = fingerprint(text)
    # fingerprint already casefolds and path-redacts; tighten leftovers.
    cleaned = _HOME_RE.sub("<path>", cleaned)
    cleaned = _USER_SEG_RE.sub("USER=<user>", cleaned)
    cleaned = _HOST_RE.sub("<host>", cleaned)
    # Collapse any remaining long absolute-looking tokens.
    cleaned = re.sub(r"(?:^|\s)(/[^\s]{3,})", " <path>", cleaned)
    return cleaned.strip()


def interpreter_kind(env_summary: dict[str, Any] | None = None) -> str:
    """Short interpreter label for drafts (no absolute path)."""
    env = env_summary or {}
    parts: list[str] = []
    py = str(env.get("python") or sys.version.split()[0])
    parts.append(f"python {py}")
    if env.get("uv_managed"):
        parts.append("uv-venv")
    elif env.get("has_pip"):
        parts.append("pip")
    if env.get("has_uv"):
        parts.append("uv-on-path")
    return ", ".join(parts) if parts else "python"


def render_template(template: str, mapping: dict[str, str]) -> str:
    """Replace ``{{key}}`` placeholders; unknown keys become empty."""

    def _sub(match: re.Match[str]) -> str:
        return mapping.get(match.group(1), "")

    return re.sub(r"\{\{(\w+)\}\}", _sub, template)


def build_unknown_assist(
    symptom: str,
    *,
    env_summary: dict[str, Any] | None = None,
    counts: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Return anonymized GitHub issue body + AI prompt for an unmatched symptom.

    Includes version, OS family, interpreter kind, redacted symptom, and
    **counts only** — never vault roots, usernames, or personal page titles.
    ``runner`` is always conceptually null (caller does not execute a fix).
    """
    kb = load_heal_kb()
    env = env_summary or {}
    count_bits = counts or {}
    # Counts only: ints/bools/short enums — stringify without paths.
    safe_counts = {
        str(k): v
        for k, v in count_bits.items()
        if isinstance(v, (int, float, bool))
        or (isinstance(v, str) and "/" not in v and "\\" not in v and len(v) < 40)
    }
    counts_text = (
        ", ".join(f"{k}={v}" for k, v in sorted(safe_counts.items()))
        if safe_counts
        else "n/a"
    )
    mapping = {
        "version": str(env.get("llmwiki_version") or __version__),
        "os": str(env.get("os") or platform.system() or "unknown"),
        "interpreter_kind": interpreter_kind(env),
        "symptom_redacted": redact_symptom(symptom),
        "counts": counts_text,
        "agents_url": agents_md_github_url(),
        "kb_url": heal_kb_github_url(),
    }
    templates = kb.unknown_templates
    return {
        "issue_body": render_template(templates["issue_body"], mapping),
        "ai_prompt": render_template(templates["ai_prompt"], mapping),
        "agents_url": mapping["agents_url"],
        "kb_url": mapping["kb_url"],
        "symptom_redacted": mapping["symptom_redacted"],
    }
