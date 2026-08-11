---
title: "Slash commands reference (part 3/4: /wiki-build)"
slug: slash-commands-reference-03
project: slash-commands-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/slash-commands.md"
content_sha256: b914ad5a59ba24c268c483ba5ec07399a0c9cbe9939abfcc4d7a50b7216c9763
---

> Part 3 of 4 of **Slash commands reference** — /wiki-build.

### `/wiki-build`

**What:** regenerate the static HTML site.

**Wraps:** `python3 -m llmwiki build`.

**When to use:** after manual edits to `wiki/`, or when you want to see
a fresh site without running the full sync pipeline.

**Example:**

```
/wiki-build
/wiki-build to ~/public_html
/wiki-build in tree search mode
```

---

### `/wiki-serve`

**What:** start a local HTTP server for the built site.

**Wraps:** `python3 -m llmwiki serve`.

**Example:**

```
/wiki-serve
/wiki-serve on port 9000
```

The server is local-only (`127.0.0.1`) by default. Say "on my LAN" and
Claude will pass `--host 0.0.0.0`.

---

### `/wiki-export-marp`

**What:** generate a Marp slide deck from wiki pages matching a topic.

**Wraps:** `python3 -m llmwiki export-marp --topic …`.

**Example:**

```
/wiki-export-marp topic "cache tiers"
/wiki-export-marp topic Karpathy save to ~/slides/karpathy.marp.md
```

---

### `/wiki-all`

**What:** run the full pipeline end-to-end — optional sync/synth → build → graph → lint. AI-consumable exports (`llms.txt`, `sitemap.xml`, etc.) are written by `build`, not a separate step.

**Wraps:** `python3 -m llmwiki all`.

**When to use:** after `/wiki-sync`, when you want a CI-ready site in one shot
instead of chaining `/wiki-build` + `/wiki-graph` + `/wiki-lint` yourself.

**Example:**

```
/wiki-all
/wiki-all --with-sync --with-synth
/wiki-all --graph-engine builtin
/wiki-all --skip-graph --strict
```

Pass `--strict` to turn any lint warning into a non-zero exit, which is
exactly what CI wants. Pass `--skip-graph` or `--graph-engine builtin`
when the optional Graphify backend is not installed. Pass `--with-sync` or
`--with-synth` when you want session conversion or synthesis folded into
the same run.

---
