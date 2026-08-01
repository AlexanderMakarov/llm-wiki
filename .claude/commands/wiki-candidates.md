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
     and rewrites `status: candidate` → `status: reviewed`.
     ```
     python3 -m llmwiki candidates promote --slug MyEntity
     ```

   - **merge** — candidate is essentially a duplicate of an existing page.
     Appends the candidate's body under a `## Candidate merge — <date>`
     heading in the target page, then archives the candidate.
     ```
     python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
     ```

   - **discard** — candidate is a hallucination or noise.
     Moves it to `wiki/archive/candidates/<timestamp>/` with a
     `.reason.txt` audit-trail file.
     ```
     python3 -m llmwiki candidates discard --slug BogusEntity \
       --reason "not a real company; LLM hallucinated"
     ```

3. After any promote/merge, run `/wiki-lint` to catch broken wikilinks
   from pages that used to point at the candidate location.

4. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] review | <N> promoted, <M> merged, <K> discarded
   ```

## Related

- #51 — approval workflow; #84 — Home/Analytics observability; #90 — harvest produce side
- `/wiki-lint` — finds stale candidates (age > 30 days) automatically
- `llmwiki synthesize --candidates-only` — harvest stubs from synthesized sources
- `/wiki-ingest` — optional enrichment / review discussion over candidates
