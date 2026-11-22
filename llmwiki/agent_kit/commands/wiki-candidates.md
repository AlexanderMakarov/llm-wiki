Review and triage candidate wiki pages — promote, flip and promote, merge, or discard — and review possible duplicate live pages.

Candidate pages live under `wiki/candidates/<kind>/<slug>.md`. They are usually created by `llmwiki synth` (default harvest after sources) or `llmwiki synth --candidates-only`. They are **not** part of the trusted wiki layer until a human or agent approves them. Harvest is offline (no classify LLM call).

Separately, `llmwiki candidates list` and `site/candidates.html` also list **Possible duplicate pages**: live entity/concept/project pages that vocabulary folding treats as the same topic (#365). Those are not harvest stubs — decide **merge-pages** (fold one live page into the other) or **keep-distinct** (durable; the pair stops resurfacing). Doctor (`candidates.duplicate_pairs`) and lint (`duplicate_page_pairs`) surface the pending count the same way overdue stubs are flagged.

Home **Candidates** (Knowledge layer) and Analytics **Candidates to review** show the stub backlog after `llmwiki build`. Open `site/candidates.html` (header: Home → Raw → **Candidates** …) to read what is pending: it lists every stub **and** possible duplicate pairs, and prints the `llmwiki candidates apply --vault <vault> --actions -` command plus a ready-made JSON batch to pipe into it.

Usage: `/wiki-candidates`

## Workflow

1. List all pending candidates **and** possible duplicate pages:
   ```
   python3 -m llmwiki candidates list
   ```
   Or filter stubs to stale (age > 30 days):
   ```
   python3 -m llmwiki candidates list --stale
   ```
   JSON includes a `duplicate_pairs` array alongside the stub list.

2. For each **candidate stub**, decide:

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
     Moves it to `wiki/archive/candidates/<timestamp>/` and records the reason in `wiki/archive/candidates/dismissals.json` (new discards do not write a sibling `.reason.txt`). Turns every `[[link]]` to the name into plain text. When the name really means an existing page, add `--redirect <page>`: links become `[[page|text]]` and the name is recorded under that page's `## Aliases`. Near-matches of earlier dismissals show on `candidates list` / `candidates.html` with a **Prior dismissals** list and optional *Discard with prior reason*. Reconciles `wiki/index.md`.
     ```
     python3 -m llmwiki candidates discard --slug BogusEntity \
       --reason "not a real company; LLM hallucinated"
     python3 -m llmwiki candidates discard --slug "Old Name" \
       --reason "duplicate of ExistingPage" --redirect ExistingPage
     ```

3. For each **possible duplicate page pair** (live pages, not stubs), decide:

   - **merge-pages** — fold one live page into the other (survivor keeps its kind; works across entity/concept/project). Applied only via `candidates apply --actions` (same JSON `site/candidates.html` prints).
   - **keep-distinct** — record the pair in `wiki/archive/candidates/dismissals.json` so detection and consolidation stop treating them as one topic.
   - Leave undecided — the pair stays on the next list / lint / doctor report.

4. **apply** — batch stub intents and/or duplicate-page decisions in one process (same JSON as `site/candidates.html` prints):
   ```
   python3 -m llmwiki candidates apply --actions '[{"action":"promote","slug":"MyEntity","kind":"entities"}]'
   python3 -m llmwiki candidates apply --actions '[{"action":"merge-pages","from":"Foo","into":"Bar"},{"action":"keep-distinct","a":"Alpha","b":"Beta"}]'
   ```

5. Prefer these CLI actions (same library as `/candidates.html`). Do **not** run idle `sync`/`synth` only to refresh the catalog after review — promote/merge/discard/apply already reconcile `index.md`. `candidates apply` rebuilds `site/` after a successful batch so reload `candidates.html`; pass `--no-rebuild` to skip. After one-off `promote` / `merge` / `discard`, run `llmwiki build` (those actions do not rebuild) and `/wiki-lint` to catch broken wikilinks.
   Trusted pages that still have clipped regex Key Facts (or pasted harvest-stub `## Candidate merge` blocks) can be rewritten with the opt-in LLM path:
   ```
   python3 -m llmwiki candidates rewrite-key-facts --slug MyEntity
   ```
   or `--all` for the whole knowledge layer (costs one LLM call per page). Promote itself does not need that.

6. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] review | <N> promoted, <M> merged, <K> discarded
   ```

## Related

- #51 — approval workflow; #84 — Home/Analytics observability; #90 — harvest; #97 — `candidates.html` pending listing + copyable `apply --actions` batch; #101 — promote/merge/discard/apply reconcile index.md; #103 / #147 — promote fills empty Key Facts from source `fact:` bullets (offline); #365 — Possible duplicate pages (merge-pages / keep-distinct)
- `/wiki-lint` — finds stale candidates (age > 30 days), pending `duplicate_page_pairs`, and broken wikilinks after review
- `llmwiki doctor` — `candidates.review_pending` (overdue stubs) and `candidates.duplicate_pairs` (pending live-page pairs)
- `llmwiki synth` / `synth --candidates-only` — harvest stubs from synthesized sources (offline)
- `/wiki-ingest` — optional enrichment / review discussion over candidates
