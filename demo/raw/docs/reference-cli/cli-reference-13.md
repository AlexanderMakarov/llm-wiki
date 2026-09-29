---
title: "CLI reference (part 13/19: broken-provenance — remap or clear hops to missing raw sessions)"
slug: cli-reference-13
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/cli.md"
content_sha256: 80394a36c35bb48cc2c8a5640d51d9180b601f9274c4cb944e18a4be261b1dbc
---

> Part 13 of 19 of **CLI reference** — broken-provenance — remap or clear hops to missing raw sessions.

1. Finds every real (non-stub) source page whose `source_file:` names an existing `raw/sessions/` or `raw/docs/` file and whose path differs from the derived one. A doc's `--part-NN` pages move as one group, keeping their part suffixes.
2. Moves each page to its derived path with body and frontmatter intact. `title` changes only while it still reads `Session: <old name> — <date>` (the converter's title for the old name); it then becomes the raw file's current title.
3. Rewrites `[[old-stem]]`, `[[old-stem|label]]` and `[[old-stem#anchor]]` links across `wiki/`, and the stem in frontmatter `sources:` lists. A label changes only when it equals the old title. When more than one page answers to a bare stem, the link (or `sources:` entry) in page P follows the one source page with that stem whose body links back to P (matched with the same case/punctuation fold as `link_integrity`); if that back-linker stays put the link is left as it is, and with no back-linker, several, or a back-linker whose new name would itself be ambiguous, the link is reported as ambiguous and left alone — the report counts links disambiguated by backlink, links still ambiguous, and those that will break because every page of that name moves; a path-qualified link (`[[sources/<project>/<stem>]]`, `[[<project>/<stem>]]`) is rewritten when its path matches exactly one page. `wiki/archive/` and the log are never edited.
4. Records synth state (`synth.files` in `<vault>/llmwiki-state.json`, the raw file's mtime) for each moved source, and for a real page already at its derived path, when the source has no state entry yet. An existing entry is kept as it is — one older than the raw file means the raw was re-converted after synthesis, and synth still has to see that page as stale. Moves are applied first; a move that fails to write or to leave its old path is undone, reported, and dropped together with its link rewrites and state entry. Then refreshes the Home pending count, rebuilds `wiki/index.md` when the vault keeps one, and appends a `migrate | source page paths` entry to `wiki/log.md`.
5. Reports a collision — and changes nothing for that source — when a real page already sits at the derived path. A stub at the derived path for the same source is replaced.

Implementation: `llmwiki/migrate_source_page_paths.py`. `raw/` is never written. Rebuild the site afterwards: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate source-page-paths --vault /path/to/vault --dry-run
python3 -m llmwiki migrate source-page-paths --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/` and `raw/`. |
| `--dry-run` | Print planned moves, collisions, link rewrites, ambiguous links and state upserts; write nothing. |

Idempotent: a second run finds nothing to move and prints `nothing to migrate: every source page sits at its derived path`.

### `broken-provenance` — remap or clear hops to missing raw sessions

After a Cursor Agent CLI re-sync that used the filesystem stem `store` as `sessionId`, force-convert can leave wiki pages pointing at deleted `raw/sessions/…` paths while newer raw files exist under the same project slug (`cursor-<hash>`). This offline migration walks wiki pages that carry `source_file:` / `sources:` provenance and, when a hop targets a missing `raw/sessions/` file:

1. Parses the project slug from the missing path (for example `cursor-<hash>`).
2. Finds existing raw files whose names contain that project slug.
3. Restricts candidates to the **same calendar day** (`YYYY-MM-DD` prefix). Never remaps across days (that used to point every June stub at a single January session).
4. Remaps only among same-day **interactive** raw files: explicit `is_headless: false`, or legacy unmarked (no `is_headless` field — same eligibility rule as synth). When several remain, remaps to the uniquely closest HH-MM in that shortlist.
5. Otherwise clears the broken `source_file` (same-day headless-only pools, ambiguous closest-time ties, or no same-day interactive candidate) and drops matching `sources:` list aliases. Wiki pages themselves are never deleted. Never remaps to a row that is explicitly `is_headless: true`.

Implementation: `llmwiki/migrate_broken_provenance.py`. Preview with `--dry-run`. Prefer a Cursor Agent CLI re-sync first so raw filenames carry real chat dates and `is_headless` is stamped; unmarked legacy same-day files remain remap-eligible until then.

```bash
python3 -m llmwiki migrate broken-provenance --vault /path/to/vault --dry-run
python3 -m llmwiki migrate broken-provenance --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/` and `raw/`. |
| `--dry-run` | Report what would change; write nothing. |

The report prints `remapped` / `cleared` / `unresolved` counts. Idempotent once hops are healed or cleared.

---
