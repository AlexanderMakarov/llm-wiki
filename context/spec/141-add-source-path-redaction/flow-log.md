# Flow log — #141 add source path redaction

## fetch-bug (2026-08-28)

- **BUG_ID:** 141
- **Title:** llmwiki add records the absolute source path unredacted, leaking the operator's home directory
- **Symptom:** `llmwiki add` writes `source: "/home/<operator>/…"` in raw/docs frontmatter; sync redacts to `/home/USER/…`
- **Repro confirmed** in worktree `$WT`: `grep ^source:` shows full home path
- **Branch:** fix/141-add-source-path-redaction
- **WT:** .claude/worktrees/fix-141-add-source-path-redaction
- **TMP_VAULT:** $WT/.worktree-vault

## resume-detection (2026-08-28)

- Issue **OPEN**; no merged PR for #141
- **SPEC_NAME:** 141-add-source-path-redaction (orphan fix-as-spec)

## classify (2026-08-28)

- **Verdict:** Conformance bug — privacy/redaction contract for committable `raw/` is correct; `add` violates it
- **Amend spec:** skip (no functional-spec; no divergence)

## fix + regression-test + verify (2026-08-28)

- **Root cause:** `convert_path()` set `source_label = str(real)` without redaction
- **Fix:** `_source_path_label()` — cwd-relative when under cwd; `_substitute_path_username` via `_resolve_convert_config`
- **Files:** llmwiki/add_doc.py, tests/test_add_doc.py, CHANGELOG.md, docs/privacy.md
- **Test:** `test_source_path_label_redacts_username_and_prefers_relative`
- **Evidence:** `source: "docs/test-doc.md"` after add (no home path leak)
- **Classification:** conformance (no spec amend)
- **Local review:** Request changes → fixed CHANGELOG #149 restore, docstring, removed scratch file
- **Next:** commit-push → PR → CI → merge (pending user)
