# `llmwiki add` — universal document intake CLI (issue #16)

**Date:** 2026-07-04
**Issue:** [AlexanderMakarov/llm-wiki#16](https://github.com/AlexanderMakarov/llm-wiki/issues/16)
**Companion:** [AlexanderMakarov/kbbuilder#7](https://github.com/AlexanderMakarov/kbbuilder/issues/7) (slug convergence)

## Problem

There is no synchronous, local way to add an arbitrary document (URL, file, folder) to the
wiki. kbbuilder's `wiki-add` flow is asynchronous, queue-based, and needs the
kbbuilder/tailnet infrastructure. The wiki should gain a first-class `llmwiki add` that
converts a source to Markdown, lands it under `raw/docs/`, and synthesizes + rebuilds the
site immediately — with zero kbbuilder participation, while staying byte-compatible with
what kbbuilder produces so a laptop running both never sees double work or format drift.

## Decisions (locked with the user)

1. **Post-add default = synthesize + build.** Multiple sources may be added in one
   invocation; conversion/writing happens per source, then ONE synthesis pass and ONE site
   build for the whole batch. `--no-synthesize` and `--no-build` opt out.
2. **Layout matches kbbuilder exactly**: `raw/docs/<slug>/<slug>.md`, chunked to
   `raw/docs/<slug>/<slug>-NN.md` when large. Chunking is **section-aware** (splits on
   `#`/`##` heading boundaries, fence-aware, paragraph-packing for oversized sections;
   the ~7000-char cap is soft, never a hard slice). Docs must explain the rationale:
   each chunk becomes one synthesis input that fits the model context — avoiding
   context-overflow / overload failures on large documents.
3. **Input scope v1**: URL, local file (`.md` pass-through, PDF/docx/etc. via optional
   converter, other text fenced), and folder (walk textual files into one doc).
4. **No pullmd dependency.** Pure-python layering instead; trafilatura (pullmd's own base
   extraction library) is the optional quality upgrade.

## CLI surface

```
llmwiki add <source> [<source> ...]
            [--vault PATH] [--project SLUG] [--title TITLE]
            [--tag TAG]... [--note TEXT]
            [--no-synthesize] [--no-build]
            [--render | --no-render]
            [--dry-run]
```

- `<source>` — URL (`http://`/`https://`), file path, or directory path. Repeatable.
- `--vault` — same semantics as `sync`/`build`/`synthesize` (`_add_vault_arg`, role
  `"add"`), with `_apply_default_vault` fallback. kbbuilder's engine runner passes
  `--vault` to every command, so this is required for convergence.
- `--project` — override the project/directory slug (default: derived doc slug).
- `--title` — override title derivation (single-source invocations only; error with 2+).
- `--tag` — extra frontmatter tags appended after the standard `[wiki-add, raw-doc]`.
- `--note` — prepended blockquote note (kbbuilder payload `note` equivalent).
- `--render` / `--no-render` — force / forbid the headless-browser layer (see fetching).
- `--dry-run` — convert and report what would be written (paths, titles, chunk counts),
  write nothing, run nothing.
- Exit code: 0 if all sources landed; 2 if any source failed (successful ones still land
  and still get synthesized/built).
- New console script `llm-wiki-add` in `[project.scripts]` → thin wrapper that reuses the
  main parser with `add` pre-seeded (`main_add(argv) -> main(["add", *argv])`).

## URL fetching — three layers with a quality gate

All layers share one SSRF-guarded fetcher (stdlib `urllib.request`, manual redirects):

- http/https only; every hostname resolved via `socket.getaddrinfo` and every address
  checked against blocked ranges (0/8, 10/8, 127/8, 169.254/16, 172.16/12, 192.168/16,
  100.64/10 CGNAT/tailnet, multicast/reserved; IPv6: loopback/unspecified, v4-mapped,
  NAT64 64:ff9b::/96, fc00::/7, fe80::/10, ff00::/8 — port of kbbuilder's
  `isBlockedAddress`, including numeric hextet expansion).
- Redirects followed manually, ≤5 hops, each hop re-validated.
- Injectable fetch function for tests (kbbuilder's `fetchFn` pattern); an injected fetcher
  is trusted and used as-is.

**Layer 1 — markdown content negotiation (stdlib, always on).**
Request with `Accept: text/markdown, text/html;q=0.9` and an honest agent User-Agent
(`llmwiki-add/<version>`). If the response `Content-Type` is `text/markdown` — Cloudflare
"Markdown for Agents", Read the Docs, and similar — use the body verbatim; no conversion.
Report `x-markdown-tokens`/`x-original-tokens` savings when present.

**Layer 2 — static HTML extraction.**
If HTML: use `trafilatura` when importable (`extract(html, output_format="markdown",
include_links=True, include_formatting=True)`), else the built-in stdlib converter — an
`html.parser.HTMLParser` subclass with a readability-lite heuristic (prefer
`<article>`/`<main>` subtree when present; drop `script/style/nav/header/footer/aside`;
convert headings, links, lists, paragraphs, code blocks; entities via `html.unescape`).
Non-HTML text responses pass through as text.

**Quality gate.**
After layer 2, score the result: extracted text below a minimum absolute length, tiny
relative to the HTML size, or containing challenge markers ("Just a moment", "Enable
JavaScript", "Checking your browser") → treat as JS-rendered/bot-walled and escalate.

**Layer 3 — headless render (optional).**
If `playwright` is importable (already an `[e2e]` extra), re-fetch with headless Chromium,
wait for network-idle, take rendered HTML, re-run layer 2 extraction. Triggered
automatically by the quality gate, forced by `--render`, disabled by `--no-render`. The
initial URL is SSRF-validated before hand-off. Without playwright, write what layer 2 got
and print a warning that the capture may be a shell, suggesting
`pip install 'llm-notebook[e2e]' && playwright install chromium`.

**Anti-bot posture.** First request uses the honest agent headers (that is what unlocks
Cloudflare markdown negotiation). On 403 or a challenge-marker body, one retry with a
pinned realistic browser User-Agent. No UA-rotation machinery.

## File and folder conversion

- `.md`/`.markdown` — body passed through as-is.
- PDF / docx / pptx / xlsx / other binary formats `markitdown` knows — converted via
  `markitdown` when importable; otherwise a clear error naming the missing extra
  (`pip install 'llm-notebook[add]'`). PDFs have no plain-text fallback (binary).
- Other textual files — fenced as code blocks with a language tag from the extension
  (kbbuilder's `TEXTUAL_EXT` set + `fenceCode`, backtick-escaping inside).
- Folders — recursive walk (depth ≤ 6), sorted entries, skip dotfiles/`node_modules`,
  never follow symlinks, skip sensitive paths, textual files only, each file a `##`
  section — port of kbbuilder's `walkFolderToMarkdown`.
- Path safety — reject `..` segments, resolve via `Path.resolve(strict=True)`, refuse
  sensitive paths (`.env*`, `.ssh/`, `.aws/`, `.gnupg/`, `.netrc`, `id_*` keys,
  `*.pem/key/p12/pfx/keystore/jks`, `credentials*/secret*/shadow`) — port of kbbuilder's
  `SENSITIVE_PATH_PATTERNS` + `assertReadablePath` (no allowlist roots in v1: the CLI
  runs as the user who typed the path).

## Slug and title derivation — new shared module `llmwiki/slugs.py`

Fixes the kbbuilder#7 failure cases; kbbuilder later converges on this via shelling out.

Title preference order:
1. `--title` flag;
2. first `#` heading of the **converted markdown** (fence-aware);
3. HTML `<title>` (layer-2 URLs), after suffix-stripping;
4. meaningful URL path segments (skip empty/`index.html`-ish tails);
5. filename stem (files/folders);
6. host name (last resort for URLs).

Title cleanup: strip site-name suffixes (`X - Site`, `X | Site`, `X — Site` when the
suffix ≠ the content), collapse immediate repeated words case-insensitively
("OpenClaw - OpenClaw" → "OpenClaw").

Slugify (`slugify(text) -> str`):
- lowercase; NFKD-decompose and drop combining marks (é→e);
- built-in Cyrillic→Latin transliteration table (ru: а→a … я→ya) so Russian titles
  produce readable slugs instead of the `document` fallback;
- any remaining non-`[a-z0-9]` runs → `-`; trim dashes; cap at 80 chars;
- empty result → caller falls to the next title candidate (never the literal `document`
  unless every candidate is empty).
- Output alphabet is a subset of `raw_docs_site._SAFE_SEG_RE` (`^[A-Za-z0-9._-]+$`), so
  added docs are never silently invisible to the site build.

Collision handling (raw immutability): if `raw/docs/<slug>/` exists (or the target file
inside it), suffix `-2`, `-3`, … on the **doc slug** before writing. Never overwrite.

## Output format (byte-compatible with kbbuilder `makeRawDocWriter`)

`raw/docs/<project>/<slug>.md` single-chunk, `raw/docs/<project>/<slug>-NN.md` (zero-padded)
multi-chunk; `project` defaults to the doc slug. Frontmatter:

```yaml
---
title: "Doc Title"            # multi-chunk: "Doc Title (part i/N: Section)"
slug: <slug or slug-NN>
project: <project>
type: source
tags: [wiki-add, raw-doc]     # + --tag extras
date: YYYY-MM-DD
source: "<URL or absolute path>"
---
```

Multi-chunk files carry the breadcrumb blockquote (`> Part i of N of **Title** — Section.`).
Chunking port: `chunk_markdown_by_sections(text, max_chars=7000, heading_levels=(1, 2))` —
fence-aware section split, greedy packing, paragraph-split then hard-slice only for a
single oversized paragraph. 7000 chars keeps each chunk inside the agent-delegate
synthesizer's `raw_body[:8000]` embed with headroom for frontmatter + breadcrumb.

## Post-steps (batch)

After ALL sources are written:
1. **Synthesize** (unless `--no-synthesize`): call `synthesize_new_sessions(...)` in-process
   with `resolve_backend(config)`, scoped paths honoring `--vault` — same wiring as
   `cmd_synthesize`. New docs only (the state file already ensures incremental behavior).
2. **Build** (unless `--no-build`): invoke the build entry point in-process, honoring
   `--vault` — CLAUDE.md hard rule 6.
3. Append `## [YYYY-MM-DD] add | <title>` per doc to `wiki/log.md` (existing log format).
4. Failures in synthesize/build do not un-land written docs (kbbuilder's add-doc guard
   precedent): report and exit 2, docs remain for the next sync/build.

## Module layout

- `llmwiki/slugs.py` — `slugify`, `derive_title`, `strip_site_suffix`; shared, no deps.
- `llmwiki/htmlmd.py` — stdlib `HTMLParser` HTML→Markdown converter (layer-2 fallback).
- `llmwiki/add_doc.py` — SSRF guard, guarded fetch, layered URL pipeline, file/folder
  conversion, section chunker, raw-doc writer, `add_sources(...)` orchestrator.
  All I/O seams injectable (fetch fn, renderer fn, clock) for offline tests.
- `llmwiki/cli.py` — `cmd_add` + subparser + `main_add`; lazy imports per house style.
- `pyproject.toml` — `add = ["markitdown>=0.1.2", "trafilatura>=2.0.0"]` extra (NOT a
  resurrected `[pdf]` extra — that name was deliberately pruned); `llm-wiki-add` script.

## Testing (offline; TDD)

- `tests/test_slugs.py` — kbbuilder#7 cases: "OpenClaw - OpenClaw" → `openclaw`;
  "Source: External" boilerplate beaten by URL segments; Russian title → transliterated
  slug; empty → URL path fallback; suffix stripping; 80-char cap; safe alphabet.
- `tests/test_htmlmd.py` — fixture HTML → markdown (headings/links/lists/code, entity
  decoding, article-subtree preference, script/nav dropping).
- `tests/test_add_doc.py` — injectable-fetch URL adds (markdown negotiation short-circuit,
  HTML conversion, redirect revalidation, SSRF blocks, 403→browser-UA retry, quality-gate
  escalation stubbed); file adds (`.md` pass-through, text fencing, PDF-without-markitdown
  error, `tests/fixtures/pdf/sample.pdf` when markitdown installed —
  `pytest.importorskip`); folder walk (symlink/sensitive skips); chunking parity cases;
  collision suffix `-2`; frontmatter exactness vs a golden file; multi-source batch =
  one synthesize call (DummySynthesizer spy) + one build call.
- `tests/test_cli.py` addition — `python -m llmwiki add --dry-run <fixture.md>` smoke.
- README CLI-reference block gains `add` (enforced by `test_cli_doc_parity.py`).
- No network, no LLM, no playwright in tests (renderer injected as a stub).

## Docs

- README: `add` in CLI reference + a short "Adding documents" section (layers, extras).
- `docs/architecture.md`: mention `add_doc.py` intake path.
- CHANGELOG entry.
- Explain dir-per-doc + section chunking rationale (context limits) where the layout is
  documented.
- Comment on kbbuilder#7 linking to `llmwiki/slugs.py` once merged (convergence step).

## Out of scope (v1)

- stdin `content` source (kbbuilder classify parity) — trivial follow-up if wanted.
- kbbuilder actually shelling out to `llmwiki add` — kbbuilder-side change, separate PR.
- UA rotation feeds, OCR, YouTube/Reddit special-casing (pullmd territory).
- Quarantine-file integration for failed adds — stderr + exit code is enough for a
  synchronous CLI; the user is present.
