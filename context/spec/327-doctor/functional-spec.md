# Functional Specification: `llmwiki doctor` — heal the install and vault until sound

- **Roadmap Item:** Guided health check — `llmwiki doctor` (#110)
- **Status:** Completed (amended 2026-10-13: heal loop, not read-only reporter)
- **Author:** Aleksandr Makarov
- **Issue:** [#110](https://github.com/AlexanderMakarov/llm-wiki/issues/110)
- **Date:** 2026-10-12 (amended 2026-10-13)

## 1. Overview and Rationale (The "Why")

Today there is no single place to ask “is my install healthy, and is my vault consistent?” — and worse, fixing gaps means knowing which of many commands to run. Gaps show up only when an operation fails midway. Each failure is isolated and arrives too late.

**Desired outcome:** `llmwiki doctor` gets llmwiki **working sound**. It finds problems across environment and vault, proposes concrete repairs from a maintained knowledge base, and — with the user’s consent — **runs** those repairs (including install, migrate, synth, build when confirmed). A report-only mode exists for scripts; that is secondary. Wheel and Homebrew users get the same public links to the heal knowledge base and `AGENTS.md` as source-checkout users.

**Success:** after a doctor session (interactive or `--yes` for the safe set), the install and vault are healthy, or the user has a clear remaining blocker plus ticket/AI assist for unknowns. Exit codes support scripting but are not the product’s main result.

## 2. Functional Requirements (The "What")

### 2.0 — Heal knowledge base: check areas

Doctor’s bundled catalog is organized by these areas. Each area may have many concrete entries (filled during implementation from real messages). An unmatched symptom still uses the unknown-assist path (R5), but **every area below must have at least one known entry** in the first ship so the catalog is not a hollow shell.

| # | Area | What doctor looks for | Example failure themes (from product + issues) |
|---|------|------------------------|--------------------------------------------------|
| A | **Install & interpreter** | Which Python runs `llmwiki`, how it was reached, whether the distribution name/install path matches docs | Wrong/missing PyPI name (`llm-wiki` vs `llm-wiki-plus`, #210); Homebrew tap missing (#212); editable checkout vs wheel; uv venv without `pip`; multiple Pythons |
| B | **Optional extras** | Whether `[add]`, `[graph]`, `[e2e]` (and aliases) import in *this* interpreter; install into this interpreter when confirmed | PDF/docx add dies without converters (#169); graph without `[graph]`; e2e-only deps |
| C | **Config & vault binding** | Which `config.json` loaded; vault root; wiki present; settings parse | No `vault.default_path` / missing wiki (exit 2); clone mistaken for vault; settings unreadable |
| D | **Session sources / adapters** | Which adapters are present vs enabled; store paths visible; sync readiness | Core vs contrib surprise (#182); missing store; quarantine backlog |
| E | **Ingest / `add`** | Readiness to land documents; run converter install or guided add repairs when confirmed | Missing markitdown/trafilatura; known add/MCP failure patterns (#286) |
| F | **Synthesis backend** | Configured backend; whether underlying CLI resolves; help set/configure when confirmed | dummy/unset blocking promote (#110); PATH misses Claude (#275) |
| G | **Pipeline backlog** | Raw vs synthesized sources vs pending candidates — only when overdue; may run `synth` / candidates / `build` when confirmed | Unsynthesized raw; pending candidates; failed-synth leftovers (#310) |
| H | **Candidates review** | Pending review that blocks the loop; may run review/apply actions when confirmed | Promote/merge/discard needed (#282) |
| I | **Wiki lint / consistency** | Registered lint rules (when lint stage runs); apply mechanical repairs when confirmed | Broken wikilinks; orphans; `index_sync`; stale; uncontexted folders |
| J | **Provenance / trace** | Broken provenance chains; run guided repair commands when confirmed | Empty provenance (#307); broken hops (#122); `migrate broken-provenance` / `synth` / `trace` |
| K | **Migrations / schema drift** | Vault shape needing `migrate …`; dry-run then apply when confirmed | State leftovers (#23); topic kinds; provenance migrates |
| L | **Automation / schedulers** | Declared vs active automation; run install-automation / activation steps when confirmed | Units not activated (#198); PATH/lookback issues (#206, #275) |
| M | **Build / site freshness** | Site/wiki skew; run `build` when confirmed | Stale Home/Analytics after synth |
| N | **Agent kit / MCP consumer path** | Kit / MCP mismatches; run kit install or print exact repair when confirmed | Outdated kit; MCP flag mismatches (#336) |
| O | **Privacy / redaction posture** | High-level redaction expectations; anonymization rules for drafts (never leak vault roots) | Path redaction surprises (#253) |

**Normal heal run order:** A → B → C (hard stop if unusable) → D → E → F → if early actionable failures that block further work, heal those first (may skip lint until env/vault usable) → else I+J (lint) and G/H when overdue → K/L/M/N as detectors fire → O as constraints on drafts / obvious misconfig.

**`--error` mode:** match symptom into A–O; if unmatched → R5 (no invented runnable fix). Does not run the full lint pass unless the user continues into a heal loop afterward.

**Out of area (v1):** CI/test-harness, release/demo publishing, AWOS contributor tooling, visual/CSS — unknown-assist only if pasted.

### R1 — Heal loop is the default

- **As a** user, **I want** `llmwiki doctor` to find problems and help me fix them until things work (or I stop), **so that** I am not left with a report and no repair.
  - **Acceptance Criteria:**
    - [ ] Given a configured vault with fixable problems, when I run `llmwiki doctor` on a TTY, then doctor presents each fixable finding with what it will do and asks y/n before running that fix (unless `--yes` — see R3).
    - [ ] After applying fixes, doctor re-checks affected areas (heal loop) rather than exiting on the first finding alone.
    - [ ] General information (interpreter, extras, backend, config/vault) still appears so I know what environment is being healed; it is supporting context, not the main deliverable.

### R2 — Report-only mode for scripts

- **As a** script author, **I want** a non-mutating check mode, **so that** CI/cron can inspect health without applying repairs.
  - **Acceptance Criteria:**
    - [ ] `llmwiki doctor --check` and `llmwiki doctor --dry-run` perform diagnosis only: print findings and suggested fixes, apply nothing.
    - [ ] In report-only mode, exit codes follow R8; no interactive apply prompts.

### R3 — Consent and `--yes`

- **As a** user, **I want** control over what runs, **so that** installs, migrations, and LLM/synth work never surprise me.
  - **Acceptance Criteria:**
    - [ ] Interactive (TTY) default: confirm each fixable finding before it runs.
    - [ ] `--yes` applies all **safe** fixes without per-item prompts; **dangerous** fixes (package install into the interpreter, migrate rewrite, synth/LLM spend, and other pipeline work that can take significant time or rewrite many pages) still require an explicit confirm unless the product documents a stronger `--yes-all` later — for v1, `--yes` covers the safe vault set only; dangerous tiers still ask on TTY, and on non-TTY are skipped with a printed command unless the user passed an explicit per-tier flag agreed in tech (minimum: non-TTY without `--yes` applies nothing and prints the plan).
    - [ ] Non-TTY without `--yes`: print the plan only (like dry-run for apply), exit per R8; do not mutate.

*Clarification locked with operator (1a):* interactive y/n per fix; `--yes` = unattended **safe** set; non-TTY needs `--yes` or report-only. Pipeline/env installs are runnable when confirmed (2c) — on TTY via y/n even without `--yes`.

### R4 — Runnable fix tiers (everything may run when confirmed)

- **As a** user, **I want** doctor to actually run repairs I agree to — including pipeline steps — **so that** I do not have to copy-paste every command.
  - **Acceptance Criteria:**
    - [ ] When confirmed, doctor may run: safe vault repairs (e.g. index reindex), env installs via interpreter-correct install hints, migrations (prefer dry-run preview then apply), pipeline commands (`synth`, candidates actions, `build`), automation install/activation helpers, and agent-kit install — as listed in the knowledge base for that finding.
    - [ ] Every runnable finding names the exact command or internal API equivalent before it runs.
    - [ ] Guided-only items (hand-edit prose with no safe runner, or unknown errors) are never auto-executed as invented shell.

### R5 — Unknown problem → ticket draft + AI prompt (no invented fix)

- **As a** user with a symptom doctor does not recognize, **I want** ready-to-paste escalation help, **so that** I can get a real fix without doctor guessing a command to run.
  - **Acceptance Criteria:**
    - [ ] Unmatched KB (including `--error`): offer (1) anonymized GitHub issue draft and (2) AI investigation prompt linking `AGENTS.md` + heal KB; ask for root-cause investigation, local fix, and eventually filing a GitHub issue.
    - [ ] Drafts may include version, OS family, interpreter kind, finding codes/messages with paths redacted, and **counts only**. No vault roots, usernames, hostnames, or personal page titles.
    - [ ] Doctor does **not** invent or run a fix for unmatched symptoms.

### R6 — `--error` looks up one symptom

- **As a** user who already has an error message, **I want** `llmwiki doctor --error "…"`, **so that** I get a KB match (and may apply that fix with consent) or unknown-assist without a full lint pass first.
  - **Acceptance Criteria:**
    - [ ] Matches heal KB; on match, offers the same confirm-and-run path as the heal loop for that fix when not in `--check`/`--dry-run`.
    - [ ] Skips the automatic full lint pass for the lookup itself.
    - [ ] Unknown → R5 only.

### R7 — When to run lint (and backlog)

- **As a** user, **I want** lint included when it still adds information, **so that** vault consistency is healed in the same session.
  - **Acceptance Criteria:**
    - [ ] If doctor already found actionable errors that make lint useless or `--error` lookup-only, lint may be skipped until those are cleared or the user continues a full heal.
    - [ ] Otherwise lint **always** runs as part of a full doctor heal/check; findings enter the same confirm-and-fix flow when a runner exists.
    - [ ] Pipeline backlog appears **only when overdue**, with suggested (and runnable-when-confirmed) next commands.

### R8 — Exit codes (secondary)

- **As a** script author, **I want** reliable exit codes in check/heal runs, **so that** automation can gate — without making exit codes the product’s focus.
  - **Acceptance Criteria:**
    - [ ] Exit **2** when vault/config is missing or unusable.
    - [ ] Exit **1** when actionable problems remain (declined, failed, or still broken after re-check).
    - [ ] Exit **0** when nothing actionable remains (healthy, or all agreed fixes applied and re-check clean).

### R9 — Hard stop without a vault

- **As a** user without a usable vault, **I want** an immediate clear failure with the fix path, **so that** doctor does not pretend to heal a missing vault.
  - **Acceptance Criteria:**
    - [ ] Missing/unusable vault or wiki: print that error and fix guidance; exit **2**; no lint; no heal menu beyond helping configure/init if that fix is confirmed and applicable.

### R10 — Heal knowledge base (bundled + public URLs)

- **As a** user on any install method, **I want** a single catalog of known problems, solutions, and runners, **so that** doctor can heal offline and still point humans/AI at canonical repo docs.
  - **Acceptance Criteria:**
    - [ ] Package ships one bundled heal catalog (JSON) covering areas A–O with ≥1 entry each; actionable entries include fix text and whether/how doctor can run them.
    - [ ] Doctor prints stable GitHub links to that catalog and to repo `AGENTS.md` (wheel/Homebrew safe).
    - [ ] Provenance problems suggest and may run the same class of repair already taught by lint/trace/migrate when confirmed.

### R11 — Clean / all-clear

- **As a** user on a healthy install, **I want** confirmation that things are sound and an optional way to explain a pasted error, **so that** doctor stays useful when green.
  - **Acceptance Criteria:**
    - [ ] After a clean heal/check (lint included when applicable), print general info + all-clear; exit 0.
    - [ ] TTY: offer explain-a-specific-error (same as `--error`). Do not offer “run linter” — lint already ran on the full path.
    - [ ] Non-TTY: mention `--error` / `--check`; no interactive menu.

## 3. Scope and Boundaries

### In-Scope

- `llmwiki doctor` heal loop (default) + `--check` / `--dry-run` report-only + `--error` + `--yes` (safe unattended)
- Running confirmed fixes across env install, migrate, pipeline (`synth` / candidates / `build`), automation, agent-kit, and safe vault repairs
- Bundled heal KB (areas A–O) + public GitHub URLs
- Unknown → anonymized issue draft + AI prompt (no invented run)
- Exit codes per R8; docs/CHANGELOG/reference row

### Out-of-Scope

- Inventing fixes for unmatched errors
- Filing GitHub issues without the user pasting/submitting
- Replacing standalone `llmwiki lint` / `synth` / `migrate` as commands
- `--yes-all` that skips confirms for dangerous tiers (unless added later)
- Other Phase 2 roadmap items (#109, etc.)
- Changing `llmwiki lint`’s own default exit policy when invoked alone
