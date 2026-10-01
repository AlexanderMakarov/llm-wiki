---
title: "CLI reference (part 14/19: install-agent-kit — copy packaged slash commands and skills (#109))"
slug: cli-reference-14
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 14 of 19 of **CLI reference** — install-agent-kit — copy packaged slash commands and skills (#109).

## `install-agent-kit` — copy packaged slash commands and skills (#109)

A pip install carries the user-facing `/wiki-*` slash commands and skills inside the package (`llmwiki/agent_kit/`). This command copies `commands/` and `skills/` beneath a directory you name so Claude Code (or any agent that reads that layout) can see them. `--dest` is **required** — the command does not guess at agent directory conventions.

Typical destinations, by where you want the commands and skills to be visible:

| `--dest` | Who reads it |
|---|---|
| `~/.claude` | Claude Code, every project on the machine |
| `~/.cursor` | Cursor, every project on the machine (it reads top-level `commands/` and `skills/`) |
| `~/.codex` | Codex CLI, every project on the machine |
| `.claude` | Claude Code, this project only — what contributors in this clone use to get `/wiki-*` locally |

Point `--dest` at whichever agent directory you actually use; install into more than one if you switch between agents. The files are plain markdown and the format is portable, so an agent with a different layout can take the same `commands/` and `skills/` folders. The packaged skills themselves are catalogued in [`slash-commands.md`](slash-commands.md#agent-kit-skills).

Re-running after an upgrade refreshes the copies, and reports which of them were stale. A destination file whose content already matches the kit is left alone and counted as `unchanged`. A file that differs is classified by what its content is, using the same digests that gate pruning:

| Class | What it means | What happens |
|---|---|---|
| `outdated` | The bytes are the revision `<dest>/.llmwiki-agent-kit.json` records for that path, so they are a copy llmwiki itself installed. | Reported as outdated, naming the version that installed it when the manifest records one, and overwritten. **No `.bak`** — these are llmwiki's own bytes, so a backup of them is noise, and writing one can overwrite a real backup beside it. |
| `customised` | The bytes match nothing the manifest records there, so you edited the file (or it predates the manifest). | Reported as customised, naming the version you patched when the manifest knows the path. Your edits cannot be merged into the kit update, so the file is copied to `<filename>.bak` beside it before the kit version is written, and the backup is reported once it is on disk. |

Running `--dry-run` against an install is therefore how you ask *is my agent kit stale?* — it classifies exactly as a real run and writes nothing. Version attribution comes only from `<dest>/.llmwiki-agent-kit.json`: with no manifest, or for a path the manifest does not record, the report names no version rather than guessing one.

The install also prunes commands and skills the kit has retired (#214), so an agent directory populated by an older install stops offering them. Pruning is gated on content, never on the name: a file is deleted only while it still hashes to a revision llmwiki is known to have written at that path. Two things supply those digests — a small list of retired paths carried in the package, each mapped to the digests of every revision it ever shipped, and `<dest>/.llmwiki-agent-kit.json`, a manifest of the llmwiki version and a `path → sha256` record of what this command installed, written after a pass. Anything the previous manifest recorded that the current kit no longer ships is pruned when its bytes are unchanged. A file this command never installed is never touched, whatever its name, so your own commands beside the kit's are safe; a retired command you customised is safe for the same reason — an unrecognised digest leaves the file alone and reports it as `kept`. Manifest entries that are absolute, escape the destination, or sit outside `commands/`/`skills/` are ignored, and a manifest that is missing, unreadable, or written in an older shape that carries no digests falls back to the retired list. Because only bytes llmwiki itself wrote are ever removed, a prune makes no backup; only files are removed — never directories. `--dry-run` reports the prune and deletes nothing.

The manifest is a normal file in `--dest`. When that is a git-tracked `.claude/`, commit `.llmwiki-agent-kit.json` alongside `commands/` and `skills/`: it is what lets a later upgrade recognise its own files and clean them up. Because it is also what decides which files are replaced without a `.bak`, treat a manifest you did not generate the way you treat the files beside it.

Contributor-only commands (`fix-bug`, `implement-feature`, `release`) and skills (`docs-that-work`, `pytest-best-practices`, `release`, …) stay in this repository's `.claude/` tree and are not part of the kit. Cutting a tagged release uses `.claude/skills/release/SKILL.md` via `/release` (see [`docs/maintainers/RELEASE_PROCESS.md`](../maintainers/RELEASE_PROCESS.md)).

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

The command prints every path written, every outdated copy it replaced, every customised file with the `.bak` its previous content went to, every path pruned, every retired path it kept because the content was not its own, and a count of identical files left untouched. Every path in the report, errors included, is absolute, so you can open it straight from the output. Exit `0` on success, `1` if a file could not be read or written.

---

## `version` — print the installed version

```bash
python3 -m llmwiki version
python3 -m llmwiki --version
```

Both print `llmwiki <version>`.

---
