# Flow log — 255-demo-pipeline-parity (#255)

## fetch-ticket
- Issue #255 open: demo Pipeline state on GitHub Pages
- Route: `/implement-feature` (enhancement label)
- Next: implement

## implement
- Extracted `llmwiki/synth/state_backfill.py` (`backfill_synth_state_from_wiki_pages`, `is_shipped_demo_vault`)
- `build` reconciles shipped `demo/` before Pipeline snapshot refresh
- `migrate topic-kinds` uses shared backfill module
- Refreshed committed `demo/llmwiki-state.json` (+ `.js` via lint/build)
- Tests: `tests/test_demo_pipeline_state_parity.py`
- Docs: `docs/deploy/github-pages.md`, CHANGELOG
- PR keyword: `Closes #255`
