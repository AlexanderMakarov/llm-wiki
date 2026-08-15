Update a single wiki page in place without running a full re-ingest.

Usage: /wiki-update <page-path> [reason]

`$ARGUMENTS` is the path to one wiki page — typically under `wiki/sources/`, `wiki/entities/`, or `wiki/concepts/`.

Use this when:

- The source under `raw/` changed and only one wiki page needs updating
- You spotted a stale claim or broken wikilink and want to patch just that page
- You need to update `last_updated` after a content edit
- A new contradiction surfaced that should be added under `## Contradictions`

**Do NOT** use this for bulk changes — that's what `/wiki-ingest` and `/wiki-sync` are for.

Steps:

1. **Read the target page** using the Read tool.
2. **Read `wiki/index.md`** to understand how this page is referenced elsewhere.
3. **Read the source(s)** listed in the frontmatter's `sources:` field.
4. **Compute the delta** — what needs to change on the page? Typically one of:
   - A fact or claim is now stale
   - A wikilink is broken
   - A contradiction needs recording
   - `last_updated` needs bumping
   - A new cross-reference should be added under `## Connections`
5. **Edit the page** with minimal targeted changes. Use the Edit tool, not Write — this is a surgical update, not a rewrite.
6. **Update `last_updated`** in the frontmatter to today's date.
7. **If you added/removed wikilinks**, check whether backlinks on OTHER pages need updating. Report these to the user; don't update them automatically without permission.
8. **Append to `wiki/log.md`**:
   ```
   ## [YYYY-MM-DD] update | <page-name> — <reason>
   ```

Hard rules (per `.kiro/steering/page-format.md`):

- **Never overwrite contradictions.** If new information conflicts with old, add a `## Contradictions` section, don't delete the old claim.
- **Keep the frontmatter schema intact.** `title`, `type`, `tags`, `sources`, `last_updated` stay.
- **Don't mass-rewrite.** If you find yourself wanting to rewrite more than 30% of the page, stop and run `/wiki-ingest` against the underlying source instead.

After the update, summarize to the user: which page was changed, what the delta was, whether any other pages need follow-up updates, and the log entry you added.
