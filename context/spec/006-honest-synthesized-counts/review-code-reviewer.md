# Code review — 006 honest synthesized counts (#81)

**Reviewer:** code-reviewer subagent
**Scope:** `git diff origin/main...HEAD` (spec docs only) plus all uncommitted work in the `feat/81-honest-synthesized-counts` worktree — `llmwiki/build.py`, `llmwiki/cli.py`, `llmwiki/render/js.py`, `llmwiki/synth/estimate.py`, `llmwiki/synth/pipeline.py`, `llmwiki/synth/reporting.py`, `tests/test_state_widget.py`, `tests/test_synthesize_estimate.py`, `tests/test_81_acceptance.py` (untracked), docs, CHANGELOG, `context/`.
**Verdict:** **Request changes** — 1 critical, 2 important.

## Gate status

| Gate | Result |
|---|---|
| `ruff check llmwiki tests scripts` | pass (exit 0) |
| `python3 -m pytest tests/ -q` | pass (no failures; skips only) |
| CHANGELOG under `## [Unreleased]` | present (`### Changed`, #81 entry) |
| Docs for user-visible change | `docs/reference/cli.md`, `docs/reference/ui.md`, `docs/UPGRADING.md`, `docs/cheatsheet.md`, `docs/tutorials/08-synthesize-with-ollama.md` all updated |
| AWOS `context/` touched (CONTRIBUTING #13) | yes |
| New runtime deps | none |
| One concern per PR | yes |

## Critical

### C1. `On disk` sessions are bucketed by a frontmatter field synth never writes, producing phantom agent rows (confidence 95)

`llmwiki/synth/pipeline.py:486` — inside `scan_wiki_sources_disk`, on-disk session pages are attributed with `detect_agent_label(meta)` where `meta` is the **wiki page's** frontmatter. But `_build_source_page` (`llmwiki/synth/pipeline.py:1174-1186`) writes only `title / type / tags / date / source_file / project / model / last_updated` — there is **no `agent:` key**. So `detect_agent_label` skips its step-1 (explicit `agent:`) branch and falls through to step 2, model-family inference (`llmwiki/agent_label.py:26-34`).

Meanwhile the eligible-source columns (`raw` / `pending` / `synthesized`) are bucketed from the **raw session's** frontmatter at `llmwiki/synth/estimate.py:354`, which *does* carry the adapter's `agent:` stamp. The two sides therefore disagree whenever the producing agent's name differs from the model family — OpenClaw, Cursor, or OpenCode running a Claude or GPT model.

Reproduced against this branch (one raw session, one real page, no stubs):

```
label=OpenClaw     kind=session  raw=1 synth=1 pending=0 on_disk=0
label=Claude       kind=session  raw=0 synth=0 pending=0 on_disk=1
label=Stubs        kind=stubs    raw=0 synth=0 pending=0 on_disk=0
```

One session and its one page render as **two rows**: the real agent row shows `On disk 0`, and a phantom `Claude` row appears with `Raw 0 / To synthesize 0 / Synthesized 0 / On disk 1`. That is precisely the "numbers that don't line up" confusion #81 exists to remove, and it is worse than the pre-change table because the new row implies an agent that contributed nothing. The default vault for this repo is an OpenClaw vault, so this fires on the maintainer's own Home page.

The existing tests do not catch it because their fixtures write frontmatter real synth output never produces — `tests/test_synthesize_estimate.py` and `tests/test_state_widget.py` both put `agent: claude-code` directly into the `wiki/sources/` page.

**Fix:** attribute on-disk session pages by resolving `source_file` back to the raw session's agent (the estimate walk already computes `agent_label` per source key), rather than re-inferring from the page. Alternatively add `agent: {agent}` to the `_build_source_page` frontmatter list — but that only fixes pages written after the change, so existing vaults still mis-bucket until re-synth; the join is the safer fix. Either way, change the test fixtures to use frontmatter matching `_build_source_page` exactly (no `agent:` key) so the regression stays caught.

## Important

### I2. The Home widget's empty-state guidance is now unreachable (confidence 85)

`llmwiki/synth/estimate.py:511-524` appends the `Stubs` row **unconditionally**, before the `files_other > 0` guard. Verified on an empty vault:

```
EMPTY VAULT pipeline_rows = [{'id': 'stubs', 'label': 'Stubs', ..., 'on_disk': 0}]
```

`llmwiki/render/js.py:215` gates the onboarding message on `if (!bodyRows)`. With one row always present, `bodyRows` is never falsy, so the branch is dead code and the string at `js.py:216` — "No pipeline rows yet — run `llmwiki sync` then `llmwiki synth --estimate`" — can no longer render. A user on a fresh vault now sees a table whose only row is `Stubs / — / — / — / 0` plus an all-zero Total footer, instead of the instruction telling them what to run. This also silently drops the guidance that `synth_pipeline_shape_ok` (`llmwiki/state_store.py:89-102`) explicitly documents as a valid state ("A present but empty `rows` list is valid (genuinely empty vault after sync/estimate)").

**Fix:** append the `Stubs` row only when there is at least one other row, or when `files_stubs > 0` (mirroring the `files_other > 0` guard directly below it). If the always-present Stubs row is deliberate, then move the empty-state check in `js.py` to test for "no non-`diskOnly` row with any non-zero count" instead of `!bodyRows`, and add a test asserting the guidance still renders for an empty vault — there is currently no test covering that string anywhere in `tests/`.

### I3. Untracked screenshot from a locally-built personal vault would be committed, and does not satisfy the UI checklist (confidence 80)

`docs/screenshots/006-honest-synthesized-counts-pipeline-home.png` is new, untracked, and **not gitignored** (`git check-ignore` returns no match), so any `git add -A` sweeps it into the PR. `docs/screenshots/` does not exist on `origin/main`, so this also introduces a new binary-artifact directory without an established convention.

Two problems:

1. **Privacy (CONTRIBUTING "Privacy rules" #7 / the no-local-vault rule).** Per the repo's local-site-build convention a bare `llmwiki build` renders the maintainer's personal Obsidian vault, so this is a screenshot of a personal vault. The visible crop happens to show no paths or project names, but committing personal-vault renders is exactly what the rule prohibits; PR-attached images are the intended channel, not repo files.
2. **It does not serve as the evidence it looks like.** Pre-merge checklist item 14 requires UI changes verified in **light and dark** mode with screenshots. This is light mode only, and the image is cropped above the `Pipeline state` table header row — it does not show the new `On disk` column, the `Stubs` row, or the `—` cells at all. Nothing in this branch demonstrates the changed table renders correctly in either theme.

**Fix:** delete the file (or gitignore `docs/screenshots/`), and attach light + dark captures of the full pipeline table to the PR body instead. While capturing, confirm the `—` placeholder cells and the new 5-column footer alignment hold in both themes.

## Non-blocking notes (below the report threshold)

- `_tags_contain` (`llmwiki/synth/pipeline.py:421-428`) uses substring matching on the string branch (`needle.lower() in tags.lower()`) but exact matching on the list branch. A string `tags: raw-docs-archive` would count as a `raw-doc` page. Tags are near-always a list here, so impact is negligible, but the two branches should agree.
- `print_source_pages_current_state` emits `1 sessions` / `1 docs` for singular counts. Cosmetic, and the current tests assert the plural form, so changing it means updating them.
- Total diff is roughly 690 changed lines against the ≤500-line PR guideline. Most of the excess is docs and `context/`, so this is likely fine, but worth a one-line waiver in the PR body.
- All implementation work is uncommitted, so commit atomicity, conventional-commit titles, GPG signing, and AI-co-author trailers (checklist item 16) could not be reviewed.
