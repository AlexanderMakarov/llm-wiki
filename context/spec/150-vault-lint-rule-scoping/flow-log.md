# Flow log — 150-vault-lint-rule-scoping

Feature: per-vault lint rule scoping (#150). Driven by `/implement-feature`.

---

## Stage: fetch-ticket — done

- Source: GitHub issue [#150](https://github.com/AlexanderMakarov/llm-wiki/issues/150), state `OPEN`, label `important`, no comments.
- Ask: let a vault opt out of individual lint rules via config — explicitly **not** a growing `--rules` allowlist in `wiki-checks.yml`. Then the demo can keep `content_freshness` off and still fail CI on the other warning-severity rules.
- Linked context: #109 amended its R4 to errors-only for this reason. Recorded in `context/spec/008-make-product-explain-itself/` (functional-spec R4, technical-considerations Stage B2, risk table, flow-log). No unreachable links.
- Roadmap item: Phase 1 → "Pipeline efficiency and recovery" → "Per-vault lint rule scoping (#150)".

## Stage: resume-detection — done

- Issue open; no spec directory for #150; no branch, no worktree, no open or merged PR referencing 150. Nothing to resume — full chain from spec.

## Stage: workspace — done

- Branch `feat/150-lint-rule-scoping` from `origin/main` @ `cefb89e`.
- Worktree `.claude/worktrees/feat-150-lint-rule-scoping`; `LLMWIKI_SKIP_AUTOMATION=1 bash ./setup.sh` (note: `setup.sh` is not executable in a fresh worktree checkout — invoke via `bash ./setup.sh`, the §2 recipe's `./setup.sh` fails with "Permission denied").
- Throwaway vault `.worktree-vault` created and initialised; worktree `config.json` points `vault.default_path` at it. Primary checkout `config.json` never copied.
- Primary checkout working tree was dirty with two untracked screenshots (`candidates*.png`) predating this run — unrelated, left alone.

## Stage: specs — functional spec drafted, awaiting approval

- Spec directory: `context/spec/150-vault-lint-rule-scoping/`.
  - **Decision:** `.awos/scripts/create-spec-directory.sh` allocated `162-` because it takes `max+1` over a directory set that now mixes sequential feature indices (`001`–`010`) with issue-numbered fix directories (`140`, `161`). `162` corresponds to nothing. Directory renamed to `150-` to match the issue, consistent with the two most recent directories.
- `functional-spec.md` written. Six requirements: R1 vault-carried opt-out declaration, R2 skipped checks always named in both report forms, R3 unknown rule name fails loudly, R4 run-time option to fail on warnings, R5 demo opts out of `content_freshness` + its CI gate tightened to warnings, R6 documentation with an explicit hiding-real-findings caution.
- **User answers taken in place of the interview** (the question set was declined in favour of a direct answer): opt-out lives in the vault itself; switch-off only, no severity re-grading; must be documented; concrete outcome now is `content_freshness` off for the in-repo demo vault. User also stated the real cure for demo staleness is refreshing the demo more often — recorded in the spec's rationale and placed out of scope for this work.
- **Assumption stated to the user, not blocked on:** CI gate tightening (R5) is in scope, because #150's stated goal is that the demo *can enforce* warnings; shipping the mechanism alone would not deliver it.

### Investigation that reshaped the spec (2026-08-26)

The user asked why the demo cannot enforce warnings and whether it has broken links. Measuring instead of trusting #150's recorded premise changed the feature substantially.

Measured on the committed demo (120 pages, 0 errors, 123 warnings):

| Rule | Findings | Note |
| --- | --- | --- |
| `link_integrity` | 120 (106 distinct targets) | — |
| `contradiction_detection` | 3 | — |
| `content_freshness` | **0** | demo pages carry `last_updated` 2026-08-11/12; 90-day rule fires ~2026-11-09 |

So #150's premise ("the only rule that warns on the demo is `content_freshness`") is stale: the rule is currently silent and `link_integrity` is the real blocker.

**Root cause of the 120.** Four components disagree about an unmaterialized `[[wikilink]]`:

- `synth` writes one for every topic it names (vault schema hard rule 3, "cross-link everything").
- `candidates_harvest` materializes only targets named by `DEFAULT_MIN_REFS = 3`+ source pages. Measured distribution of the 106 broken targets: **92 at 1 ref, 14 at 2, zero at 3+**.
- `topics.py` treats the same names as first-class nodes and builds topic pages (29 built; 22 of them appear in "broken" links).
- `link_integrity` (warning) reports all of them.

Not demo-specific: read-only probe of the operator's live vault → **650 `link_integrity` + 24 `contradiction_detection` across 717 pages**, same shape.

**Options put to the user:** B1 resolve against topic pages · B2 unlink what nothing materializes · B3 lower the threshold so everything materializes · B4 = B1+B2.

**User decisions:**

- **B2 rejected**, with the decisive argument: rewriting `[[X]]` → `X` is irreversible, since nothing marks where the reference was, so recovery needs a full re-synth (LLM spend, non-deterministic). Recorded in the spec's Out-of-Scope.
- **B3 direction adopted, but inverted:** rather than the demo lowering its threshold, `lint` gains `--min-refs` and `link_integrity` honours the same threshold harvest uses, with the stock value imported from the harvest module so there is one definition.
- **The demo runs at stock settings** — "a good demo uses defaults to be as representative as possible". Its only declared opt-out is `content_freshness`.
- **Pipeline threshold plumbing fixed in this branch.**

**Measured outcome of the adopted design** (threshold-aware `link_integrity` at the stock threshold of 3): demo `120 → 0`; live vault `650 → 256`, and the 256 are genuine gaps (targets at 3+ refs with no page).

**Correction issued to the user.** My earlier claim that "`llmwiki all` ignores the existing `--min-refs` flag" was wrong. `--min-refs` is added only by `_add_synth_arguments` (cli.py:2643) to the `synth` and deprecated `synthesize` parsers (2718/2725); the `all` parser never defines it, so `getattr(args, "min_refs", DEFAULT_MIN_REFS)` at `pipeline.py:309` is equivalent to the hardcoded default today. Accurate statement: `all` offers no way to set the threshold at all. Still wired in this branch.

**Residual demo findings triaged** (3 `contradiction_detection`) — 1 genuine, 2 rule-precision bugs:

- `sources/01-installation/…` — **genuine documentation defect**, verified in the repo: `pyproject.toml:10` `requires-python = ">=3.12"`, `docs/tutorials/01-installation.md:10` "Python 3.12+", but line 26 says `# expect 3.9 or newer`. Fixed under R8.
- `sources/cli-reference/…-07` — opens "None identified." but the explanation contains "conflict with prior wiki entries", so `_AFFIRMATIVE_CUE_RE` overrides `_FILLER_OPENING_RE`. R7.
- `sources/configuration-reference/…-01` — "None evident."; `evident` is absent from `_NONE_SYNONYMS`. R7.

### Stage: specs — functional spec rewritten, awaiting approval

Nine requirements: R1 vault-carried opt-out declaration · R2 skipped checks always named · R3 unknown name fails loudly · R4 threshold-aware cross-reference check with one shared stock value · R5 threshold reaches the full-pipeline path · R6 run-time fail-on-warnings · R7 conflicting-claims boilerplate precision · R8 demo passes an enforced gate at stock settings, including the Python-version doc fix · R9 documentation with the hiding-real-findings caution.

**Approved by the user 2026-08-26 ("lgtm"). Status → Approved.**

### Stage: specs — technical spec drafted, awaiting approval

`technical-considerations.md` written. Five changes: vault settings file, one threshold definition, threshold plumbing, reporting honesty, MCP parity — plus two `contradiction_detection` precision fixes, the demo settings file, the CI flip, and the surfaced doc defect.

Design decisions worth carrying forward:

- **`<vault>/llmwiki.json`** chosen over the clone's `config.json` (gitignored, install-scoped, cannot travel with the demo) and over a hidden `.llmwiki/` path (a committed file a reviewer must read should be visible). Accepts a list or an object with reasons.
- **`DEFAULT_MIN_REFS` moves to a new `llmwiki/thresholds.py`.** A direct import from `llmwiki.lint` to `candidates_harvest` would be circular — `candidates_harvest` already imports `_norm_slug` from `llmwiki.lint.rules.link_integrity`. Re-exported for existing importers.
- **Only reference *counting* is shared between harvester and rule, never resolution.** They invert each other deliberately: harvest treats `candidates/` as unresolved (evidence must refresh each run) and `archive/` as resolved (dismissal ledger, #140); lint does the opposite. Sharing resolution would break one.
- **Options are set on the rule instance, not passed as a kwarg.** 16 of 17 rules declare `run(self, pages, *, llm_callback=None)`, and `run_all` converts rule exceptions into error-severity issues — a new kwarg would have turned a clean vault into 16 errors.
- **`run_all` keeps its signature**; the richer `run_lint` → `LintOutcome` is additive, so ~20 test call sites are untouched.

Bug found while specifying: `cmd_lint` returns on `--fail-on-errors` before `_apply_default_vault` and `update_state`, so a failing lint never records `last_lint_run_at`. `--fail-on-warnings` must not inherit it.

Both `contradiction_detection` fixes verified empirically before being written down: adding `evident` to `_NONE_SYNONYMS` and modal hypotheticals (`could|would|might|may`) to `_NEGATOR_RE` turns the two demo pages into filler while leaving the genuine `01-installation` finding — and a crafted `"None in the summary. However, this page contradicts prior guidance…"` regression — still flagged.

**Correction issued to the user.** I first recorded MCP `wiki_lint` as a risk of reading reshaped internals. It does not: `tool_wiki_lint` (`llmwiki/mcp/server.py:989`) is an independent reimplementation importing only `load_pages`. Also unfounded was a suspicion that it lints the git clone — `REPO_ROOT` in that module is `resolve_content_root()`, so it is vault-aware.

### Scope change — MCP parity folded in (user decision)

User: "MCP should behave exactly as CLI. And documentation should be updated accordingly." Added as functional **R9** (documentation renumbered to R10) and technical **§2.10**.

Divergences found, all of which parity fixes:

- MCP runs **2** hand-rolled checks against the registry's **17**.
- Its broken-link test is an exact `target in {p.stem}` match — no `_norm_slug`, no anchor stripping — so it **over-reports** versus `link_integrity`.
- Its orphan test counts inbound `[[wikilinks]]` only and skips a hardcoded `index/overview/log`, where `orphan_detection` also counts catalog markdown links and skips `SYSTEM_PAGE_SLUGS` — so it **over-reports** there too.
- Its advertised description already claims it finds "contradictions, and stale summaries", **neither of which it implements**. Parity makes the description true rather than requiring it be walked back.

Precedent supporting the change: `tests/test_archive_cold_storage.py:272` already asserts MCP and CLI agree about discarded slugs, so parity is an existing project principle.

Accepted cost: **breaking change to the `wiki_lint` payload** — `orphans`/`orphan_count`/`broken_links`/`broken_link_count` replaced by the CLI's `summary`/`issues`/`disabled_rules`/`total_pages`. Keeping both shapes would defeat the parity requirement. Announced in `CHANGELOG.md` + `docs/UPGRADING.md`; `tests/test_v02.py:157` and the archive test need updating.

**Both specs approved by the user 2026-08-26 ("go"). Status → Approved on both.**

## Stage: specs — tasks drafted — done

`tasks.md` written. Nine slices, draft-approval loop suppressed per delivery-flow §10.

1. Lint honours the significance threshold (thresholds module, shared counting, `LintOptions`, threshold-aware `link_integrity`, `lint --min-refs`)
2. Vault opt-out declaration + `LintOutcome` + shared reporter + `cmd_lint`
3. `lint --fail-on-warnings` + the exit-code ordering fix
4. Threshold reaches `all` / `pipeline`; pipeline uses the shared reporter
5. `contradiction_detection` precision + the Python-version doc fix + the one demo page it invalidates
6. MCP parity + payload change announced
7. `demo/llmwiki.json` + CI `--fail-on-warnings`
8. `docs/configuration-reference.md`
9. Feature Testing & Regression (`testing-expert`)

`SKIP_TESTS = false`. QA agent `testing-expert` (project-local, `.claude/agents/testing-expert.md`). All implementation tasks fall to `general-purpose`: `hired-agents.md` records Python/CLI as partial coverage with no dedicated agent (template-generated agents declined by the user) and the MCP surface as missing. Recorded in the tasks Recommendations table rather than silently absorbed.

Slice 5 carries an accepted deviation: `demo/wiki/` is generated output, but regenerating it needs a synthesis backend and `scripts/refresh_demo.py` is maintainer-only, so the one `## Contradictions` section the docs fix invalidates is hand-edited. `demo/raw/` stays untouched.

**Next:** commit specs → `/awos:implement`.
