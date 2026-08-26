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

## Stage: commit-specs — done

Commit `1abc99f` — `docs: add spec for #150 per-vault lint rule scoping`. Four files under `context/spec/150-vault-lint-rule-scoping/`. Not pushed.

## Stage: implement — in progress

Deviation from `/awos:implement`'s per-task loop: dispatching **one agent per slice** rather than one per task. The delivery-flow §8 decision is that implementation is delegated (to keep the orchestrator's context small for review); the per-task granularity is an AWOS default, and ~40 cold-start agents each re-reading both specs would cost far more than it saves. Slice-level delegation preserves the context isolation §8 asks for.

Slices 1 and 5 were run in parallel — different production modules, no logical dependency. Their only shared file would have been `tests/test_lint_rules.py`, so slice 5 was directed to a new `tests/test_contradiction_filler.py` instead.

### Slice 5 — done

`contradiction_detection` precision (`evident` added to `_NONE_SYNONYMS`; `could|would|might|may` added to `_NEGATOR_RE`), `docs/tutorials/01-installation.md` corrected to 3.12 throughout (Step 1 verification line and the troubleshooting entry), and the demo page's `## Contradictions` section rewritten. New `tests/test_contradiction_filler.py`, 20 tests. Demo `contradiction_detection`: **3 → 0**. Ruff clean.

Two follow-ups the agent surfaced, both acted on or scheduled:

- **Acted on now:** the demo page's `## Key Claims` still read "Installation requires Python 3.9+", which the docs fix turned into a false statement — and left the page self-contradictory, since its own `## Contradictions` section now asserted everything says 3.12. Corrected to 3.12+ under the same accepted hand-edit deviation. The agent was right to flag it and right not to exceed its brief.
- **Scheduled:** no `CHANGELOG.md` entry was added, deliberately, to avoid colliding with the concurrent agent. Folded into Slice 8's remit — the `#150` entry must cover the precision fixes and the installation-guide correction alongside the vault-settings feature and the MCP payload change.

### Slice 1 — done, then amended

Delivered `llmwiki/thresholds.py`, `count_source_refs`, `LintOptions` on the rule instance, the `LinkIntegrity` gate, and `lint --min-refs`. New `tests/test_lint_min_refs.py`. Demo `link_integrity` **120 → 0** at stock settings, **120** at `--min-refs 1`. Ruff clean.

**Placement decision the agent made and was right about:** the tech spec said to extract `count_source_refs` "from `harvest_targets`", but putting it *in* `candidates_harvest.py` recreates exactly the cycle §2.2 exists to avoid (`link_integrity` → `candidates_harvest` → `link_integrity`). It went into `llmwiki/wikilinks.py`, the existing leaf module that already documents itself as importing nothing from `llmwiki` and already owns wikilink parsing for graph/lint/harvest/synth. Correct call; §2.3's wording was imprecise, not the implementation.

**Pre-existing test failure confirmed, not introduced:** `tests/test_add_doc.py::test_thin_page_without_renderer_warns` fails on a pristine `git archive HEAD` checkout — a trafilatura-version artifact. Unrelated to this branch.

#### Amendment — the zero-reference hole (spec-violating, caught by the implementing agent)

The agent flagged that counting over `sources/` only meant a target named by **zero** source pages fell below the threshold and was excused **at every threshold, `--min-refs 1` included**. That silently voids R4's "lower the threshold and every unmaterialized cross-reference is reported" guarantee, and deletes a whole class of genuine finding while looking correct. The tell was that it had to move `test_broken_link`'s fixture from an entity page under `sources/` to keep it passing — a test bending to fit a rule that had got the semantics wrong.

Measured before deciding: **0** such links on the demo, **1** on the 717-page live vault (`entities/AmeriaBank.md → [[Banking-APIs]]`). Rare enough to slip through review, real enough to matter.

Root cause: a two-way gate conflated "harvest declined this" with "harvest never saw this". Corrected to a three-way gate — `0` references reported at every threshold, `1 … min_refs-1` excused, `>= min_refs` reported. This *increases* agreement with the harvester rather than reducing it: harvest's decision domain is exactly the source-named targets, so the rule now excuses only inside that domain.

`functional-spec.md` R4 and `technical-considerations.md` §2.5 amended to state the three-way gate and why the zero case is load-bearing.

Correction delivered: gate is now `if 0 < n_refs < min_refs: continue`. `test_broken_link` restored to its original `entities/Foo.md → [[Nowhere]]` fixture with no pin. The two remaining `_link_rule(min_refs=1)` pins were reviewed individually and kept — both have their target named by exactly one source page, so they genuinely sit in the decline band. Four new tests: zero case at stock threshold, zero case threshold-independent (parametrised 1 / `DEFAULT_MIN_REFS` / 10), link from a non-source page, and a decline-band regression guard (parametrised `min_refs` 2/3/5). Demo unchanged at 0 / 120.

Invariant the follow-up agent identified and documented: **zero source references can only arise from a link written in a non-source page**, because a `[[link]]` inside a source page necessarily counts itself. So the closed hole was exactly "links from entity/concept/project pages" — the shape of the single real instance on the live vault.

### Slices 2 + 3 — done

Dispatched together because both centre on `cmd_lint` and `llmwiki/lint/__init__.py`; splitting them would only have produced a merge conflict.

Added `llmwiki/vault_settings.py` (`load_vault_settings`, `disabled_lint_rules`, `vault_settings_path`, `VaultSettingsError`), `llmwiki/lint/report.py` (`render_text` / `render_json`), and `tests/test_lint_vault_settings.py` (31 tests). `LintOutcome` + `run_lint` added to `llmwiki/lint/__init__.py` with `run_all` reduced to a one-line wrapper — signature and `**_kwargs` tolerance unchanged, so all ~20 call sites and `pipeline.py` were untouched. `cmd_lint` rewritten; `lint --fail-on-warnings` added; the exit code now computes last so a failing lint still records `last_lint_run_at`.

Suite: 4512 passed, 48 skipped, 1 known pre-existing failure. Ruff clean. Demo unchanged at 0 issues over 120 pages, already exiting 0 under `--fail-on-errors --fail-on-warnings`.

Decisions the agent made beyond the spec, all sound:

- **"Nothing was checked" keys on `outcome.ran` being empty**, not on `len(skipped) == len(REGISTRY)`. A strict superset of the spec's condition: it also catches `--rules X` where X is itself disabled. The counts line is replaced outright rather than printing `0 issues`.
- **Malformed *shape* is fatal, not just malformed JSON** — `"lint": 3`, `disabled_rules: "name"`, or a non-string entry all raise. Same reasoning as R3: a declaration nobody can read must not quietly leave a check switched on. A non-string dict *value* is coerced, since that is a reason rather than structure.
- **The error message names the settings file** when an unknown rule name came from it, distinguishing it from a `--rules` typo.
- **`disabled_rules` is always present in JSON**, empty when nothing is declared, so consumers never probe for the key.
- `ran` deliberately not exposed in JSON. Parity for Slice 6 is unaffected — MCP consumes the same `render_json`.

### Slices 4 + 6 — dispatched in parallel, killed, recovered

Disjoint file ownership: Slice 4 took `llmwiki/pipeline.py` and the `all` subparser; Slice 6 took `llmwiki/mcp/server.py`, `CHANGELOG.md`, `docs/UPGRADING.md`, and MCP tests. Slice 4 was told explicitly not to write `CHANGELOG.md` to avoid a concurrent-edit conflict.

**Both agents were terminated mid-run by a monthly spend limit.** Neither left the tree broken — ruff clean, suite green — but a green suite proved less than usual here, because the tests that would have exercised the new paths were exactly what had not been written yet. Each slice's acceptance criteria were re-verified directly against the code rather than trusting either agent's final message, both of which understated how far they had got: production code for both slices was complete; tests and the breaking-change documentation were not. A third agent closed those gaps.

**Correction to a claim carried through several earlier entries:** `tests/test_add_doc.py::test_thin_page_without_renderer_warns` passes. Two agents independently reported it as a pre-existing failure and one claimed to have reproduced it on a pristine `HEAD` checkout; it is environment-dependent (a trafilatura resolution artifact) and green here. The bar for this branch is a **fully green suite**, not green-minus-one.

### Slices 4 + 6 — closed

`tests/test_all_min_refs.py` (19 tests) and `tests/test_mcp_lint_parity.py` (20 tests), both RED-validated by mutation: reverting the harvest/lint threading broke 4 slice-4 tests, forcing `disabled={}` in `tool_wiki_lint` broke 4 parity tests; both mutations reverted and files hash-verified. `CHANGELOG.md` and `docs/UPGRADING.md` record the `wiki_lint` payload break.

Noted for review: `tests/test_v02.py::test_mcp_tool_wiki_lint` remains a weak smoke test (key presence and types against a machine-dependent root). Deliberately left rather than widened; real parity coverage is the new module.

#### Amendment — non-deterministic finding order

The closing agent reported that `issues` ordering varies across processes: several rules iterate a `set` (`LinkIntegrity` walks `wikilink_targets`, which returns one), so `PYTHONHASHSEED` changes the order. Reproduced before acting: **five distinct payload hashes across five seeds** on a four-target fixture.

Pre-existing, but §2.10 made it load-bearing — the MCP server and the CLI are different processes, so R9's "the same report" would have been false on a byte-diff. Fixed in `run_lint` with `sorted(rule.run(pages), key=_issue_sort_key)` on `(page, message)` — **within** each rule, preserving the `REGISTRY` enumeration order that `llmwiki/lint/rules/__init__.py` documents as deliberate. One place, every rule, no rule module touched. R9 gained a determinism criterion; §2.6 records the reasoning.

**Orchestrator error corrected mid-flight.** My Slice 7 brief told the agent to prove determinism with `lint --vault demo --min-refs 1`. The user caught it: the demo must be exercised only at stock settings, and lowering its threshold to manufacture findings contradicts the decision Slice 7 exists to encode. The demo has zero findings at stock, so the check needed a fixture, not a bent demo. Instruction retracted; the agent built a fixture whose targets clear the stock threshold instead.

### Slice 7 — done

`demo/llmwiki.json` (committed) disables `content_freshness` only, with a reason; a test pins `set(settings) == {"lint"}` and `"min_refs" not in json.dumps(settings)` so the demo cannot later be quietly bent off stock settings. `.github/workflows/wiki-checks.yml` now passes `--fail-on-warnings`. `tests/test_demo_gate.py` (11 tests) pins all four verifications, including a `frozen_clock` fixture at +400 days **with a control** proving `content_freshness` still fires under that clock — otherwise "demo passes at +400 days" would also pass if the rule were simply broken.

### Slice 8 — done

`docs/configuration-reference.md` gained `### llmwiki lint` (flag table read off the live parser) and `## Vault file (llmwiki.json)`. The agent validated the documentation by executing it — ran the worked example verbatim against a fresh vault, reproduced the sample report byte-for-byte, and exercised both error paths live. `CHANGELOG.md` gained the determinism entry; `tests/test_ci_workflow.py:157`'s docstring, which still claimed the gate must not enforce warnings, was corrected. Also fixed two further falsified pages: `docs/reference/cli.md` (missing `--min-refs`, `--fail-on-warnings`, `--vault`) and `docs/cheatsheet.md`.

Reported, deliberately not fixed — pre-existing drift, each its own task:

- `docs/reference/slash-commands.md` says "15 rules", links a dead anchor `#lint--run-13-wiki-quality-rules`, and lists 16 by name (missing `provenance_integrity`); the live count is 17. Needs a single source of truth, not another hand-edit.
- `llmwiki/agent_kit/commands/wiki-lint.md` instructs agents to hand-roll lint with Grep and Read instead of running `llmwiki lint`, so it knows nothing about vault opt-outs or the threshold. This is the same disease as the MCP divergence — a third private definition of "what counts as broken", this time as agent instructions.

### Slice 9 — done

`tests/test_150_acceptance.py`, 7 acceptance tests. Deliberately complements rather than duplicates the per-slice suites: the module docstring maps each requirement to its covering test and records which requirements are already exhaustively covered elsewhere. The agent stopped before delivering its final report (waiting on a background run), so its output was verified directly.

## Stage: verify — done

All **38 acceptance criteria** marked verified with live evidence. No UI criteria — the feature is CLI, library, and MCP — so no screenshots apply.

| Req | Evidence |
| --- | --- |
| R1 | Baseline vs declared, both shapes, reason surfaced, second vault unaffected |
| R2 | Skipped named on a *clean* vault; `disabled_rules` in `--json`; all-17-disabled → "nothing was checked — … so this is not a clean result" |
| R3 | Typo → exit 2 naming file, entry and all 17 valid names; truncated JSON → exit 2 with line/column |
| R4 | Three-way gate: `NeverNamed` (0 refs, from an entity page) reported at min-refs 3 **and** 1; `Once` suppressed at 3, reported at 1; `Thrice` always reported |
| R5 | `all --min-refs 2` and `synth --candidates-only --min-refs 2` → identical candidate sets (`diff` clean); default correctly yields none at 2 refs |
| R6 | Four exit paths: default 0, `--fail-on-errors` 0, `--fail-on-warnings` 1, clean+strict 0, offending-rules-disabled 0 |
| R7 | Both boilerplate strings → filler; genuine Python-version conflict and the `"None … However, contradicts …"` regression both still flagged |
| R8 | Demo gate exit 0 at stock settings, `content_freshness` named with reason; `pyproject.toml` ≥3.12 and tutorial lines 10/26/118 all agree |
| R9 | MCP and CLI payloads identical on a vault with findings **and** an opt-out (`{'warning': 6, 'info': 3}`, matching `disabled_rules`); unknown rule → `isError`; 5 hash seeds → 1 distinct hash |
| R10 | `## Vault file (llmwiki.json)`, `### llmwiki lint`, both shapes, worked example, caution, threshold explanation all present |

Status → Completed on both specs; `context/product/roadmap.md` item `#150` ticked.

**Next:** commit → user smoke confirm → local review.
