# Flow log — #253 private vaults keep real home paths

## fetch-bug (2026-09-14)

- **BUG_ID:** 253
- **Title:** bug(convert/redaction): private vaults should keep real home paths; USER placeholder is for publish/git
- **Symptom:** `sync` rewrites `/home/<you>/…` → `/home/USER/…` in vault `raw/sessions/` and the local site, although the vault is local-only
- **Acceptance:** private vault keeps real home paths (incl. Windows forms); publish/share path still supports `USER`/custom replacement; tests cover both modes; docs updated; documented restore path for over-redacted vaults
- **Non-goals:** real usernames in PRs/CHANGELOG/fixtures; disabling token/secret redaction

## resume-detection (2026-09-14)

- Issue **OPEN**; no PR references #253
- No owning `functional-spec.md` for username redaction → **SPEC_NAME:** 253-private-vault-real-paths (orphan fix-as-spec)

## workspace (2026-09-14)

- **Branch:** fix/253-private-vault-real-paths (from origin/main 4e6566e)
- **WT:** .claude/worktrees/fix-253-private-vault-real-paths
- **TMP_VAULT:** $WT/.worktree-vault (worktree `config.json` points at it)

## diagnose (2026-09-14)

- **Repro (code path):** `sync` → `convert_all` → `_resolve_convert_config(None)`; `_ensure_real_username` fills `$USER`; `Redactor.__call__` → `_substitute_path_username` rewrites `/home/<u>/` and `-home-<u>-`
- **Root cause:** no switch for username redaction — empty `real_username` is re-autodetected, so a private vault cannot opt out; build-time `display_cwd` restores only the `cwd` field, body text keeps `USER`
- **Publish paths:** `migrate raw-redaction` (explicit, must keep redacting); `llmwiki-action.yml`/`action.yml` sync; demo generator hardcodes `/home/USER` (unaffected)
- **Fix shape:** `redaction.redact_username` bool; private default off in `DEFAULT_CONFIG` + `examples/sessions_config.json`; `Redactor` + `add_doc._source_path_label` honor it; hand-built configs without the key keep redacting; docs + CHANGELOG + UPGRADING

## classify (2026-09-14)

- **Verdict:** Divergence — `docs/privacy.md` documents username redaction ON by default; the fix intentionally changes that documented behavior
- **Amend spec:** no pre-existing `functional-spec.md`; the amendment lands in `docs/privacy.md`, policy docs, configuration docs and UPGRADING

## decisions (2026-09-14, operator)

- `redaction.redact_username` default **false** (private vault keeps real paths); publish/share sets true or runs `migrate raw-redaction`
- **Reverse migrate in this PR:** `llmwiki migrate raw-unredaction` (placeholder → real username in `raw/`)
- GitHub Action code left as-is; docs warn repos that commit `raw/` to set the key

## fix + regression-test (2026-09-14)

- **Files:** llmwiki/convert.py, llmwiki/add_doc.py, llmwiki/cli.py, llmwiki/build.py (comments), llmwiki/exporters.py (docstring), scripts/migrate_raw_encoded_username.py (`raw-unredaction`), examples/sessions_config.json, docs (privacy, configuration, configuration-reference, UPGRADING, reference/cli, adapters/claude-code, windows-setup), agent_kit llmwiki-sync SKILL.md, CHANGELOG.md
- **Tests:** new `tests/test_redact_username_toggle.py` (27 cases; 17 RED on origin/main, all green on fix); migrate unit tests in `tests/test_migrate_raw_encoded_username.py`; `tests/test_112_acceptance.py` migrate catalog 6→7

## verify-criteria (2026-09-14)

- **Private default:** real scoped `sync` into `$TMP_VAULT` → new raw files keep the real home path, none carry `/home/USER/`; site HTML shows real paths
- **Publish mode:** covered by `test_redact_username_true_*` + `test_convert_all_raw_output_follows_toggle[publish]`
- **Restore path:** `migrate raw-unredaction --real-username alice` on a synthetic raw file — dry-run writes nothing; run rewrites cwd, tool path, dash-encoded segment, leaves prose `USER`; rerun rewrites nothing; `--real-username USER` refused exit 2
- **Privacy:** diff + new files contain no real username/home; ruff clean

## smoke confirm (2026-09-14)

- Operator asked the agent to run the live commands itself
- **Result:** `migrate raw-unredaction` then `sync` + `build` on the live vault → session raw files and site pages carry real home paths; remaining `/home/USER/` hits are literal placeholder text; full suite green
- **Incident (flow defect):** the worktree `config.json` holds only the vault path, so a worktree `sync` against the live vault ignored the operator's `adapters`/`filters` and ingested sessions from a disabled adapter plus their project stubs
- **Rollback (operator-approved):** backed up state/index/stubs outside the repo; removed exactly the ingested raw files, stubs and their sync/synth state entries; reindexed `wiki/index.md`; rebuilt site; counts verified back to pre-smoke
- **Flow fix:** `.claude/commands/fix-bug.md` Step 8 live-smoke rule + `delivery-flow.md` §10 entry

## local-review (2026-09-14)

- **Verdict:** Request changes — 2 Blockers, 6 Nits (review file session-only, not committed)
- **Kept (all):** B1 policy docs reworded (CONTRIBUTING, SECURITY, architecture, framework, feature-matrix, research); B2 CHANGELOG `**Breaking:**` + UPGRADING/Action docs warning (no Action code change) + PR label `breaking`; N1 dead `migrate_text` removed; N2 shared migrate loader in cli.py; N3 unredaction limits documented + test; N5 live-vault counts removed from flow docs; N6 `cwd` display note in privacy.md
- **N4:** PR size (tests ≈ half) and bundled flow lesson stated in the PR body
- **Next:** static gate → commit-push → PR
