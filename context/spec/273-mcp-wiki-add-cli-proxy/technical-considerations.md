# Technical Specification: MCP Add as CLI Add Proxy (Text / Pipe Input)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Extract the CLI `add` post-conversion orchestration (pipeline lock, optional synthesize, build, `wiki/log.md`, queue/state tracking, `refresh_synth_pending`) into a single in-process entry point that both `cmd_add` and MCP `wiki_add` call. Extend `add_doc` with a text/stdin conversion path that records provenance as `piped` (no temp file as source of record). MCP becomes a thin parameter adapter onto that shared entry point.

**Default behavior (CLI and MCP) — product flip vs historical CLI:**

| Step | Default | Opt-in / opt-out |
|---|---|---|
| Write raw doc(s) | always (unless dry-run / error) | — |
| Synthesize | **off** | CLI `--synthesize` / MCP `synthesize: true` |
| Rebuild site | **on** | CLI `--no-build` / MCP `no_build: true` |

Long-document chunking remains exclusively in `add_doc` (`DEFAULT_CHUNK_MAX_CHARS = 7000`). Transport: **in-process shared orchestration**, not an OS subprocess.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Shared add orchestration

| Piece | Responsibility |
|---|---|
| New callable (proposed name `run_add` / `add_pipeline`) | Own the body currently in `_cmd_add_locked`: call `add_sources` → optional synth (existing rollback rules, only when synthesize requested) → optional build → log lines → `refresh_synth_pending` → queue/state row updates |
| `llmwiki/cli.py` `cmd_add` / `_cmd_add_locked` | Parse argparse; acquire `pipeline_lock` (unless dry-run); delegate to shared callable; print human-facing progress |
| `llmwiki/mcp/server.py` `tool_wiki_add` | Validate args; map MCP fields → shared callable kwargs; return structured `{written, titles, warnings}` (surface failures consistent with CLI exit semantics) |

**Assumptions:**

- Module home: prefer `llmwiki/add_doc.py` (or thin `llmwiki/add_pipeline.py` if needed) — no new runtime deps.
- Queue worker `_handle_add_doc` stays raw-only unless this ticket must touch it for DRY — **out of scope** by default.

### 2.2 CLI / MCP flag flip

| Historical CLI | New CLI | New MCP |
|---|---|---|
| Synthesize on by default; `--no-synthesize` to skip | Synthesize **off** by default; `--synthesize` to run | `synthesize` default `false`; set `true` to run |
| Build on by default; `--no-build` to skip | Unchanged | `no_build` default `false` |

- Remove or deprecate `--no-synthesize` as the primary control: prefer `--synthesize` for clarity. Migration: keep `--no-synthesize` as a no-op / hidden alias that warns once (“synthesis is already off by default”) **or** reject with a pointer to the new default — prefer **warn + no-op** for one release so existing scripts that pass `--no-synthesize` do not break; scripts that relied on default synth must add `--synthesize`.
- Document the behavior change prominently in CHANGELOG and CLI/MCP help.

### 2.3 Text / pipe conversion and provenance

| Piece | Change |
|---|---|
| `ConvertedDoc.source_label` | Allow literal `"piped"` for stdin/text adds |
| New helper (e.g. `convert_text`) | In-memory markdown/text → `ConvertedDoc` with `source_label="piped"` |
| `add_sources` | Accept sentinel `"-"` and/or explicit text so callers need not write `/tmp` |
| Frontmatter | `source:` continues to serialize `doc.source_label` |
| Path / URL | Unchanged provenance |

CLI stdin: `llmwiki add -` reads `sys.stdin` in the process locale encoding (not forced UTF-8). Mixing `-` with other sources in one invocation: **reject**. `--title` recommended; else derive from first heading / body start.

### 2.4 MCP tool contract

| Argument | Required | Notes |
|---|---|---|
| Exactly one of `url`, `path`, `content` | yes | Unchanged |
| `title`, `project`, `tags`, `note` | no | Unchanged |
| `synthesize` | no | Default `false` — mirrors `--synthesize` |
| `no_build` | no | Default `false` — mirrors `--no-build` |

- Default: raw write + site build; no synthesis.
- `content` → shared text path (`source: "piped"`); **remove** tempfile branch.
- Same vault/`REPO_ROOT` resolution and pipeline lock as CLI.

Tool description: proxy-to-CLI-add; default raw+build; opt-in synthesize; opt-out build; multi-chunk via add (~7k); source-layer guardrail.

### 2.5 Docs and agent kit

| Path | Update |
|---|---|
| `docs/reference/cli.md` | New defaults; `--synthesize`; `add -` / `piped`; deprecation note for `--no-synthesize` |
| `docs/reference/mcp.md` | Same defaults; `synthesize` / `no_build`; content → piped |
| `llmwiki/agent_kit/skills/llmwiki-ingest/SKILL.md` (+ `wiki-ingest` command if needed) | Proxy model; default no synth; guardrail |
| `CHANGELOG.md` | **Breaking/behavior change:** default `add` no longer synthesizes |

### 2.6 Logic notes

- Chunking: existing `add_doc` only.
- When synthesize is off: always `refresh_synth_pending` so later `synth` sees the new docs.
- When synthesize is on: keep existing rollback-if-no-wiki-page behavior.
- Site build on by default so Home/raw visibility updates without waiting for synth.

---

## 3. Impact and Risk Analysis

### System Dependencies

- Synthesis backends only when `--synthesize` / `synthesize: true`.
- `pipeline_lock`, vault resolution, `build_site` — same as today.
- Callers/scripts/docs that assumed “add always synthesizes” must opt in.

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Breaking change for operators who expected synth-on-add | CHANGELOG + help text; `--synthesize`; update demo/docs/skills; grep repo for `--no-synthesize` / “add then synth” assumptions |
| Scripts already passing `--no-synthesize` | Warn + no-op alias for one release |
| Agents that expected MCP raw-only without build | Default now builds; they pass `no_build: true` if needed — document clearly |
| Stdin `-` vs file named `-` | Sentinel-only; reject mix with other sources |
| Temp-file provenance regression | Delete tempfile path; assert `source: "piped"` |

---

## 4. Testing Strategy

- **Unit:** `convert_text` / `-` → `source: "piped"`; long body → multiple chunks, shared piped provenance.
- **CLI default:** add without `--synthesize` → raw files + site build artifacts updated; **no** new `wiki/sources/` pages for those docs; pending refreshed.
- **CLI opt-in:** `--synthesize` → wiki source pages (dummy backend harness).
- **CLI `--no-build`:** raw written, site not rebuilt by that run.
- **MCP parity:** same matrix via `synthesize` / `no_build`; `content` never temp provenance.
- **Regression:** update tests that assumed default synth-on-add; path/URL provenance unchanged.
- **Docs:** reference + ingest skill match new defaults.

No new runtime dependencies. No schema migrations.

## Amendments (local-review keep)

Status remains **Approved**. Post-implement local-review keep decisions:

- **`build_site`:** do not fail solely because `discover_sources(raw/sessions)` is empty; proceed when `raw/docs/` has ≥1 markdown file; still require `raw/sessions/` to exist.
- **`run_add`:** optional `writer: Callable[[str], None] | None`; accumulate `messages: list[str]`; record `build_failed` distinctly from add/synth failure; `exit_code` non-zero when either fails (CLI); MCP maps build-only failure → `_ok` + warning.
- **MCP timeouts:** shared config `mcp.tool_timeouts.<tool>` (defaults 120) for `wiki_add` and `wiki_sync`.

