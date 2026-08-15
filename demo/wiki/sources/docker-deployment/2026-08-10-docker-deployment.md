---
title: "Docker deployment"
type: source
tags: [wiki-add, raw-doc, session-transcript, docker-deployment, self-hosting]
date: 2026-08-10
source_file: 
project: docker-deployment
model: 
last_updated: 2026-08-11
---
## Summary

This documentation describes how to run [[llm-wiki]] in Docker containers, eliminating the need for local Python installation. It covers two approaches: using pre-built images from GitHub Container Registry (recommended) and building locally from source code. The guide includes quick-start instructions, CLI command execution in containers, volume mounting configuration, image specifications, and troubleshooting for common issues.

## Key Claims

- llm-wiki can run containerized with no local Python, pip, or virtual environment installation required
- Pre-built images are published to `ghcr.io/pratiyush/llm-wiki:latest` on every release tag
- The container runs as a non-root user (UID 1000) to preserve host volume ownership when mounted
- All output directories (raw/, wiki/, site/) are bind-mounted, so container changes immediately appear on the host
- The Docker setup provides identical privacy guarantees to the CLI version: no telemetry or external API calls
- The container is configured with `restart: unless-stopped` for automatic recovery after reboots

## Key Quotes

> "Run llmwiki in a container — no Python install, no pip, no venv."
Captures the core value proposition: containerization eliminates dependency management friction.

> "Because the repo's `raw/`, `wiki/`, and `site/` directories are bind-mounted, the output shows up on the host too."
Explains how containerized operation integrates with local development workflows.

> "The container reads from your bind-mounted directories. Nothing leaves the container — no telemetry, no external API calls. Same privacy guarantees as the CLI version."
Addresses security concerns by confirming containerization introduces no additional privacy risks.

## Connections

- [[llm-wiki]] — the project whose containerized deployment this documents
- Related deployment alternatives mentioned: GitHub Pages, GitLab Pages, Vercel/Netlify (each likely has its own documentation page)

## Contradictions

None identified.