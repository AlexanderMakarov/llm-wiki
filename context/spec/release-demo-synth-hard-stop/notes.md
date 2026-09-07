# Release demo synth hard stop

## Why

The v2.2.0 cut refreshed `demo/raw/docs` for a plan of product docs, then tagged while wiki coverage for those slugs was still incomplete (Claude rate limit mid-synth). CI stayed green because lint/build do not require every raw doc to have a `wiki/sources` page. The `/release` skill already said “refresh then commit before tag,” but “proceed with delivery” + lint green overrode that.

## What changed

- Skill + `RELEASE_PROCESS.md`: incomplete / rate-limited synth is a **hard stop**; “proceed with delivery” is not a waiver; human gate must report synth status.
- `refresh_demo.py`: after path-scoped synth, refuse to advance `.demo-source-rev` when plan-added raw docs lack wiki pages; add `--verify-slugs` for the same check after a manual synth.
- Scope is **plan slugs only** — not the vault-wide historical docs backlog.
- No new CI rule in this change (maintainer chose local gate only).
