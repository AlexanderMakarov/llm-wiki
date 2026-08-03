# System Architecture Overview: llm-wiki

---

## 1. Application & Technology Stack

- **Language / runtime:** Python 3.12+ (stdlib + `markdown` only at runtime — no new runtime deps)
- **Primary interface:** CLI package (`llmwiki` / `python3 -m llmwiki`) — sync, synth, candidates, build, lint, serve, etc.
- **Human browse surface:** Generated static HTML site (`site/`) from markdown vault content
- **Agent consumer surface:** MCP server so any agent can query/search/read the wiki (consumer ≠ session-source adapter)
- **Agent authoring surface:** Skills / slash commands for ingest, synth, candidate review, and related wiki maintenance workflows
- **Non-goals for the stack:** No primary multi-tenant HTTP/API server product; no FastAPI (or similar) as a required surface

---

## 2. Data & Persistence

- **Source of truth:** Local markdown vault — `raw/` (immutable session transcripts), `wiki/` (LLM-generated / human-reviewed pages), `site/` (generated HTML; do not hand-edit)
- **Vault location:** User-configured local path (`config.json` / vault settings); coexist with tools like Obsidian is optional, not required
- **Derived artifacts:** Knowledge graph outputs (e.g. `graph/graph.json` + related HTML) from `[[wikilinks]]`; state files such as `llmwiki-state.json` and quarantine records for sync failures
- **No hosted database:** File-first design — no cloud PKM store, no required networked primary DB

---

## 3. Infrastructure & Deployment

- **Where it runs:** End-user machine (local install)
- **Distribution:** pip / uv (PyPI) and optional Homebrew; source via GitHub
- **CI / quality gate:** GitHub Actions on the repository (lint, tests, link-check hygiene as product phases land)
- **Serving the site:** Local only — `llmwiki serve` / open generated `site/`; no multi-tenant cloud host as a product requirement
- **Contributor enablement:** Cursor-compatible AWOS and related maintainer tooling support shipping product work; not an end-user runtime dependency

---

## 4. External Services & Integrations

- **Session source adapters:** Read local agent session stores (Claude Code, Cursor, Codex, and others as adapters mature); convert into immutable `raw/` markdown
- **Wiki consumption:** MCP for any agent as a knowledge consumer
- **Product backlog:** GitHub Issues (human + tooling)
- **LLM synthesis backends:** Pluggable — local **Ollama** and subscription-backed CLI paths (e.g. Claude Code `claude` backend) for synth / Key Facts and related higher-level work; core **sync / convert / build** remain usable without a cloud LLM API key
- **Future providers:** Additional local backends and cloud/gateway providers (e.g. OpenRouter-like) via the same pluggable backend contract
- **Explicit non-integrations for this architecture:** No auth/payments SaaS; no required third-party productivity-suite deep links as product requirements

---

## 5. Observability & Quality Signals

- **CLI feedback:** Process exit codes and structured/stderr messaging for operators and scripts
- **Vault operations log:** Append-only `wiki/log.md`; quarantine / failure records when sync cannot write safely
- **Repo health:** GitHub Actions as the CI signal for the product codebase
- **Guided health (roadmap):** `llmwiki doctor` (#110) — read-only environment + vault health with fix commands
- **Wiki quality loop:** First-class lint, knowledge graph, and reflect — not deferred niceties
- **Non-requirement:** No hosted APM or mandatory product-analytics SaaS
