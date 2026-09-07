---
title: "CLI reference (part 11/15: install-agent-kit — copy packaged slash commands and skills (#109))"
slug: cli-reference-11
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/cli.md"
content_sha256: 68214fcdadc8d21482c73af718d17b4858152fb41607ffe75ccafc726af46640
---

> Part 11 of 15 of **CLI reference** — install-agent-kit — copy packaged slash commands and skills (#109).

## `install-agent-kit` — copy packaged slash commands and skills (#109)

A pip or Homebrew install carries the user-facing `/wiki-*` slash commands and skills inside the package (`llmwiki/agent_kit/`). This command copies `commands/` and `skills/` beneath a directory you name so Claude Code (or any agent that reads that layout) can see them. `--dest` is **required** — the command does not guess at agent directory conventions.

Typical destinations: `.claude` in the project you are working in, or a user-level agent directory. Contributors working in this clone who want `/wiki-*` locally run `llmwiki install-agent-kit --dest .claude`.

Re-running after an upgrade refreshes the copies. A destination file whose content already matches the kit is left alone. A destination file that differs is saved as `<filename>.bak` beside it before the kit version is written, and the backup is reported, so a customisation is never overwritten silently. `--dry-run` prints the same report and writes nothing.

The install also prunes commands and skills the kit has retired (#214), so an agent directory populated by an older install stops offering them. Pruning is gated on content, never on the name: a file is deleted only while it still hashes to a revision llmwiki is known to have written at that path. Two things supply those digests — a small list of retired paths carried in the package, each mapped to the digests of every revision it ever shipped, and `<dest>/.llmwiki-agent-kit.json`, a manifest of the llmwiki version and a `path → sha256` record of what this command installed, written after a pass. Anything the previous manifest recorded that the current kit no longer ships is pruned when its bytes are unchanged. A file this command never installed is never touched, whatever its name, so your own commands beside the kit's are safe; a retired command you customised is safe for the same reason — an unrecognised digest leaves the file alone and reports it as `kept`. Manifest entries that are absolute, escape the destination, or sit outside `commands/`/`skills/` are ignored, and a manifest that is missing, unreadable, or written in an older shape that carries no digests falls back to the retired list. Because only bytes llmwiki itself wrote are ever removed, a prune makes no backup; only files are removed — never directories. `--dry-run` reports the prune and deletes nothing.

The manifest is a normal file in `--dest`. When that is a git-tracked `.claude/`, commit `.llmwiki-agent-kit.json` alongside `commands/` and `skills/`: it is what lets a later upgrade recognise its own files and clean them up.

Contributor-only commands (`fix-bug`, `maintainer`, `release`, …) and skills (`docs-that-work`, `pytest-best-practices`, `release`, …) stay in this repository's `.claude/` tree and are not part of the kit. Cutting a tagged release uses `.claude/skills/release/SKILL.md` via `/release` (see [`docs/maintainers/RELEASE_PROCESS.md`](../maintainers/RELEASE_PROCESS.md)).

```bash
python3 -m llmwiki install-agent-kit --dest .claude --dry-run
python3 -m llmwiki install-agent-kit --dest .claude
python3 -m llmwiki install-agent-kit --dest /path/to/agent-dir
```

### Flags

| Flag | What |
|---|---|
| `--dest PATH` | **Required.** Directory that will receive `commands/` and `skills/`. |
| `--dry-run` | Report what would be written; write nothing. |

The command prints every path written, every path pruned, every `.bak` it created for an overwrite, every retired path it kept because the content was not its own, and a count of identical files left untouched. Exit `0` on success, `1` if a file could not be read or written.

---

## `version` — print the installed version

```bash
python3 -m llmwiki version
python3 -m llmwiki --version
```

Both print `llmwiki <version>`.

---

## `query` — search the knowledge graph

```bash
python3 -m llmwiki query "what projects is Pratiyush working on"
python3 -m llmwiki query "Flutter mobile" --depth 2 --budget 1000
```

### Flags

| Flag | What |
|---|---|
| `--depth N` | BFS traversal depth. Default: `3`. |
| `--budget N` | Max output tokens. Default: `2000`. |

Requires Graphify (`pip install llm-wiki-plus[graph]`). Run `llmwiki graph` first to build the graph.

---

## `trace` — print downward provenance to raw transcripts (#122)

Walk a wiki page’s encoded chain to its source summaries and raw files. Uses only frontmatter (`sources:`, `source_file:`) — no body excerpts. Missing hops are marked; the walk still succeeds.

```bash
python3 -m llmwiki trace Demo --vault /path/to/vault
python3 -m llmwiki trace wiki/entities/Demo.md --vault /path/to/vault
```

### Positional

| Arg | What |
|---|---|
| `PAGE` | Vault-relative wiki path (`wiki/entities/Foo.md`) or a resolvable page name/stem under `wiki/`. |

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | Trace under this vault (reads `wiki/` + `raw/`). Without it, uses `config.json` `vault.default_path` or the repo demo content. |

### Expected output

One line per hop: `role`, title, location; missing hops append ` (missing)`. A page with no provenance prints the page line plus `(no further provenance)`.

```
page    Demo  wiki/entities/Demo.md
source  Kickoff session  wiki/sources/kickoff.md
raw     Kickoff transcript  raw/sessions/2026-01-01T12-00-demo-kickoff.md
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Walk completed (including chains with missing hops). |
| `1` | Starting page could not be resolved (or locator unsafe / empty). |
| `2` | Configured `--vault` / default vault path is unusable. |

Guided repair of broken hops will live under `doctor` (#110); this command only prints the chain.

---
