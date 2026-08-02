Review and triage candidate wiki pages — promote, merge, or discard.

Candidate pages live under `wiki/candidates/<kind>/<slug>.md`. They are usually created by `llmwiki synthesize --candidates-only` (harvest from `wiki/sources/` wikilinks) and sometimes by `/wiki-ingest`. They are **not** part of the trusted wiki layer until a human or agent approves them.

Home **To review** and Analytics **Candidates to review** show the backlog after `llmwiki build` — that is the signal that review is waiting, not “run `/wiki-ingest` again so pages appear.”

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
     When `## Key Facts` is empty (or heading-only), promote has the configured synthesis backend write it from harvest evidence — every line where the `sources:` / Connections source pages name the subject. Non-empty reviewer Key Facts are preserved; do **not** invent a separate free-text enhance pass or hand-edit Key Facts for the common case — use the CLI so slash and library stay in sync.
     Promote **fails** (exit 2, candidate left pending) when Key Facts need writing and `synthesis.backend` is unset or `dummy`. Configure `claude` or `ollama` in `config.json` and re-run — do not work around it by writing the bullets yourself.
     ```
     python3 -m llmwiki candidates promote --slug MyEntity
     ```

   - **merge** — candidate is essentially a duplicate of an existing page.
     Unions the candidate's evidence (`sources:` frontmatter + Connections links)
     into the target page and records the merged-away name under `## Aliases`,
     then archives the candidate. Reconciles `wiki/index.md`. A candidate
     carrying reviewer prose also gets that prose appended under
     `## Candidate merge — <date>`.
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

3. Prefer these CLI actions (same library as the site will use). Do **not** run idle `sync`/`synth` only to refresh the catalog after review — promote/merge/discard already reconcile `index.md`. Do **not** hand-fill empty Key Facts on promote when the CLI already does it (#103).
   Trusted pages that still have clipped regex Key Facts (or pasted harvest-stub `## Candidate merge` blocks) are fixed with:
   ```
   python3 -m llmwiki candidates rewrite-key-facts --slug MyEntity
   ```
   or `--all` for the whole knowledge layer (costs one LLM call per page).

4. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] review | <N> promoted, <M> merged, <K> discarded
   ```

## Related

- #51 — approval workflow; #84 — Home/Analytics observability; #90 — harvest; #101 — promote/merge/discard reconcile index.md; #103 — promote fills empty Key Facts from evidence
- `/wiki-lint` — finds stale candidates (age > 30 days) and broken wikilinks after review
- `llmwiki synth --candidates-only` — harvest stubs from synthesized sources
- `/wiki-ingest` — optional enrichment / review discussion over candidates
