---
title: "Docker deployment"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-docker, docker-deployment, ghcr, docker-compose, containerized-cli, bind-mounts, container-image]
date: 2026-09-08
source_file: 
project: deploy-docker
model: 
last_updated: 2026-09-08
---
## Summary

This source documents how to run **llmwiki** in Docker so users avoid a local Python install, pip, or venv. The recommended path is pulling a pre-built image from GitHub Container Registry (`ghcr.io/pratiyush/llm-wiki:latest`) on release tags and driving CLI work through `docker compose run`; an alternative is building from the repo `Dockerfile` for development or unreleased changes. The repo’s `raw/`, `wiki/`, and `site/` directories are bind-mounted so builds and sync output land on the host as plain files, with no long-running service or exposed ports.

## Key Claims

- The published image uses base `python:3.12-slim`, runs as non-root user `app` (UID 1000), and declares runtime dependency on `markdown` only (stdlib plus optional `graphify` extra).
- Default container entrypoint is `python -m llmwiki` with default CMD `build`; any subcommand (`build`, `sync`, `lint`, `graph`, etc.) can be run via `docker compose run --rm llmwiki <subcommand>`.
- Official GHCR publishing to `ghcr.io/pratiyush/llm-wiki` is maintainer-only; forks can publish under their own namespace on tag push via the release workflow, or manually with `docker build` / `docker push`.
- Container behavior matches CLI privacy: it only reads bind-mounted directories and does not send telemetry or make external API calls.
- Permission errors on mounted volumes are expected when the host UID differs from 1000; remediation is matching UID in the image or `chown` on `raw/`, `wiki/`, and `site/` to `1000:1000`.

## Key Quotes

> "Nothing leaves the container — no telemetry, no external API calls. Same privacy guarantees as the CLI version." — states the privacy model for Docker vs bare CLI.

> "The site is plain files. `site/` is bind-mounted, so the pages land on the host and open straight from disk — nothing keeps running afterwards." — clarifies that Docker is a batch CLI runner, not a hosted wiki server.

> "**Ports:** none — the container runs commands, it hosts nothing" — distinguishes containerized llmwiki from deploy targets that serve HTTP.

## Connections

- [[llmwiki]] (entity) — product documented for containerized install and CLI execution.
  - fact: Docker path is positioned as equivalent to local CLI for build, sync, lint, and graph with bind-mounted vault layout.
- [[Static Site]] (concept) — primary in-container workflow is `llmwiki build` producing `./site/index.html` on the host.
  - fact: Generated HTML is written through a `./site` → `/wiki/site` volume mount.
- [[GitHub Pages]] (concept) — related deployment doc for publishing the built site to the web (cross-linked from this guide).
- [[GitHub Actions]] (concept) — release tags trigger publishing the pre-built image to GHCR; fork workflows can publish under the fork namespace.
