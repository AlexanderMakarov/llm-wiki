# Technical Specification: Cursor Agent CLI synthesis backend

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (#230)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Add a `BaseSynthesizer` that shells out to Cursor’s Agent CLI (`agent` on `$PATH`) the same way `ClaudeCLISynthesizer` uses `claude -p`. Register `synthesis.backend: cursor_cli`. Unify per-engine settings under nested blocks (`synthesis.claude`, `synthesis.ollama`, `synthesis.cursor_cli`) with legacy flat-key fallbacks so existing configs keep working. Add `llmwiki synth --backend <name>` as a one-run override (no config write, no auto-failover). Drive site-overview LLM from the active synthesis backend (skip when `dummy`). Extend `model_pricing.csv` with Cursor-published rates. No new runtime dependencies.

---

## 2. Proposed Solution & Implementation Plan

### Architecture

| Piece | Path / responsibility |
|---|---|
| New backend | `llmwiki/synth/cursor_cli.py` — `CursorCLISynthesizer`, lean argv, availability probe |
| Nested config loaders | Claude: read `synthesis.claude.*` with flat `claude_*` fallback (mirror `load_ollama_config`); Cursor: `synthesis.cursor_cli.{model,timeout}`; keep `load_ollama_config` nested-first |
| Resolver | `llmwiki/synth/pipeline.py` `resolve_backend` — `cursor_cli` branch |
| CLI | `llmwiki/cli.py` — `synth --backend`; overlay for check/estimate/run; unknown CLI name → exit 2 |
| Overview | `llmwiki/build.py` — overview follows active backend; `dummy`/unavailable → skip LLM (no Claude default spend) |
| Pricing | `llmwiki/model_pricing.csv` — Composer / Grok (+ aliases matching `agent --model`); stand-in only if needed |
| Docs / automation | configuration + reference + UPGRADING + CHANGELOG + `context/`; install-automation backend list includes `cursor_cli` |

### Nested config shape

```json
"synthesis": {
  "backend": "cursor_cli",
  "claude": { "model": "sonnet", "timeout": 180, "lean": true, "effort": null, "path": "" },
  "ollama": { "model": "llama3.1:8b", "base_url": "http://127.0.0.1:11434", "timeout": 60, "max_retries": 3 },
  "cursor_cli": { "model": "composer-2.5", "timeout": 180 }
}
```

- Nested wins; flat `claude_*` / legacy flat ollama keys remain readable for compatibility.
- No user-facing `cursor_cli.path` — invoke `agent` from the operator’s `$PATH` (session auth). Tests inject via PATH or subprocess doubles.
- Default Cursor model: cheapest Composer (`composer-2.5`; alias `composer` if Agent CLI accepts it — verify at implement time).

### Lean Agent CLI invocation

- Binary: `shutil.which("agent")` then `which("cursor-agent")` if needed.
- Argv: `-p` / `--print`, `--mode ask`, `--sandbox enabled`, `--model <model>`, `--output-format text` (JSON only if usage parsing is stable and useful).
- Do **not** pass `--force` / `--yolo` / `--approve-mcps`; do **not** use `--worktree` (so `--skip-worktree-setup` unused).
- Prompt: stdin if supported; else argv with Claude’s body char cap. Verify during implement.
- Docs: Cursor has no Claude-equivalent empty-tools / empty-MCP / empty-settings; ask + sandbox is the closest documented lean set.
- `is_available` / `synth --check`: binary on PATH + tiny live probe (not PATH-only). Missing/unreachable → hard fail; no backend failover.

### `synth --backend`

- Values: `dummy` | `ollama` | `claude` | `cursor_cli`
- Overlay `synthesis.backend` for this process only; do not write `config.json`
- Unknown `--backend` → clear error (exit 2)
- Config typo without `--backend` → keep today’s warn + dummy
- Honored by normal synth, `--check`, `--estimate`

### Overview / Key Facts

- Key Facts already uses `resolve_backend` → Cursor once registered
- `build --synthesize` overview: resolve active backend; `claude` / `cursor_cli` / `ollama` complete overview; `dummy` or unavailable → skip (spend nothing). Never call Claude solely because overview was requested while backend is dummy.

### Estimate / pricing

- Active `cursor_cli` → price with `synthesis.cursor_cli.model` (nested)
- Prefer [Cursor models & pricing](https://cursor.com/docs/models-and-pricing); Kimi K3 stand-in only when an id has no published rate (label source/notes)
- No live Agent CLI price fetch

### Tests

- Unit: resolve_backend `cursor_cli`; argv has `-p`, `--mode ask`, `--sandbox enabled`, model; nested + flat Claude load; default Composer model; timeout isolation
- CLI: `--backend` override; unknown rejected; check/estimate honor override
- Overview: dummy skips LLM; cursor/claude paths mocked
- Pricing aliases; mocked subprocess only — no real account/session data in CI

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| MCP/tools still in Cursor context under ask | Document; ask + sandbox; no force/approve-mcps |
| Headless trust / login hangs | Probe timeout; actionable errors; mock in CI |
| Nested migration breaks old configs | Flat-key fallback for claude/ollama |
| Confuse synth backend with ingest `cursor_cli` adapter | Docs distinguish generator vs adapter |
| Argv length | Body cap; prefer stdin |

**Dependencies:** `llmwiki/synth/*`, `cli.py`, `build.py` overview, estimate/cache pricing, `model_pricing.csv`, install-automation, docs, `context/spec/226-*`.

---

## 4. Testing Strategy

- Mocked unit + CLI tests as above
- Manual smoke against throwaway vault: configure nested `cursor_cli`, `synth --check`, one `--path` synth
- No network/live Cursor in CI
