"""Agent label detection from session frontmatter.

Extracted from ``build.py`` so synth/estimate (and other light modules) can
label sessions without importing the full HTML builder (#58 PLC0415).
"""

from __future__ import annotations

import html
from typing import Any


def detect_agent_label(meta: dict[str, Any]) -> tuple[str, str]:
    """Return (label, css_class) for the agent that produced this session.

    Detection order:
    1. Explicit ``agent:`` frontmatter field (set by adapters)
    2. Model name patterns (claude-* → Claude, gpt-* → Codex/Copilot, etc.)
    3. Source file path patterns (codex → Codex, copilot → Copilot)
    4. Default: ``Agent`` / ``agent-unknown``
    """
    agent = str(meta.get("agent", "")).strip().lower()
    if agent:
        return _agent_map(agent)

    model = str(meta.get("model", "")).lower()
    if "claude" in model:
        return ("Claude", "agent-claude")
    if "gpt" in model or "o1" in model or "o3" in model or "o4" in model:
        return ("Codex", "agent-codex")
    if "gemini" in model:
        return ("Gemini", "agent-gemini")
    if "copilot" in model:
        return ("Copilot", "agent-copilot")

    source = str(meta.get("source_file", "")).lower()
    if "codex" in source or ".codex" in source:
        return ("Codex", "agent-codex")
    if "copilot" in source:
        return ("Copilot", "agent-copilot")
    if "cursor" in source:
        return ("Cursor", "agent-cursor")
    if "openclaw" in source:
        return ("OpenClaw", "agent-openclaw")
    if "opencode" in source:
        return ("OpenCode", "agent-opencode")
    if "gemini" in source:
        return ("Gemini", "agent-gemini")
    if "claude" in source or ".claude" in source:
        return ("Claude", "agent-claude")

    tags = meta.get("tags", [])
    if isinstance(tags, list):
        tag_str = " ".join(str(t).lower() for t in tags)
    else:
        tag_str = str(tags).lower()
    if "codex" in tag_str:
        return ("Codex", "agent-codex")
    if "copilot" in tag_str:
        return ("Copilot", "agent-copilot")
    if "cursor" in tag_str:
        return ("Cursor", "agent-cursor")
    if "openclaw" in tag_str:
        return ("OpenClaw", "agent-openclaw")
    if "opencode" in tag_str:
        return ("OpenCode", "agent-opencode")
    if "claude" in tag_str:
        return ("Claude", "agent-claude")

    return ("Agent", "agent-unknown")


def _agent_map(agent: str) -> tuple[str, str]:
    """Map an explicit agent name to (label, css_class)."""
    m = {
        "claude": ("Claude", "agent-claude"),
        "claude-code": ("Claude", "agent-claude"),
        "codex": ("Codex", "agent-codex"),
        "codex-cli": ("Codex", "agent-codex"),
        "copilot": ("Copilot", "agent-copilot"),
        "copilot-chat": ("Copilot", "agent-copilot"),
        "copilot-cli": ("Copilot", "agent-copilot"),
        "cursor": ("Cursor", "agent-cursor"),
        "cursor-cli": ("Cursor", "agent-cursor"),
        "gemini": ("Gemini", "agent-gemini"),
        "gemini-cli": ("Gemini", "agent-gemini"),
        "openclaw": ("OpenClaw", "agent-openclaw"),
        "opencode": ("OpenCode", "agent-opencode"),
        "obsidian": ("Obsidian", "agent-obsidian"),
        # Simplification sweep removed the PDF adapter. The "pdf" entry
        # used to live here; left as a comment so a future grep sees
        # the rationale instead of guessing why the agent-pdf badge is
        # gone. CSS class .agent-pdf is also removed (see render/css.py).
    }
    return m.get(agent, (agent.title(), "agent-unknown"))


def render_agent_badge(meta: dict[str, Any]) -> str:
    """Render an inline agent badge chip."""
    label, css_class = detect_agent_label(meta)
    return f'<span class="agent-badge {html.escape(css_class)}">{html.escape(label)}</span>'
