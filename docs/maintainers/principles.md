# Product principles

Evergreen design intentions for llmwiki. Use these when reviewing features, writing docs, or deciding whether an idea belongs in the product. Rejected alternatives live in [`DECLINED.md`](DECLINED.md).

## Cross-tool, cross-project session memory

Coding agents scatter transcripts across tools and project directories. llmwiki treats that scatter as the boundary problem: one local wiki that can ingest sessions from multiple agents and projects so memory is searchable and interlinked without living inside a single vendor chat UI.

## Cheap by default

Prefer what stays free and offline after install: stdio MCP on demand (no always-on server) so agents can search and read the vault, plain markdown files on disk, and a static HTML site for humans (pipeline state, metrics, settled entities and concepts). Do not add a vector database, hosted index, or background daemon as a default dependency of the happy path.

## Measure, then strip synthesis context

Synthesis cost is dominated by how much context you send the model. The method is: measure what the prompt actually carries, then strip or tier context that does not change the output. Document the method and trade-offs; do not publish private vault token counts or personal spend figures in the repo.

## Sessions and documents

Session sync is core. `llmwiki add` (CLI) and `wiki_add` (MCP) are the scriptable intake for a file, URL, PDF, or folder — markdown structured for LLM digest — so notes, bookmarks, and other automation can feed the same vault. Once synthesised, that material is ordinary wiki content beside session-derived pages.

## Human gate before promotion; contradictions stay visible

Harvest may propose entity and concept stubs under `wiki/candidates/`, but trusted hubs are not auto-promoted. A human (or deliberate agent review) promotes, merges, or discards. When sources disagree, keep both claims side by side under contradictions — never silently overwrite.

## Analytics as product signal

Site and vault analytics exist to show whether the wiki is used (for example retrievals-per-page as a usefulness idea), not to advertise a particular operator’s private metrics. Keep examples generic; never commit personal vault scale numbers.

## See also

- [`DECLINED.md`](DECLINED.md) — ideas we already rejected, with dates and reasons
- [`../architecture.md`](../architecture.md) — Karpathy three-layer model and build layers
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — maintainer one-pager: what can land where
