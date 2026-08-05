# Flow log — 004-topic-page-kind-and-key-facts (#108)

## fetch-ticket

Issue #108 — "feat: topic page shows kind, last_updated and Key Facts — project topics route to their project page". State OPEN, label `enhancement`, no comments, no linked issues, no attachments. Roadmap owner: Phase 3 → Visual knowledge depth.

## resume-detection

No prior spec directory, no branch, no PR for #108. Fresh start — no stage skipped.

## workspace

- Branch `feat/108-topic-page-kind-key-facts` off `origin/main` (`e1b869f`)
- Worktree `.claude/worktrees/feat-108-topic-page-kind-key-facts`
- Throwaway vault `.worktree-vault` + worktree-local `config.json` pointing at it; `python3 -m llmwiki init` run against it
- `setup.sh` run with `LLMWIKI_SKIP_AUTOMATION=1` (note: not executable — invoked as `bash ./setup.sh`)

## specs — functional-spec.md

`context/spec/004-topic-page-kind-and-key-facts/functional-spec.md` — approved by the user.

Nine requirements: FR1 identity line, FR2 freshness from evidence, FR3 recorded content, FR4 project topics route to project page, FR5 connected topics on project pages, FR6 distinct colour per kind, FR7 map side panel, FR8 page-less topics, FR9 docs.

### Findings that shaped the spec

Established from code during the interview; carry these into `/awos:tech` rather than re-deriving them.

- **Graph input is wikilinks inside `wiki/sources/*.md` only.** `_session_pages()` (`llmwiki/topics.py:66`) filters `scan_pages()` to `type == "sources"`. A topic node exists because a source summary links to it, *not* because a page describes it. Page-less nodes (`kind: other`) are therefore the normal resting state of every un-promoted candidate, not an edge case.
- **The project match is already known and then discarded.** `resolve_topic_kind()` returns `projects` only when the topic's canonical spelling or one of its aliases matched a page slug or title (`topic_kind_lookup`, `topics.py:197`). No fuzzy matching is needed — the fix is carrying the matched page through instead of keeping only its folder name.
- **The FR4 fallback is for a different case than the issue assumed.** Site project pages are built from sessions grouped by project, not from `wiki/projects/*.md`. A hand-authored project page with no sessions yields a wiki page and no `site/projects/<slug>.html`.
- **Colour collision is `projects` vs `other`.** `colors` (`llmwiki/graph.py:615`) defines `sources, entities, concepts, syntheses, root, topic`; `kindColor = k => (colors[k] || colors.topic)()`. `projects`, `questions`, `comparisons`, `other` all fall through to `--g-node-topic`. Only the projects/other collision is reachable in practice.
- **`questions` / `comparisons` cannot be populated.** No code path writes into either folder; both are scaffolded by `init`, exported by `obsidian_output.py:40`, and described in `exporters.py:446` while staying empty. `syntheses` has no pipeline producer either (promote target + agent-written only). Routed to #109; out of scope here.
- **Project pages carry no `last_updated`.** `ensure_project_stubs()` (`llmwiki/build.py:340`) writes `title/type/project/topics/description/homepage` and no date; none of `resolve_last_updated`'s fallbacks (`ended`/`started`/`date`) exist there either. FR2 derives project freshness from oldest/newest session instead.
- **Entity/concept pages never carry prose above `## Key Facts` in a real vault.** `_preserved_body()` (`candidates_harvest.py:222`) seeds `# {name}` + `## Key Facts`; `synth/prompts/key_facts.md` demands bullets only. Demo pages with description paragraphs are hand-authored. FR3 is therefore format-neutral and renders whatever is present.
- **`docs/reference/ui.md` has no topic-pages section** — it documents every other site surface. FR9 closes that.

### Decisions taken

- Project topics **forward** to the project page (not a link, not an inline copy), and project pages gain a Connected topics list immediately above the session list — so forwarding loses nothing.
- Freshness is two distinct facts: session-derived activity (first seen / last seen) and the page's own review date, labelled separately. Never invented when absent.
- Naming the coding agents on a project page was specced, then **dropped**: `group_by_project` is agent-blind, so a mixed-agent project group only forms when two adapters happen to derive the same slug. Deferred with #126.

### Issues filed / updated during this stage

- **#126** (new) — project aggregation splits one project across worktrees, clones and adapters.
- **#109** (rewritten, retitled) — "make the product explain itself": rebuild the demo from the real pipeline, decide prose vs bullets, settle which page kinds are real, document field provenance, rewrite README.

## specs — technical-considerations.md

`context/spec/004-topic-page-kind-and-key-facts/technical-considerations.md` — approved by the user.

Nine work areas: 2.1 `scan_pages` dates · 2.2 lookup returns the matched page · 2.3 node fields · 2.4 project URL resolution pass · 2.5 build ordering + project page section · 2.6 topic page identity line, content extraction, wikilinks · 2.7 wikilink consolidation · 2.8 viewer colours + panel · 2.9 docs.

### Further code facts established

- **`_compute_site_url()` (`llmwiki/graph.py:107`) already maps `wiki/projects/<slug>.md` → `projects/<slug>.html`.** The value is computed on every scan and discarded with the rest of the page record. §2.4 verifies it against the built project set rather than reconstructing it.
- **`kind` is folder-derived (`scan_pages`, `rel.parts[0]`), never frontmatter-derived.** This is what makes pre-#102 project pages (`type: entity` + `entity_type: project`, per `docs/UPGRADING.md`) resolve correctly. Recorded in §2.2 as a do-not-change.
- **`graph/graph.json` is write-only** — nothing reads it back; `build` reconstructs in memory each run. Stale files from older versions are inert.
- **Search-index topic entries are hand-constructed** (`build.py:2613`), not a copy of node keys, so new node fields cannot leak into the contract frozen by `docs/reference/reader-api.md`.
- **Other `build_topic_graph` consumers** — `synth/pipeline.py:297`, `topics_consolidate.py:54` — read named keys only. MCP does not read the graph at all.
- **`parse_frontmatter` returns `({}, text)`** for absent/malformed frontmatter; `_parse_scalar` strips quotes, so `last_updated` parses whether written quoted (`synth/pipeline.py:631`) or bare (`:1042`).
- **Wikilink duplication is wider than four regexes:** three byte-identical declarations (`graph.py:30`, `lint/__init__.py:36`, `backlinks.py:101`), one function-local variant with different anchor handling (`graphify_bridge.py:77`), and **seven** call sites stripping anchors by hand (`topics.py:140`, `topics.py:258`, `candidates_harvest.py:91`, `backlinks.py:116`, `orphan_detection.py:29`, `link_integrity.py:40`, `references.py:150`).

### Decisions taken

- Node metadata is identity-only; page content is read at render time. `graph.html` embeds the whole graph inline, so anything on a node is downloaded before the map draws.
- Content extraction is heading-agnostic: everything after the H1 except `## Connections` and `## Sessions`. Survives #109 renaming `## Key Facts`.
- Palette recorded in FR6. `#dc2626` was proposed for `other` and rejected — it is already `--g-orphan` and `--g-search-match`; `#65a30d` substituted, and the user approved the correction.
- **Wikilink consolidation brought into scope** at the user's direction, as a §2.6 prerequisite. Target: new leaf module `llmwiki/wikilinks.py` owning `WIKILINK_RE` + `wikilink_targets()`. A leaf avoids the import edge that electing `graph` or `lint` as owner would create.
- **No vault migration.** Every field is derived at build time; existing vaults get the new pages on the next `build`.

**Next stage:** `/awos:tasks` → `tasks.md`. Per delivery-flow §4 / §10 this stage has no document gate and no draft Approve ask under `/implement-feature`.
