Cut a tagged llmwiki release by following the maintainer release skill.

Usage: `/release <version>` — e.g. `/release 2.2.0`

`$ARGUMENTS` is the version (`X.Y.Z`, no leading `v`).

## Instructions

1. Read and follow `.claude/skills/release/SKILL.md` end to end (scripted cut: preflight → bump → editorial → commit/tag → **human gate** → push → watch automation).
2. Keep `docs/maintainers/RELEASE_PROCESS.md` as the canonical checklist order; do not contradict it.
3. Pass `$ARGUMENTS` as the proposed version; confirm Theme and version with the human before editing files.
4. Do not invent a second happy-path `gh release create` — the tag push triggers `.github/workflows/release.yml`.
