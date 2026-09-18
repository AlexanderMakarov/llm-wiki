# Flow log — 248-wiki-site-search-corpus

## fetch-ticket
- TICKET_ID: 248
- Title: MCP search and the browser palette index disjoint corpora
- State: open; blocker #197 closed via PR #254
- Note: user paste about #240/#254 was adjacent context; this flow targets #248
- Next: resume-detection → workspace (done) → specs (/awos:spec interview)

## resume-detection
- No prior context/spec/*248*; issue open; no merged PR for #248
- Entry: start at /awos:spec

## workspace
- BRANCH: feat/248-wiki-site-search-corpus
- WT: .claude/worktrees/feat-248-wiki-site-search-corpus (absolute under repo)
- TMP_VAULT: $WT/.worktree-vault
- Next: specs (awaiting product answers for browse/search/candidates)

## resume-detection (2026-09-16 re-entry)
- Prior run stopped at `workspace` awaiting product answers; no commits, no spec artifacts on disk
- Blocker #197 closed (PR #254 merged 2026-09-12) — #248 unblocked
- Issue #248 still open; no merged PR for it
- Reused existing worktree; rebased branch onto origin/main @ 680680a
- Entry: `/awos:spec`

## product decisions (user, 2026-09-16)
- Shape: **render + index the curated layer** — generate HTML for `wiki/entities/` and `wiki/concepts/`, add them to `search-index.json`, link from nav
- Scope: **site-only** — `llmwiki/mcp/server.py` and `llmwiki/search/*` unchanged (wiki_search already covers the curated layer; the gap is site → curated)
- Out of scope: rendering synthesised `wiki/sources/**` as pages distinct from raw session pages; MCP corpus convergence
- Next: specs

## specs — functional-spec (2026-09-16)
- Produced: `context/spec/248-wiki-site-search-corpus/functional-spec.md` (Status: Approved by user "lgtm")
- Premise correction found during drafting and confirmed with the user: #108 already renders curated entity/concept content at `topics/<slug>.html`; 12 of 13 demo curated pages have a page. The issue's "0 URLs point at entities/concepts" measures the path, not reachability.
- Real defects specced instead: (a) `derive_vocabulary` builds vocabulary only from inbound `[[wikilinks]]` in `wiki/sources/**` and `build_topic_graph` drops anything under `min_sessions=2`, so `demo/wiki/entities/Python.md` (3 declared sources, 1 actual inbound link) has no page and no search entry; (b) `topics/index.html` is generated but absent from `nav_bar` — only 2 of 355 demo pages link it; (c) no search-index entries typed entity/concept.
- Revised decisions (user, 2026-09-16): topic pages stay canonical — NO parallel `site/entities` / `site/concepts` hierarchy; surface the existing topics index in nav rather than adding a new index page.
- FR1 scoping decision: only names with a curated page behind them bypass the min_sessions threshold; derived keywords still need 2 mentions.
- Next: `/awos:tech`

## specs — scope widened to search parity (2026-09-16)
- User asked how the topics index would look and whether ⌘K would match MCP by term. Investigation showed the palette scores with a bespoke JS formula (`js.py:971`) over title/project/short body, while MCP uses `score_extract` (`search/scoring.py:42`) over full page text — different corpus AND different algorithm.
- Decisions (user): fold the search unification into #248 rather than a follow-up; port `score_extract` verbatim including its phrase bonus (literal parity); carry FULL wiki page text (MCP's per-file cap is 4 MiB, effectively uncapped); topics index = grouped sections with counts, NO filter/sort controls.
- Result-row shape (user): one index row per reader page — a session's raw transcript and its wiki summary merge into one entry. Accepted consequence: same formula and corpus, but the merged scoring unit can order some results differently from MCP. Recorded in the functional spec Out-of-Scope; the "identical order" acceptance criterion was corrected to "same pages, same relevance measure" rather than left unachievable.
- Assumption taken, not asked: `wiki/syntheses/` and `wiki/candidates/` are excluded from site search because no reader page exists for them (FR7 forbids dead-end results). Flagged in tech spec §5.3.
- Measured size impact (demo, 175 live wiki pages): eager meta index 149→158 KB (+9 KB); lazy chunks 45→493 KB (~139 KB gzipped); site on disk 10.23→~11.1 MB (+8.7%, `.js` sidecar doubles every payload).
- Corrected an error in the approved functional spec: the "0 findable today" baseline was wrong — 12 of 13 curated pages already have correctly badged palette entries; only `Python` is absent.
- Artifacts: `functional-spec.md` (amended, Status: In Review — FR7 added, scope widened), `technical-considerations.md` (rewritten).
- Next: user approval of both, then `/awos:tasks`

## specs — search data separation + spin-off issue (2026-09-16)
- Investigated why the eager index would grow 1.9×: `search-index.json` is fetched per page view while chunks load once on first ⌘K (`js.py:923-958`). Inlining curated page text into meta entries would put search-only data on every page view.
- Tech spec §2.6 revised (user approved): session/document entries take summary text inline (already lazy); entity/concept/project meta entries keep short bodies and their page text ships in a lazy text payload merged by `id` on load, with an optional manifest key so pre-change sites still work. Added two risk rows (missing payload → name-only + on-page error; merge must not duplicate rows) and three acceptance tests.
- Filed https://github.com/AlexanderMakarov/llm-wiki/issues/269 — `build` writes every raw session twice (`render_session` → `sessions/*.html`, `shutil.copy2` → `sources/*.md`, `build.py:3205-3221`), ~80% of built-site bytes. Issue uses distribution ratios and a demo-vault repro only; no vault-specific data, per user instruction. Consumers documented (`build.py:880` `md_source`, `build.py:1406` `raw_md_path`) so any fix keeps the raw affordance.
- Still open: tech spec §5 decisions 1–3 (sparse-graph split, topic-page `active` key, excluding `wiki/syntheses/`).
- Next: `/awos:tasks` once §5 is settled

## specs — threshold disambiguation + Topics tab naming (2026-09-16)
- User asked why the spec cites 5 when "the default to make a topic is 3", and believed the demo overrides it to 2. Investigation: three unrelated gates — `DEFAULT_MIN_REFS = 3` (`vault_settings.py:39`, candidate harvest + link_integrity, the ONLY per-vault configurable one), `min_sessions = 2` (`topics.py:291` default arg, graph node admission), `_TOPIC_GRAPH_MIN_NODES = 5` (`build.py:3318`, whether the graph renders at all). `demo/llmwiki.json` sets only `lint.disabled_rules` — no threshold override. Table added to tech spec §2.3 and to the `ui.md` docs task.
- Finding while verifying: `demo/wiki/entities/Python.md` lists three sources in frontmatter, none of which cite it; the sole `[[Python]]` citation is a fourth unrelated page (checked under `norm_page_key` folding, #204 rule). Recorded provenance and live link graph are disjoint — harvest at min_refs=3 would not produce the page, the graph at min_sessions=2 drops it, yet it is `status: reviewed`. Strengthens FR1's "key on page existence, not reference count". Recorded in tech spec §2.1; flagged as possibly its own data-defect issue (not filed — pending user).
- User also asked whether the functional spec states the Topics tab is currently absent. It did so only obliquely; §1 problem 2 and FR3 now name the **Topics** label explicitly and state the listing is already generated but unreachable.
- Decision 1 (§5.1, split the sparse-graph `if`) APPROVED by user. §5.2 and §5.3 still open.

## specs — FR7 corrected to match-mode parity (2026-09-17)
- **Correction:** FR7 had been specced against `score_extract` (`mode=extract`). User asked for "by term" = `mode=match`, a different algorithm: literal case-insensitive substring, NO scoring, ordering = title/path matches first then body-only, each group sorted by `rel_path`, returns every matching line. Caps `DEFAULT_PAGE_CAP`/`DEFAULT_HIT_CAP` = 200/200 (`search/engine.py:23-24`).
- Simplifications that follow: no scorer port, no log2 normalisation, no phrase-bonus decision, and no tokenisation — so the Python/JS `\W` Unicode divergence risk is gone (substring compare only).
- WIKI group corpus = exactly what MCP scans from the wiki: every `.md` under `wiki/` except `archive/` (no underscore filter — MCP reads `_context.md`). Demo = 205 files (162 sources, 24 candidates, 9 entities, 4 concepts, 4 root, 1 categories, 1 syntheses).
- Rows with no `_compute_site_url` destination (`overview.md`, `log.md`, `candidates/`, `syntheses/`, `categories/`) render listed-but-not-clickable. This SUPERSEDES the earlier "exclude syntheses" proposal and keeps full MCP coverage without dead ends.
- Raw session search explicitly out of scope (user: "let's don't add requirements for raw search").
- Presentation: two groups, WIKI first, both ALWAYS rendered; an empty group shows a zero-results line. Structured filters stay SITE-only except `kind:`.
- `Python.md` forensics resolved — NOT an LLM glitch and NOT a live harvest bug. At harvest (`0f2b710`, 2026-08-15) the stub recorded `2026-04-26-csv-import-rounding`, `2026-05-09-pagination-cursors`, `2026-07-13-request-id-logging`, and all three cited `[[Python]]` in that tree (verified via `git grep` at that rev). The v2.3.0 regeneration (`0c87174`, 2026-09-08) date-shifted every session filename and dropped `[[Python]]` from all three; `sources:` was remapped to the new slugs but never revalidated. Promote (`15d98a0`) was a file move carrying stale evidence. Nuance: `2026-08-11-request-id-logging` does mention "Python" in prose, just not as a wikilink. Underlying gap — candidate evidence is never revalidated after re-synth, and no lint detects it — is real but out of scope here.
- Both specs now **Approved**. §5 rewritten as Decisions Taken (7) + §6 Assumptions Flagged (2).
- Next: `/awos:tasks`

## tasks (2026-09-17)
- Produced `context/spec/248-wiki-site-search-corpus/tasks.md` — 8 slices, 32 tasks. No draft-approval loop (implement-feature §4 Local Customization).
- Slice order: 1 curated-node bypass (+ build_candidates regression) → 2 sparse-vault decoupling → 3 nav entry → 4 grouped topics index → 5 FR7 build half (lazy wiki payload) → 6 FR7 viewer half (match-mode, two groups) → 7 docs/CHANGELOG → 8 Feature Testing & Regression.
- FR7 split across slices 5/6 so the build half is independently verifiable before any viewer JS exists.
- Agents: `testing-expert` (registered) for slice 8; everything else `general-purpose` — hired-agents.md records Python/CLI and static-site roles as partial/missing by the operator's own earlier choice. Recorded in the tasks.md Recommendations table.
- Next: commit specs, then `/awos:implement`

## operator smoke fixes — visible hit and shared destination (2026-09-18)
- The `file://` demo smoke exposed two presentation defects after the first verified build. A 400-character matcher snippet could contain the correct `<mark>` beyond the palette row's clipped right edge, so rendering now takes a second, narrower window with the first hit near its start; matcher data and Python/JavaScript parity are unchanged.
- A synthesized source page in Wiki and its raw session/document record in Site can resolve to the same reader URL. Both searchable corpora remain intact, but the shared destination now renders once with Wiki precedence; a Site row still appears when its raw text matches and the wiki summary does not.

## independent review keep/drop — 2026-09-18
- Independent verdict: **Request changes** — 1 blocker and 4 nits recorded in the session-only `review.md`.
- Operator decision: keep B1 and N1–N3; waive N4 (PR size), because #248 intentionally delivers the approved end-to-end curated browsing and search-parity flow in one branch. Record the waiver in the PR body.
- B1 + N1 resolution: harden and deterministically sort the shared corpus traversal before reads, then make the site build reuse `iter_scanned_pages` with the same 4 MiB per-file and 50 MiB aggregate caps as assistant search. Publish completeness flags so the static UI warns when pages were omitted.
- N2 product decision: empty input stays a 10-row browse preview; every explicit Site text/filter/sort query may return up to 200 rows. Filter-only and sort-only overflow states say `Showing 200 of N matching results.`; text retains the 200-page / 200-line matcher caps.
- N3 resolution: README now names Topics and the two-group Wiki/Site quick search.
- The earlier “full text, effectively uncapped” decision is superseded by the shared cap-aware traversal above; retained pages remain whole and are never partially read.

## commit-push — accepted review remediation (2026-09-18)
- Implemented accepted findings B1 and N1–N3; N4 remains explicitly waived by the operator.
- Security/DRY: `iter_scan_files` now resolves and contains candidates before reads, skips final symlinks, sorts paths deterministically, and `read_capped` uses a no-follow regular-file descriptor where the platform provides it. `build_wiki_corpus_entries` now consumes `iter_scanned_pages` rather than maintaining a second reader.
- Parity/completeness: browser corpus uses the shared 4 MiB/file and 50 MiB aggregate caps and emits `_wiki_corpus_status`; palette warnings replace definitive no-match claims when the static corpus is incomplete. Boundary coverage includes symlink rejection, over-4-MiB pages, the 50 MiB budget, and more than 200 files created out of order.
- Site cap: empty input stays a 10-row preview; explicit text/filter/sort queries use the 200-result ceiling, with exact totals for filter-only/sort-only truncation.
- Static gate: `ruff check llmwiki tests scripts` passed. Full pytest had only the same three environment-only failures (one real-home write blocked by the read-only sandbox; two isolated wheel builds blocked from dependency downloads). The full suite passed with exactly those three cases deselected. Fresh demo build: 205 corpus entries, no input cap reached, zero oversized skips.
- Next: commit and push, rebase against current `origin/main`, open PR, and watch required checks. Do not append to this tracked log after the PR opens.
