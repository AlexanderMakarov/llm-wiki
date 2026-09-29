---
title: "Upgrade guide (part 2/8: Unreleased — source pages filed under a stale name (#265))"
slug: upgrade-guide-02
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 2 of 8 of **Upgrade guide** — Unreleased — source pages filed under a stale name (#265).

## Unreleased — source pages filed under a stale name (#265)

Optional offline migration, recommended when `synth` keeps skipping sources. After upgrade:

- **Symptom:** every `synth` run reports `skipped N source(s) already claimed by a real page under another name` (older releases printed one `real source page already claims this source` line per source), and `synth --estimate` / Home keep counting those sources as pending. The pages were filed under a name an earlier release derived — a generic session description shared by many sessions, or the whole raw filename after the date — while synth now derives `<date>-<slug>` for them.
- **Number-shaped slugs:** a raw `slug:` that looks like a number (`0123`, `68657849`, `12e4`) now keeps its written text in the page name instead of falling back to the raw filename, which produced a doubled date (`<date>-<date>T<hh-mm>-<project>-<slug>`). Existing pages under that doubled name are moved by the same migration.
- **Fix:** run `llmwiki migrate source-page-paths --vault <vault> --dry-run`, check the planned moves, collisions and ambiguous links, then run it without `--dry-run`. It moves each real page to its derived path (a doc's `--part-NN` pages move together), rewrites `[[old-stem]]` links and `sources:` entries across `wiki/` (`wiki/archive/` and the log are left alone), and records synth state so the next `synth` treats the source as done. Zero LLM, `raw/` never written; a second run changes nothing.
- **Left for you:** a real page already at the derived path is reported as a collision and both pages stay put; a bare `[[old-stem]]` that more than one page answers to follows the one candidate that links back to the referring page; with no such candidate, or several, it is reported as ambiguous and not rewritten (the report says how many of those will break). Rebuild afterwards: `llmwiki build --vault <vault>`.

```bash
llmwiki migrate source-page-paths --vault /path/to/vault --dry-run
llmwiki migrate source-page-paths --vault /path/to/vault
```

## Unreleased — Findability by page title (#259)

No required migration. After upgrade:

- **Title is the findability key:** `llmwiki search`, MCP `wiki_search`, and the `page_findability` lint rule judge findability by each page's frontmatter **title**, not by slug/filename or bare link text. Slug/filename stays filesystem and `[[wikilink]]` resolution metainfo (`link_integrity` still covers broken links).
- **R2 removed:** `page_findability` no longer searches for raw wikilink anchor strings (e.g. hub pages that list many `[[session-slug]]` sources no longer fail findability solely because the slug string is not a search hit). Title-not-found / ranked-past-cap errors are unchanged.
- **Prefer `[[slug|Title]]`:** visible link text should show the page title while the slug keeps resolution stable. Bare `[[slug]]` links that resolve correctly are not findability failures.
- **Optional cosmetic migrate:** when you want display text to match titles across existing wiki pages, run offline `llmwiki migrate wikilink-titles --vault <vault> [--dry-run]` — reads titles already on disk under `wiki/`, rewrites resolving bare `[[slug]]` to `[[slug|Title]]`, zero LLM, `raw/` never written. Not required for lint green. Fenced/example `[[slug]]` tokens are rewritten the same as prose — skim `--dry-run` changed pages before apply. Rebuild after apply if you want HTML to show the new display text: `llmwiki build --vault <vault>`.
- **Re-run after #262:** if an earlier `wikilink-titles` pass left case/punctuation variants bare (e.g. `[[LLM-Wiki]]` while the page is `llm-wiki`), run the migrate again — those uniquely fold to a page under shared `norm_page_key` (same fold as `link_integrity` / harvest) and rewrite to `[[canonical-slug|Title]]`. True aliases and ambiguous collisions stay skipped.

```bash
llmwiki migrate wikilink-titles --vault /path/to/vault --dry-run
llmwiki migrate wikilink-titles --vault /path/to/vault
```

## Unreleased — private vaults keep real home paths (#253)

Behaviour flip, no required migration. `sync` (and `llmwiki add` `source:` paths) no longer rewrite the home-path username to `USER` by default: new key `redaction.redact_username` defaults to `false`. API key, token, and email redaction is unchanged and still always runs.

- **Mixed vault after upgrade:** files synced before the upgrade keep `/Users/USER/…` / `-Users-USER-…`; new files carry real paths. The site restores cwd either way.
- **Restore real paths in old files:** `llmwiki migrate raw-unredaction --vault PATH --dry-run`, then without `--dry-run`, then `llmwiki build --vault PATH`. It touches only home-path and dash-encoded positions, never a bare `USER` word, and is idempotent.
- **Warning — repositories that commit `raw/`:** a vault synced by the composite Action (`action.yml`) or the reusable workflow (`.github/workflows/llmwiki-action.yml`) runs `llmwiki sync` inside the repository checkout, so real home paths land in committed files. Such repositories must set `"redact_username": true` under `redaction` in `config.json`. This matters most on self-hosted runners, whose home directory belongs to a real account.
- **You share `raw/` or publish the site:** set `"redact_username": true` under `redaction` in `config.json` before the next sync, and run `llmwiki migrate raw-redaction --vault PATH` for files synced after the upgrade.

## Unreleased — Session `description:` assigned names + scored fallback (#249)

No migration. After upgrade, optional refresh of existing raw sessions:

- **Assigned names win:** when an adapter exposes a session title, that becomes `description:` (redacted). Claude Code: `customTitle` then `aiTitle`. Cursor CLI: store meta `name`, except the placeholder `New Agent` (treated as absent). Other adapters: none yet — ChatGPT already sets a conversation title on its own convert path.
- **Scored fallback:** without an assigned name, convert ranks real user prompts (type bands → position → length 0..120) and picks the top. Punctuation-only turns are out. Cursor XML chrome is normalized off the description path so scores are not dominated by `<user_info>` wrappers.
- **Refresh:** `llmwiki sync --force` then `llmwiki build` rewrites `raw/sessions/` and the site. No wiki synth required — `description:` is convert-time frontmatter only.

| Adapter | Assigned-name source |
|---|---|
| `claude_code` | `customTitle` + `aiTitle` |
| `cursor_cli` | store meta `name` (not `New Agent`) |
| others | none yet (ChatGPT uses conversation title on its own path) |
