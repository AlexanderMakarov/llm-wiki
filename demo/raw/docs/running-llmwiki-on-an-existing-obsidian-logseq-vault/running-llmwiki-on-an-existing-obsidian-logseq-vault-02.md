---
title: "Running llmwiki on an existing Obsidian / Logseq vault (part 2/2: Non-goals (explicitly out of scope for #54))"
slug: running-llmwiki-on-an-existing-obsidian-logseq-vault-02
project: running-llmwiki-on-an-existing-obsidian-logseq-vault
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/guides/existing-vault.md"
content_sha256: 403725d5e68459adf28c5b0bf1bc5590e2d7e430a6a20706b9042381192aebf3
---

> Part 2 of 2 of **Running llmwiki on an existing Obsidian / Logseq vault** — Non-goals (explicitly out of scope for #54).

## Non-goals (explicitly out of scope for #54)

- **Bidirectional `raw/` sync** — sessions still live in the repo's
  local `raw/sessions/`, not inside the vault. This keeps auto-
  generated transcripts from cluttering the user's notes.
- **Config.edn parsing** — Logseq detection is marker-only. If your
  Logseq config sets a non-default `pages/` directory, the pipeline
  doesn't discover it today.
- **Flat `namespace___slug.md` mode for Obsidian** — Obsidian users
  get folder nesting even if their existing convention is flat. Custom
  `VaultLayout` can't shape the filename format yet (only the prefix).
  Follow-up if there's demand.

## Related

- `#54` — the issue
- `llmwiki/vault.py` — implementation
- `docs/guides/obsidian-integration.md` — the original symlink-based
  integration (still works; vault-overlay is the "no-symlink"
  alternative)
- `#43` — OpenCode adapter (similar vault-touching pattern)
