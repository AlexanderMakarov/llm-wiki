# Flow log — #170 wiki-all skill pipeline

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/170 (OPEN, label: bug)
- Title: shipped /wiki-all skill describes a pipeline that omits synth
- Symptom: `llmwiki/agent_kit/skills/wiki-all/SKILL.md` teaches wrong stages (init/sync/graph/build/lint), omits synth, wrong order, hardcoded Obsidian path, chains per-stage cmds instead of `llmwiki all`, stale lint-rule count
- Related: #156 fixed sibling command `wiki-all.md`; skill left OOS; noted in `context/spec/010-automation-profiles/flow-log.md`
- No comments; no linked PR
- Next: resume-detection

## resume-detection
- Issue OPEN; no PR for #170; no prior `context/spec/170-*`
- Owning feature spec for agent-kit packaging: `008-make-product-explain-itself` (ships kit); `010-automation-profiles` documented `all` stages but explicitly deferred this skill
- SPEC_NAME: `170-wiki-all-skill-pipeline` (orphan fix-as-spec #164)
- Already-fixed? No
- Next: workspace

## workspace
- BRANCH: `fix/170-wiki-all-skill-pipeline`
- WT: `.claude/worktrees/fix-170-wiki-all-skill-pipeline`
- TMP_VAULT: `$WT/.worktree-vault` (isolated config.json)
- Dirty primary tree: untracked `candidates*.png` only (unrelated)
- Next: diagnose

## diagnose
- Reproduced: SKILL.md L12–16 stage list init/sync/graph/build/lint (omits synth; wrong order); L22–69 per-stage cmds; L50–55 hardcoded Obsidian home path; "14" lint rules; frontmatter/description stale
- Sibling `commands/wiki-all.md` already correct post-#156
- Root cause: skill never updated when synth joined `all`; #156 left skill OOS
- Actual order: `run_pipeline` sync → synth → build → graph → lint (no init)
- Honesty checks: none for skill stage content (presence-only install/packaging tests)
- Proposed fix: rewrite skill to mirror command; drop hardcoded export path; add assert vs pipeline stage order
- Next: classify

## classify
- Verdict: **conformance** — code/`run_pipeline` and sibling command are correct; skill violates them
- SPEC_NAME: `170-wiki-all-skill-pipeline` (orphan); no pre-existing functional-spec to amend (010 deferred this file; 008 only packages kit)
- Amend-spec: skip
- Next: fix

## fix
- Rewrote `llmwiki/agent_kit/skills/wiki-all/SKILL.md` to mirror `commands/wiki-all.md` (single `llmwiki all`; sync→synth→build→graph→lint; no init/Obsidian path/numeric lint count)
- Added `PIPELINE_STAGES` in `llmwiki/pipeline.py` for honesty tests
- CHANGELOG Fixed bullet under `[Unreleased]` for #170
- Next: testing-expert

## regression-test
- Added `tests/test_170_wiki_all_skill.py` to lock wiki-all skill and command content to `PIPELINE_STAGES` order and block #170 regressions
- pytest: 4 passed; ruff clean
- Next: verify-criteria

## verify-criteria
- AC stage list == PIPELINE_STAGES: pass (sync→synth→build→graph→lint)
- AC init not a pipeline stage: pass (prose clarifies; no numbered init)
- AC directs at `llmwiki all`: pass
- AC no hardcoded vault path: pass (no Documents/Obsidian…)
- AC no drifting lint count: pass ("every registered lint rule")
- AC honesty check: pass (`tests/test_170_wiki_all_skill.py`)
- Evidence: worktree pytest + skill/command parse; no live-vault mutation needed for this surface
- Next: smoke confirm (paused)

## smoke-confirm
- Operator asked agent to self-check; worktree pytest 4/4, install-agent-kit writes corrected skill, skill/command/PIPELINE_STAGES parity PASS
- Next: local-review

## local-review
- Verdict: Approve; Blockers 0; Nits 3 (`context/spec/170-wiki-all-skill-pipeline/review.md`, session-only)
- Keep #2 (lock PIPELINE_STAGES to run_pipeline banners) + #3 (command gets same init/Obsidian asserts); drop #1 (commit stage)
- Applied: lint banner literal `lint`; `test_pipeline_stages_match_run_pipeline_banners`; shared asserts on command test
- Next: commit-push

## commit-push
- Staging product fix + flow-log; excluding review.md
- Next: push then remote-gates

