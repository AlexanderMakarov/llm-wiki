<!--
Architectural HOW — not a copy-paste implementation guide.
-->

# Technical Specification: Trace wiki pages back to raw transcripts

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** AWOS `/implement-feature` (issue #122)

---

## 1. High-Level Technical Approach

Add a shared provenance walker in `llmwiki/trace.py` that resolves a vault-relative wiki page into an ordered downward hop list: starting page → `sources:` slugs → `wiki/sources/*` pages → each page’s `source_file:` → vault `raw/` path (with optional built-site href). Wire that walker into:

1. CLI `llmwiki trace`
2. Lint rule `provenance_integrity` (severity `error`)
3. Static-site renderers for topic + session/document pages (Sources entries become links)

No new MCP tool. Guided repair of broken hops remains on `#110` (`doctor`); lint only reports.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

- New module `llmwiki/trace.py` — pure library (no argparse / MCP). Single public entrypoints, e.g. `trace_page(vault: Path, locator: str) -> TraceResult` and helpers used by lint/build to resolve one hop or list Sources link targets.
- No new runtime dependencies (stdlib + existing `markdown` only).
- Reuse (do not fork) slug → source page resolution from `llmwiki/candidates.py` (`_parse_sources_field`, `_resolve_source_page`) — promote to non-underscore shared helpers or import carefully from one place if export is cleaner.
- Site URL / existence: reuse `graph._compute_site_url` / `_verify_site_url` patterns for “prefer HTML”; raw fallback uses vault-relative raw path and/or copied `site/sources/…` markdown when that is what the session page already exposes.

### Data Model

No on-disk schema change. Inputs are existing frontmatter:

| Field | On | Meaning |
| --- | --- | --- |
| `sources:` | entity / concept / project / other wiki pages | list of source-summary slugs |
| `source_file:` | wiki source pages | pointer into `raw/` |

In-memory hop shape (conceptual):

| Field | Meaning |
| --- | --- |
| `role` | `page` \| `source` \| `raw` |
| `title` | display title |
| `location` | vault-relative path or unresolved slug |
| `status` | `ok` \| `missing` |
| `site_href` | optional site-relative URL when HTML (or raw site copy) exists |

### API / CLI Contracts

**CLI**

```text
llmwiki trace <page> [--vault PATH]
```

- `<page>`: vault-relative path (`wiki/entities/Foo.md`) or resolvable name/slug.
- Exit `0` on successful walk (including partial missing hops).
- Exit non-zero when the starting page cannot be resolved at all.
- stdout: human-readable chain (titles + locations + missing markers); no body excerpts.
- Document under `docs/reference/cli.md` (`## trace`) — required by reference-coverage CI.

**MCP**

- Unchanged tool set. Docs/CHANGELOG note that true link-following is `llmwiki trace`; `wiki_search`/`include_raw` remains term search.

**Lint**

- New rule id: `provenance_integrity`
- File: `llmwiki/lint/rules/provenance_integrity.py` + import in `rules/__init__.py`
- Severity: `error` per broken hop
- Scope: every loaded wiki page with `sources:` and/or `source_file:`
- Walk: for each `sources:` slug → must resolve under `wiki/sources/`; for each source page (or current page if it has `source_file:`) → raw path must exist under vault
- Message text names page + missing target; docs mention healer belongs to `doctor` (#110)
- Register in tests that assert rule count/names; add Rules row in `docs/reference/cli.md`

### Component Breakdown

| Component | Responsibility |
| --- | --- |
| `llmwiki/trace.py` | Resolve locator; walk hops; mark missing; optional site_href |
| `llmwiki/cli.py` `cmd_trace` | Argparse + print + exit codes |
| `llmwiki/lint/rules/provenance_integrity.py` | Emit lint issues via walker |
| `llmwiki/topics_page.py` | Render Sources as links on topic HTML |
| `llmwiki/build.py` `render_session` (+ document renderer) | Render Sources / wiki-summary links; raw fallback `target="_blank"` `rel="noopener"` |
| Docs / CHANGELOG / `context/` | CONTRIBUTING-required surfaces |

### Logic / Algorithm

1. Resolve starting page under `vault/wiki` (path first; else slug/title scan consistent with existing helpers).
2. Emit hop for starting page.
3. Parse `sources:`; for each slug resolve file; `ok` or `missing`; recurse into each found source page’s `source_file:`.
4. If starting page itself has `source_file:`, emit raw hop.
5. For site links: if `site_href` for that hop exists and file would be emitted/present → use it; else if raw exists → href to raw site copy or safe serve path, label “(raw)”, `target=_blank`.
6. Never invent `entities/*.html` / `concepts/*.html` URLs (`site_url` is intentionally `None` there — topics remain the browse surface).

### Configuration

- No new config keys. Vault root from existing `--vault` / `config.json` / `_content_root`.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** frontmatter parsers; candidates source resolution; graph site_url helpers; lint registry; build topic/session/document render paths; reference-coverage + lint-rule registration tests.
- **Upgrade impact:** vaults with stale `sources:` / `source_file:` will newly see **lint errors**. Document in UPGRADING/CHANGELOG; point heal to #110 — do not auto-prune in this change.
- **Path safety:** raw and site href resolution must stay inside the vault (reuse existing safe-path patterns from MCP/build).
- **Mitigations:** unit-test missing hops; HTML tests assert `target="_blank"` only on raw fallback; no new deps.

---

## 4. Testing Strategy

- Unit: `tests/test_trace.py` — full chain, missing source slug, missing raw, page with no provenance, path traversal rejected.
- CLI: invoke `cmd_trace` / parser with tmp vault.
- Lint: in-memory pages + tmp vault cases; registry name/count bump; severity `error`.
- Build/HTML: topic + session fixtures assert Sources `<a href=…>`; HTML preference; raw fallback has `(raw)` (or equivalent label) and `target="_blank"`.
- Docs: `tests/test_reference_coverage.py` greenn for `## trace`; Rules list includes `provenance_integrity`.
