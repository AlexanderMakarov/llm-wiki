# Technical Specification: `llmwiki doctor` (heal loop)

- **Functional Specification:** `context/spec/327-doctor/functional-spec.md`
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

## 1. High-Level Technical Approach

Implement `llmwiki doctor` as a **heal orchestrator**: diagnose → plan → confirm → **execute** existing llmwiki/env operations → re-check. Default UX is the heal loop; `--check` / `--dry-run` are diagnose-only for scripts. Success is a **sound install/vault**, not a report or an exit code (exit codes remain secondary for automation).

Package: `llmwiki/doctor/`. Compose existing APIs (`install_hint`, vault resolve, synth backend probes, `run_lint`, `reindex` / migrate runners, backlog/candidates, automation/kit helpers) rather than reimplementing them. A **single bundled JSON** catalog `heal_kb.json` ships in the wheel (stdlib `json` only — no YAML / no new runtime deps).

Live detectors cover every functional area A–O in v1. CLI sits under **Look around**. Public GitHub blob URLs (via `docs_pages`) always point at the catalog file and repo `AGENTS.md` so wheel/Homebrew users get the same links as a source checkout.

**Hard rules locked with the operator:**

1. Doctor **may** invoke synthesis / pipeline work that spends LLM tokens — **only** after explicit confirm of a dangerous-tier fix (never under `--check`/`--dry-run`; never under `--yes` alone).
2. The heal knowledge base is **release-shipped** with the package. Doctor does **not** append local “learned” entries; unknowns escalate via ticket/AI templates.
3. Fixes prefer **in-process Python APIs**; fall back to `sys.executable -m llmwiki …` when the CLI is the stable contract. Doctor **never** escalates to superuser (`sudo` / admin); privilege-gated repairs stay guided (print the command).
4. **No semantic-search / embedding engine** dedicated to doctor. Matching is ID-first + normalized fingerprint/pattern (+ optional cheap lexical fallback). Catalog evolution is a packaging/process concern, not a retrieval-model concern.
5. `heal_kb.json` stays **current with this package only** — no retired/deprecated museum. Code ↔ catalog drift is a **bug** (tests must catch it).

---

## 2. Proposed Solution & Implementation Plan

### 2.1 Modules

| Path | Responsibility |
|------|----------------|
| `llmwiki/doctor/__init__.py` | `run_doctor(mode, …)` → `DoctorReport` |
| `llmwiki/doctor/models.py` | `Finding`, `DoctorReport`, `FixTier` (`safe` \| `dangerous` \| `guided`), run modes |
| `llmwiki/doctor/kb.py` | Load `heal_kb.json`; resolve by stable `id`; fingerprint + pattern match; optional lexical fallback; validate every actionable entry has `fix` + consistent `runner`/`tier` |
| `llmwiki/doctor/heal_kb.json` | Single catalog: areas A–O, entries, unknown templates, matcher metadata |
| `llmwiki/doctor/checks.py` | Live detectors A–O; emit findings **keyed by catalog `id`** (not by free-text guessing) |
| `llmwiki/doctor/lint_fold.py` | Map lint issues → findings (`lint:<rule>` and/or catalog ids); honor `auto_fixable` → safe runners where mapped |
| `llmwiki/doctor/runners.py` | Dispatch `runner` ids → in-process APIs or `sys.executable -m llmwiki …`; refuse privilege escalation |
| `llmwiki/doctor/anon.py` | Redact paths/usernames; build GH issue draft + AI prompt (counts/version/OS/interpreter only) |
| `llmwiki/doctor/report.py` | Render env summary, plan, confirm prompts, progress, all-clear |
| `llmwiki/cli.py` | `cmd_doctor`; flags; Look around registration |
| Docs / CHANGELOG / `pyproject.toml` package-data | CONTRIBUTING requirements |

### 2.2 Modes and flags

| Flag / mode | Behavior |
|-------------|----------|
| (default) | Heal loop: diagnose, confirm, run, re-check |
| `--check` / `--dry-run` | Diagnose only; no runners; exit per policy |
| `--error TEXT` | Query KB with pasted symptom (see §2.4); on match, same confirm-and-run path unless check/dry-run; **does not** run full lint for the lookup itself |
| `--yes` | Auto-apply **safe** tier only; dangerous still y/n on TTY; non-TTY + `--yes` applies safe only and prints skipped dangerous commands |
| Non-TTY, no `--yes` | Plan only (no mutate) |

### 2.3 LLM / backend token spend

| Situation | Backend / tokens? |
|-----------|-------------------|
| Env probes, extras import checks, lint, reindex, most migrates, `--check` | No LLM |
| User confirms a finding whose runner is `synth`, candidates promote/Key Facts, or any other synthesizer-backed step | **Yes** — uses configured `synthesis.backend` (ollama / claude / cursor_cli). Cost is whatever that backend already costs for a normal CLI run |
| `--yes` without further confirm | Must **not** start synth/LLM runners |
| Unknown / guided entries | No LLM from doctor; AI prompt is for the **user** to paste elsewhere |

Doctor does not add a second “doctor brain” model call for ranking fixes or interpreting errors in v1.

### 2.4 Heal knowledge base — persistence, querying, evolution

#### Persistence (what is stored where)

- **Canonical store:** `llmwiki/doctor/heal_kb.json` inside the installable package (`package-data`). Loaded at runtime via `importlib.resources`.
- **Versioning:** the file ships with each llmwiki release. The JSON carries a monotonic `version` integer for diagnostics (“catalog vN”).
- **Not persisted:** per-vault or per-machine learned entries, embedding indexes, or “last unmatched error” caches that mutate the catalog.
- **Public copy:** the same path on GitHub (`…/blob/<default-branch>/llmwiki/doctor/heal_kb.json`) is what ticket/AI prompts link to, so wheel users are not told to open a missing local checkout file.
- **Updating knowledge:** humans (or agents in a normal product PR) edit `heal_kb.json` when:
  - a new failure mode is productized,
  - an error **message string** in code changes (**replace** `patterns` / `message` so they match the new text — do not keep retired wording),
  - a failure mode is removed from the product (**delete** its catalog entry in the same PR),
  - a new runner becomes available.
  The catalog describes **only errors this package version can emit**. No `retired` / `deprecated` / `superseded_by` museum. Unmatched production symptoms do **not** auto-write the KB; they produce R5 drafts so a maintainer can later add a stable `id` + current patterns in-repo. Pastes from older package versions that no longer match → unknown-assist (expected).

#### Two query paths (avoid needing semantic search)

Doctor solves “what is wrong?” in two different ways. Only the second looks like search.

**Path 1 — Detector / lint → stable id (primary, ~all of the default heal loop)**

1. A check function or lint rule decides the failure using structured conditions (missing import, `backend == "dummy"`, `index_sync` issue dict, quarantine count, …).
2. It emits a `Finding` with `code` / catalog `id` already known (e.g. `env.extra_add_missing`, `lint:index_sync`).
3. `kb.get(id)` loads message/fix/tier/runner. **No text search.**

This is why semantic search is unnecessary for the main product loop: as the project evolves, detectors keep pointing at **stable ids**; wording in `message`/`fix` can change freely without breaking match.

**Path 2 — `--error` / pasted stderr (secondary)**

User paste is messy and will drift as we reword exceptions. Strategy (stdlib only, no embeddings):

1. **Normalize / fingerprint** the paste before matching:
   - casefold; collapse whitespace;
   - redact absolute paths, home prefixes, vault roots → `<path>`;
   - replace long hex/uuids/numbers with placeholders where helpful;
   - strip ANSI and quotation noise.
2. **Exact / structured hooks first:** if the paste contains a known stable token (`rule=index_sync`, catalog id, `error: …` code we document), resolve by id.
3. **Pattern match:** each KB entry lists `patterns[]` (literal substrings and/or regexes) for **current** package wording only. First hit in catalog order wins (document order = priority). Stable `id`s persist across rewords; `patterns` are rewritten to the new strings in the same PR — not accumulated as a history log.
4. **Optional cheap lexical fallback (no embeddings):** if nothing hits, score entries by token overlap (e.g. Jaccard / shared significant tokens after stopword drop) against current `patterns` + entry `message`. Accept only above a high threshold; otherwise treat as **unknown** (R5). This is a tie-break aid, not “semantic search,” and must not invent a runner on weak scores.
5. **Unknown:** issue draft + AI prompt with links to `AGENTS.md` + `heal_kb.json`; `runner = null`. Doctor does not execute a guessed fix. Includes pastes that only matched a previous package’s wording.

**Explicit non-goal:** vector DB, embedding model, LLM-as-retriever, doctor-only semantic index, or a retired/deprecated error museum in `heal_kb.json`. If free-text matching is weak, fix with **stable ids in product errors** and **current** `patterns` kept in lockstep with code — not retrieval or historical aliases.

#### How the KB stays accurate as llmwiki evolves

| Evolution event | What we do |
|-----------------|------------|
| New user-visible error string in `llmwiki/` | Prefer a **stable error code** in the message; add KB entry in the **same PR** |
| Reword message without new meaning | Keep the same catalog `id`; **replace** `message` / `patterns` with the new wording (delete obsolete patterns) |
| Split one failure into two | Add new ids; **delete** or fully rewrite the old entry — no `retired` / `superseded_by` fields |
| Remove a failure mode | **Delete** the catalog entry in the same PR |
| Detector / code string drifts from KB | **Bug** — tests must fail (detector ids ⊂ KB; asserted error substrings ⊆ some entry’s `patterns` or stable-code map) |
| Field report via R5 | Maintainer adds id + **current** patterns + runner in a follow-up PR; next release ships the heal |

**Contributor rule (authoritative in CONTRIBUTING):** when changing an exception/help string that doctor or install hints surface, update `heal_kb.json` in that PR so it matches this package — see CONTRIBUTING *CLI error strings and the doctor heal catalog* (TL;DR #14) and the short summaries in `.claude/rules/contributing.md` / `.cursor/rules/contributing.mdc` / `.kiro/steering/contributing-rules.md`. Do not put this process in root `AGENTS.md` / `CLAUDE.md`. Tests should fail on code↔catalog drift, missing detector ids, or actionable entries lacking `fix` / inconsistent `runner`/`tier`.

#### Catalog schema (contract)

Top-level:

- `version` (int)
- `areas`: `A`…`O` → `{ title, summary }`
- `entries`: list of entry objects
- `unknown_templates`: `{ issue_body, ai_prompt }` with placeholders (`{{version}}`, `{{os}}`, `{{interpreter_kind}}`, `{{symptom_redacted}}`, `{{counts}}`, `{{agents_url}}`, `{{kb_url}}`)
- `matcher`: `{ min_lexical_score, stopwords[] }` (optional knobs for the cheap fallback)

Each entry:

```text
id              stable string (primary key for detectors)
area            A…O
patterns        string[]   # current package literals and/or regex only
message         user-facing problem statement (current)
fix             what will be done / command summary (required if actionable)
actionable      bool
severity        error | warning | info
tier            safe | dangerous | guided
runner          string | null   # null => never execute
```

No `retired`, `deprecated`, or `superseded_by` fields — removed failures are deleted from the file.

### 2.5 Applying fixes — in-process vs shell vs privileges

#### Decision order for a runner

1. If `tier == guided` or `runner is null` → print `fix` only; never execute.
2. If the runner maps to an **in-process** function that already owns the behavior (`apply_reindex`, `migrate_*.run_migration`, candidate helpers, etc.) → call it with the resolved vault path. Prefer this for testability and shared validation (`--dry-run` of migrates, etc.).
3. Else run **`[sys.executable, "-m", "llmwiki", …]`** as a subprocess with the same vault flags the user would type. Using `sys.executable` keeps installs/extras targeting the interpreter that is actually running doctor (same invariant as `install_hint`).
4. **Never** prefix with `sudo`, never call `os.setuid`, never write to system package locations deliberately. If `install_hint` / automation would require elevation (system Homebrew prefix, system systemd unit without user lingering, etc.):
   - mark the entry `tier: guided` (or keep dangerous but runner refuses),
   - print the exact command for the user to run in their own elevated session,
   - record the finding as unresolved if not fixed.

#### Example runner table

| Runner id | Mechanism | Tier |
|-----------|-----------|------|
| `reindex` | in-process `plan_reindex` / `apply_reindex` | safe |
| `migrate:<name>` | in-process migrate API; dry-run then apply on confirm | dangerous |
| `install_extra:<extra>` | subprocess of `install_hint(extra)` string (user-scoped env) | dangerous |
| `synth` / `build` / `candidates:*` | `sys.executable -m llmwiki …` | dangerous (may spend tokens) |
| `install_automation` / `install_agent_kit` | in-process cmd helpers or module CLI | dangerous |
| `configure_backend` | guided, or narrow existing config API if safe | guided / dangerous per entry |

Failed runner → finding remains; print stderr; do not invent an alternate privileged command.

### 2.6 Default heal pipeline

1. Resolve vault (area C). Unusable → exit 2; offer init/config runner only if non-privileged and confirmed.
2. Print short env summary (support context).
3. Run detectors A–O; attach KB rows by **id**.
4. Lint: skip while env/vault still blocking or in pure `--error` lookup; else run and fold (ids / `lint:<rule>`).
5. Emit G/H backlog findings only when overdue.
6. For each actionable finding with a runner: confirm (or `--yes` if safe) → execute per §2.5 → re-check that area (re-lint if pages changed).
7. Guided/unknown: assist only.
8. All-clear → optional TTY `--error` offer; exit 0/1/2 per functional R8.

### 2.7 CLI, packaging, docs

- Help group: **Look around** (with lint, trace).
- `pyproject.toml` package-data: `doctor/heal_kb.json` (and package modules).
- `docs/reference/cli.md` + CHANGELOG; replace roadmap-only doctor mentions when shipping.
- CONTRIBUTING (+ agent contribution pointers) hardens error rewording ↔ `heal_kb.json` co-updates; shipped in the same feature PR as doctor.

---

## 3. Impact and Risk Analysis

### System dependencies

- Lint registry + `auto_fixable`, `reindex`, migrate_* , `install_hint` / `detect_env`, synth/build/candidates CLIs, automation/kit installers, `docs_pages` GitHub URL helpers, package-data wheel layout.

### Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Heal loop spends LLM tokens unexpectedly | Dangerous tier + confirm; `--yes` never starts synth; `--check` never runs runners |
| Free-text `--error` misses after rewording | Same-PR catalog refresh; stable ids; fingerprinting; high-threshold lexical fallback; else R5 — **not** embeddings or historical aliases |
| Catalog rot / code↔KB drift | Same-PR rule + tests treat drift as failure: detector ids ⊂ KB; current error substrings covered; no retired rows |
| Subprocess vs in-process drift | Prefer shared APIs; acceptance tests on tmp vault |
| Privilege / sudo damage | Refuse elevation; guided print-only for system-level fixes |
| Privacy CI | KB examples and anon drafts use `<vault>` / `<user>` placeholders only |
| Single JSON becomes huge | Still one file by operator choice; split only if a future release proves need — not v1 |

---

## 4. Testing Strategy

- **Unit:** fingerprinting; current-pattern match; lexical fallback threshold (accept/reject); unknown path has `runner is null`; `--yes` matrix; sudo/elevation refusal; exit codes; lint skip rules; every area A–O has ≥1 entry; schema rejects retired-style fields if present.
- **Acceptance:** `tests/test_doctor_acceptance.py` (`# @spec: 327-doctor`) — heal applies reindex on dirty index; `--check` mutates nothing; confirming synth-class fix is opt-in (can mock runner); `--error` unknown → templates only; non-TTY without `--yes` mutates nothing; detector unknown id fails test.
- **Reference/help:** `doctor` in Look around + `docs/reference/cli.md` row.
- **Static:** `ruff check llmwiki tests scripts`; full `pytest`; no new runtime deps.
