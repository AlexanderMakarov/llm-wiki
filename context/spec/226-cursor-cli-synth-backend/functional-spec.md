# Functional Specification: Cursor Agent CLI synthesis backend

- **Roadmap Item:** GitHub [#230](https://github.com/AlexanderMakarov/llm-wiki/issues/230) — feat: Cursor Agent CLI synthesis backend
- **Status:** Approved
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

llmwiki already supports multiple synthesis engines (stub, local Ollama, Claude CLI). Operators who use Cursor’s Agent CLI need that same class of engine: configure it, probe it, run synth, and get real wiki pages — with feature parity to Claude and Ollama.

**Desired outcome.** `cursor_cli` is a first-class synthesis backend beside `claude` and `ollama`: same jobs, nested per-engine settings under the synthesis config section (unified with Claude and Ollama), health check, and a one-run CLI override to pick any backend without editing config or auto-switching.

**Success.** An operator can set `cursor_cli` (or pass `--backend cursor_cli` for one run), rely on the default cheapest Composer model (or override it), pass the synth health check, and produce real source pages / Key Facts / overview work the same way they do with Claude or Ollama. Cost estimates resolve Cursor model names on the packaged rate card. Default backend remains `dummy` (no spend). No automatic backend fallbacks.

---

## 2. Functional Requirements (The "What")

### R1 — First-class `cursor_cli` backend (parity with Claude / Ollama)

- **As an** operator, **I want** Cursor Agent CLI available as a normal synthesis backend named `cursor_cli`, **so that** I can choose it the same way I choose Claude or Ollama.

- **Acceptance Criteria:**
  - [ ] Given synthesis is set to `cursor_cli` with valid Cursor-specific settings, when I run synth on an eligible raw document, then a real wiki source page is written (not a dummy stub).
  - [ ] Given the shipped default is unchanged, when I install or upgrade without selecting Cursor, then existing Claude / Ollama / dummy behavior stays the same.
  - [ ] Given `cursor_cli` is selected, when I use Key Facts rewrite and site-overview paths that already go through the configured synthesis engine, then those jobs work under `cursor_cli` as they do under Claude.
  - [ ] Docs list `cursor_cli` in the same backend table as `dummy` / `ollama` / `claude`, without framing it as a Claude substitute or exhaustion workaround.

### R2 — One-run backend override; no automatic fallbacks

- **As an** operator, **I want** `llmwiki synth --backend <name>` to use that engine for this run instead of whatever is saved in config, **so that** I can try Claude, Ollama, or Cursor without rewriting config — and without the tool silently switching engines for me.

- **Acceptance Criteria:**
  - [ ] Given config names one backend, when I run `llmwiki synth --backend claude` (or `ollama` / `cursor_cli` / `dummy`), then that run uses the named backend; config on disk is unchanged.
  - [ ] Given `--backend` is omitted, when I run synth, then the backend comes from config as today.
  - [ ] Given the selected backend (from config or `--backend`) is missing, misconfigured, or unreachable, when I run synth or `--check`, then the command fails with an actionable error — it does **not** automatically fall over to another engine.
  - [ ] Unknown `--backend` values are rejected with a clear error (not silently treated as dummy), consistent with “no surprise engine.”
  - [ ] `--check` and `--estimate` honor the same `--backend` override when present.

### R3 — Nested per-engine settings (unified Claude / Ollama / Cursor)

- **As an** operator, **I want** Cursor, Claude, and Ollama options under nested blocks in the synthesis section, **so that** config is consistent and backends do not share a flat namespace.

- **Acceptance Criteria:**
  - [ ] Cursor settings live under `synthesis.cursor_cli` (at least `model`, `timeout`). Claude settings are readable from `synthesis.claude` (with legacy flat `claude_*` fallback so old configs keep working). Ollama stays nested as today (flat legacy fallback unchanged).
  - [ ] Default Cursor model is the cheapest Composer id Agent CLI accepts (documented as `composer-2.5`, with `composer` alias if supported) — not an opaque account default and not a hard error when unset.
  - [ ] Per-page timeout is optional, with a documented default analogous to Claude’s timeout.
  - [ ] No user-facing binary-path key for Cursor — llmwiki runs `agent` from the operator’s `$PATH` so normal session login applies. Effort/thinking: document model bracket overrides; do not invent a fake key unless Cursor exposes a stable flag.
  - [ ] Lean invocation uses the closest documented Agent CLI set (`--print`, `--mode ask`, `--sandbox enabled`); docs state there is still no Claude-equivalent empty-tools / empty-MCP / empty-settings switch.
  - [ ] Configuration reference documents nested blocks for all three engines and any legacy flat fallbacks.

### R4 — Lean, non-interactive generation

- **As a** vault owner, **I want** Cursor synthesis to be text-in / markdown-out like Claude’s lean scripted path — no agent writing wiki files, no interactive tool approvals — **so that** synth is safe and predictable.

- **Acceptance Criteria:**
  - [ ] Successful Cursor synth returns markdown to llmwiki; the agent is not the writer of vault files.
  - [ ] Invocation uses non-interactive print, ask/read-only mode, and sandbox enabled; does not create a git worktree for synth.
  - [ ] Runs do not require “run everything” / force-approve-all-tools / approve-all-MCP to complete a normal synth.
  - [ ] Docs state honestly where Cursor cannot match Claude’s empty-tools / empty-MCP / stripped-system-prompt switches.

### R4b — Overview follows the active backend (no silent Claude spend)

- **As an** operator with the default `dummy` backend, **I want** optional site-overview synthesis to spend nothing unless I chose a real backend, **so that** build never bills Claude by surprise.

- **Acceptance Criteria:**
  - [ ] Given `synthesis.backend` is `dummy` (or the overview path’s resolved backend is unavailable), when overview LLM synthesis is requested, then no Claude/Cursor/Ollama call runs for overview.
  - [ ] Given backend is `claude`, `cursor_cli`, or `ollama`, when overview LLM synthesis is requested, then overview uses that backend (not a hardcoded Claude path).

### R5 — Health check with a real tiny probe

- **As an** operator, **I want** `llmwiki synth --check` (honoring `--backend` when set) to prove the selected engine can answer a tiny prompt, **so that** I fail fast before a long run.

- **Acceptance Criteria:**
  - [ ] Given `cursor_cli` is correctly configured and authenticated enough to answer, when I run `--check`, then it reports available / success.
  - [ ] Given missing binary, bad auth, missing model, or probe failure, when I run `--check`, then it fails with an actionable message.
  - [ ] Binary-on-PATH alone is not enough for success.

### R6 — Docs and distinction from ingest

- **Acceptance Criteria:**
  - [ ] Configuration, CLI reference, CHANGELOG / UPGRADING mention `cursor_cli`, flat keys, and `--backend`.
  - [ ] Docs distinguish the **synthesis** backend from Cursor **session ingest** adapters (IDE vs Agent CLI stores).

### R7 — Cost estimate rate card includes Cursor models

- **As an** operator running `synth --estimate` with `cursor_cli`, **I want** known Cursor model names to resolve on the packaged rate card, **so that** estimates do not die with “unknown model” and dollar figures are in the same ballpark as other backends.

- **Acceptance Criteria:**
  - [ ] Given a configured `cursor_cli` model that appears on Cursor’s published pricing page, when I run `--estimate`, then the model resolves via the packaged rate card (`model_pricing.csv`) and a cost figure is shown (same ±heuristic caveats as today — estimate does not call Cursor for live prices; Agent CLI is not assumed to return a price).
  - [ ] Rate-card rows for Cursor-relevant models prefer **Cursor’s published per-token rates** (and aliases that match `agent --model` / `agent models` naming where practical).
  - [ ] Given a Cursor model id with **no** usable published per-token rate, when we still need a row so estimates do not hard-fail, then we may temporarily mirror **Kimi K3** list rates (Cursor’s own table or OpenRouter) and mark the row’s source/notes as an approximate stand-in — not as measured Cursor billing.
  - [ ] Docs mention that Cursor estimates use the static rate card, not live Agent CLI pricing, and that stand-in rows are labeled as such.
  - [ ] Existing Claude / other rows remain valid; this work only adds or aliases what `cursor_cli` needs.

---

## 3. Scope and Boundaries

### In-Scope

- First-class `cursor_cli` synthesis backend with Claude/Ollama job parity
- Nested `synthesis.cursor_cli` / `synthesis.claude` (plus existing `synthesis.ollama`) with legacy flat fallbacks
- Default Cursor model = cheapest Composer; `llmwiki synth --backend <name>` one-run override; no auto-failover
- Lean/safe Agent CLI invocation (`-p`, ask, sandbox); health check with live probe
- Overview LLM follows active backend; dummy skips spend
- Packaged rate-card rows/aliases for Cursor models used with this backend
- Docs + tests (no real session data)

### Out-of-Scope

- Changing the shipped default backend away from `dummy`
- Automatic fallback from one backend to another
- User-facing Cursor binary-path config (PATH `agent` only)
- Cursor IDE / session ingest as a generator
- Demo-refresh path/plan selection changes
- Inventing Cursor CLI flags that do not exist
- Live price fetch from Agent CLI or Cursor billing APIs
