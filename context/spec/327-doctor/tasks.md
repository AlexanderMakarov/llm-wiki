# Tasks: `llmwiki doctor` heal loop (#110)

Spec: `context/spec/327-doctor/` (functional + technical Approved).

- [ ] **Slice 1: Skeleton CLI + empty heal catalog load**
  - [ ] Add `llmwiki/doctor/` package: `models.py` (`Finding`, `DoctorReport`, tiers/modes), `kb.py` (load `heal_kb.json` via `importlib.resources`), minimal `heal_kb.json` (`version`, `areas` A–O stubs, `entries` with ≥1 placeholder per area or defer full entries to Slice 2 — at minimum schema validates and areas exist), `__init__.py` with `run_doctor` stub returning exit 2 when vault unusable / 0 otherwise for empty findings. Wire `pyproject.toml` package-data for `doctor/heal_kb.json`. **[Agent: python-pro]**
  - [ ] Register `llmwiki doctor` under Look around in `cli.py` (`--vault`, `--check`/`--dry-run`, `--error`, `--yes`); help prose laconic, no issue numbers. Add `docs/reference/cli.md` section + CHANGELOG `[Unreleased]` *Added* bullet; update Look around table. **[Agent: general-purpose]**
  - [ ] Unit tests: catalog loads; missing vault → exit 2; `--check` path does not mutate; package-data present. **[Agent: python-pro]**
  - [ ] Verify: `ruff check llmwiki tests scripts`; `python3 -m pytest` on new tests; `python3 -m llmwiki doctor --help`; delete tmp vaults. **[Agent: general-purpose]**

- [ ] **Slice 2: Heal KB match + unknown assist (no runners yet)**
  - [ ] Flesh `heal_kb.json` with real entries for areas A–O (≥1 each), `unknown_templates`, matcher knobs. Implement fingerprint + pattern match + high-threshold lexical fallback; reject `retired`/`deprecated`/`superseded_by` keys. `--error` resolves by id/patterns or prints anonymized issue + AI prompt (`anon.py`) with GitHub URLs for KB + `AGENTS.md`. **[Agent: python-pro]**
  - [ ] Tests: match current patterns; unknown → templates and `runner is null`; schema forbids retired fields; privacy placeholders only. **[Agent: python-pro]**
  - [ ] Verify: pytest for kb/anon; no vault mutation. **[Agent: general-purpose]**

- [ ] **Slice 3: Live detectors A–F + env summary (diagnose)**
  - [ ] Implement `checks.py` detectors for A–F emitting findings by stable catalog `id` (interpreter/extras via `install_hint`, vault/config, adapters presence, add-extra readiness, synthesis backend `resolve_backend`/`is_available`). Print general info section. Map findings through KB. **[Agent: python-pro]**
  - [ ] Tests with tmp vaults/fixtures: missing extra, dummy backend, good vault smoke. Detector ids ⊂ KB. **[Agent: python-pro]**
  - [ ] Verify: `doctor --check` on worktree vault shows env section; exit codes per actionable findings. **[Agent: general-purpose]**

- [ ] **Slice 4: Lint fold + backlog G/H + detectors I–O (diagnose)**
  - [ ] `lint_fold.py`: run lint when not skipped (early actionable / `--error` lookup); map issues to findings + fixes. Backlog G/H only when overdue. Thin live detectors for J–O (provenance via lint, migrate hints, automation, site freshness, agent-kit, privacy posture). **[Agent: python-pro]**
  - [ ] Tests: lint skip matrix; overdue backlog only; index_sync / provenance fold; drift test that detector ids resolve in KB. **[Agent: python-pro]**
  - [ ] Verify: `--check` on vault with broken index lists finding; healthy path runs lint. **[Agent: general-purpose]**

- [ ] **Slice 5: Runners + consent heal loop (safe + dangerous)**
  - [ ] `runners.py`: dispatch table (reindex in-process; migrate/synth/build/install_extra via APIs or `sys.executable -m llmwiki`); refuse sudo/elevation. Heal loop in `run_doctor`: confirm per finding on TTY; `--yes` auto-safe only; non-TTY without `--yes` plan-only; re-check after apply. Dangerous (incl. synth) never under `--yes` alone. **[Agent: python-pro]**
  - [ ] Tests: reindex applies under confirm/`--yes`; `--check`/`dry-run` never calls runners; non-TTY no `--yes` no mutate; elevation refused; synth runner not invoked by `--yes`. **[Agent: python-pro]**
  - [ ] Verify: dirty `index.md` heal with `--yes` repairs; `--check` afterward clean / exit 0. Use `$TMP_VAULT` only. **[Agent: general-purpose]**

- [ ] **Slice 6: Docs polish + CONTRIBUTING already present + roadmap**
  - [ ] Retire “doctor roadmap-only” prose in `docs/reference/cli.md` / related; tick roadmap `#110` when behavior matches; ensure CONTRIBUTING heal-catalog section stays accurate; agent_kit or help epilog mention if required by lifecycle help tests. **[Agent: general-purpose]**
  - [ ] Verify: `tests/test_reference_coverage.py` and CLI help smoke include `doctor`. **[Agent: general-purpose]**

- [ ] **Slice 7: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 327-doctor` and `@regression` if suitable for long-term regression. Prefer `tests/test_doctor_acceptance.py` (no issue digits in filename). **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
