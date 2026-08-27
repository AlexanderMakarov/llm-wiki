<!--
Architectural HOW for #174. Not a copy-paste implementation guide.
-->

# Technical Specification: Offline migrate-topic-kinds (#174)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (approved)
- **Status:** Approved
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

Add a package-local one-time migration in the existing `migrate-*` family (same packaging reason as `migrate-page-kinds`: pip/Homebrew users have no `scripts/` checkout).

`llmwiki migrate-topic-kinds --vault PATH [--dry-run]` builds a case-folded name→kind map from `wiki/entities/`, `wiki/concepts/`, `wiki/candidates/entities/`, and `wiki/candidates/concepts/` (stem → `entity` | `concept`). Names present under both kinds are recorded as ambiguous and never stamped. It walks `wiki/sources/**/*.md`, edits only the `## Connections` section, and for each top-level topic bullet whose wikilink target is in the map and which lacks a usable `(entity|concept)` kind, inserts the kind after the link, leaving the description and nested `fact:` lines untouched. `raw/` is never written. No synthesis backend or network call is used.

After a non-dry-run that stamps at least one page, write a machine-readable stamped list at the vault root (JSON) so operators can later force-resynthesize exactly those sources. Report counters and an explicit “0 facts derived” line. Document the one-way lock-in beside the #147 UPGRADING note.

No new runtime dependencies. No change to `source_page_needs_topics_rewrite` or the #147 page shape.

---

## 2. Proposed Solution & Implementation Plan

### 2.1 Module: `llmwiki/migrate_topic_kinds.py`

Mirror the surface of `migrate_page_kinds.py`:

| Symbol | Role |
| --- | --- |
| `STAMPED_LIST_FILENAME` | Vault-root JSON name, e.g. `.llmwiki-topic-kinds-stamped.json` |
| `build_kind_map(wiki: Path) -> tuple[dict[str, str], list[str]]` | Case-folded stem → kind; second value = ambiguous names skipped |
| `stamp_connections_body(body: str, kind_map: dict[str, str], ambiguous: set[str]) -> tuple[str, dict]` | Edit Connections only; return new body + per-page counters |
| `run_migration(*, vault: Path, dry_run: bool = False) -> dict` | Orchestrate scan/write/report |
| `print_report(report: dict) -> None` | Operator-facing summary |

Kind map construction:

- Scan `*.md` under the four folders (skip `_context.md` and non-files).
- Key = filename stem case-folded; value = `entity` or `concept` from folder.
- If the same key would get both kinds → remove from map, add to ambiguous list (never guess).

Stamping:

- Locate `## Connections` with the same heading regex spirit as `synth.pipeline._CONNECTIONS_HEADING_RE` / next `##` boundary.
- For each line that is a top-level topic bullet (`- [[Name]]…`), reuse `llmwiki.wikilinks.WIKILINK_RE` + `strip_anchor` and `source_topics._split_kind_and_description` / `_normalize_kind` so “already has usable kind” matches the rewrite predicate.
- If kind already usable → leave line byte-identical.
- If name ambiguous or unknown → leave unchanged; count unresolved.
- If name in map → insert ` (entity)` or ` (concept)` immediately after the closing `]]` of the leading wikilink (before any existing non-kind remainder / description dash). Do not invent descriptions or `fact:` lines.
- Nested fact lines and other sections are untouched.

Per-page outcome: if any bullet stamped and afterward `source_page_needs_topics_rewrite(body)` is False (or was True before and False after), count as page stamped. Also count pages that remain pending rewrite after the pass (whole vault walk).

### 2.2 Stamped list (FR6) and synth-state backfill (FR8)

On successful non-dry-run with ≥1 page stamped, write vault-root JSON:

```json
{
  "version": 1,
  "command": "migrate-topic-kinds",
  "issue": 174,
  "stamped_at": "<ISO-8601 UTC>",
  "pages": [
    {
      "wiki_path": "wiki/sources/….md",
      "source_file": "raw/sessions/….md" 
    }
  ]
}
```

`source_file` comes from frontmatter when present (so `synth --force --path …` can target raw files); omit or null when missing. Dry-run must not overwrite this file as an applied migration. Re-running a real migration may replace/merge the list (prefer replace with this run’s stamped set, documented in CLI help).

**Synth state backfill (FR8):** after the stamp pass (and on re-runs that stamp nothing), upsert `llmwiki-state.json` → `synth.files` for every eligible raw session/doc whose derived wiki target(s) exist, are non-stub, and are rewrite-clear — using the same rel keys as `synthesize_new_sessions` (`<rel under raw/sessions>` / `docs::<rel>`). Shared synth filenames all get entries. Report `state entries updated`. Dry-run counts without writing.

### 2.3 CLI wiring

- `cmd_migrate_topic_kinds` in `llmwiki/cli.py` (same pattern as `cmd_migrate_page_kinds`).
- Subparser `migrate-topic-kinds` with required `--vault`; optional `--dry-run`.
- Exit `0` on success / nothing to migrate; `1` if errors list non-empty (I/O failures), matching siblings.
- Import the module in `cli.py` like `migrate_page_kinds` (package surface, not `scripts/`).

### 2.4 Docs / CHANGELOG / context

- `docs/reference/cli.md` — new `## migrate-topic-kinds` section (CI CLI coverage).
- `docs/UPGRADING.md` — under the #147 Unreleased section: cheap shape, one-way lock-in once any usable kind exists, facts still missing, point at stamped JSON + `synth --force --path`.
- `CHANGELOG.md` `[Unreleased]` + release-note bullet.
- Touch `context/` (product note or this spec dir is already the AWOS artifact) so the context CI gate is satisfied.

### 2.5 Explicit non-goals (code)

- Do not call any synth backend / HTTP client.
- Do not modify `source_page_needs_topics_rewrite`.
- Do not edit `raw/`, Key Claims, Key Quotes, or frontmatter.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** `source_topics` parser; wikilink helpers; Connections section boundaries shared with synth/harvest.
- **Risks & Mitigations:**
  - **One-way lock-in:** stamping one kind clears rewrite forever without `--force` — mitigated by report wording, UPGRADING, and stamped JSON for targeted force.
  - **Ambiguous dual pages:** skip + report; never prefer one folder.
  - **Partial Connections edits:** only insert after `]]` when kind missing; already-kinded lines must remain byte-identical (tests).
  - **Wrong section edited:** restrict to Connections span only (tests with Key Claims/Quotes unchanged).

---

## 4. Testing Strategy

New `tests/test_migrate_topic_kinds.py` (stdlib + pytest, no network):

- Stamping flips `source_page_needs_topics_rewrite` True→False when ≥1 resolvable kind is applied.
- Ambiguous entity+concept stem skipped; bullet unchanged; name in report.
- Already-kinded bullets byte-identical; Key Claims / Key Quotes untouched.
- Candidates folders supply kinds; dry-run writes nothing and does not write stamped JSON.
- Nothing-to-migrate prints the quiet line and exits 0 via parser/`cmd`.
- Assert no provider import/call path (migration module must not import synth backends).

Optional CLI smoke: `build_parser().parse_args(["migrate-topic-kinds", "--vault", …, "--dry-run"])`.
