# Technical Specification: Configurable adapters and configure-sources

- **Functional Specification:** [functional-spec.md](./functional-spec.md) — GitHub [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Unify three divergent code paths today — **discovery** (`discover_adapters` vs `discover_contrib`), **config lookup** (top-level `<name>` vs `adapters.<name>`), and **selection** (`convert_all`, `cmd_adapters`, `watch`) — behind a small adapters config module and a single `select_sync_adapters()` helper.

Default `llmwiki sync` and `llmwiki adapters` will call `discover_all()` and use merged config from `_load_sessions_config()` (same as synth/schedule). A new `llmwiki configure-sources` command implements the R4 interview and writes `adapters.*` blocks to gitignored `config.json`. `setup.sh` offers it on TTY before the existing `install-automation` prompt.

Internal `adapters/` vs `adapters/contrib/` package layout stays; user-facing docs drop “core vs contrib.”

No new runtime dependencies.

---

## 2. Proposed Solution & Implementation Plan

### 2.1 Config resolution (`llmwiki/adapters/settings.py` — new)

| Function | Responsibility |
|----------|----------------|
| `adapter_block(config, name) -> dict` | Return merged settings for one adapter. Precedence: `adapters.<canonical>` merged over legacy top-level `<canonical>` (and kebab alias for `copilot_chat`). |
| `adapter_enabled_flag(config, name) -> bool \| None` | `True` / `False` / `None` (auto) from `enabled` key in the merged block. |
| `select_sync_adapters(config, explicit: list[str] \| None = None) -> list[type]` | Shared selection for sync and watch. |

**`select_sync_adapters` rules:**

1. Always `discover_all()` first.
2. If `explicit` names provided (`--adapter`): load named adapters only; resolve aliases; skip enablement filter (current behavior).
3. Else for each registered adapter class:
   - Skip if `not cls.is_available()` (with config passed into ctor when adapter supports config-aware availability — see ChatGPT below).
   - Read `enabled` via `adapter_enabled_flag`.
   - If `enabled is False` → skip.
   - If `is_ai_session` (default True) and `enabled is not False` → include when available (auto).
   - If `not is_ai_session` → include only when `enabled is True` (#326 / R5).

Instantiate adapters with full merged config dict so path overrides in `adapters.<name>` apply during `is_available()` where needed.

### 2.2 Wire consumers

| File | Change |
|------|--------|
| `llmwiki/convert.py` | Replace inline loop (~1698–1730) with `select_sync_adapters(config, adapters)`; pass config into adapter instances during convert. |
| `llmwiki/adapters/status.py` | Use `adapter_block()` for enable lookup; keep column semantics (`auto`/`explicit`/`off`, `active` yes/no). |
| `llmwiki/cli.py` `cmd_adapters` | `discover_all()` + `_load_sessions_config()` instead of example-only JSON. |
| `llmwiki/watch.py` | Reuse `select_sync_adapters()`; pass merged config to adapter ctor in scan loop. |

### 2.3 `configure-sources` command (`llmwiki/configure_sources.py` — new)

CLI subcommand registered in `cli.py`.

**Flow:**

1. `discover_all()`; load merged config.
2. For each adapter in sorted `REGISTRY` order, probe `is_available()` (config-less probe for detection; note detected default paths from a fresh instance).
3. Partition: AI session vs notes/export (`is_ai_session`).
4. Interactive prompts via existing `_ask_choice` / `_ask_until` helpers from `cli.py` (extract shared helpers to a small `llmwiki/prompts.py` only if import cycle forces it — prefer importing from cli or colocating interview in `configure_sources.py` with duplicated thin wrappers).
5. `_write_adapters_config(updates: dict)` — read/merge `config.json` `adapters` section (same pattern as `_write_synth_backend`).
6. Print summary + suggest `llmwiki adapters`.

**Flags:** `--yes` / non-TTY → no-op with message (exit 0); used by CI. Document `LLMWIKI_SKIP_CONFIGURE_SOURCES=1` for `setup.sh`.

### 2.4 `setup.sh` / `setup.bat`

After `llmwiki adapters` + `sync --status`, before `install-automation` prompt:

```bash
if [ -t 0 ] && [ "${LLMWIKI_SKIP_CONFIGURE_SOURCES:-}" != "1" ]; then
  printf "Run configure-sources now? [Y/n] "
  ...
fi
```

Default **Y** when TTY (user can Enter to accept). Windows `setup.bat`: equivalent optional prompt.

### 2.5 Shipped config and docs

| Artifact | Change |
|----------|--------|
| `examples/sessions_config.json` | Add `adapters` block with commented stubs per shipped source; remove stale “enable with --adapter” comment. |
| `docs/getting-started.md`, `multi-agent-setup.md`, `configuration-reference.md`, `docs/reference/cli.md` | Single enablement model; document `configure-sources`; remove user-facing core/contrib; add CLI row. |
| `CHANGELOG.md` | User-visible behavior change under `[Unreleased]`. |
| `docs/UPGRADING.md` | Note bare sync now includes all enabled AI adapters; `--adapter` still limits per run. |

### 2.6 ChatGPT adapter edge case

`ChatGPTAdapter.is_available()` currently always returns `False` at class level. Change to: unavailable unless `adapter_block` has `enabled: true` **and** at least one `export_dirs` path exists. Keeps export opt-in while making config meaningful.

### 2.7 Backward compatibility

- Legacy top-level `{ "openclaw": { "enabled": true } }` continues to work via `adapter_block` merge.
- `--adapter cursor_cli` unchanged.
- `enabled: false` on AI adapters now honored in sync (fixes status/sync mismatch).

---

## 3. Impact and Risk Analysis

- **System dependencies:** `convert`, `watch`, CLI `adapters`, automation status (indirect), docs CI grep for stale adapter claims.
- **Risks:**
  - *Surprise sync volume* — users with many agent stores may sync more on first bare `sync` after upgrade. Mitigation: UPGRADING note; `enabled: false` escape hatch; interview on setup.
  - *Obsidian accidental ingest* — mitigated by unchanged `is_ai_session=False` + explicit `enabled: true` only.
  - *Config shape drift* — single `adapter_block()` resolver; tests lock precedence.
  - *Import cycles* — keep `configure_sources` importing prompt helpers from a thin module if `cli` ↔ `configure_sources` cycles.

---

## 4. Testing Strategy

| Layer | Coverage |
|-------|----------|
| Unit | `adapter_block` precedence (top-level vs `adapters.*`, kebab alias); `select_sync_adapters` matrix (auto, explicit on/off, non-AI, `--adapter` override, `enabled: false`). |
| Integration | `convert_all` with tmp stores + config enables OpenClaw without `--adapter`; Obsidian skipped unless explicit. |
| CLI | `cmd_adapters` lists full roster; reads merged `config.json`; `configure-sources --yes` no-op; interactive path tested via stdin fixture. |
| Docs | Grep/acceptance test for absence of user-facing “contrib — `--adapter`” where replaced; CLI reference row for `configure-sources`. |

Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` before push.
