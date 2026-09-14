# Tasks: Release-cut local demo review (#240)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Worktree: `.claude/worktrees/feat-240-release-demo-local-review`. Drive `python3 -m llmwiki` from the worktree. Mutating vault commands use `$TMP_VAULT` (`.worktree-vault`) only — never the live Obsidian vault. Do not regenerate committed `demo/usage/` unless a test requires a fixture write under a temp path.

Hired specialists: none required — **generalPurpose** for implementation; **testing-expert** for test slices.

---

- [ ] **Slice 1: `release_demo_gate.py` (usage + build + URL + case-fold)**

  > End state: maintainer can run `python3 scripts/release_demo_gate.py --today YYYY-MM-DD` and get usage regen, local demo build, printed `file://…/index.html`, case-fold pytest, and non-zero exit on failure — without relying on LLM prose for those steps.

  - [ ] Add `scripts/release_demo_gate.py` (stdlib + existing helpers). CLI: `--today YYYY-MM-DD` (required for real runs), `--dry-run`, `--skip-usage`, `--out DIR` (default `/tmp/demo-site`). Steps: call `generate_demo_usage` logic (subprocess or import) unless `--skip-usage`; run `python3 -m llmwiki build --vault demo --out <DIR> --local-root /home/user`; print concrete `file://<DIR>/index.html` (and optional serve one-liner); run `python3 -m pytest tests/test_case_insensitive_paths.py -q`; prefer also `python3 -m llmwiki lint --vault demo --fail-on-errors`. Exit 0 only when mechanical steps succeed; non-zero on failure. No version bump / git / CHANGELOG. **[Agent: generalPurpose]**
  - [ ] Add `tests/test_release_demo_gate.py`: `--dry-run` exits 0 and prints planned URL/steps; failure path returns non-zero (mock/subprocess); `--today` forwarded to usage path. Keep tests off the live vault and avoid rewriting committed `demo/usage/` on the default happy path (use tmp / dry-run / mocks). **[Agent: testing-expert]**
  - [ ] Verify: `ruff check scripts/release_demo_gate.py tests/test_release_demo_gate.py`; `python3 -m pytest tests/test_release_demo_gate.py -q`. **[Agent: testing-expert]**

- [ ] **Slice 2: Thin skill + RELEASE_PROCESS around the gate**

  > End state: skill and process doc say “run the gate script → stop on non-zero → pause for human demo OK” instead of duplicating usage/build command lists; CI-does-not-invent and case-fold are named; session-regen wording matches in-place-by-slug.

  - [ ] Update `docs/maintainers/RELEASE_PROCESS.md`: after sessions/docs/synth completeness, run `release_demo_gate.py --today …`; commit `demo/usage/` (+ keep `#255` state bullet); human reviews printed URL before tag push; clarify Pages/CI only build + version-assert. Keep incomplete-synth hard stop. **[Agent: generalPurpose]**
  - [ ] Update `.claude/skills/release/SKILL.md` to thin wrappers around the script + human pause; fix “filenames change” → in-place-by-slug alignment with process doc. Optional one-liner in `docs/maintainers/REFRESH_DEMO.md`. CHANGELOG Unreleased Changed bullet for #240. **[Agent: generalPurpose]**
  - [ ] Extend `tests/test_209_release_skill.py`: skill + RELEASE_PROCESS mention `release_demo_gate`, human pause after gate / local URL, and CI does not invent sessions/usage. Run those tests + `ruff` on touched Python. **[Agent: testing-expert]**

- [ ] **Slice 3: Feature Testing & Regression**

  > Verifies FR1–FR6 against functional-spec.md after slices 1–2.

  - [ ] Map FR1–FR6 to tests/docs evidence; fill any gap with `@spec: 250-release-demo-local-review` coverage. Confirm `pages.yml` still has no session/usage generation. **[Agent: testing-expert]**
  - [ ] Full `python3 -m pytest tests/ -q` and `ruff check llmwiki tests scripts` on the worktree; fix failures. **[Agent: testing-expert]**
