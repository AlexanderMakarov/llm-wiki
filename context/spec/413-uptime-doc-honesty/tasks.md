# Tasks: 413-uptime-doc-honesty

## Slices

- [x] **Slice 1: Delete guide, retarget links, update contracts + demo + CHANGELOG**
  - [x] Delete `docs/uptime.md`; retarget `docs/deploy/github-pages.md` and `docs/maintainers/RELEASE_PROCESS.md` away from it; ensure publisher / version-freshness guidance remains in those docs without claiming an uptime workflow. **[Agent: general-purpose]**
  - [x] Remove demo raw + wiki uptime source, prune `demo/wiki/index.md`, entity wikilink / sources, and `demo/llmwiki-state.json` entry; fix deploy-github-pages demo raw link + stale “no separate scheduled freshness” claim. **[Agent: general-purpose]**
  - [x] Update `tests/test_demo_session_freshness_workflow.py` (drop `UPTIME_DOC` / uptime-specific tests and map entry); add `CHANGELOG.md` Unreleased *Removed* bullet for #288. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/test_demo_session_freshness_workflow.py -q`; `test ! -f docs/uptime.md`; grep tracked tree for `docs/uptime.md` / pasteable `uptime.yml/badge` outside historical `context/spec/**` and this spec — expect none; delete any ephemeral verify artifacts. **[Agent: testing-expert]**

- [x] **Feature Testing & Regression**
  - [x] Confirm FR1–FR4 acceptance criteria with evidence (paths gone, links retargeted, demo pruned, CHANGELOG bullet, pytest green); annotate any new/changed tests with `# @spec: 413-uptime-doc-honesty` / `# @regression` as applicable. **[Agent: testing-expert]**
