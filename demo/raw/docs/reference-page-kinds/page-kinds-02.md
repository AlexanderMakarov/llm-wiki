---
title: "Page kinds (part 2/3: entity)"
slug: page-kinds-02
project: reference-page-kinds
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/page-kinds.md"
content_sha256: dfa6fdd3b0463588ce7292deb4bd68ac2f7b553d5e4c09a8581092aebc9a492c
---

> Part 2 of 3 of **Page kinds** — entity.

## `entity`

A person, company, product, tool, or library. Harvest writes a stub under `wiki/candidates/entities/` when enough source pages name the same target (default three), folding case/punctuation variants (`[[LLMWiki]]` / `[[llmwiki]]`) into one stub under the dominant spelling (#204). Kind, short description, and facts come from Connections topic bullets on those sources — no classify LLM call. A person then promotes it into `wiki/entities/`. The body is attributed fact bullets under `## Key Facts`; the opening description is the one harvest already recorded from the source pass.

**Demo.** [`demo/wiki/entities/Claude Code.md`](../../demo/wiki/entities/Claude Code.md) is a promoted entity. Pending harvest stubs remain under [`demo/wiki/candidates/entities/`](../../demo/wiki/candidates/entities/).

### Fields harvest writes

| Field | Provenance | What it is |
|---|---|---|
| `title` | harvest | The `[[wikilink]]` target name |
| `type` | harvest | `entity` (or `concept` — taken from the source topic bullet; a person can flip on promote) |
| `status` | harvest | `candidate` on the stub. `candidates promote` rewrites it to `reviewed` |
| `tags` | harvest | Always `[]`. A person fills tags later (`llmwiki tags add`) |
| `sources` | harvest | Slugs of the source pages that named this target — the evidence list |
| `last_updated` | harvest | UTC date of the harvest run |

Promote keeps those fields, fills an empty `## Key Facts` from source topic `fact:` bullets offline (no synthesis backend required), and does not add `confidence`, `lifecycle`, or a new `last_updated`.

### Opt-in model profile (human)

An entity with `entity_kind: ai-model` is picked up by the `/models/` index. Every field below is **human** — no synth, harvest, or build path writes them. Full schema: [Entity schema](entity-schema.md).

| Field | Provenance |
|---|---|
| `entity_kind` | human |
| `provider` | human |
| `model` | human (inline JSON: `context_window`, `max_output`, `license`, `released`) |
| `pricing` | human (inline JSON: `input_per_1m`, `output_per_1m`, `cache_read_per_1m`, `cache_write_per_1m`, `currency`, `effective`) |
| `modalities` | human |
| `benchmarks` | human |

### Conventionally absent

| Field | Why |
|---|---|
| `source_file`, `date`, `project`, `model` (session id) | Those belong on source pages. An entity points at sources through `sources:` |
| `topics` | Entities use `tags:` |
| `confidence`, `lifecycle`, `last_verified` | No producer writes them. Valid if a person adds them (`frontmatter_validity`) |
| `homepage`, `description` as project-stub fields | Those are the project-stub keys; an entity page does not get them from `ensure_project_stubs` |

---

## `concept`

An idea, framework, method, or theory. Same producer as `entity`: harvest reads a name whose source topic bullets mark it `concept` and writes `wiki/candidates/concepts/<Name>.md`. Promote moves it to `wiki/concepts/`. Flip-and-promote swaps entity ↔ concept and rewrites `type:` to match the destination folder.

**Demo.** [`demo/wiki/concepts/Adapters.md`](../../demo/wiki/concepts/Adapters.md) is a promoted concept. A pending concept stub is [`demo/wiki/candidates/concepts/Wiki Synthesis.md`](../../demo/wiki/candidates/concepts/Wiki Synthesis.md).

### Fields

The harvest table under [`entity`](#entity) applies unchanged, except `type` is `concept` and the stub lives under `candidates/concepts/`. There is no opt-in schema analogous to `entity_kind: ai-model`.

### Conventionally absent

The same absences as entity, plus every `entity_kind` / `provider` / `pricing` / `modalities` / `benchmarks` field — those are defined only for `type: entity`.

---

## `project`

A codebase or work stream, one page per session `project:` slug, under `wiki/projects/<slug>.md`. `ensure_project_stubs()` (`llmwiki/build.py`) writes a stub when `build --seed-project-stubs` is set, or when `sync` builds (sync always passes that flag). A bare `build` does not seed — it is read-only on `wiki/`. Existing files are never overwritten.

**Demo.** No committed project page. Sessions that would seed one are on disk under [`demo/raw/sessions/llm-wiki/`](../../demo/raw/sessions/llm-wiki/) (and the other project folders beside it). The stub `demo/wiki/projects/llm-wiki.md` appears after `llmwiki sync` or `llmwiki build --seed-project-stubs`.

### Fields the stub writer writes

| Field | Provenance | What it is |
|---|---|---|
| `title` | build | The project slug |
| `type` | build | Always `project` |
| `project` | build | The same slug, matching session `project:` |
| `topics` | build | Derived from session tags / `tools_used`, noise tags dropped. A person may edit afterwards; the stub is not rewritten |
| `description` | build | From the most recent session's summary or slug. Same edit rule as `topics` |
| `homepage` | build | Written as `""`. Any real URL is **human** |

### Conventionally absent

| Field | Why |
|---|---|
| `last_updated` | `ensure_project_stubs()` does not write it. Project freshness on the compiled site is derived from the project's sessions (oldest and newest session dates) at build time, not from a date on the stub |
| `date` | Same reason — no page-owned date |
| `sources` | Sessions *are* the evidence. Lint `claim_verification` treats a `## Sessions` section as a citation; the stub has none until a person adds one |
| `tags` | Project pages use `topics:`, not `tags:` (`tags_topics_convention`) |
| `status`, `confidence`, `lifecycle`, `last_verified`, `source_file`, `model` | No producer writes them on a project stub |
| `entity_kind` and the model-profile block | Those are entity-only |

---
