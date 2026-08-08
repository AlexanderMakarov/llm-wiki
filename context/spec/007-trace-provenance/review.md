# Local review — #122 trace provenance (checklist)

**Branch:** `feat/122-trace-provenance` · **Diff base:** `origin/main...HEAD` **plus uncommitted working-tree changes** (implementation is largely uncommitted; the only commit is `a8e0f58 docs: add spec for #122 trace provenance`).

**Reviewed against:** `docs/maintainers/REVIEW_CHECKLIST.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/DECLINED.md`, `CONTRIBUTING.md`, `SECURITY.md`.

**Verdict: request changes.**

**Findings: 5 blockers · 8 nits.**

---

## Verified green

| Gate | Result |
|---|---|
| `ruff check llmwiki tests scripts` | exit 0 |
| `python3 -m pytest tests/ -q` | full suite green (~90 s), 0 failures |
| Focused #122 suites (`test_trace`, `test_cli_trace`, `test_provenance_sources_links`, `test_source_file_index`, `test_122_acceptance`, lint/topics/state slices) | green |
| Runtime deps | none added (stdlib + `markdown`) |
| Layer boundaries | mostly respected — walker/CLI/lint/build/topics; no converter/`markdown` pull into L0 adapters |
| XSS surface | `format_sources_html` / topic evidence items use `html.escape` on hrefs and titles; raw links ship `rel="noopener"` |
| Path traversal | locator/`source_file` reject `..` and `_under_vault`; covered in `test_trace.py` |
| AWOS context gate | satisfied — `context/spec/007-trace-provenance/**` changes with product code |
| `DECLINED.md` | nothing here re-proposes a declined idea |
| CHANGELOG / UPGRADING / `docs/reference/cli.md` (`## trace` + Rules) | present for the user-visible surface |

The shared walker (`llmwiki/trace.py`), CLI `trace`, lint `provenance_integrity`, session Sources HTML, topic graph Sources collapse, and the `source_file` build index are a coherent #122 story. The #81-shaped `on_disk` backfill and the document Sources path need packing and product fixes before push.

---

## Blockers

### B1 — Core implementation files are still untracked

These paths are **untracked** (not staged). `git commit -a` will not pick them up; a careless push ships docs/partial wiring without the library, lint rule, or acceptance tests:

- `llmwiki/trace.py`
- `llmwiki/lint/rules/provenance_integrity.py`
- `tests/test_trace.py`
- `tests/test_cli_trace.py`
- `tests/test_provenance_sources_links.py`
- `tests/test_source_file_index.py`
- `tests/test_122_acceptance.py`

Without them, imports from `build.py` / `cli.py` / lint registry fail and CI cannot pass. Explicit `git add` before the `feat:` commit. See [REVIEW_CHECKLIST §Meta](docs/maintainers/REVIEW_CHECKLIST.md#meta) (tests + shippable change) and [CONTRIBUTING.md](CONTRIBUTING.md) commit rules.

### B2 — Two concerns in one diff: #122 provenance + #81 Home `on_disk` backfill

Independent of #122, the working tree adds:

- `pipeline_rows_missing_on_disk` in `llmwiki/state_store.py`
- `_ensure_synth_pipeline_snapshot` shape-ok bypass in `llmwiki/build.py`
- CHANGELOG **Fixed** bullet for “Home On disk column stuck at 0 after upgrading past #81”
- tests in `tests/test_state_widget.py`
- notes under `context/spec/006-honest-synthesized-counts/flow-log.md`

That is a follow-up bugfix for #81, not provenance. [REVIEW_CHECKLIST §Meta — One concern per PR](docs/maintainers/REVIEW_CHECKLIST.md#meta) and [CONTRIBUTING.md TL;DR #1](CONTRIBUTING.md) require a split (or a separately reviewed tiny fix PR). Land #81 backfill first (or after) as its own `fix:` PR; keep this branch to #122 only.

### B3 — Absolute home path / OS username in committed AWOS flow-log

`context/spec/007-trace-provenance/flow-log.md` (already in `origin/main...HEAD`) contains:

`WT=.claude/worktrees path (redacted)/.claude/worktrees/feat-122-trace-provenance`

PRs and commits are public; [SECURITY.md](SECURITY.md) / [CONTRIBUTING.md privacy](CONTRIBUTING.md) / `.cursor/rules/no-local-vault-in-prs.mdc` forbid absolute home paths and usernames. Rewrite to placeholders (`/home/USER/…`, worktree relative name only) before any push that includes this file.

### B4 — Diff exceeds the ≤500-line PR limit with no waiver

Tracked working-tree + committed spec alone is **~803** lines (+721 / −82) across 20 modified files; untracked implementation adds **~1774** lines. [CONTRIBUTING.md — PR size](CONTRIBUTING.md) caps at ≤500 and expects a split or an explicit PR-body waiver. Even after extracting B2, #122 remains large (spec + walker + lint + site + acceptance). Prefer: (1) extract #81, (2) waive leftover size naming what dominates (spec + acceptance suite, not “sloppy scope”), or (3) ship walker/CLI/lint then site as sequenced PRs if reviewers insist.

### B5 — Document-page Sources links are effectively dead (FR2 gap + no regression test)

`raw_site_copy_href` returns `None` for every `raw/docs/…` path. Top-level docs (`raw/docs/guide.md` without `project:`) also get `site_href=None` from `_compute_site_url` (`documents/{project}/…` requires project). Net effect from a quick probe: `provenance_links_for_raw(vault, "raw/docs/guide.md", …)` returns `[]` whether or not `site/documents/guide.html` exists, and still `[]` after self-`exclude_href` on nested document URLs because there is no raw fallback.

`render_document_pages` wires `format_sources_html`, but typical document chains emit no Sources block. Spec FR2 explicitly includes document pages (“prefer HTML; else raw marked (raw), new tab”). No test asserts document HTML provenance (session paths only). This is a broken user-visible acceptance path — see [REVIEW_CHECKLIST §Tests](docs/maintainers/REVIEW_CHECKLIST.md#tests) and FR2 in `functional-spec.md`. Fix the href strategy (e.g. relative path under `documents/` that matches `raw_docs_site` layout, and/or a documented raw/serve fallback that the static site can open) and add a failing-then-passing document fixture alongside the session one.

---

## Nits

### N1 — Slice 4 task text is stale relative to the redesigned FR2

`tasks.md` Slice 4 is checked off while still describing “render every Sources entry from the backing wiki page” via walker/`site_href`. Approved `functional-spec.md` (and the code) use the graph evidence Sources collapse instead, and deliberately omit `provenance-sources` on topics. Update the task prose so future reviewers do not think the implementation missed the slice.

### N2 — `technical-considerations.md` still describes topic frontmatter Sources links

Committed tech spec still lists topic pages as consuming walker Sources links. FR2 redesign made topics graph-only. Align the technical doc (or add an explicit “superseded by functional-spec redesign” note) so the how-doc matches the what-doc.

### N3 — Identity line / index copy: `sessions` → `sources` while the metric is still `session_count`

Topic identity and topics index now say “N sources” for the same graph `session_count` that used to read “N sessions”. That matches the Sources chrome rename but can blur “evidence pages in the graph” vs provenance `sources:` frontmatter. Worth a one-line UI note in `docs/reference/ui.md` if the rename sticks.

### N4 — Process-global `_SOURCE_FILE_INDEX_CACHE` never invalidates

When callers omit `index=`, the first `build_source_file_index` for a vault `resolve()` is cached for the process lifetime. Fine for one-shot CLI/`build`; stale if a long-lived process (tests sharing a vault, future MCP) mutates `wiki/sources/` between lookups. Prefer documenting “pass `index=` for multi-step jobs” more loudly, or invalidate on mtime / clear in tests.

### N5 — `context/spec/006-…/flow-log.md` ride-along

The #81 backfill note under 006 should move with B2’s split PR so each feature’s AWOS log stays coherent.

### N6 — README tests badge jump (3279 → 3904)

Updating the badge is fine if it matches `main` after this lands; avoid mixing badge churn into a feature PR if the count is only true locally with untracked tests. Prefer updating the badge in the commit that actually adds the tests, after CI confirms the number.

### N7 — Lint rule silently no-ops when vault root cannot be inferred

`ProvenanceIntegrity._infer_vault` returns `None` → empty issues. Correct for synthetic in-memory pages without paths; in a mis-wired runner it could also hide real provenance breakage. A single debug/info when `pages` is non-empty but vault is missing would make that failure mode visible.

### N8 — No `Closes #122` / conventional `feat:` commit yet

Only `docs: add spec…` is on the branch. Before opening the PR: one (or more) `feat:` / `fix:` commits with `Closes #122` in the body, after B1–B5 are addressed. Title must stay in the allowed conventional set ([REVIEW_CHECKLIST §Meta](docs/maintainers/REVIEW_CHECKLIST.md#meta)).

---

## Next steps

1. Redact the home path in `flow-log.md` (B3).
2. `git add` every untracked #122 module/test (B1).
3. Split out the #81 `on_disk` backfill (+ 006 flow-log + Fixed CHANGELOG bullet + state tests) (B2).
4. Fix document Sources href/fallback and add an HTML regression test (B5).
5. Trim or waive PR size explicitly in the PR body (B4).
6. Refresh Slice 4 / technical-considerations wording (N1–N2).
7. Open PR with conventional title, linked issue, and only applicable checklist boxes.

Do **not** treat local green alone as merge-ready until the packagers’ blockers above are fixed; after push, wait for GitHub Actions per CONTRIBUTING *After you push*.
