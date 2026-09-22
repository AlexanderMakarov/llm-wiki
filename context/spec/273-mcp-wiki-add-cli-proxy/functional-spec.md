# Functional Specification: MCP Add as CLI Add Proxy (Text / Pipe Input)

- **Roadmap Item:** GitHub issue #273 — MCP wiki_add matches CLI add; shared text/pipe input; explicit provenance; no MCP-local chunking
- **Status:** Approved
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

Operators and agents should add documents through one path. The MCP **Add** action is a proxy for the CLI **add** command: same defaults, same optional controls for synthesize and site build, same conversion and long-document splitting. Pasted or piped text is a first-class CLI input (origin recorded as something like “piped”), not a disposable temp-file path. MCP supplies that text through the same text/pipe input path rather than inventing its own file-based shortcut.

**Default add behavior (CLI and MCP):** land the raw document and rebuild the browsable site so the new material is visible — **do not** synthesize wiki source pages unless the operator explicitly asks. Synthesis remains available as an opt-in for the same add invocation.

Success means:

- MCP Add with no extra flags behaves like CLI `add`: raw document(s) written, site rebuilt, no synthesis unless requested
- Optional controls can skip the site rebuild and/or turn synthesis on, matching between CLI and MCP
- Long documents split only inside CLI add
- Piped/pasted text never records a `/tmp/…` origin; path and URL keep the exact named source
- Agent instructions still forbid silently reconstructing input from wiki pages

## 2. Functional Requirements (The "What")

- **As an** operator, **I want** MCP Add to be a proxy for CLI add, **so that** outcomes match for the same source and flags.
  - **Acceptance Criteria:**
    - Given the same path, URL, or text and the same synthesize/build choices, when I add via MCP or CLI, then raw files, synthesis, and site build outcomes match.
    - Given MCP Add or CLI add with no extra flags, when it completes successfully, then raw document file(s) exist, the site has been rebuilt to include them, and **no** new synthesized wiki source pages were produced by that add.
    - Given add with synthesis explicitly enabled, when it completes successfully, then synthesized wiki pages for the new raw docs are produced (same rules as today’s synthesize-after-add path).
    - Given add with site rebuild skipped, when it completes, then raw docs are written and the site is not rebuilt by that invocation; when synthesis was also off, bookkeeping for later synthesis matches the existing raw-only pending behavior.

- **As an** operator, **I want** long documents split only by CLI add, **so that** MCP never has its own chunking rules.
  - **Acceptance Criteria:**
    - Given a source longer than the usual chunk size (~7,000 characters), when Add runs (CLI or MCP proxy), then multiple raw pieces come from CLI add logic only.
    - Given MCP Add, when inspecting the implementation path, then MCP does not implement a separate splitter.

- **As an** operator, **I want** CLI add to accept piped or pasted text without writing a temp source file, **so that** origin stays meaningful.
  - **Acceptance Criteria:**
    - Given text on stdin (or equivalent text input) to CLI add, when raw files are written, then they succeed and the recorded origin identifies piped/pasted input (e.g. “piped”), not a `/tmp/…` path.
    - Given a path or URL, when raw files are written, then the recorded origin is that exact path or URL.
    - Given MCP content, when Add runs, then it feeds text into the CLI add path by the shared text/pipe interface, not by relying on a temp file as the recorded source.

- **As an** agent author, **I want** tool help and ingest instructions to describe the proxy model, defaults, text/pipe input, chunking-via-add, and the source-layer guardrail, **so that** agents use the user’s named source.
  - **Acceptance Criteria:**
    - Given the MCP Add description, when an agent reads it, then it states: same as CLI add by default (raw add + site rebuild, **no** synthesis unless requested); optional skip of rebuild / opt-in synthesis; long docs may become multiple raw pieces via add; use exact path/URL/text — do not reconstruct from wiki pages unless the user asked.

## 3. Scope and Boundaries

### In-Scope

- CLI `add` text/stdin (pipe) support with “piped”-style provenance (no temp file as source of record)
- MCP Add as proxy to CLI add (**default: raw + site rebuild; synthesis opt-in**)
- Flip of CLI/MCP default so synthesis is off unless requested (site rebuild remains on by default)
- Provenance for path, URL, and piped/pasted text
- Shared bookkeeping when synthesis is skipped (pending for later synth)
- Tool description + ingest skill / agent instruction updates
- Tests covering long input, provenance, default vs opt-in synthesize / skip-build, and MCP/CLI parity

### Out-of-Scope

- MCP-local conversion or chunking
- Changing the ~7,000-character chunk size policy itself
- New MCP tools unrelated to Add
- Closing the GitHub issue from this flow
- Unrelated roadmap items

## Amendments (local-review keep)

Status remains **Approved**. Post-implement local-review keep decisions:

- **Build gate:** site build must succeed on a docs-only vault (empty `raw/sessions/` that still exists, non-empty `raw/docs/`); fail only when both sessions and docs are empty.
- **MCP vs CLI on build failure:** when the doc landed and only the post-add site build failed, MCP `wiki_add` returns success with a warning; CLI may still exit non-zero.
- **Stdin encoding:** document stdin as process locale encoding (not forced UTF-8); leave `sys.stdin.read()` as-is.
- **MCP timeouts:** `mcp.tool_timeouts.wiki_add` / `wiki_sync` (default 120s each).

