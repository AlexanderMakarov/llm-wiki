"""Resolve durable sync lookback (`filters.since` + per-adapter) (#192).

Precedence: CLI ``--since`` → adapter ``YYYY-MM-DD`` → adapter ``"all"``
→ shared ``filters.since`` → unlimited (``None``).

After a successful sync, ``gc_sync_files_for_lookback`` drops that
adapter's ``sync.files`` stamps whose stored mtime is before the
effective lookback.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from llmwiki.adapters.settings import adapter_block
from llmwiki.state_store import mtime_from_state


def parse_since_date(value: str) -> datetime:
    """Parse ``YYYY-MM-DD`` into an aware UTC midnight datetime.

    Raises
    ------
    ValueError
        When ``value`` is not a valid calendar day (same style as a bad
        CLI ``--since``).
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"--since must be YYYY-MM-DD, got {value!r}") from exc


def resolve_effective_since(
    cli: str | None,
    config: dict[str, Any] | None,
    adapter_name: str,
) -> datetime | None:
    """Effective lookback for one adapter this sync run.

    Returns ``None`` when there is no date gate (unlimited). Invalid date
    strings raise :class:`ValueError` for the caller to map to exit 2.
    """
    if cli is not None:
        cli_s = str(cli).strip()
        if cli_s:
            return parse_since_date(cli_s)

    block = adapter_block(config, adapter_name)
    adapter_raw = block.get("since", None)
    if adapter_raw is not None:
        if not isinstance(adapter_raw, str):
            raise ValueError(f"--since must be YYYY-MM-DD, got {adapter_raw!r}")
        adapter_s = adapter_raw.strip()
        if adapter_s == "all":
            return None
        if adapter_s:
            return parse_since_date(adapter_s)
        # Empty / whitespace-only → inherit shared ``filters.since``.

    if not isinstance(config, dict):
        return None
    filters = config.get("filters")
    if not isinstance(filters, dict):
        return None
    shared_raw = filters.get("since")
    if shared_raw is None:
        return None
    if not isinstance(shared_raw, str):
        raise ValueError(f"--since must be YYYY-MM-DD, got {shared_raw!r}")
    shared_s = shared_raw.strip()
    if not shared_s:
        return None
    return parse_since_date(shared_s)


def gc_sync_files_for_lookback(
    files_dict: dict[str, Any],
    adapter_name: str,
    since_dt: datetime,
) -> int:
    """Drop ``adapter::`` stamps whose stored mtime is before ``since_dt``.

    Mutates ``files_dict`` in place. Only keys prefixed
    ``f"{adapter_name}::"`` are considered; other adapters and
    unparseable values are left alone. Returns the number of keys
    removed.
    """
    prefix = f"{adapter_name}::"
    since_ts = since_dt.timestamp()
    drop: list[str] = []
    for key, value in files_dict.items():
        if not isinstance(key, str) or not key.startswith(prefix):
            continue
        stored = mtime_from_state(value)
        if stored is not None and stored < since_ts:
            drop.append(key)
    for key in drop:
        del files_dict[key]
    return len(drop)
