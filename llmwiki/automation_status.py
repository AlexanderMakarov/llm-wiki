"""Persisted automation status for setup / Home page panel."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki.automation_plan import DEFAULT_SCHEDULE
from llmwiki.cron_spec import describe, parse_cron

STATUS_DIRNAME = ".llmwiki"
STATUS_FILENAME = "automation-status.json"


def default_log_path() -> Path:
    """XDG state home (or ~/.local/state) / llmwiki / last-automation.log."""
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(xdg) if xdg else (Path.home() / ".local" / "state")
    return base / "llmwiki" / "last-automation.log"


def status_path(root: Path) -> Path:
    return Path(root) / STATUS_DIRNAME / STATUS_FILENAME


def load_status(root: Path) -> dict[str, Any] | None:
    path = status_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_status(root: Path, data: dict[str, Any]) -> Path:
    path = status_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def empty_status() -> dict[str, Any]:
    """Status shape for a vault where automation has never been installed."""
    return {
        "job": None,
        "graph": "none",
        "lint_fail": "never",
        "label": None,
        "schedule": DEFAULT_SCHEDULE,
        "schedule_label": describe(parse_cron(DEFAULT_SCHEDULE)),
        "profile": None,
        "hour": 8,
        "minute": 0,
        "watch_enabled": False,
        "hooks": [],
        "synth_backend": "dummy",
        "log_path": str(default_log_path()),
        "updated_at": "",
    }
