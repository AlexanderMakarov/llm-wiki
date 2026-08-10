# Technical Specification: Make the product explain itself

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (Status: Approved)
- **Status:** Approved
- **Author(s):** 4ellendger
- **Issue:** [#109](https://github.com/AlexanderMakarov/llm-wiki/issues/109)
- **Date:** 2026-08-09

---

## 1. High-Level Technical Approach

Three sequenced stages on one branch chain, matching R11. Each stage leaves the repository buildable and the test suite green.

**Stage A — make the repository honest about its own shape.** Move the demo into a self-contained `demo/` tree, delete dead assets, relocate the UI surface specs, guard the repo root against being used as a vault, and hard-cut the `question` and `comparison` page kinds with a migration. No demo content is regenerated yet; `wiki/` is moved with history rather than deleted, so every commit in the chain still builds.

**Stage B — regenerate the demo through the real pipeline.** Add `scripts/refresh_demo.py`, a maintainer-only script that reads git to decide which `docs/` pages changed, drives the existing CLI (`add` / `remove` / `synth` / `build` / `lint`) against `demo/`, and commits nothing itself. Repair `wiki-checks.yml` into a real gate, and repoint `pages.yml` at the demo folder.

**Stage C — remove the server, then explain the result.** Delete `serve` and move candidate review to the command line first, so the docs written next describe a static-file product. Then add a page-kind reference, rewrite the README, and move the user-facing agent commands and skills into the installable package behind a new `install-agent-kit` subcommand.

The guiding constraint throughout: **no new runtime dependency, and no new product surface that only makes sense inside this repository.** The refresh script is repo-only and therefore lives in `scripts/`, not in the CLI.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Stage A1 — Repository layout (R1)

| Change | From | To | Mechanism |
| --- | --- | --- | --- |
| Demo vault | `wiki/` (23 tracked files) | `demo/wiki/` | `git mv` — preserves history and keeps every commit buildable |
| Demo sessions corpus | `examples/demo-sessions/` | `demo/raw/sessions/` | `git mv` |
| Demo docs corpus | `examples/demo-docs/` | `demo/raw/docs/` | `git mv` (content replaced in Stage B) |
| Demo pre-synthesized sources | `examples/demo-wiki/sources/` | `demo/wiki/sources/` | `git mv` (content replaced in Stage B) |
| Demo telemetry fixtures | `examples/demo-usage/` | `demo/usage/` | `git mv` |
| UI surface specs | `specs/` (10 files) | `docs/maintainers/surfaces/` | `git mv` + fix inbound links |
| Outdated media | `docs/videos/` (4 files) | *deleted* | `git rm` |

`demo/site/` is **not** tracked — it is built from `demo/raw/` + `demo/wiki/` by CI and by the refresh script. Add `demo/site/` to `.gitignore`.

**Repo-root guard.** `cmd_init` (`llmwiki/cli.py:192`) currently falls back to `REPO_ROOT` when no vault is configured, which is what lets the root become a half-vault. Add a marker file at the repository root (e.g. `.llmwiki-source-checkout`) and a shared helper that refuses to scaffold, synthesise, or build into a directory containing it, with an error naming `--vault` and pointing at `demo/`. This only affects source checkouts — an installed package has no such marker, so the existing fallback behaviour for real users is unchanged.

`context/` stays where it is; `CONTRIBUTING.md` gains a line identifying it as contributor tooling.

### Stage A2 — Page body decision (R6)

No production code changes. `key_facts.md` already produces exactly the facts-only shape the spec ratifies.

Two documentation defects must be fixed, because they instruct agents to write a shape the pipeline never produces:

- `CLAUDE.md` "Entity / Concept / Project Page Format" — contains `One-paragraph description.`
- `AGENTS.md` "Entity / Concept / Project page" — same defect

Both lose the paragraph line. A follow-up issue is filed proposing a description-generating synth step.

### Stage A3 — Hard-cut `question` and `comparison` (R7)

**Vocabulary.** Remove both from `PAGE_KINDS` in `llmwiki/schema.py:50-58`. This is the single source that `lint/rules/frontmatter_validity.py:19` reads, so the lint vocabulary follows automatically.

**Call sites to clear (14 files).** `schema.py`, `topics.py:193-194`, `topics_page.py:44`, `graph.py:44-45,347-372,594`, `render/graph_viewer.py:34-46`, `graphify_bridge.py:409`, `obsidian_output.py:40` (`EXPORTED_DIRS`), `exporters.py:446-447`, `docs_pages.py:645`, `categories.py:50`, `reindex.py:26` (docstring only), `lint/rules/duplicate_detection.py`, `mcp/server.py`, `usage.py`.

**Must survive untouched:** `llmwiki/compare.py` and `build.py:2501-2509` render the auto-generated **model** comparison index. Different feature, same word. A test must pin that it still renders.

**Migration** — new subcommand `migrate-page-kinds`, following the existing `migrate-*` convention (`migrate-state`, `migrate-raw-redaction`, `migrate-tools-used`):

| Input | Action |
| --- | --- |
| Page with `type: question` or `type: comparison` | Rewrite `type:` to `concept`, `git mv`-equivalent into `wiki/concepts/`, keep the filename so `[[Name]]` links still resolve |
| `wiki/questions/_context.md`, `wiki/comparisons/_context.md` | Delete |
| Now-empty `wiki/questions/`, `wiki/comparisons/` | Remove the directory |
| Non-empty after the pass | Leave in place and report — never delete unrecognised content |

Supports `--dry-run` and `--vault`, appends a `## [YYYY-MM-DD] migrate | page kinds` entry to `wiki/log.md`, and prints a per-file report. In practice this is a no-op for almost everyone: no code path has ever written a page into either folder.

**Removals recorded** in `docs/maintainers/DECLINED.md`, dated, matching the existing entry format.

### Stage B1 — `scripts/refresh_demo.py` (R2, R3)

Maintainer-only. Never shipped, never referenced by the CLI.

**Change detection.** The last-refreshed revision is stored in `demo/.demo-source-rev` (a single commit SHA, tracked). Changed documents are the union of:

- `git diff --name-status <recorded-rev> HEAD -- docs/` — committed changes since the last refresh
- `git status --porcelain -- docs/` — uncommitted working-tree edits, so a maintainer can preview before committing

Rename detection uses git's own `R` status. Deletes come through as `D`.

**Per-document actions**, driven entirely through the existing CLI so the script owns no vault-writing logic:

| Git status | Command sequence |
| --- | --- |
| `A` (added) | `llmwiki add <path> --vault demo --no-build` |
| `M` / `R` (modified / renamed) | `llmwiki remove <slug> --vault demo --yes` **then** `llmwiki add <path> --vault demo --no-build` |
| `D` (deleted) | `llmwiki remove <slug> --vault demo --yes` |

The remove-then-add ordering is mandatory and non-obvious: adding an already-ingested document lands a *second* snapshot under a drifted slug (`test-doc` → `test-doc-2`) and leaves the original in place. Removing first preserves the original slug and therefore every inbound `[[wikilink]]`. This was verified experimentally; the ordering carries a code comment citing the reason.

**Then, once per run:** `llmwiki synth --vault demo --docs-only` → `llmwiki build --vault demo --out demo/site` → `llmwiki lint --vault demo`. Finally the script writes `HEAD` into `demo/.demo-source-rev`.

**Preflight.** `llmwiki synth --check` probes backend availability and exits non-zero when unreachable; the script runs it first and fails with an actionable message rather than part-way through.

**Flags:** `--dry-run` (print the plan, touch nothing), `--force` (treat every `docs/` file as changed), `--base <rev>` (override the recorded revision).

The git-selection logic is factored into a pure function — `(diff_output, status_output) → [(action, path, slug)]` — so it is unit-testable without a live repository.

### Stage B2 — CI gate (R4)

`wiki-checks.yml` is repaired rather than replaced. It is currently broken in three ways: it triggers on `master` (this fork uses `main`, so the push trigger never fires), it invokes `python -m llmwiki eval` which **is not a subcommand** — masked by `|| true` — and it fails only on errors, not warnings.

Repairs: trigger on `main`; delete the `eval` step; drop the seeding dance; run `python -m llmwiki build --vault demo --out demo/site` followed by `python -m llmwiki lint --vault demo --fail-on-errors`. Path filters become `llmwiki/**`, `demo/**`, `docs/**`, and the workflow file itself.

**Errors fail the build; warnings are printed but tolerated** (amended R4). `--strict` was considered and rejected: the only rule that warns on the current demo is `content_freshness`, which fires when a page's `last_updated` exceeds 90 days. A committed demo ages by the calendar, so that rule is structurally guaranteed to fire and would turn CI red on a timer with nothing wrong. The other eight warning-severity rules — notably `link_integrity`, `stub_source_pages` and `duplicate_detection` — are genuinely valuable here, but there is no way to exclude a single rule without either an allowlist that silently drifts as rules are added, or a change to lint. **Lint is explicitly out of scope for this work**, so the gate enforces errors only, and a follow-up issue proposes per-vault rule scoping so warnings can be enforced later.

### Stage B3 — Publication (R5)

`pages.yml` loses its entire `init` + copy block. It becomes: checkout → install → `python -m llmwiki build --vault demo --out ./site` → `.nojekyll` → upload → deploy. No AI model, no synth, no seeding. The README links the published URL.

### Stage C0 — Remove the server, move review to the CLI (R12)

`llmwiki/serve.py` (225 lines) is not only a static file server: it hosts `POST /api/candidates`, the backend for the #97 review UI, and `candidates.html` posts batch promote/discard/merge decisions to it.

**Why the removal is not lossy.** `llmwiki candidates apply --actions JSON` already accepts *the same batch action shape* the endpoint consumes — its own help text says "same shape as POST /api/candidates". The command line is therefore a complete functional substitute, not a downgrade. `candidates` also offers `list`, `promote`, `flip-promote`, `merge`, `discard` and `rewrite-key-facts` individually.

**Changes.**

| Area | Change |
| --- | --- |
| `llmwiki/serve.py` | Deleted, together with its `serve` subcommand wiring in `cli.py` |
| `serve.sh`, `serve.bat` | Deleted |
| `candidates.html` (built page) | Becomes a read-only listing of pending candidates. Instead of controls that cannot work, it states the command to run and — ideally — renders the ready-made `--actions` JSON for the listed candidates so a reviewer can copy it straight into `candidates apply --actions -` |
| `script.js` / page JS | Drop the `fetch("/api/candidates")` path |
| Agent kit, docs, README, `CLAUDE.md`, `AGENTS.md` | Every "run the server to view your wiki" instruction becomes "open the site". The `/wiki-serve` slash command and `wiki-serve` skill go |
| `docs/UPGRADING.md`, `CHANGELOG.md` | Record the removal and what to do instead |
| Deploy docs | `docs/deploy/*` describe hosting the built output; check each for a local-serve instruction |

**Vendoring the remaining CDN assets.** The site pulls three files from `cdn.jsdelivr.net`: `highlight.min.js` and two themes, `github.min.css` and `github-dark.min.css`, all pinned at 11.9.0. Vendor them exactly as #127 vendored vis-network:

- Pinned copies under `llmwiki/vendor/`, with `llmwiki/vendor/NOTICE` extended to record project, version, license, homepage and upstream source for highlight.js (matching the existing entry's shape).
- Emitted beside the page that needs them at build time, the way `graph.py:681` does `shutil.copy2(VIS_NETWORK_VENDOR, …)`, and referenced by relative path rather than absolute URL.
- **`pyproject.toml:109` currently packages `vendor/*.js` only.** It must also carry `vendor/*.css`, or the themes are silently absent from an installed package while the JS ships — a failure that would only appear for pip/Homebrew users, never in a source checkout.
- Consider the `onerror` offline-notice affordance `graph.py:540` uses; for highlighting, degrading to unstyled code blocks is acceptable and needs no notice.

**Verified prerequisite for "open the file works".** The built site loads its data through `<script src="llmwiki-state.js">` rather than `fetch`, and uses no `type="module"` scripts — both of which would fail under `file://`. So the site is already file-openable by design. The two exceptions found: `candidates.html`'s API call (removed by this stage) and a `highlight.js` tag pointing at `cdn.jsdelivr.net`, which needs network for syntax highlighting only. The CDN dependency is pre-existing and out of scope here; note it rather than fix it.

### Stage C0b — Displayed local paths become a build input (R13)

`restore_local_path` (`llmwiki/convert.py:874`) reverses the username redaction applied at import, and `build.py:1130` and `build.py:1792` call it so project titles and session descriptions show a real path. Three defects follow:

- **Builds are not reproducible.** The same vault renders `/home/<operator>/…` locally and the runner's path in CI. This is why the demo site displayed a username the committed corpus did not contain.
- **Redaction and its reversal are permanently coupled.** Two functions must agree forever; the code comments on the drift risk itself.
- **It rewrites prose.** `build.py:1792` applies it to session *descriptions*, so it edits arbitrary text rather than a path field.

**Replacement.** Add a `--local-root` input to `build`. The substituted value is resolved once per run: from the current environment by default, or from the flag when given. `restore_local_path` and its dependence on the convert-time redaction config are removed from the build path. Substitution is restricted to path-shaped values — the `cwd` field — and no longer applied to descriptions.

The demo build and `pages.yml` both pass an explicit fixed string, so published output is identical wherever it is produced.

### Stage C1 — Page-kind reference (R8)

New `docs/reference/page-kinds.md`. For every surviving kind (`source`, `entity`, `concept`, `project`, `synthesis`, plus the system kinds `navigation` and `context`): what it is for, a real example linked into the rebuilt demo, and a frontmatter field table.

Each field carries a provenance column with one of four values — **synth** (written when summarising), **harvest** (written when collecting candidates), **build** (derived by the site build), **human** (only ever hand-filled). Conventionally-absent fields are listed explicitly, including that `ensure_project_stubs()` (`llmwiki/build.py:340`) writes project stubs with no `last_updated`, so project freshness derives from sessions.

`docs/reference/ui.md` already carries a complete `## Topic pages` section from #108 / PR #128 — **verify only, do not rewrite.**

### Stage C2 — README (R9)

Structural rewrite, no code. Target roughly half of today's 364 lines. Order: what you get → live demo → install → the loop (`sync / add → synth → review candidates → build`) → one merged agent table → configuration pointer → docs index → acknowledgements → license.

The merged agent table has one row per agent with columns *Supplies sessions* / *Reads the wiki* / *Core or contrib*. Ground truth: core is `llmwiki/adapters/{claude_code,codex_cli}.py`; contrib is `llmwiki/adapters/contrib/` — `chatgpt`, `copilot_chat`, `copilot_cli`, `cursor`, `cursor_cli`, `gemini_cli`, `obsidian`, `opencode`, `openclaw`. Python version comes from `pyproject.toml:10` (`>=3.12`) and the CI matrix (3.12, 3.13).

Displaced detail (`Manual queue`, the gitignore path table, tutorial overlap) moves into existing pages under `docs/`.

### Stage C3 — Agent kit packaging (R10)

**Source layout.** User-facing material moves inside the package so setuptools ships it:

```
llmwiki/agent_kit/
  commands/    <- the user-facing wiki-*.md slash commands
  skills/      <- llmwiki-sync, llmwiki-ingest, llmwiki-query, wiki-all, wiki-add
```

`pyproject.toml:108-109` extends `package-data` for `llmwiki` with `agent_kit/**/*.md`. Nothing else about packaging changes.

**Contributor material stays in `.claude/`** and is explicitly not shipped: `awos/`, `fix-bug.md`, `implement-feature.md`, `maintainer.md`, `release.md`, `triage-issue.md`, and the skills `docs-that-work`, `gha-diagnosis`, `modern-python-development`, `project-maintainer`, `pytest-best-practices`, `self-learn`.

**New subcommand** `llmwiki install-agent-kit --dest PATH`:

- `--dest` is **required** — no auto-detection, no guessing at agent directory conventions
- Copies `commands/` and `skills/` beneath the destination, reporting every path written
- On a conflicting file whose content differs, writes a `.bak` copy alongside and reports it; never overwrites silently
- `--dry-run` prints the plan and writes nothing
- Re-running after an upgrade refreshes files and reports what changed

**`.claude-plugin/` is deleted.** `plugin.json` declares `path: "."` with `commands/wiki-init.md`, which resolves to `./commands/` — a directory that does not exist. It also names the upstream author, claims `python >=3.9` against an actual floor of `3.12`, and lists 7 of ~15 commands. It cannot work today, so nothing can depend on it, and the chosen delivery channel is the package plus installer.

**`CLAUDE.md` / `AGENTS.md`** are re-scoped to contributors: they state plainly that they are for people working on llmwiki itself and point users at `install-agent-kit`.

`homebrew/llmwiki.rb` is retargeted at this fork (`AlexanderMakarov/llm-wiki`, branch `main`) so a brew install carries the packaged agent kit.

---

## 3. Impact and Risk Analysis

### System Dependencies

- **`schema.PAGE_KINDS`** is the single vocabulary source feeding both the lint rule and the MCP tool schema — editing it changes both surfaces at once, which is why the migration must ship in the same stage.
- **`reindex.CANONICAL_FOLDERS`** already treats non-canonical folders generically (`reindex.py:26`), so a leftover folder in a user vault is catalogued rather than becoming lint noise. This is what makes the hard cut survivable.
- **`pages.yml` and `wiki-checks.yml`** both consume the demo; they must be changed in the same stage as the folder move or the published site breaks.
- **`llmwiki add` / `remove`** are the only supported way to mutate `raw/docs/`; the refresh script must not write there directly.

### Potential Risks & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Migration moves a page between folders and breaks `[[wikilinks]]` | Resolved — no longer a risk | **Resolution is name-based, not path-based, so Slice 6's migration must NOT rewrite inbound links — moving the file and keeping its filename is sufficient and complete.** Evidence: `llmwiki/wikilinks.py` parses `[[Target]]` into a bare name with no path handling, and every consumer keys pages by filename stem — `graph.scan_pages` (`pages[p.stem]`), `backlinks._collect_pages` (`out[p.stem]`), `references.build_index` (`_rel_to_slug(rel)`), `lint/rules/link_integrity` (`_page_slug(rel)` = basename), and `topics.topic_kind_lookup` (slug/title lookup). The folder is read only for a page's *kind* and its site URL, never for link resolution. Pinned by `tests/test_page_kinds.py::test_wikilink_resolution_survives_a_move_between_wiki_folders`, which moves a page from `wiki/questions/` to `wiki/concepts/` and asserts the graph edge, the backlink referrer, `link_integrity` and the reference index are all identical before and after, with the referring page untouched. |
| Deleting `.claude/commands/wiki-*.md` removes commands our own contributors use | Medium | Source of truth becomes `llmwiki/agent_kit/`; `CONTRIBUTING.md` documents `install-agent-kit --dest .claude` for contributors who want them locally. |
| Publishing breaks when `pages.yml` is repointed | High | Stage B changes the workflow and the demo folder together, and the repaired `wiki-checks.yml` builds the demo on every PR — so a broken demo fails before merge, not after deploy. |
| Demo refresh needs a synth backend and costs money | Medium | `synth --check` preflight; `--dry-run` shows the work first; incremental selection keeps a routine refresh to the handful of docs that changed. |
| Moving `specs/` breaks inbound documentation links | Medium | Grep for inbound references as part of the move; the link-check workflow covers the rest. Overlaps #107, which should land first. |
| Stage A leaves the demo temporarily inconsistent | Medium | `git mv` rather than delete-and-recreate; content is replaced in Stage B, so each stage's tip is buildable. |
| Hard cut surprises a user who skips the migration | Medium | Pages with a removed type produce a lint error naming `migrate-page-kinds`; documented in `docs/UPGRADING.md` and `CHANGELOG.md`. |
| Removing `serve` strands a user who relied on the review UI | Medium | `candidates apply --actions` accepts the identical batch format, so no capability is lost. The candidates page states the replacement command, and `docs/UPGRADING.md` records the change. |
| Errors-only gate lets a warning-severity defect reach the published demo | Medium | Accepted trade-off (amended R4). `link_integrity`, `stub_source_pages` and `duplicate_detection` are warning-severity and so would not fail CI. Mitigated by the refresh script printing the full lint report to the maintainer on every run, and by the follow-up issue for per-vault rule scoping. Lint itself is out of scope for this work. |

### Known constraint carried from the functional spec

The product cannot update an already-ingested document in place. The refresh script works around it with remove-then-add. A follow-up issue records the gap; nothing here changes behaviour for user vaults.

---

## 4. Testing Strategy

Conventions: `pytest`, tests under `tests/`, acceptance tests named `tests/test_109_acceptance.py` per the existing `test_<issue>_acceptance.py` pattern. Gates are `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`.

**Unit**

- Page-kind removal: `question`/`comparison` rejected by `frontmatter_validity`; the surviving kinds still accepted; MCP tool schema no longer advertises the removed kinds.
- Model comparison index still renders — a regression pin so the hard cut does not take `compare.py` with it.
- `migrate-page-kinds`: retype + relocate; `_context.md` cleanup; empty-directory pruning; non-empty directory left intact and reported; `--dry-run` writes nothing; wikilinks still resolve after the move.
- Refresh-script selection logic: the pure `(diff, status) → actions` function across added / modified / deleted / renamed / unchanged, including an uncommitted edit and a no-change run producing an empty plan.
- `install-agent-kit`: writes to `--dest`; missing `--dest` errors; conflicting file produces a `.bak` and a report; identical file is a no-op; `--dry-run` writes nothing.
- Packaging: the built distribution contains `llmwiki/agent_kit/commands/*.md` and `skills/*` — this is the criterion that actually proves the Homebrew fix.
- Repo-root guard: refuses to scaffold into a directory carrying the marker; unaffected without it.

**Integration**

- `scripts/refresh_demo.py --dry-run` against a temporary git fixture with a seeded `docs/` tree: correct plan for each git status, and remove-then-add ordering asserted for the modified case.
- `llmwiki lint --vault <tmp> --fail-on-errors` over a fixture vault: exits non-zero on a seeded error, and zero when the vault carries only warnings — pinning the amended R4 boundary so a later `--strict` reintroduction is a deliberate change, not an accident.

**End-to-end / smoke**

- The committed demo builds and lints clean — enforced in CI by the repaired `wiki-checks.yml`, and runnable locally as the same command.
- Demo **content generation** needs an AI model and is therefore not exercised in CI. CI verifies the committed artefact; the maintainer verifies generation when running the refresh script. This boundary is deliberate and matches R3's local-only decision.

**Acceptance** — `tests/test_109_acceptance.py`, one test per functional-spec acceptance criterion that is machine-checkable, annotated `@spec`. Criteria that are inherently editorial (README leads with the benefit; no fact stated twice) are verified at the smoke-confirm step, not automated. Structural README criteria that *are* checkable — one agent table, correct Python version, no lineage paragraph above Acknowledgements — get assertions.

**Specialist gap:** `context/product/hired-agents.md` records no Python/CLI or packaging specialist (only `testing-expert`). These sections were drafted without one; `/awos:hire` can address it if packaging work proves to need it.
