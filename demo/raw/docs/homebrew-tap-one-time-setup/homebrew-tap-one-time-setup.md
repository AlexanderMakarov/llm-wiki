---
title: "Homebrew tap — one-time setup"
slug: homebrew-tap-one-time-setup
project: homebrew-tap-one-time-setup
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/deploy/homebrew-setup.md"
content_sha256: 461162c80bfedc4050a4974fd22a0e2b455975bc4fe60b9845bdb57b3f56e59e
---

# Homebrew tap — one-time setup

> Status: the formula is shipped at `homebrew/llmwiki.rb`. This doc is the
> checklist for creating the **Homebrew tap repository** that unblocks
> `brew install Pratiyush/tap/llmwiki` (#102).

## Why a tap?

Homebrew's main `homebrew/core` has strict acceptance criteria (notability,
age, stability). Small-but-useful CLIs like `llmwiki` ship via third-party
"taps" instead. A tap is just a GitHub repo called
`homebrew-<name>` that Homebrew can add with `brew tap`.

Users install with:
```bash
brew tap Pratiyush/tap             # one-time
brew install llmwiki               # or: brew install Pratiyush/tap/llmwiki
```

## One-time setup

### 1. Create the tap repo

**[Create a new public GitHub repo](https://github.com/new)** called exactly
`homebrew-tap` under the `Pratiyush` account (the name **must** start
with `homebrew-`):

```
Repository name: homebrew-tap
Description:     Homebrew tap for Pratiyush/llm-wiki and friends.
Visibility:      Public
Add README:      yes (you can replace the contents in step 3)
```

### 2. Clone it locally

```bash
git clone git@github.com:Pratiyush/homebrew-tap.git ~/src/homebrew-tap
cd ~/src/homebrew-tap
mkdir -p Formula
```

### 3. Seed the tap with the llmwiki formula

From inside this repo:

```bash
cd /path/to/llm-wiki

# Bump the formula to point at the current release (computes the SHA-256
# from GitHub's tarball). Requires the tag to already exist on GitHub.
scripts/bump-homebrew-formula.sh v1.1.0

# Copy the updated formula into the tap repo
cp homebrew/llmwiki.rb ~/src/homebrew-tap/Formula/llmwiki.rb
```

Then in the tap repo:

```bash
cd ~/src/homebrew-tap
git add Formula/llmwiki.rb
git commit -S -m "Add llmwiki v1.1.0 formula"
git push
```

### 4. Verify

From any machine with Homebrew:

```bash
brew tap Pratiyush/tap
brew install llmwiki
llmwiki --version        # should match the tag
llmwiki adapters
brew test llmwiki        # runs the `test do` block in the formula
```

## On every new release

After tagging a new version (`vX.Y.Z`) in this repo:

```bash
# 1. Refresh the formula in this repo
scripts/bump-homebrew-formula.sh vX.Y.Z

# 2. Commit the updated homebrew/llmwiki.rb into this repo (keeps
#    history) — e.g. as part of the release commit or a follow-up
git add homebrew/llmwiki.rb
git commit -S -m "chore: bump Homebrew formula to vX.Y.Z"

# 3. Copy into the tap repo + push
cp homebrew/llmwiki.rb ~/src/homebrew-tap/Formula/llmwiki.rb
cd ~/src/homebrew-tap
git add Formula/llmwiki.rb
git commit -S -m "llmwiki vX.Y.Z"
git push
```

Users then:
```bash
brew update && brew upgrade llmwiki
```

## Optional: auto-bump via CI

If you want every release tag to auto-update the tap repo:

1. Generate a **personal access token** with `repo` scope for the
   `Pratiyush/homebrew-tap` repo (or a fine-grained token scoped to
   "Contents: write" on just that repo).
2. Add it as a secret `HOMEBREW_TAP_TOKEN` on the `llm-wiki` repo:
   ```bash
   gh secret set HOMEBREW_TAP_TOKEN --repo Pratiyush/llm-wiki
   ```
3. The `.github/workflows/homebrew-bump.yml` workflow will then, on
   each `v*.*.*` tag push, regenerate the formula, commit to the
   tap repo, and push. Without the secret, it skips the push and
   just prints the new formula so you can copy-paste manually.

## Troubleshooting

**`brew install` fails with "404 on tarball"** — the release tag is a
pre-release (v1.1.0-rc1) that GitHub marked as "draft" or the tag
was deleted. Check: `gh release view vX.Y.Z`.

**`brew test` fails on `llmwiki init`** — the formula runs `init` in a
sandboxed tmpdir; if `init` now writes to paths outside the working
directory, update the test to match (`testpath/"raw"`, etc.).

**Formula class name mismatch** — Ruby class name in the formula must
be the camel-cased filename. `Formula/llmwiki.rb` → `class Llmwiki`.
If you rename to `llm-wiki.rb`, the class becomes `LlmWiki`.

**Stale SHA after a force-push to a tag** — GitHub regenerates the
tarball when a tag is moved, so the old SHA no longer matches. Re-run
`bump-homebrew-formula.sh` and push the new SHA to the tap repo.

## Related

- `#102` — this issue
- `homebrew/llmwiki.rb` — the formula source of truth
- `scripts/bump-homebrew-formula.sh` — SHA refresh helper
- `.github/workflows/homebrew-bump.yml` — optional auto-bump workflow
- `docs/deploy/pypi-publishing.md` — sibling doc for the PyPI pipeline (#101)
