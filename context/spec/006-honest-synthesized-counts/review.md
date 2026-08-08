# Local review — #81 honest synthesized counts (checklist half)

**Branch:** `feat/81-honest-synthesized-counts` · **Diff base:** `origin/main...HEAD` **plus uncommitted working-tree changes** (the feature is implemented but not committed).

**Reviewed against:** `docs/maintainers/REVIEW_CHECKLIST.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/DECLINED.md`, `CONTRIBUTING.md`, `SECURITY.md`.

**Verdict: request changes.** The feature itself is correct, well-tested, and honest about its own units — which is the whole point of #81. Every blocker below is about how the change is packaged for a PR (untracked files, an orphan binary, diff size), not about the implementation. Nothing in the code needs to be rewritten to land this.

**Findings: 3 blockers · 13 nits.**

---

## Verified green

| Gate | Result |
|---|---|
| `ruff check llmwiki tests scripts` | exit 0, all checks passed |
| `python3 -m pytest tests/ -q` | full suite green (~91 s), 0 failures, only pre-existing skips |
| `llmwiki build` smoke (synthetic vault) | 100 HTML files, no crashes, no new warnings |
| Build-time network calls | none; only the pre-existing client-side highlight.js + Google Fonts CDN refs |
| XSS surface | clean — `on_disk` passes through `Number()` into `stageCell`, labels through `escapeHtml`, `kind` is only compared and never interpolated |
| A11y (WCAG 2.1 AA) | muted dash cells 4.83:1 light / 6.92:1 dark, "On disk" header 6.65:1 dark — all ≥ 4.5:1 |
| Console | 0 errors, 0 warnings on Home |
| Layer boundaries | respected — L2/L3 render, synth logic, CLI; no cross-layer reach |
| Runtime deps | none added (stdlib + `markdown`) |
| AWOS context gate | satisfied — `context/spec/006-*` and `context/product/roadmap.md` both change |
| `DECLINED.md` | nothing here re-proposes a declined idea |

Two things worth calling out as genuinely good. First, replacing the two separate `wiki/sources` walks (`discover_synth_source_keys()` + `discover_stub_source_keys()`) with a single `scan_wiki_sources_disk()` pass is a real performance win on a mature vault, and it incidentally fixes a bug: `discover_synth_source_keys()` was called with no argument, so it ignored the caller's `wiki_sources_dir` and always read the default `wiki/sources`. The new code honors the injected directory. That behavior change is not mentioned in the CHANGELOG, but it makes tests more hermetic rather than less, so it needs no user-facing note.

Second, the docs pass is unusually thorough for a labelling change — `CHANGELOG.md`, `docs/UPGRADING.md`, `docs/reference/cli.md`, `docs/reference/ui.md`, `docs/cheatsheet.md`, and the Ollama tutorial all move off the old "pages in `wiki/sources/`" framing together, including the retroactive fix to the #84 CHANGELOG entry so history does not contradict the new wording.

---

## Blockers

### B1 — Untracked files will be silently dropped from the commit

`tests/test_81_acceptance.py` (439 lines — the entire acceptance-criteria mapping suite) and `docs/screenshots/006-honest-synthesized-counts-pipeline-home.png` are untracked, and neither is covered by `.gitignore`. `git commit -a` stages modifications only; it does not add untracked files. If the author commits the feature with `-a`, the PR ships the implementation with none of its acceptance tests, and CI would still pass because the missing tests simply would not exist.

The only commit currently on the branch is `2ab4491 docs: add spec for #81 honest synthesized counts`. The implementation needs a `feat:` commit (per `CONTRIBUTING.md` the type table, with `Closes #81` in the body) and the test file needs an explicit `git add`. Verify with `git status --porcelain --untracked-files=all` immediately before pushing.

### B2 — `docs/screenshots/` is a new, non-canonical, unreferenced binary location

The repo already has a canonical screenshot pipeline: `scripts/regen_docs_screenshots.py` writes `home.png`, `recent.png`, `projects.png`, `sessions.png`, and `analytics.png` into `docs/images/`, and `.github/workflows/regen-screenshots.yml` regenerates them on demand. The new file creates a second, parallel `docs/screenshots/` directory that no script maintains and no document links to, holding a one-off 44 KB PNG. It is an orphan the moment it lands, and it will rot silently the next time the widget changes.

Two further reasons to keep it out of the tree. It is not good evidence: at 780×493 the capture stops at the table header row, so the "On disk" column and the Stubs row — the actual subject of the change — are not visible in it. And its provenance is unverified: per the repo's local-build convention a bare `llmwiki build` renders the maintainer's real Obsidian vault, so a less-cropped capture of the same page would put real project names into a public PR, which `CONTRIBUTING.md` privacy rule 7 and `.cursor/rules/no-local-vault-in-prs.mdc` both forbid. The current crop happens to show nothing personal, but the workflow that produced it is the one the rule warns about.

Recommendation: delete the file from the tree and attach the image to the PR body instead. If a shipped screenshot is genuinely wanted, regenerate `docs/images/home.png` through the canonical script against a synthetic vault (see N6, which is the same problem from the other direction).

### B3 — Diff exceeds the ≤500-line PR limit with no waiver

`CONTRIBUTING.md` (*PR size*) sets a hard ≤500-line diff and says the reviewer will ask for a split beyond it. Current totals: 734 insertions / 55 deletions across 19 tracked files, plus the 439-line untracked acceptance suite. Roughly 306 lines of that is product code, ~205 lines is edits to existing tests, ~250 lines is `context/spec/**`, and the rest is docs.

This is genuinely one concern, so a split would be artificial and I do not recommend one. But the rule is not self-waiving: the PR body needs an explicit one-line waiver naming what dominates the count (spec artifacts plus the acceptance suite, not product code). Without it the size gate is simply unmet.

---

## Nits

### N1 — The widget's empty-state hint is now unreachable

`pipeline_rows` unconditionally appends the Stubs row, so it is never empty once an estimate has run:

```python
rpt = synthesize_estimate_report(raw_sessions=[], docs_root=empty, wiki_sources_dir=empty_sources, state_keys=set(), prefix_tokens=2000)
# → pipeline_rows == [{"id": "stubs", "label": "Stubs", "on_disk": 0, "raw": 0, ...}]
```

In `llmwiki/render/js.py` the `if (!bodyRows)` branch renders the onboarding hint "No pipeline rows yet — run `llmwiki sync` then `llmwiki synth --estimate`". Because `bodyRows` is now always truthy after an estimate, a user with an empty vault sees a table containing one "Stubs / — / — / — / 0" row and an all-zero Total footer instead of the instruction telling them what to run next. The hint still fires on the pre-estimate path where `build.py` seeds `rows: []`, so this only affects the "ran the commands, found nothing" case — but that is exactly the user who needs the hint. Consider suppressing the Stubs row when it and every other row are zero, or keying the empty state on the input columns rather than on row count.

### N2 — Five state keys are written but never read

`refresh_synth_pending` merges `source_pages_on_disk`, `source_page_stubs`, `source_pages_sessions`, `source_pages_docs`, and `source_pages_other` onto `synth.estimate`, and `build.py` carries a comment explaining that this is "so Home gets current-state page counts". But the viewer reads its numbers from `pipeline_rows[*].on_disk`; nothing in `llmwiki/render/js.py` touches `estimate.source_pages_*`. The smoke redesign that removed the under-table note removed the only consumer. The tests assert the keys are present, not that anything uses them, so the dead data is locked in rather than caught. Either drop the merge (and the `build.py` comment, which currently describes an effect that does not happen), or state in the docstring that these are a machine-readable surface for external consumers only.

### N3 — The new CLI line breaks the estimate block's numeric alignment

Every other line in the block right-aligns its number to a fixed column via `{:>6}`; the new one does not. Actual output:

```
Corpus:                     3 eligible sources (3 sessions + 0 docs)
Already synthesized:        1 of 3 eligible sources
Source pages (current state): 1 on disk (1 sessions + 0 docs + 0 stubs)
New since last run:         2
```

The whole point of the line is making a gap between two numbers visible at a glance, and the two numbers no longer sit in the same column. Padding the label or the value would restore the scan.

### N4 — Singular counts read as plurals

The same real output gives "1 sessions + 0 docs + 0 stubs". On a line whose purpose is legibility, `1 session` is worth the two-line helper change in `print_source_pages_current_state`.

### N5 — Tutorial example does not match real output

`docs/tutorials/08-synthesize-with-ollama.md` shows `New since last run:     71` and an aligned `Source pages (current state): 700 on disk` block. Neither matches what the code prints (see N3). The pre-change example was already approximate, so this is not a regression — but since the example was being touched anyway, pasting real output would have been free.

### N6 — Canonical `docs/images/home.png` is now stale

`docs/tutorials/setup-guide.md` embeds `../images/home.png` twice. That screenshot still shows the four-column table captioned "Files layer", which this PR renames to "Eligible sources" and widens to five columns. The checklist's "README/docs updated if a user-visible surface changed" covers shipped screenshots of that surface. Regenerate with `scripts/regen_docs_screenshots.py` (this is the flip side of B2 — one canonical image refreshed, rather than one ad-hoc image added).

### N7 — Four new tests read the developer's real `wiki/sources`

`test_ac_211_corpus_session_doc_split_in_report`, `test_ac_211_corpus_sessions_only_when_no_docs`, `test_ac_221_already_synthesized_n_of_m_in_report`, and `test_ac_221_fully_synthesized_still_reports_corpus_m` call `synthesize_estimate_report` without `wiki_sources_dir`, so `scan_wiki_sources_disk` falls back to `_WIKI_SOURCES` and walks the checkout's real `wiki/sources`. The checklist asks for no reliance on the real filesystem outside `tmp_path`. It passes today only because this worktree's `wiki/sources` holds a single `_`-prefixed file that the scan skips; on a checkout with a populated vault, `real_source_keys` would feed back into the `synthesized` assertions. These tests already receive a `tmp_path` — passing it through costs one argument each.

(For context, the `cwd=REPO_ROOT` in `_run_cli` is *not* a finding: `test_113_acceptance.py`, `test_102_acceptance.py`, and seven other suites do the same, and the `--vault` flag isolates the writes.)

### N8 — Duplicate JS branches

In `renderStateWidget`, `kind === "stubs"` and `kind === "other"` produce byte-identical `sourceLabel` markup in two separate branches, immediately after `diskOnly` has already computed exactly that disjunction. Collapsing to `if (diskOnly)` removes a branch and makes the "these two row types render the same" intent explicit.

### N9 — `_tags_contain` matches inconsistently

For a string `tags` value it does a substring match (`"raw-docs-archive"` would match `"raw-doc"`); for a list it does an exact per-item match. A page with `tags: raw-documentation` in string form would be miscategorised as a doc page. Pick one semantic — exact match after splitting the string form is the closer analogue to the list branch.

### N10 — `scan_wiki_sources_disk` returns an untyped eight-key dict

The signature is `-> dict[str, Any]`, the contract lives only in prose in the docstring, and all four call sites index it with string literals (`disk_scan["files_by_agent"]`, `disk_scan["stub_keys"]`, …). A typo in a key is a `KeyError` at runtime rather than a type error at author time, and the checklist asks for type hints on new public functions. A `TypedDict` or a small frozen dataclass would make the return contract checkable without changing any call site's shape.

### N11 — `pipeline_buckets` keyed by display label can collide

The merge loop calls `_bucket(label, kind="session", css=css)` for each agent found on disk, but `pipeline_buckets` is keyed by display label, and `docs_row` occupies the key `"Documents"`. If `detect_agent_label` ever returned `"Documents"` for a session page, the loop would fetch the docs row, set its `on_disk`, and then line 485's `docs_row["on_disk"] = files_docs` would clobber it. No current label makes this reachable, so this is a latent trap rather than a bug — worth a comment noting the label key is assumed collision-free, or keying by a stable id.

### N12 — Table `min-width` not revisited for the fifth column

`.state-pipeline-table` keeps `min-width: 520px` while gaining a column. Verified at 375 px: the wrapper still scrolls horizontally (`overflow-x: auto` plus `tabindex="0"`, so keyboard scroll survives) and headers wrap rather than overflow, so nothing is broken. But columns are noticeably tighter — "To synthesize" gets 121 px and carries a parenthesised dollar figure. Consider bumping the min-width so the scrollport, rather than the text, absorbs the extra column.

### N13 — New `--json` keys are undocumented

`_synthesize_estimate` adds five keys to the `--json` payload. `docs/reference/` documents no estimate JSON keys at all today (`incremental_usd` and `full_force_usd` are equally absent), so this is a pre-existing gap the PR merely widens by five. Mentioned only because the `--json` output is a machine-readable public surface and the reference docs are where a consumer would look.

---

## Checklist coverage

| Section | Status |
|---|---|
| Meta — linked issue (#81 in spec, CHANGELOG, docs) | pass |
| Meta — one concern per PR | pass in substance; see B2 (screenshot dir) and B3 (size waiver) |
| Meta — conventional-commit title | pending — implementation still uncommitted (B1) |
| Meta — CHANGELOG under `## [Unreleased]` | pass |
| Meta — tests added or updated | pass, but see B1 (test file untracked) and N7 (hermeticity) |
| Meta — CI green | not applicable, nothing pushed yet; local lint + suite are green |
| Meta — AWOS context changed | pass |
| Layer boundaries | pass |
| No new runtime deps / Layer-0 stdlib-only | pass |
| Security — no real session data | pass in the diff; screenshot provenance unverified (B2) |
| Security — redaction untouched | not applicable, redaction paths unchanged |
| Security — no XSS in rendered HTML | pass |
| Security — no build-time network calls | pass |
| Security — localhost binding / no telemetry | not applicable, no server or network code touched |
| Code quality — docstrings, type hints, error handling | pass, except N10 (untyped return contract) |
| Code quality — no dead code | `discover_synth_source_keys` / `discover_stub_source_keys` are still used by `cli.py`, `pipeline.py`, and `test_stub_backlog.py`, so the thin-wrapper refactor leaves nothing orphaned; see N2 for dead *data* |
| Tests — happy path plus edge cases | pass — empty dir, `_`-prefixed skip, two files sharing one `source_file`, multi-chunk doc, stale-bookkeeping divergence |
| Tests — behavior-describing names | pass |
| Tests — `tmp_path` only | see N7 |
| Docs — README / CHANGELOG / reference updated | pass, except the stale shipped screenshot (N6) |
| Build + runtime smoke | pass — build clean, widget renders 5 columns, 0 console errors, AA contrast in both themes |
