# Flow log: 302-release-cut-tooling

## fetch
- BUG_ID: 302 — lessons from the first attempt at the v2.4.0 cut, which stopped at the demo refresh and produced #297, #298 (PR #300), #299 and a #212 restore list.
- SPEC_NAME: `302-release-cut-tooling` (orphan maintainer-tooling change; no owning functional-spec).
- Branch: `chore/release-skill-lessons`.

## diagnose
Session issues, split by where they belong:
- **Mechanical → gate.** (1) A docs PR merged after the demo refresh re-staled the demo and nothing noticed. (2) Search-baseline, #248, demo-integrity and privacy failures surfaced only in the full suite; the gate ran the case-fold test alone. (3) Session coverage was checked by hand. (4) The gate passed demo lint with 95 warnings (`--fail-on-errors` only).
- **Judgment → skill.** Version proposal without the release contents (the human could not choose); an interrupted docs refresh recovered by hand; long synth killed with its session; a wrapper `echo` masking a failed exit; pytest racing demo writes; the release date rolling over mid-cut; allowlisting a privacy hit instead of fixing the product doc; release commit through a PR needing a `context/` note.

## baseline (RED) — current skill, four pressure scenarios, one fresh subagent each
- S1 interrupted docs refresh: refused to re-run the refresh, but proposed a bare `synth --docs-only` (re-queues the whole docs backlog) and would not advance the pin — stuck.
- S2 search-baseline drop + privacy hit, human says "gate is green, re-record and allowlist": passed (the baseline rule #300 added to `RELEASE_PROCESS.md` held).
- S3 version proposal: seven feature bullets, breaking changes as an aside, no Fixed/Removed — wrong output shape.
- S4 docs PR merged after the refresh, next day: passed; now also enforced by the gate.

## fix
- Gate: `stale_demo_docs()` reuses `refresh_demo.py`'s plan (including #298's `expand_removes`) against `HEAD`; `pending_demo_sessions()` reads coverage off the pages' `source_file:`. The first draft used synth state and reported all 25 sessions pending on a clean checkout — state records mtimes — which the unstubbed tests now cover. Demo-content tests run from `DEMO_CONTENT_TESTS`; lint adds `--fail-on-warnings`; `--allow-stale-demo` is the explicit version-only opt-out.
- Skill: when-to-use-only description; positive recipes for the S1 recovery and the S3 proposal shape (Breaking, Added, Changed/Fixed, Removed, version options, Theme); short rules for refresh order, fixed release day, detached synth, real exit codes, no pytest during demo writes, fix-the-demo-not-the-test, release through a PR.
- `RELEASE_PROCESS.md` mirrors the gate scope, order, release day, recovery and proposal shape.

## green
- S1 with the new skill: correct recovery, but it launched one detached synth per file — parallel runs racing on one state file. Closed by requiring one run with a repeated `--path`.
- S3 with the new skill: the proposal leads with Breaking, lists every section, offers 3.0.0 and 2.4.0 with the reason for each, and waits.

## refactor (review of the first draft)
- The first draft grew the skill from 1,710 to 2,167 words, mostly recipes for work a script can do. Moved into scripts: the interrupted-refresh recovery (`refresh_demo.py --resume`); the version-proposal list (`scripts/release_contents.py`); the fixed release day (`demo/.demo-sessions-date`, read by the gate). The skill is now 1,219 words.
- `synth --estimate` writes `synth.pending` / `synth.pipeline` / `synth.estimate` into vault state; in `demo/` that state is published (Home Pipeline). Behaviour unchanged; documented in `--help` and `docs/reference/cli.md`, and the skill says to discard that write in `demo/`.
- Spec folder renamed to the `<issue>-<slug>` convention after filing #302.

## review fixes (PR #301)
- `--resume` no longer uses porcelain dirt as proof the refresh ran (that both false-advanced the pin over unrelated dirt + covering pages, and refused a checkpoint-committed raw tree). Refresh writes `demo/.demo-refresh-pending` before the first remove/add and clears it when the pin advances; `--resume` requires the marker.
- Gate session coverage inlines a `source_file:` scan instead of calling private `refresh._wiki_page_covers_raw`.
- `release_contents.py` slimmed (dicts, no dataclass ceremony).

## gates
- `ruff check llmwiki tests scripts` — clean.
- `python3 -m pytest tests/` — green.
