---
title: "Slash commands reference (part 3/4: /wiki-build)"
slug: slash-commands-reference-03
project: reference-slash-commands
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/slash-commands.md"
content_sha256: 89c2c1c8024aaf4a27741adc0fc10604afbc26da69181caedf1c1317103081ac
---

> Part 3 of 4 of **Slash commands reference** — /wiki-build.

**No CLI wrapper** — it's a model-orchestrated workflow that reads the
index + overview + sample of pages and outputs suggestions.

**Example:**

```
/wiki-reflect
```

Use sparingly; it's the most token-heavy command.

---

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

### `/wiki-all`

**What:** run the full pipeline end-to-end — sync → synth → build → graph → lint. Every stage runs unless you opt out of it. AI-consumable exports (`llms.txt`, `sitemap.xml`, etc.) are written by `build`, not a separate step.

**Wraps:** `python3 -m llmwiki all`.

**When to use:** after `/wiki-sync`, when you want a CI-ready site in one shot
instead of chaining `/wiki-build` + `/wiki-graph` + `/wiki-lint` yourself.

**Example:**

```
/wiki-all
/wiki-all --no-synth
/wiki-all --graph-engine builtin
/wiki-all --skip-graph --strict
```

Pass `--strict` to turn any lint warning into a non-zero exit, which is exactly what CI wants. Pass `--skip-graph` or `--graph-engine builtin` when the optional Graphify backend is not installed. Pass `--no-sync` or `--no-synth` to leave session conversion or synthesis out of the run — `--no-synth` is the one that keeps the run away from your AI provider.

---
