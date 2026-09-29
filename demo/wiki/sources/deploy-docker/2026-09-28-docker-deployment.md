---
title: "Docker deployment"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-docker, docker-deployment, containerization, github-container-registry, cli-distribution]
date: 2026-09-28
source_file: 
project: deploy-docker
model: 
last_updated: 2026-09-28
---
## Summary

The documentation describes how to run llmwiki in Docker containers, supporting both pulling pre-built images from GitHub Container Registry and building locally for development. It covers Docker Compose setup, running all CLI commands within containers, image specifications using `python:3.12-slim` base (~45 MB), volume mounting for host integration, and troubleshooting common issues.

## Key Claims

- The llmwiki image is published to `ghcr.io/alexandermakarov/llm-wiki:latest` on every release tag
- The Docker image uses `python:3.12-slim` as the base (~45 MB) with only `markdown` as a runtime dependency
- The container runs as non-root user (UID 1000) to prevent permission conflicts with bind-mounted host volumes
- All `llmwiki` CLI subcommands (build, sync, lint, graph) are executable via `docker compose run`
- The containerized deployment provides identical privacy guarantees to the CLI version — no telemetry or external API calls
- Bind-mounted `raw/`, `wiki/`, and `site/` directories allow session transcripts and generated output to persist on the host

## Key Quotes

> "The site is plain files. `site/` is bind-mounted, so the pages land on the host and open straight from disk — nothing keeps running afterwards."
— Clarifies the stateless, file-based output model of containerized deployment

> "The container reads from your bind-mounted directories. Nothing leaves the container — no telemetry, no external API calls. Same privacy guarantees as the CLI version."
— Reassures users that containerization does not introduce tracking or external service dependencies

## Connections

- [[llmwiki]] (entity) — the tool being containerized for distribution and ease of deployment
  - fact: Docker packaging eliminates the need for local Python installation or virtual environment setup
  - fact: All `llmwiki` subcommands work via `docker compose run` with bind-mounted volumes
- [[Docker]] (entity) — containerization technology enabling isolated, reproducible deployments
  - fact: Uses `python:3.12-slim` base image and runs as non-root user (UID 1000) to prevent permission conflicts
  - fact: Container is stateless with no exposed ports; it runs commands and exits
- [[GitHub Actions]] (entity) — CI/CD automation for publishing Docker images
  - fact: Release workflow automatically publishes images to fork namespace on tag push

## Contradictions

None identified.