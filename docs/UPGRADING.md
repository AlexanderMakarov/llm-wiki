---
title: "Upgrade guide"
type: navigation
docs_shell: true
---

# Upgrade guide

How to upgrade between `llmwiki` releases.  Most releases are drop-in (`pip install -U llmwiki` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`.

The canonical per-release detail is [CHANGELOG.md](https://github.com/Pratiyush/llm-wiki/blob/master/CHANGELOG.md) — this guide focuses on "what might break".

## Unreleased — exclude headless across adapters (#180)

- **`filters.exclude_headless` (still default on) now classifies automated launches for every coding-agent adapter, not only Claude.** Cursor Agent CLI sessions with `subagentInfo` or `approvalMode=auto-review` are skipped on sync and omitted from synth / `--estimate` backlog once marked. OpenClaw sessions stay eligible (never treated as headless). Codex / OpenCode / Copilot stay eligible until verified markers exist.
- **Re-sync to classify older Cursor Agent CLI rows.** Raw files converted before this change have no `is_headless` frontmatter and stay eligible for synthesis until you re-convert them (`llmwiki sync --force` for those sessions, or a full force sync if you accept the cost). After re-sync, newly classified headless rows drop out of the synth backlog.
- **Cursor CLI `sessionId` / chat time fix on re-sync.** Convert now writes store meta `agentId` as `sessionId` (never the filesystem stem `store`) and uses meta `createdAt` for `started` / filenames. Re-sync Cursor Agent CLI after upgrading so new raw files are stable and correctly dated.
- **Optional: `llmwiki migrate-broken-provenance --vault <vault>`** when wiki pages still point at missing `raw/sessions/…` paths left by an older `sessionId: store` sync. Preview with `--dry-run`. Remaps only to a **same-calendar-day** interactive raw under the same project (`is_headless: false` or unmarked legacy; uniquely closest HH-MM when several); never to explicit headless rows, and never across days. Otherwise clears the broken `source_file` without deleting wiki pages. See `docs/reference/cli.md`.
- **Nested Cursor Task / subagent runs are under `exclude_headless`, not `include_subagents`.** Turning off `exclude_headless` includes them again. Support map: [multi-agent-setup.md](multi-agent-setup.md).
- **Contrib adapters still need `--adapter`.** This change does not implement [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182); Cursor Agent CLI / OpenClaw / Copilot still require an explicit adapter choice on sync.

## Unreleased — `synth --estimate` Already synthesized follows synth state (#163)

- **`synth --estimate` Already synthesized now uses the same state+mtime predicate as a real `synth` run.** Pages on disk alone no longer count as done. If synth state is missing or stale, you may see Already synthesized drop and New / incremental $ rise — that matches what the next non-force run would process. No vault migration; the real `synth` skip rules were already this way.

## Unreleased — auto-generated `/vs/` model comparisons removed (#138)

- **No vault migration.** The `/vs/` surface was never called from `build_site` and never wrote `site/vs/` for a normal vault build. Rebuild as usual.
- **Optional cleanup.** If you hand-authored `wiki/vs/*.md` overrides from older docs, they are no longer read; delete or keep as personal notes. `/models/` is unchanged.
## Unreleased — a vault can switch checks off, and MCP `wiki_lint` returns the CLI report (#150)

- **BREAKING — the MCP `wiki_lint` tool's payload changed shape.** It used to return `orphans` / `orphan_count` / `broken_links` / `broken_link_count`; it now returns `summary` / `issues` / `total_pages` / `disabled_rules` / `ran` — byte for byte the payload `llmwiki lint --json` prints for the same vault. **Anything reading the old keys breaks.** `broken_links` becomes the entries of `issues` whose `rule` is `link_integrity`; `orphans` becomes those whose `rule` is `orphan_detection`; the two counts become their lengths. Nothing to run, and nothing in your vault changes — it is the tool's output contract, not your data.
- **Why it had to break: the tool was running different checks from the command.** It implemented **2** hand-rolled checks against the registry's **17**, and both were stricter than the real ones — its broken-link test demanded an exact filename-stem match (no slug normalisation, no `#anchor` stripping) and its orphan test counted inbound `[[wikilinks]]` only, skipping a hardcoded `index`/`overview`/`log` list rather than the full system-page set. So it **over-reported on both**, while its own description advertised contradictions and stale summaries it had never implemented. Keeping both payload shapes would have preserved exactly the disagreement this fixes.
- **Expect findings your assistant did not report before.** All 17 rules run through MCP now, so contradictions, staleness, frontmatter completeness, provenance and catalog health show up there for the first time. Broken-link and orphan counts, meanwhile, should go **down** — those two were the over-reporting ones.
- **`wiki_lint` gained two optional arguments mirroring the CLI flags:** `rules` (a list of names, or the CLI's comma-separated string) and `min_refs`. There is no `fail_on_*` — there is no exit code over MCP. An unrecognised rule name is an error, not a silent skip, so a narrower run can never be misread as a clean one.
- **A vault can now declare the checks that do not apply to it, in a committed `<vault>/llmwiki.json`.** `lint.disabled_rules` takes either a list (`["content_freshness"]`) or an object mapping each rule to a written reason. The declaration travels with the wiki, and every report — `lint`, `lint --json`, the `all` pipeline's lint stage, and `wiki_lint` — names each skipped rule with its reason **whether or not anything was found**. Switching off every rule reports that nothing was checked rather than a clean summary. **Nothing to do if you want the old behaviour**: a vault with no `llmwiki.json` behaves exactly as before.
- **A misspelled or retired rule name in that file stops the run with exit 2,** naming the file, the bad entry, and the valid names; an `llmwiki.json` that cannot be parsed is the same hard error. Neither is ever a silent "no opt-outs" — a declaration nobody can read might be switching every check off.
- **`llmwiki lint --min-refs N` and `llmwiki all --min-refs N`.** `link_integrity` now honours the same significance threshold the candidate harvest uses (default **3**), so a `[[wikilink]]` to a topic the harvest deliberately declined to materialize is no longer reported as broken. **Expect your broken-link warnings to drop sharply** — the shipped `demo/` vault goes from 120 to 0. Lowering the threshold reports more, not fewer: `--min-refs 1` restores every unresolved link, so nothing is permanently hidden. A link to a target no source page names at all is still reported at every threshold. `--min-refs` was previously reachable only from `synth`, so `llmwiki all` harvested at the stock value no matter what you passed; it now threads through to both the harvest and the lint stage.
- **`llmwiki lint --fail-on-warnings`** stops the gate on warning-severity findings as well as errors. The default posture is unchanged. Checks a vault switched off cannot stop the gate, because they never ran.
- **A failing `lint` now records that it ran.** `--fail-on-errors` used to return above the `last_lint_run_at` state update, so the Home "last lint" timestamp stood still exactly while the gate was red. No migration — the next run records itself.

## Unreleased — `all` runs every stage; automation setup is plain-language (#156)

- **`llmwiki all` now includes `sync` and `synth`, which used to be opt-in.** The pipeline is `sync` → `synth` → `build` → `graph` → `lint`, and each stage has an opt-out flag: `--no-sync`, `--no-synth`, `--skip-graph`, `--skip-lint`. **If you have a bare `llmwiki all` in cron, it will start summarising your sessions.** How much that matters depends on your backend: the default `synthesis.backend` is `dummy`, which makes no provider call, so a default install spends nothing — the change only reaches you if you configured a real backend. To keep the old shape, add `--no-sync --no-synth`; to keep sync but never call a provider, add `--no-synth`. If a real backend is configured, the first `llmwiki all` you run in a terminal prints the same warning once, before any provider request; scheduled runs stay quiet because their output is a log file, not a terminal.
- **`--with-sync` / `--with-synth` still parse, but do nothing.** They are accepted so an already-installed scheduled command does not die on "unrecognized arguments"; each prints a one-line notice. `--no-synth` wins over `--with-synth` and `--no-sync` over `--with-sync`, in any order.
- **Lint findings no longer fail `all` unless you ask.** The new `--lint-fail {never,errors,warnings}` decides, and the default is `never` — lint still prints its full report and the run still exits `0`. `--strict` is the spelling for `--lint-fail warnings`; when both are given, the stricter wins.
- **Re-run `llmwiki install-automation` if you already have a scheduled job.** The wrapper command it writes changed with the `all` flip, and an old unit keeps running yesterday's command line forever. Re-running replaces the existing job rather than adding a second one. Jobs installed by an older version still show up on the site's Home Automation panel — the recorded `A` / `B` / `C` letters are read as *Ingest only* / *Maintain*.
- **`--hour` / `--minute` are superseded by `--schedule` with a cron expression.** Both flags still work and are translated to `"{minute} {hour} * * *"`; they are ignored with a notice when `--schedule` is also given. `--schedule "0 8 * * 1-5"` is what makes "weekdays only" expressible. Standard 5-field cron only: nicknames (`@daily`), Vixie/Quartz extensions (`L`, `W`, `#`), a seconds field, and any expression restricting both day-of-month and day-of-week are refused with exit `2`.
- **`--profile {A,B,C}` is deprecated in favour of `--job {ingest,maintain}`.** `A` maps to `ingest`, `B` and `C` both to `maintain`; the old letters still work and print a notice. The extras that used to be welded to a letter — the knowledge graph and the quality-failure policy — are now their own flags (`--graph {none,builtin,graphify}`, `--lint-fail {never,errors,warnings}`), off unless you ask for them.

## Unreleased — one synthesis pass per source (#147 / #145)

- **Next `synth` rewrites source pages that lack parseable topic bullets.** Summaries written before this change are treated as out of date once; after that catch-up, only new or otherwise stale sources are synthesized. If you override `wiki/prompts/source_page.md`, update it so Connections match the new shape (`- [[ExactName]] (entity|concept) — …` with nested `fact:` lines) — Key Claims / Key Quotes stay.
- **Optional cheap catch-up: `llmwiki migrate-topic-kinds --vault <vault>` (#174).** When most connection targets already have entity/concept (or pending candidate) pages, this offline stamp fills missing `(entity|concept)` labels on source Connections from the wiki on disk — no language-model or network call. Preview with `--dry-run`. It does **not** invent nested `fact:` lines or rewrite Key Claims / Key Quotes; the report states that no facts were derived. After stamping (and on a re-run over already-clear pages), it also upserts synth state for every raw session/doc whose wiki target is rewrite-clear, including when many raw files share one synth filename, so plain `llmwiki synth` / `--estimate` will not re-bill those sources (#163 done predicate).
- **One-way lock-in after a stamp.** Once a source page has at least one usable topic kind, a normal `synth` treats it as caught up and will not revisit it for the #147 topics rewrite unless you pass `--force`. Prefer dry-run first; stamp only when clearing the mass-rewrite backlog is worth that trade-off.
- **Facts still need a forced re-synthesis.** After a successful non-dry-run that stamped pages, the vault root gains `.llmwiki-topic-kinds-stamped.json` listing each stamped wiki page and its frontmatter `source_file` (when present). To buy fact lines later for exactly that set, run `llmwiki synth --force --path <raw/…>` for each `source_file` entry (repeat `--path`, or script the list) — not a bare vault-wide `synth`.
- **`llmwiki consolidate-topics` is gone as a lifecycle step.** The name still resolves but always exits `2` with a message that synthesis prepares the known-names list. Do not run `--complete` or expect a prompt file / `.llmwiki-topics.json` write.
- **Promote no longer needs a language-model backend.** Empty Key Facts are filled from source `fact:` bullets offline; Dummy/`None` is fine. Reviewer-written Key Facts are preserved. `rewrite-key-facts` still requires `claude` or `ollama`. This supersedes the older Unreleased note that said promote failed with `KeyFactsBackendError` without a backend (#103).
- **Ctrl+C during `synth` harvests from written pages** (unless `--sources-only`, which prints `llmwiki synth --candidates-only`) and exits **130**. Run that recovery command if you interrupted a sources-only pass.
- **Home pipeline `on_disk` recovers on `build` (#145).** When stored totals disagree with `wiki/sources/**/*.md`, the next `llmwiki build` refreshes them — you do not need an estimate run to unstick zeros after an interrupt.

## Unreleased — agent commands ship in the package (#109)

- **`llmwiki install-agent-kit --dest PATH` copies the slash commands and skills into any agent directory you name.** A pip or Homebrew install now carries them; you do not need this repository. `--dest` is required — there is no auto-detection. Typical destinations: `.claude` in the project you are working in, or a user-level agent directory. Re-running after an upgrade refreshes the copies; a file you edited that now differs from the packaged version is saved as `<file>.bak` beside it before it is replaced. `--dry-run` prints the plan and writes nothing. See `docs/reference/cli.md` → `## install-agent-kit`.
- **`.claude-plugin/` is gone.** The Claude Code plugin manifest could not work (wrong paths, wrong Python floor, incomplete command list). `install-agent-kit` is the supported delivery channel.
- **Manual copy of `.claude/commands/wiki-*.md` is no longer the upgrade path.** Earlier notes that said to copy those files out of a clone (after `install-skills` was removed) are superseded: install the package and run `install-agent-kit`.

## Unreleased — the server is gone; the site is files (#109)

- **`llmwiki serve` no longer exists, and `serve.sh` / `serve.bat` are deleted.** A build already produced a site that works from disk, so **open `site/index.html`** (or `<vault>/site/index.html`) in a browser instead. Navigation, project and session pages, topic pages, search and the graph all work with nothing running. Anything scripted around `llmwiki serve` should either open the file or, when it genuinely needs an HTTP origin, use the stdlib stand-in: `python3 -m http.server 8765 --directory <vault>/site`.
- **Publishing is unchanged.** `site/` is still a static tree — GitHub Pages, GitLab Pages, Netlify, Vercel and any web server serve it as before. See `docs/deploy/`.
- **Docker: the image builds, it does not host.** `Dockerfile` drops `EXPOSE` and its default command is now `build`; `docker-compose.yml` drops `ports`, the healthcheck and the restart policy. Replace `docker compose up -d` with `docker compose run --rm llmwiki build`, then open `./site/index.html` on the host — `site/` is bind-mounted, so the pages land beside your other files.
- **Executing candidate decisions moved to the command line; deciding them did not.** The `POST /api/candidates` endpoint lived inside the removed server. `candidates.html` still carries its per-row **Decision** control (Promote · Flip and promote · Merge into… · Discard) and its **Apply** button — those are browser state and need nothing running. Apply now assembles the rows you decided into the command to run and the JSON batch to pipe into it:

  ```bash
  llmwiki candidates apply --vault <vault> --actions -
  ```

  Paste the JSON the page prints into that command. Every row starts at **No decision** and only the rows you chose enter the batch, so an undecided row stays pending and a half-finished review can be applied and resumed. The one-off subcommands (`list`, `promote`, `flip-promote`, `merge`, `discard`, `rewrite-key-facts`) and `/wiki-candidates` are unchanged. **The printed command carries `--vault`** — the old copy-CLI line omitted it, so it only ever acted on the default vault. A successful `apply` rebuilds `site/` so reload the candidates page (or reopen the file) to see the remaining queue; pass `--no-rebuild` to skip.
- **`/wiki-serve` is deleted.** If you installed the slash commands into your own agent directory, remove `wiki-serve.md` from it.
- **The site fetches nothing.** highlight.js and both of its themes are now copied into the site root at build time instead of loaded from a CDN. No action needed — the files appear on your next `llmwiki build`. If code blocks come out unstyled, re-run the build; if they still do, the installed package is missing its vendored assets and should be reinstalled.

## Unreleased — the displayed local path is a build input (#109)

- **`llmwiki build --local-root PATH` sets the value shown in place of a session's stored home directory.** Without the flag it resolves from the machine running the build, so browsing your own site locally still shows paths you can paste into a shell — no configuration needed, and nothing to do after upgrading.
- **Pass a fixed string when you publish.** `llmwiki build --vault demo --out ./site --local-root /home/user` renders the same pages on every machine, so a published site never shows whoever ran the build. The repository's own Pages workflow does exactly this.
- **The displayed path is no longer worked out by undoing the redaction applied at import.** It rewrites the home directory a stored `cwd` begins with, so it no longer depends on `redaction.real_username` / `replacement_username` in `config.json` matching what was written months ago. Those settings still control what `sync` writes into `raw/`; they simply no longer affect what the site displays.
- **Only the `cwd` field is substituted.** A session description is prose from the first user turn and is now rendered exactly as imported — previously any path-shaped text inside it was rewritten too. Descriptions on `sessions/index.html` may therefore show `/home/USER/…` where they previously showed your username. That is the redacted value as stored; it is not a regression.
- **`llmwiki.convert.restore_local_path` is removed.** Scripts importing it should call `llmwiki.build.display_cwd(cwd, local_root)` instead.

## Unreleased — page kinds `question` and `comparison` removed (#109)

- **`type: question` and `type: comparison` are no longer valid frontmatter.** They are gone from the `type:` vocabulary, so `llmwiki lint` reports a `frontmatter_validity` **error** on any page still declaring one, and `wiki_search` no longer offers them as a `kind` filter. Nothing in the product ever created such a page — `init` never scaffolded `wiki/questions/` or `wiki/comparisons/`, and no synth, harvest, or promote path wrote into them — so for almost every vault this is a no-op.
- **If you hand-wrote pages of either kind, run `llmwiki migrate-page-kinds --vault <your vault>`.** It retypes each page to `concept`, moves it into `wiki/concepts/` keeping the filename, deletes the legacy `_context.md`, and prunes `wiki/questions/` and `wiki/comparisons/` once they are empty. Inbound `[[wikilinks]]` resolve by filename, not by folder, so the move does not break a single link and no referring page is edited. Preview with `--dry-run`; a vault with no such page prints `nothing to migrate` and exits 0. A filename already taken in `wiki/concepts/` is never overwritten — that page is retyped where it stands and reported so you can settle the clash — and a legacy folder still holding other content is left in place and reported. Rebuild afterwards (`llmwiki build --vault <your vault>`) so `site/` picks up the new locations.
- **A folder you keep for your own reasons still works.** `reindex` catalogues any folder it finds under `wiki/`, so pages in a non-canonical folder stay listed in `wiki/index.md` and stay in the graph. Only the frontmatter `type:` value is constrained.

## Unreleased — trace provenance + lint `provenance_integrity` (#122)

- **New CLI: `llmwiki trace <page>`.** Prints the downward provenance chain from a wiki page to its source summaries and raw files (`sources:` / `source_file:` only). Missing hops are labelled; the walk still exits 0 unless the starting page cannot be resolved. See `docs/reference/cli.md` → `## trace`.
- **New lint rule `provenance_integrity` (errors).** After upgrading, `llmwiki lint` (and `llmwiki all`) may report **new errors** on pages whose `sources:` slugs or `source_file:` paths no longer resolve. Pages with no provenance fields are unchanged. The rule only reports — it does not prune or rewrite frontmatter. Guided repair ships with `doctor` (#110); until then, fix pointers by hand or leave the findings if the targets are truly gone.
- **Site Sources links.** Session and document pages turn provenance Sources into clickable links: built HTML when the hop compiled, otherwise the raw (or site copy) in a new tab with a “(raw)” mark. Topic pages list graph evidence under a collapsible **Sources** section (Sessions / Documents), not a separate frontmatter provenance panel. Rebuild with `llmwiki build` to see them.
- **No new MCP tool.** Agents that need the chain should call `llmwiki trace` (or read frontmatter via existing wiki tools). Do not expect a `wiki_trace` MCP entry.

## Unreleased — entity-type taxonomy dropped, `project` page kind, one search tool (#102)

Four breaking changes ship together. Three need nothing from you; the fourth is the only one with a data decision, and it is optional.

- **Lint rule `entity_consistency` is gone, and an unknown `--rules` name now fails the run.** `llmwiki lint --rules entity_consistency` exits non-zero naming the unknown rule, where before it ran zero rules and reported a clean vault. Drop the rule from any script that pins it; plain `llmwiki lint` needs no change. The rule only ever demanded an `entity_type` value from a fixed seven-value list — removing it removes errors, not coverage.
- **`synth --allow-unclassified` is gone.** That flag was removed when harvest still ran a classify pass. **#147 later made harvest offline** (kind comes from source topic bullets; no classify LLM). Drop any leftover `--allow-unclassified` from scripts; you do not need a classify-capable backend for harvest.
- **MCP tool `wiki_entity_search` is gone; `wiki_search` absorbs it.** There is no alias — an agent config or script naming `wiki_entity_search` gets an unknown-tool error, so re-read the tool list. `wiki_search` takes `term` (required), an optional `kind` (one of `source`, `entity`, `concept`, `project`, `synthesis`, matched against frontmatter `type`; the internal `navigation` and `context` kinds are not offered as a filter, and an unfiltered search still reaches those pages), an optional `format`, and the existing optional `include_raw`. The two compose independently: `include_raw` decides whether `raw/sessions/` is scanned at all, `kind` filters frontmatter `type` in every corpus that is scanned. Raw transcripts declare `type: source`, so `kind=source` with `include_raw` returns matching source pages *and* the transcripts behind them, while a kind no transcript declares (`kind=project`) simply contributes nothing from the raw corpus rather than erroring. Results are page-level (`path — title` with matching lines indented beneath) instead of bare `file:line`, and pages matching by title or path sort above pages matching only in the body. The default response is prose, not JSON: a client that did `json.loads(text)["matches"]` should pass `format: "json"`, which returns `{term, kind, include_raw, pages: [{path, title, name_match, lines: [{line, text}]}], truncated, budget_exhausted, skipped_oversize_files}`. Both renderings report completeness in two fields — `truncated` when an output cap dropped matches, `budget_exhausted` when the byte budget stopped the scan short of the corpus.
- **`project` is a first-class page kind.** `type: project` is now accepted alongside `entity` and `concept`, new project stubs are written as `type: project` with no `entity_type`, and project pages are covered by claim verification and the graph relevance bonus.

### What needs no action

- **Pages that still carry `entity_type` keep it as inert metadata.** Nothing validates it, nothing reads it, and no migration ships. Leave the field or delete it — either way the vault lints the same.
- **`entity_kind: ai-model` is untouched.** It is a different field with a similar name and it still drives the AI-model index and info-cards. Do not sweep it away while cleaning up `entity_type`.
- **Project pages written by an earlier build stay valid.** `type: entity` on a page under `wiki/projects/` is still an accepted kind, the catalog's Projects section keys off the folder rather than the frontmatter, and claim verification and the graph bonus already covered `entity`. Nothing errors and nothing is dropped.

### Optional: re-stamp existing project pages

`ensure_project_stubs` only writes *missing* stubs, so project pages created before this change keep `type: entity` + `entity_type: project` indefinitely. That is valid but inconsistent with what the build writes today, and it has one visible effect: those pages answer `wiki_search kind=entity` rather than `wiki_search kind=project`. If you want the whole folder to declare its kind, edit the frontmatter of each file under `wiki/projects/` — set `type: project` and delete the `entity_type:` line, leaving the body alone:

```bash
sed -i.bak -e 's/^type: entity$/type: project/' -e '/^entity_type: project$/d' <vault>/wiki/projects/*.md
rm <vault>/wiki/projects/*.md.bak
llmwiki lint --vault <vault>          # expect no new errors
llmwiki build --vault <vault>         # refresh the site and search index
```

Frontmatter only — a project page whose body you have written by hand is not otherwise touched.

### Built search index

`site/search-index.json` (and its sharded siblings) no longer carry an `entity_type` key per entry or an `entity_type` bucket under `_facets`. The shipped site reads neither, so the browsable site is unaffected; only a client that reads the index file directly needs to adjust. `docs/reference/reader-api.md` drops the matching invariant from its data-model list, and the surviving invariants renumbered — cite an invariant by the field it constrains, not by its position in the list.

## Unreleased — honest already-synthesized counts (#81)

- **`synth --estimate` Corpus / Already synthesized count eligible sources**, not pages under `wiki/sources/`. Expect `Corpus: N eligible sources (S sessions + D docs)` and `Already synthesized: N of M eligible sources`. A separate `Source pages (current state): T on disk (Sess sessions + D docs + X stubs)` line is the on-disk `.md` file mix (not unique `source_file` keys) — it may differ from Already synthesized when bookkeeping and disk diverge.
- **Home Pipeline** captions the input table **Eligible sources** (not Files layer as the unit of the input columns) and adds an **On disk** column (Stubs row; Other when needed). There is no under-table Source pages note.

## Unreleased — honest estimate Candidates (#113)

- **`synth --estimate` Candidates is pre-run state**, not a preview of what the next run will harvest. The block is labelled `Candidates (pre-run state):` and notes that pending sources are not yet reflected.
- **After a successful real `synth`**, the CLI prints an end-of-run summary: `Synthesized:`, `Duration:`, optional `Tokens:` / `Cost:` when known. Harvest still prints Candidates once; the end summary does not repeat that line.
- Home Knowledge-layer **Candidates** still counts pending pages under `wiki/candidates/` — distinct from the estimate pre-run harvestable figure.

## Unreleased — promote writes Key Facts with an LLM (#103)

> **Superseded for promote by [#147](#unreleased--one-synthesis-pass-per-source-147--145):** empty Key Facts are filled offline from source `fact:` bullets; Dummy/`None` is fine. The bullets below are the #103-era note (keep for `rewrite-key-facts` / merge behaviour).

- **`llmwiki candidates promote` (as of #103) filled Key Facts via the synthesis backend.** That LLM requirement for promote is lifted in #147. Pages that already have Key Facts, and pages whose sources never describe them, were always promotable without a backend.
- **`llmwiki candidates merge` no longer pastes the candidate body** when the candidate is a harvest stub. Its `sources:` and Connections links are unioned into the target page and the name goes under `## Aliases`. Reviewer-written candidates still get their prose appended under `## Candidate merge — <date>`.
- **`/wiki-candidates` should use the CLI promote path** for the common empty-Key-Facts case.
- **Pages promoted by an earlier build carry machine-assembled Key Facts.** Those bullets were clipped from the line nearest a wikilink, so some state a fact about a different subject. Rewrite them with `llmwiki candidates rewrite-key-facts --slug <Name>` (or `--all` for every entity/concept) — that still needs an LLM. That also drops pasted harvest-stub `## Candidate merge` blocks left by the old merge behaviour.

## Unreleased — `wiki/archive/` is cold storage everywhere (#140)

Discarding a candidate means you judged the term to be noise. `wiki/archive/` keeps the stub for history, and nothing that reads content surfaces it any more.

- **`wiki/index.md` stops listing archived pages.** Discarding a candidate used to write an `## Archive (N)` section that `lint` then reported as dead index links, so a correct vault failed `lint --fail-on-errors` (and the `wiki-checks` workflow with it).
- **Nothing to run.** The next `reindex` — which `sync`, `synth`, `remove` and every `candidates` action trigger — deletes a leftover `## Archive` section and its bullets. No migration command.
- **Any note you hand-wrote under a `## Archive` heading is removed along with the section.** Reindex drops the whole block, prose included. If you keep a note there, move it above the first section heading before your next `reindex`.
- **`llmwiki lint` no longer scans archived pages,** and they stop counting toward `orphan_detection` and aging into `stale_candidates`, so those two rules get quieter.
- **Your warning count may go up on the first lint after upgrading.** The archived copy of a discarded candidate used to satisfy `[[wikilinks]]` pointing at it, so those links were silently counted as resolving. They were already broken; lint just stopped hiding them. Fix them by promoting a real page, or leave them if the target genuinely should not exist.
- **Archived pages are no longer graph nodes,** so `graph.json` and the map lose one node per discarded candidate. Tags on archived pages also stop appearing in the tag index, and they no longer get backlink blocks.
- **The MCP tools honour the same rule.** `wiki_search` no longer returns archived pages, `wiki_query` no longer quotes them, and `wiki_lint` reports a `[[wikilink]]` to a discarded slug as broken — it used to resolve those links against the archived copy, so it and `llmwiki lint` disagreed about the same vault.
- **One deliberate exception: candidate harvest still counts archived slugs as resolved.** The archived stub is the only record that you dismissed the term, so `synth` will not re-propose it. Without that, every term you discarded would come back as a candidate on every run.
- **`[[wikilinks]]` to discarded slugs stay broken and are not rewritten.** That is the intended reading: the target was deliberately thrown away, so the link needs your decision, not a silent resolve.
- **Scope is exactly top-level `wiki/archive/**`.** A folder named `archive` nested deeper (say `wiki/sources/archive/`, from a project slug of that name) stays a live page set.

## Unreleased — `llmwiki synth` rename (#90)

- **`llmwiki synth` is the primary command.** Default: synthesize pending sources, then harvest entity/concept candidates. Prefer it over `synthesize`.
- **`llmwiki synthesize` is deprecated.** It still runs (scripts keep working) but prints a warning and defaults to sources-only — the old behaviour — so upgrading does not silently write a large candidate backlog. Prefer `llmwiki synth` (or `synth --sources-only` / `synth --candidates-only`).
- **`all --with-synth` / `watch`** call `synth` (sources + candidates). Harvest after sources is offline (#147) — no classify retry loop.
- Slash: `/wiki-synth` preferred; `/wiki-synthesize` remains as a deprecated wrapper.

## Unreleased — candidates review gate on Home / Analytics (#84)

- **Home** shows an **Eligible sources** table (Raw → To synthesize → Synthesized → On disk; shell-handled input counts — see #81) and a **Knowledge layer** table (Candidates → Entities / Concepts; review via agent Commands). Candidates = pending `wiki/candidates/` pages (not the estimate `Candidates (pre-run state):` harvestable figure). Entities/Concepts = trusted pages after promote.
- **Every `llmwiki build`** recounts pending/stale candidates and trusted entity/concept counts into `synth.pipeline` before copying `llmwiki-state.js` into `site/` — promote/discard no longer leave a stale Home table until the next estimate.
- **Commands** agent rows are one-shot: `cd <llm-wiki-checkout> && claude|agent|codex "/wiki-candidates"` (Purpose: review/edit candidates). Slash commands load from the checkout, not the vault. Gemini CLI stays adapter-scaffold — no Home launcher.
- **Analytics** adds a **Candidates to review** section (pending + stale). Zeros are intentional: a synthesize-only vault still shows that the review gate exists.
- **No auto-promote.** Trusted hubs still require `llmwiki candidates promote|merge|discard` or agent `/wiki-candidates` / `/wiki-ingest`.

## Unreleased — pipeline reshape: export/reindex CLI removed, `all` extended

- **`llmwiki export` is gone.** AI-consumable files (`llms.txt`, `llms-full.txt`, `sitemap.xml`, `rss.xml`, `robots.txt`, `graph.jsonld`, `ai-readme.md`, etc.) are written by `build` into `--out` (default `site/`). Replace `llmwiki export all` with `llmwiki build`. The library module `llmwiki.exporters` (`export_all`, …) remains — only the standalone CLI entry point is removed.
- **`llmwiki reindex` is gone.** Catalog reconciliation (`wiki/index.md` ↔ pages on disk) runs inside `sync`, after a sources `synth` pass that actually wrote pages, after candidate **harvest** when stubs are written, and after `candidates promote|merge|discard` (#101). Idle sync/synth with nothing new are not the path to clean the catalog after review — use the candidates consume actions. After unrelated hand-edits to `wiki/`, `llmwiki sync --no-auto-build` still reconciles; then `llmwiki lint --rules index_sync` to verify. The library module `llmwiki.reindex` (`reindex_wiki`, `plan_reindex`) remains for internal callers.
- **`sync` always reconciles `wiki/index.md`.** Reconciliation used to run only inside the auto-build branch; it now runs after every successful `sync` regardless of `--no-auto-build`, so a sync-only workflow can't drift the catalog between builds.
- **`llmwiki all` pipeline order** — `[sync?]` → `[synthesize?]` → `build` → `[graph?]` → `lint`. Optional `--with-sync` converts new agent sessions (auto-build off — `all` builds next), refreshes the synth-pending backlog, and reconciles the catalog. Optional `--with-synth` fills `wiki/sources/` from `raw/`. `build` already calls `export_all`, so there is no separate export step. `graph` is skipped with `--skip-graph`.

```bash
llmwiki all                              # build → graph → lint
llmwiki all --with-sync --with-synth     # sync → synthesize → build → graph → lint
llmwiki all --strict                     # exit 2 on any lint warning
```

- **`llmwiki all` no longer self-deadlocks.** It used to acquire the pipeline lock and then dispatch to `cmd_build` / `cmd_sync` / `cmd_synthesize`, each of which tried to acquire the same non-reentrant lock again and hung. `run_pipeline` now takes the lock exactly once and calls the library functions directly (`convert_all`, `synthesize_new_sessions`, `build_site`, …). No CLI or config change is needed — `llmwiki all` just completes instead of hanging.
- **`llmwiki watch`** — near-real-time maintain: polls agent session stores and runs sync → synthesize → build when a session finishes (turn-complete gating where the adapter supports it). Restores the v1.2.0-removed daemon as a focused maintain loop; stdlib only, no `watchdog` dep.
- **`llmwiki install-automation`** — interactive setup for OS schedulers (systemd / launchd / Task Scheduler), optional agent hooks, and synth backend; writes automation status for the site Home panel. Non-interactive flags exist; `./setup.sh` is an alias.

Index reconciliation behaviour (#71) is unchanged — existing entries stay verbatim; dead links drop; `(count)` headings refresh.

## Unreleased — lint: `--include-llm` removed (#72)

`llmwiki lint --include-llm` is gone. The flag never called an LLM (no callback was wired; the three stub rules never invoked one). Scripts that pass it will fail with `unrecognized arguments: --include-llm` — drop the flag.

`contradiction_detection`, `claim_verification`, and `summary_accuracy` now always run with the other structural rules. `contradiction_detection` no longer flags filler `## Contradictions` sections (`None identified.`, `n/a`, and similar synthesis boilerplate).

Python callers of `run_all(..., include_llm=…, llm_callback=…)` still work — those kwargs are ignored.

## v1.5.0 — Analytics layout + CallMcpTool migration

After upgrading the engine, rebuild the vault site so Analytics picks up the new section order and heatmaps:

```bash
llmwiki build --vault /path/to/vault
# or, when vault.default_path is already configured:
llmwiki build
```

`build` also one-shot backfills `synth.pipeline` in `llmwiki-state.json` / `llmwiki-state.js` when that key is missing (state last written by v1.4.0). That fills the Home **State** widget without a separate `synthesize --estimate`. The refresh is local-only (no API / no tokens) and runs only on a shape mismatch — later builds skip it once the snapshot exists. Sync / add / estimate still refresh the snapshot when content changes.

**Optional:** expand `CallMcpTool` entries in already-synced `raw/sessions/*.md` when the originating agent session file still exists:

```bash
llmwiki migrate-tools-used --vault /path/to/vault --dry-run
llmwiki migrate-tools-used --vault /path/to/vault
llmwiki build --vault /path/to/vault
```

When the origin store is gone (TTL / deleted sessions), rows are skipped safely — the migrator never invents MCP tool names. Prefer this over `sync --force` for the same TTL reasons as other raw rewrites: agent transcripts are usually retained only ~30 days, so force re-convert often has nothing left to read.

See [`reference/state-persistence.md`](reference/state-persistence.md) for how usage logs, rollup, daily series, and state file relate.

## v1.5.0 — index cwd restore + encoded-path redaction (#56)

**For AI agents maintaining a user's vault:** after the user upgrades `llm-wiki` (pull / `pip install -U` / brew), fix **their** vault — not the llm-wiki git clone. The engine change alone does not rewrite `site/` or `raw/`.

### Required: rebuild the site

```bash
llmwiki build --vault /path/to/their/vault
# or, if vault.default_path is already set in that checkout's config.json:
llmwiki build
```

That regenerates `site/projects/index.html` and `site/sessions/index.html` with restored local cwds (and a **Cwd** column on the sessions table).

**If you skip the rebuild** (engine updated, old `site/` left as-is):

| Symptom | Why |
|---|---|
| `projects/index.html` still mixes `/Users/USER/…` (or `/home/USER/…`) with real paths | Stale HTML from before restore/autodetect fixes |
| Session detail shows a usable `cd … && claude --resume …`, but the sessions index does not | Index never restored paths until #56; old build has no Cwd column |
| Descriptions on the sessions table still contain `…/USER/…` | Same — restore runs at **build** time |
| Grep checks from #56 stay non-zero (`grep -c '/Users/USER/' site/sessions/index.html`) | Expected until rebuild |

Nothing in `raw/` or `wiki/` is harmed by skipping rebuild; only the browsable site stays wrong / inconsistent with session heroes.

### Optional: deterministic raw/ redaction rewrite (no LLM)

#56 also teaches convert to rewrite dash-encoded agent-store segments
(`~/.claude/projects/-Users-<name>-…` → `-Users-USER-…`). **New** syncs do that automatically.

Existing `raw/sessions/*.md` are immutable during normal sync. For a vault that stays private and local, leaving old `raw/` alone is fine — site restore already shows usable local cwds after rebuild.

When the user intends to **publish or share `raw/`** (or otherwise wants the `USER` placeholder complete in every path shape already on disk), run the **deterministic** migrator — it rewrites path strings in place, does **not** call the LLM, does **not** enqueue `synthesize`, and does **not** touch `wiki/`:

```bash
# preview
llmwiki migrate-raw-redaction --vault /path/to/their/vault --dry-run
# or: python3 scripts/migrate_raw_encoded_username.py --vault … --dry-run

llmwiki migrate-raw-redaction --vault /path/to/their/vault
llmwiki build --vault /path/to/their/vault
```

**Do not** use `llmwiki sync --force` / re-convert from `~/.claude/projects/` or Cursor session folders for this:

- Agent stores usually retain transcripts only ~**30 days** (Claude Code retention; Cursor similar). Older sessions in `raw/` often have **no** source file left to re-convert from — force-sync silently skips or fails those rows while still looking like “migration work”.
- Force-sync is the wrong tool anyway: agents may follow it with `synthesize` / queue digest and **burn LLM tokens** rewriting wiki pages that did not need to change. The path-string rewrite above is enough.

**If you skip the raw migrator** (normal for private vaults):

- Day-to-day browsing and resume: **unaffected** after rebuild.
- Old `raw/` rows that already contain `-Users-<real-username>-…` next to a redacted `/Users/USER/…` prefix keep that incomplete masking until `migrate-raw-redaction` (or a future sync of still-present sources). That is a redaction-contract gap for publish/share workflows, not data escaping a private vault.

### Config note

If root `config.json` copied the examples placeholder `"redaction": { "real_username": "" }`, #56 re-autodetects after overlay so restore works again. No manual config edit required unless the user intentionally disabled username redaction.

## Downgrading is guarded (#29)

Pointing an **older** checkout at a vault a **newer** engine wrote used to silently reconvert everything under the old slug scheme, duplicating `raw/`. As of #29, `sync` refuses to run when the vault's `llmwiki-state.json` was written by a newer `meta.schema_version`, or is present but unreadable:

```
error: <vault>/llmwiki-state.json: state file was written by a newer llmwiki
(schema_version=2 > 1). Upgrade llmwiki, or pass --force-resync to reconvert
from scratch ...
```

The fix is to **upgrade the engine** to match the vault. Only pass `sync --force-resync` if you genuinely want a full reconvert from scratch (it implies `--force` and may duplicate an already-populated `raw/`). This guard protects the newer→older direction; the older engine that lacks it still can't see the unified file, so keep engines at or ahead of the version that last wrote the vault.

### Moving an in-clone wiki into a vault (pre-v1.5.0 checkouts only)

#29 shipped in **v1.5.0**, so a fresh install is vault-first and nothing here applies to it. If you ran a pre-release checkout that kept `raw/` and `wiki/` inside the git clone and you are now setting `vault.default_path`, move the content by hand — there is no migration command, and two trees holding the same wiki drift silently:

```bash
llmwiki init --vault /path/to/vault          # scaffold + seed the vault
cp -r raw/ wiki/ /path/to/vault/             # move your content across
llmwiki sync --vault /path/to/vault --no-auto-build   # reconcile index after copy
llmwiki lint --vault /path/to/vault --rules index_sync
```

Two things to do explicitly, because neither is obvious:

- **Delete the demo entries from the copied `index.md`.** The clone's `wiki/index.md` catalogs the repo's demo pages (`entities/Anthropic.md`, `concepts/CachePricing.md`, `projects/demo-*.md`). Copied into a vault that has none of them, every one becomes a dead index link. `llmwiki sync --no-auto-build` reconciles the catalog for you — that is the reason to run it right after the copy.
- **Remove the leftover ignored pages from the clone.** `raw/` and `wiki/` are gitignored, so anything left behind is invisible to `git status` but still real on disk. A command run without a vault (or from a script with a different config) writes there, and you end up with pages that exist in only one of the two trees.

## v1.4.0 — unified queue + vault state (hard cutover)

**Requires Python ≥ 3.12.**

**One-time migration required** if your vault still has legacy dotfiles:

```bash
python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault/llmwiki-state.json
# or:
llmwiki migrate-state --state-file /path/to/vault/llmwiki-state.json
# optional cleanup after verifying:
# rm -rf /path/to/vault/.llmwiki-state.json ...
```

### What changed

| Before | After |
|---|---|
| `.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-pending-prompts/` | `<vault>/llmwiki-state.json` (+ `llmwiki-state.js` sidecar) |
| `LLMWIKI_ROOT` env var | `vault.default_path` in `config.json` |
| SessionStart auto-sync hook | Manual `llmwiki queue run` |
| `synthesis.backend: agent_delegate` | Removed — use `dummy`, `ollama`, or `claude` |
| external `wiki_tasks` queue ownership | `llmwiki queue enqueue` into vault state |
| Python 3.9–3.11 | **Python ≥ 3.12** |
| `llmwiki add` synthesized whole backlog | `add` synthesizes **only** the docs it just wrote |

### New commands

```bash
llmwiki queue status
llmwiki queue enqueue --task-type add_doc --source https://example.com
llmwiki queue run --limit 20
```

Rebuild the site after upgrading so the Home page loads `llmwiki-state.js` from `site/` (build copies the vault sidecar into the site tree).

### State path isolation (v1.4.0+)

The active state file is **process-scoped**: `llmwiki` CLI entry points call `configure_state_file` once from `--vault` / `--state-file` / `config.json` `vault.default_path`. Library code and tests must pass an explicit `state_file=` override or rely on that configured path — there are no import-time vault bindings.

If `llmwiki-state.json` looks truncated (e.g. only a handful of `synth.files` keys after a test run), re-run the migration against your vault:

```bash
PYTHONPATH=/path/to/llm-wiki python3 scripts/migrate_state_v1_4_0.py \
  --state-file /path/to/vault/llmwiki-state.json
```

Legacy dotfiles (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, …) are merged in; verify `sync.files` / `synth.files` counts before deleting them.

### Re-run `migrate-state` to repair dead `synth_request` items (#23)

Vaults migrated with the first v1.4.0 migrator carry queue items with `task_type: "synth_request"`. The queue runner has no handler for that type, so `llmwiki queue run` marks every one of them `status: error`. Re-run the migration — it purges them, and enqueues a single `synthesize` task if (and only if) real backlog remains:

```bash
llmwiki migrate-state --state-file /path/to/vault/llmwiki-state.json
llmwiki queue run --vault /path/to/vault
```

The migration resolves each legacy `.llmwiki-pending-prompts/<uuid>.md` against the pending sentinel pages left in `wiki/sources/`, so it is safe to `rm -rf .llmwiki-pending-prompts/` afterwards — the prompts themselves are never needed again.

### Check `synthesis.backend` before syncing (#23)

`agent`, `agent-delegate`, and `agent_delegate` were **removed** in v1.4.0. `resolve_backend()` reads them as a typo and silently falls back to `dummy`, which writes stub pages (`Auto-synthesized from session`) into `wiki/sources/`. `migrate-state` prints a `WARNING:` when your `config.json` still names one — set `synthesis.backend` to `claude`, `ollama`, or `dummy`, then re-synthesize:

```bash
llmwiki synth --vault /path/to/vault
```

Stub pages left behind by the dummy backend count as **unsynthesized** backlog (#24): `llmwiki queue status` reports them under `unsynth_total`, `llmwiki lint` flags them with the `stub_source_pages` rule, and `llmwiki synth` refills them with a real backend.

## v1.3.83+ — unified queue preview (superseded by v1.4.0)

Same migration as v1.4.0; use `scripts/migrate_state_v1_4_0.py`.

## v1.3.0 — consolidated 1.2.x patch roll-up

**Released: 2026-04-26.**

### Summary

Drop-in upgrade from any 1.2.x. v1.3.0 consolidates 38 in-tree patch versions (1.2.1 → 1.2.38) under one minor release tag — no breaking API changes, no schema migrations, no config changes.

```bash
pip install -U llm-notebook   # → 1.3.0
llmwiki --version             # → 1.3.0
```

### What's in it

The full per-fix detail is preserved under the [1.2.x] entries in `CHANGELOG.md`. Two themes:

1. **Opus 4.7 deep code-review backlog (#403, ~26 issues)** — every correctness, perf, and observability finding got a one-issue-one-PR fix. Headliners: `is_subagent` strict path check (#406), `derive_session_slug` UUID-prefix collision (#424), tilde-fence counting in `_close_open_fence` (#419), `wiki_query` ranking length normalisation (#418), `wiki_search` cap (#413), per-vault synth state (#420), `--force` sync persisting `_meta`/`_counters` (#426), subprocess `claude_path` resolved via `shutil.which` (#421).

2. **Performance + features** — `DuplicateDetection` lint rule rewritten with bucket+fingerprint+SequenceMatcher (1s vs minutes on 500 pages, #412), perf-budget test suite (`-m slow`, #429), `md_to_plain_text` cache (#417), auto-seeded project stubs pre-populated from session metadata (#425), 2 new lint rules (`frontmatter_count_consistency`, `tools_consistency`, #378), `wiki-all` slash command, `_context.md` folder convention (#60).

### Breaking — none

Same CLI surface, same config schema, same on-disk state format. The only thing that changed is that the next plain `sync` after a forced re-sync will now correctly identify already-processed files as unchanged (was: re-processed every time, #426).

### Schema migrations — none

State files written by 1.2.x are read verbatim by 1.3.0.

## v1.2.0 — first stable on the 1.x line

**Released: 2026-04-25.**

### Install changes

- **PyPI distribution name is `llm-notebook`** — the `llmwiki` name was taken on PyPI. The Python module + CLI command stay `llmwiki`, only the `pip install` line changes:
  ```bash
  pip install llm-notebook        # was: pip install llmwiki
  llmwiki --version               # → 1.2.0  (CLI name unchanged)
  python3 -c "import llmwiki"     # still works (import name unchanged)
  ```

### Removed CLI subcommands

The CLI was slimmed in #362. If you scripted any of these, replace as noted:

- `llmwiki schedule` — removed. Schedule `llmwiki sync` directly via your OS's job runner (launchd / systemd / Task Scheduler).
- `llmwiki install-skills` — removed. Manually copy `.claude/commands/wiki-*.md` into `~/.claude/commands/` for global availability.
- `llmwiki check-links` — removed. Use the GitHub Actions link-check workflow instead.
- `llmwiki watch`, `llmwiki manifest`, `llmwiki link-obsidian`, `llmwiki export-obsidian`, `llmwiki export-marp`, `llmwiki export-qmd`, `llmwiki eval` — also removed. (`llmwiki eval` was never a live CLI — structural scoring never shipped; use `llmwiki lint` for wiki quality.)
- `llmwiki export marp` is the new path for Marp slide export.

### Removed adapters

`jira_adapter`, `meeting`, `pdf` were removed in #363. If you depended on any of them, pin v1.1.0-rc8 until you migrate.

### Demo data correctness

`user_messages` / `tool_calls` counts on the 8 demo session files were 2–10× higher than the body actually contained. The values are now recomputed from body content. Two new lint rules (`#16 frontmatter_count_consistency`, `#17 tools_consistency`) prevent regression.

### `sync --force` no longer drops colliding sessions

If you ran `sync --force` against a corpus where two sources had the same canonical filename (rare but real on large corpora), one of them was silently overwritten. Fix: per-run filename tracking now disambiguates regardless of `--force`. Affected ~200 of 495 sessions on a real corpus we tested.

### New: `llmwiki all`

One-shot pipeline runner for CI:

```bash
llmwiki all                  # build → graph → lint
llmwiki all --strict         # exit 2 on any lint warning
```

### Schema migrations

None. JSON sibling files now correctly emit `int` and `bool` types for `user_messages` / `tool_calls` / `is_subagent` (were strings); any downstream that string-compared `is_subagent == "false"` now needs `is_subagent is False`.

## v1.1.0-rc5

**Released: 2026-04-21.**

### New behaviour

- **Session transcripts strip project-local file refs.** Anchors pointing at `tasks.md`, `user_profile.md`, `settings.gradle.kts`, `.kiro/…`, `/Users/…`, etc. are unwrapped into inline `<span class="session-ref dead-link">` — the filename stays visible but the anchor doesn't 404. No action required.

- **`README.md` and `CONTRIBUTING.md` now compile as site pages.** `site/README.html` and `site/CONTRIBUTING.html` ship alongside `changelog.html`. Link rewriter routes to the compiled page instead of GitHub for these two files.

- **`/wiki-synthesize` slash command** — wraps `llmwiki synthesize` with natural-language flags ("estimate cost", "dry run", "force"). Copy `.claude/commands/wiki-synthesize.md` into `~/.claude/commands/` for global availability. (`llmwiki install-skills` was removed in v1.2.0; manual copy is the supported path.)

- **Dual-mode docs landing pages.** `docs/modes/api/` and `docs/modes/agent/` exist as skeletons; the actual API / Agent backends ship with #315 / #316.

### Schema migrations

None. Fully backwards-compatible with rc4 state files.

### Breaking

None.

## v1.1.0-rc4

**Released: 2026-04-20.**

### New behaviour

- **Obsidian is opt-in now.** Past versions fired the Obsidian adapter on every `sync` by default. If your workflow relied on that, add this to `sessions_config.json`:

  ```json
  { "obsidian": { "enabled": true } }
  ```

  Context: [#326](https://github.com/Pratiyush/llm-wiki/issues/326). Runs as of rc3; surfaced in `llmwiki adapters` column `will_fire`.

- **Graph clicks respect compiled-site existence.** Nodes whose corresponding page wasn't rendered to HTML show a tooltip instead of opening a 404. No action needed — if you see the tooltip on entity / concept / nav pages that's the new design.

- **Backlinks now propagate.** Run `llmwiki backlinks` once to inject managed `## Referenced by` sections into every linked-to page. Idempotent, dry-runnable, prune-able:

  ```bash
  llmwiki backlinks --dry-run --verbose   # preview
  llmwiki backlinks                       # commit writes
  llmwiki backlinks --prune               # strip every block
  ```

### Schema migrations

- `.llmwiki-state.json` keys rewrite from absolute paths to `<adapter>::<home-relative-path>` on first load under rc3+. Migration is automatic and idempotent. If you moved your repo to a new machine, old state will be preserved verbatim — re-sync to reindex.

- `.llmwiki-quarantine.json` is a new local file (gitignored). First appears when a convert error happens. Inspect with `llmwiki quarantine list`.

- Frontmatter `tags:` / `topics:` convention is lint-enforced (rule
  #14 `tags_topics_convention`) — projects use `topics:`, everything
  else uses `tags:`. Run `llmwiki tag convention` to see violations. `llmwiki tag rename <old> <new>` rewrites across every page.

### Breaking — none

No breaking CLI or config changes. Every test pre-upgrade keeps passing post-upgrade.

## v1.1.0-rc3

See the [release notes](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.1.0-rc3) for the full rc3 gap-sweep bundle. No migration required.

## v1.0.0 → v1.1.0-rc1

Config: `synthesis.backend` now accepts `"ollama"` in addition to the default `"dummy"`. See `docs/reference/prompt-caching.md` for the ollama setup.

`wiki/candidates/` directory is new — created automatically by ingest when it sees a brand-new entity/concept. Triage with `/wiki-candidates` (renamed from `/wiki-review` in rc3).

## Older versions

Pre-v1.0 milestones shipped under internal sprint tags. Upgrade from v0.9.x to v1.0.0 in one step — no intermediate migration required. If you're on a pre-0.9 build, start fresh: `llmwiki init` in a new tree and re-run `sync`.
