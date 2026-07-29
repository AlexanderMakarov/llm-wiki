#!/usr/bin/env bash
# Bump the Homebrew formula to point at a new release tag (#102).
#
# Usage:
#   scripts/bump-homebrew-formula.sh v1.1.0
#
# Fetches the GitHub archive tarball for the tag, computes its SHA-256,
# and rewrites `homebrew/llmwiki.rb` so `url` + `sha256` match. After
# running this, copy the updated formula into your `homebrew-tap` repo
# and `git push` it — that's what users `brew install` from.
#
# The script is idempotent: re-running with the same tag rewrites the
# same two fields to the same values.

set -euo pipefail

tag="${1:-}"
if [[ -z "$tag" ]]; then
  echo "usage: $0 <version-tag, e.g. v1.1.0>" >&2
  exit 2
fi

if ! [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9._-]+)?$ ]]; then
  echo "error: tag '$tag' is not semver (v<MAJOR>.<MINOR>.<PATCH>[-<PRE>])" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

# Default to this product line's GitHub repo (#69). Override with
# LLMWIKI_GITHUB_REPO=owner/name when bumping a mirror.
REPO_SLUG="${LLMWIKI_GITHUB_REPO:-AlexanderMakarov/llm-wiki}"
tarball_url="https://github.com/${REPO_SLUG}/archive/refs/tags/${tag}.tar.gz"

echo "→ Fetching $tarball_url …"
tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

if ! curl -fsSL "$tarball_url" -o "$tmpfile"; then
  echo "error: failed to download $tarball_url — does the tag exist?" >&2
  exit 1
fi

if command -v shasum >/dev/null 2>&1; then
  sha="$(shasum -a 256 "$tmpfile" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  sha="$(sha256sum "$tmpfile" | awk '{print $1}')"
else
  echo "error: need shasum or sha256sum on PATH" >&2
  exit 1
fi

echo "→ SHA-256: $sha"

# Rewrite url + sha256 lines in the formula (macOS/BSD sed needs '' arg).
formula="homebrew/llmwiki.rb"
if [[ "$(uname -s)" == "Darwin" ]]; then
  sed -i '' -E \
    -e "s|^(  url \").*(\".*)$|\1${tarball_url}\2|" \
    -e "s|^(  sha256 \").*(\".*)$|\1${sha}\2|" \
    "$formula"
else
  sed -i -E \
    -e "s|^(  url \").*(\".*)$|\1${tarball_url}\2|" \
    -e "s|^(  sha256 \").*(\".*)$|\1${sha}\2|" \
    "$formula"
fi

echo ""
echo "✓ Updated $formula:"
grep -E '^  (url|sha256) ' "$formula"
echo ""
echo "Next steps:"
echo "  1. Review the updated $formula in this repo (commit it on the release PR if desired)."
echo "  2. Do NOT push to Pratiyush/homebrew-tap — that tap is upstream's (#69)."
echo "  3. If you maintain a private tap, copy the formula there by hand."
echo ""
echo "See docs/deploy/homebrew-setup.md for background (upstream tap flow)."
