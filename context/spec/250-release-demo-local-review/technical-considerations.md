# Technical Specification: Release-cut local demo review (usage window + site gate)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Make the release-day demo refresh **hard-scriptable**: a new stdlib Python script under `scripts/` owns the mechanical steps (usage regen, local demo build, print concrete URL, case-fold guard, exit codes). The `/release` skill and `RELEASE_PROCESS.md` become thin: run the script, interpret its exit status, pause for human OK when the script says review is required — not multi-page LLM checklists that restate every command.

No Pages content invention, no redo of `#255` packaging in this PR, no new runtime package APIs for end users.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### New script (canonical mechanics)

| Path | Role |
|---|---|
| `scripts/release_demo_gate.py` (name flexible; prefer this) | Maintainer-only release-day demo gate. Stdlib + existing `llmwiki` / sibling scripts only. |

**Assumed CLI (confirm or correct):**

```text
python3 scripts/release_demo_gate.py --today YYYY-MM-DD [--dry-run] [--skip-usage] [--out DIR]
```

| Step (scripted) | Behavior |
|---|---|
| Usage regen | Invoke the same logic as `generate_demo_usage.py --today` (subprocess or shared import) unless `--skip-usage` / explicit opt-out flag for “version-only” cuts |
| Local build | `python3 -m llmwiki build --vault demo --out <DIR> --local-root /home/user` (default `/tmp/demo-site`) |
| Print URL | Always print a concrete open path, e.g. `file://<DIR>/index.html` (and optional `llmwiki serve` one-liner) to stdout |
| Case-fold guard | Run `python3 -m pytest tests/test_case_insensitive_paths.py -q` (or import the collision check if cheaper); non-zero → gate fails |
| Lint (optional but preferred) | `python3 -m llmwiki lint --vault demo --fail-on-errors` |
| Exit codes | `0` = mechanical gate passed (human still must visually OK); non-zero = blocked (do not present tag push). Distinct codes for usage fail / build fail / case-fold fail if cheap |

**Explicitly NOT scripted (stay human / skill):** version bump, CHANGELOG editorial, `git commit` / `git tag` / `git push`, incomplete-synth wait (human runs synth; script may refuse if known completeness helpers fail — reuse `refresh_demo.py --verify-slugs` when slugs are passed), browser review judgment.

**Reuse, do not rewrite:** `scripts/generate_demo_usage.py` remains the usage generator; the gate script calls it. Session regen (`generate_demo_sessions.py`) and docs refresh (`refresh_demo.py`) stay as today’s separate pre-steps — the gate assumes they already ran (or accepts optional flags later; v1 keeps the gate focused on usage + build + URL + case-fold).

### Docs + skill (thin wrappers)

| Path | Change |
|---|---|
| `docs/maintainers/RELEASE_PROCESS.md` | Demo-refresh section: after sessions/docs/synth completeness, run `release_demo_gate.py --today …`; commit `demo/usage/` (+ existing `#255` state bullet); human reviews the printed URL; then bump/tag. Clarify CI only builds + version-asserts committed `demo/`. Keep incomplete-synth hard stop. |
| `.claude/skills/release/SKILL.md` | Replace long duplicated command lists for usage/build/review with: run the gate script; on non-zero stop; on zero print its URL block and **pause for human demo OK** before push gate. Align session-regen wording with in-place-by-slug process. |
| `docs/maintainers/REFRESH_DEMO.md` | One-liner: usage/window + local review live in `release_demo_gate.py`, not the docs-rev pin. |
| `CHANGELOG.md` | Unreleased: maintainer release demo gate script + checklist. |
| `docs/reference/` or maintainers README | Short pointer if scripts are catalogued elsewhere; skip if no existing script index pattern. |

### Script / CI (explicit non-changes)

| Path | Decision |
|---|---|
| `.github/workflows/pages.yml` | No change — no inventing sessions/usage |
| `#255` demo state allowlist/commit | **Not in this PR** — already on `main` via #254; close/verify #255 separately |
| End-user `llmwiki` CLI subcommand | Out of scope for v1 (maintainer `scripts/` is enough; skill calls the script) |

### Acceptance tests

| Area | Approach |
|---|---|
| Script unit/integration | Temp demo or mocked subprocesses: `--dry-run` prints planned steps + would-be URL and exits 0; failure paths return non-zero; `--today` forwarded to usage generator |
| Skill/doc locks | Extend `tests/test_209_release_skill.py`: both skill and `RELEASE_PROCESS` mention `release_demo_gate` (or final script name), human pause after gate, and “CI does not invent” sessions/usage |
| Case-fold | Covered by script invocation of existing pytest; no duplicate collision logic |

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| Skill still grows into a second checklist | Keep skill as “run script → interpret exit → human OK”; mechanics live in Python |
| Script scope creep (full release automation) | Hard boundary: no bump/tag/push/CHANGELOG in the script |
| Subprocess fragility | Prefer calling `generate_demo_usage.main` / thin wrappers; document required cwd = repo root |
| Drift with `#255` | Do not reopen packaging here; release doc keeps existing state-commit reminder only |
| False green without human eyes | Exit 0 never means “push”; skill/process still require explicit human demo OK |

**Dependencies:** `#225` demo refresh default ON, incomplete-synth hard stop, `#255` committed demo state (already on main), existing usage/session/docs scripts.

---

## 4. Testing Strategy

- `pytest` for `release_demo_gate.py` (dry-run, flag forwarding, non-zero on simulated build/usage failure)
- Extend `test_209_release_skill.py` string locks for script name + pause + CI wording
- `ruff check` on `scripts/` + tests
- Manual: one dry-run of the gate on a checkout; confirm URL line is copy-pasteable

---

## 5. Decisions relative to prior draft

- **Changed:** prefer **Python gate script** over embedding mechanics only in SKILL.md (human request 2026-09-14).
- **Unchanged:** `#255` packaging out of this PR; Pages never invents content; human still owns visual OK and git push.
