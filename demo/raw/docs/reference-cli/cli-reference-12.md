---
title: "CLI reference (part 12/19: source-page-paths — move source pages filed under a stale name)"
slug: cli-reference-12
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/cli.md"
content_sha256: 80394a36c35bb48cc2c8a5640d51d9180b601f9274c4cb944e18a4be261b1dbc
---

> Part 12 of 19 of **CLI reference** — source-page-paths — move source pages filed under a stale name.

Since #282 `candidates discard` rewrites the links to the name it archives. Candidates discarded before that still have `[[links]]` pointing into `wiki/archive/`, which `link_integrity` reports. This offline migration finds every archived candidate that no live page answers to (by stem or `## Aliases` — merged and redirected names are left alone) and turns each `[[Name]]`, `[[name|label]]` or `[[Name#section]]` outside `wiki/archive/` into plain text: the label when the link has one, otherwise the name as written. `--redirect NAME=PAGE` (repeatable) points that name's links at an existing live page instead (`[[PAGE|text]]`) and records the name under the page's `## Aliases`, exactly like `candidates discard --redirect`. It also moves candidate stubs a `/` in their name filed into a subfolder to the flat path harvest now writes (`A/B thing` → `candidates/<kind>/A-B thing.md`), reporting a conflict instead of overwriting an existing file. No language model, no network call, `raw/` never written.

Implementation: `llmwiki/migrate_discarded_topic_links.py`. Rebuild the site afterwards: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate discarded-topic-links --vault /path/to/vault --dry-run
python3 -m llmwiki migrate discarded-topic-links --vault /path/to/vault --redirect "Old Name=ExistingPage"
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/`. |
| `--dry-run` | Report what would change; write nothing. |
| `--redirect NAME=PAGE` | Point links to discarded `NAME` at existing `PAGE` (and record the alias) instead of unlinking them. Repeatable. |
| `--force` | Unlink a name whose `reason.txt` records a merge even when no live page answers to it, instead of reporting a suggested `--redirect`. |

Every `--redirect` pair is checked before the first write: a name with no archived candidate, or a `PAGE` that is missing or ambiguous, stops the run with nothing written (`nothing was written: fix the errors above and re-run`) and exit code 1. A pair whose name a live page already answers to — including a re-run of the same command, once the alias exists — needs no redirect and is listed under `skipped:` rather than dropped. Pages the run could not read are listed under `errors:` and exit code 1, with the changes that did apply printed above them, so a vault with one unreadable page never reports success while links to a discarded name are left behind.

**Merged names are guarded.** A candidate a reviewer *merged* is archived with `Reason: merged into <target>`, and its links belong on the survivor page. The survivor normally answers to the merged-away name through its `## Aliases` entry, so the migration never touches those links. When the survivor was later renamed or re-filed — or when the merge predates the alias entry entirely — nothing but that reason file still ties the name to a page, and flattening its links to plain text would throw the target away. Such a name keeps its links, is listed under `merged, left linked:` with the page the run believes it means, and the run exits 1 so a script notices:

```text
merged, left linked: 1
  - Old Name — merged into foo (587 links)
      --redirect "Old Name=code-foo"
  a reviewer merged these names into a page that no longer answers to them, so their links were left as they are: re-run with the --redirect lines above, or --force to unlink them like a dismissal
```

Re-run with the suggested `--redirect` lines to point the links at the survivor (which then records the alias, so a third run reports nothing), or pass `--force` to unlink them like any other dismissal. The suggestion is the live page answering to the recorded target, else the single live page whose `norm_page_key` contains or is contained by it; when nothing matches, the report asks for a page (`--redirect "Old Name=<page>"`). Everything else in the same run — the flatten, plain dismissals, explicit redirects — still applies, and `--dry-run` prints the same partition.

A recorded merge with no links anywhere in the wiki needs no `--redirect`: it is left out of `merged, left linked:` entirely and never makes the run exit 1 on its own — there is nothing for an operator to preserve or flatten.

Idempotent: a second run finds nothing to rewrite and prints `nothing to migrate: no links to discarded candidates and no nested stubs`.

### `source-page-paths` — move source pages filed under a stale name

A real `wiki/sources/` page is tied to its raw file by `source_file:`. When its filename differs from the one synth derives for that raw file today (`<date>-<slug>` under `wiki/sources/<project>/`), synth's duplicate guard skips the source on every run — reported as one `skipped N source(s) already claimed by a real page under another name` line — and `synth --estimate` / Home keep counting it as pending. Earlier naming schemes (a session description shared by many sessions, the whole raw filename after the date, a number-shaped slug that fell back to the raw filename) left such pages behind.

This offline migration, with no language model and no network call:
