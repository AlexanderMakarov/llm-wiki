---
title: "Homebrew tap — one-time setup"
type: source
tags: [wiki-add, raw-doc, session-transcript, homebrew-tap-one-time-setup, cli-distribution, release-automation, github-actions]
date: 2026-08-10
source_file: 
project: homebrew-tap-one-time-setup
model: 
last_updated: 2026-08-11
---
## Summary

This documentation establishes the one-time setup and ongoing maintenance procedures for a Homebrew tap repository that enables users to install [[llmwiki]] via Homebrew. It explains why small CLIs require third-party taps rather than Homebrew core inclusion, provides step-by-step instructions for repository creation and formula seeding, and details both manual and optional CI-automated workflows for keeping the tap synchronized with new releases.

## Key Claims

- Homebrew core enforces strict acceptance criteria (notability, age, stability), requiring third-party "taps" for smaller CLIs like [[llmwiki]]
- A Homebrew tap is a GitHub repository named `homebrew-<name>` that users can add with `brew tap <owner>/<name>`
- The formula source code resides in the main [[llmwiki]] repository at `homebrew/llmwiki.rb` and is copied to the tap repository after each release to maintain history in both locations
- The `scripts/bump-homebrew-formula.sh` script automatically computes SHA-256 hashes from GitHub release tarballs, enabling reproducible and secure installations across versions
- Optional GitHub Actions CI can automatically regenerate formulas and push them to the tap repository on new version tags if a `HOMEBREW_TAP_TOKEN` secret is configured

## Key Quotes

> "Homebrew's main `homebrew/core` has strict acceptance criteria (notability, age, stability). Small-but-useful CLIs like `llmwiki` ship via third-party "taps" instead."

This articulates the primary rationale for distributing via a third-party tap rather than pursuing Homebrew core inclusion.

> "Commit the updated homebrew/llmwiki.rb into this repo (keeps history)"

This reflects a deliberate architectural choice to maintain formula version history in the main repository, creating an audit trail of release-related changes.

## Connections

- [[llmwiki]] — the CLI tool being packaged for user installation
- [[Homebrew]] — the macOS/Linux package manager providing the distribution mechanism
- [[GitHub Actions]] — optional CI system for automating formula updates on release tags
- PyPI publishing (#101) — parallel distribution channel for the same project