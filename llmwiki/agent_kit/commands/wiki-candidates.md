Review and triage candidate wiki pages — promote, flip and promote, merge, or discard.

Candidate pages live under `wiki/candidates/<kind>/<slug>.md`. They are usually created by `llmwiki synth` (default harvest after sources) or `llmwiki synth --candidates-only`. They are **not** part of the trusted wiki layer until a human or agent approves them. Harvest is offline (no classify LLM call).

Home **Candidates** (Knowledge layer) and Analytics **Candidates to review** show the backlog after `llmwiki build`. Open `site/candidates.html` (header: Home → Raw → **Candidates** …) to read what is pending: it lists every stub and prints the `llmwiki candidates apply --vault <vault> --actions -` command plus a ready-made JSON batch to pipe into it.

Usage: `/wiki-candidates`

## Workflow

1. List all pending candidates:
   ```
   python3 -m llmwiki candidates list
   ```
   Or filter to stale (age > 30 days):
   ```
   python3 -m llmwiki candidates list --stale
   ```

2. For each candidate, decide:

   - **promote** — candidate is legitimate and not a duplicate.
     Moves it into the trusted tree (`wiki/entities/` or `wiki/concepts/`)
     and rewrites `status: candidate` → `status: reviewed`. Also reconciles `wiki/index.md` (drops dead Candidates bullets; lists the trusted page).
     When `## Key Facts` is empty (or heading-only), promote fills it offline from nested `fact:` bullets on the cited source pages (and from harvest stubs). Non-empty reviewer Key Facts are preserved. Works with Dummy / no backend — no language model required for promote.
     ```
     python3 -m llmwiki candidates promote --slug MyEntity
     ```

   - **flip-promote** — kind was wrong (entity↔concept). Promotes into the opposite trusted folder and rewrites `type:`. Do **not** hand-`mv` stubs between `candidates/entities` and `candidates/concepts`.
     ```
     python3 -m llmwiki candidates flip-promote --slug Misfiled
     ```

   - **merge** — candidate is essentially a duplicate of another name in the same kind.
     Target may be a trusted page or another pending stub in the same table. Unions the candidate's evidence (`sources:` frontmatter + Connections links) into the target and records the merged-away name under `## Aliases`, then archives the candidate. Inbound `[[merged-away]]` links resolve to the survivor via that section (graph, lint, backlinks, references). Reconciles `wiki/index.md`. A candidate carrying reviewer prose also gets that prose appended under `## Candidate merge — <date>`.
     ```
     python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
     ```

   - **discard** — candidate is a hallucination or noise.
     Moves it to `wiki/archive/candidates/<timestamp>/` with a
     `.reason.txt` audit-trail file. Reconciles `wiki/index.md`.
     ```
     python3 -m llmwiki candidates discard --slug BogusEntity \
       --reason "not a real company; LLM hallucinated"
     ```

   - **apply** — batch several intents in one process (same JSON as `site/candidates.html` prints):
     ```
     python3 -m llmwiki candidates apply --actions '[{"action":"promote","slug":"MyEntity","kind":"entities"}]'
     ```

3. Prefer these CLI actions (same library as `/candidates.html`). Do **not** run idle `sync`/`synth` only to refresh the catalog after review — promote/merge/discard/apply already reconcile `index.md`. `candidates apply` rebuilds `site/` after a successful batch so reload `candidates.html`; pass `--no-rebuild` to skip. After one-off `promote` / `merge` / `discard`, run `llmwiki build` (those actions do not rebuild) and `/wiki-lint` to catch broken wikilinks.
   Trusted pages that still have clipped regex Key Facts (or pasted harvest-stub `## Candidate merge` blocks) can be rewritten with the opt-in LLM path:
   ```
   python3 -m llmwiki candidates rewrite-key-facts --slug MyEntity
   ```
   or `--all` for the whole knowledge layer (costs one LLM call per page). Promote itself does not need that.

4. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] review | <N> promoted, <M> merged, <K> discarded
   ```

## Related

- #51 — approval workflow; #84 — Home/Analytics observability; #90 — harvest; #97 — `candidates.html` pending listing + copyable `apply --actions` batch; #101 — promote/merge/discard/apply reconcile index.md; #103 / #147 — promote fills empty Key Facts from source `fact:` bullets (offline)
- `/wiki-lint` — finds stale candidates (age > 30 days) and broken wikilinks after review
- `llmwiki synth` / `synth --candidates-only` — harvest stubs from synthesized sources (offline)
- `/wiki-ingest` — optional enrichment / review discussion over candidates
