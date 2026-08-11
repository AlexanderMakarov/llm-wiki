---
title: "Docker deployment"
slug: docker-deployment
project: docker-deployment
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/deploy/docker.md"
content_sha256: 0d528576def40d42abdb3ee24b4994aa83da7a075567cfd04f7053dbaa72f75b
---

# Docker deployment

Run llmwiki in a container — no Python install, no pip, no venv. Two
supported setups:

1. **Pull pre-built image** from GitHub Container Registry (recommended)
2. **Build locally** from the repo `Dockerfile` (for development)

## Prerequisites

- Docker Desktop (macOS / Windows) or Docker Engine 20+ (Linux)
- `docker compose` plugin (bundled with recent Docker Desktop; on Linux
  install the `docker-compose-plugin` package)

## Quick start — pre-built image

The image is published to `ghcr.io/pratiyush/llm-wiki:latest` on every
release tag. To run:

```bash
# 1. Clone the repo (you need the Dockerfile + examples for the volume mounts)
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki

# 2. Pull the latest image
docker compose pull

# 3. Start the server
docker compose up -d

# 4. Open http://localhost:8765
```

The server runs in the background with `restart: unless-stopped`, so
it comes back after reboots / Docker restarts.

## Running CLI commands in the container

Any `llmwiki` subcommand works inside the container via `docker compose run`:

```bash
# Build the static site from raw/ + wiki/
docker compose run --rm llmwiki build

# Sync session transcripts (needs host agent stores bind-mounted)
docker compose run --rm llmwiki sync --status

# Run every registered lint rule (15 at last count — see `llmwiki lint --help`)
docker compose run --rm llmwiki lint --fail-on-errors

# Generate a knowledge graph
docker compose run --rm llmwiki graph
```

Because the repo's `raw/`, `wiki/`, and `site/` directories are
bind-mounted, the output shows up on the host too.

## Build locally

If you're developing llmwiki itself or need unreleased changes:

```bash
docker compose build
docker compose up -d
```

This uses the repo `Dockerfile` and re-builds on every code change.

## Image details

- **Base:** `python:3.12-slim` (~45 MB)
- **Runtime deps:** `markdown` only (stdlib + optional `graphifyy` extra)
- **User:** non-root (`app`, UID 1000) — mounted volumes stay host-owned
- **Port:** 8765 (exposed + mapped)
- **Entrypoint:** `python -m llmwiki`
- **Default CMD:** `serve --host 0.0.0.0 --port 8765 --dir site`
- **Labels:** OCI standard (title, description, source, licenses, authors)

## Volumes

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `./raw` | `/wiki/raw` | Session transcripts (gitignored user data) |
| `./wiki` | `/wiki/wiki` | LLM-maintained wiki pages (gitignored) |
| `./site` | `/wiki/site` | Generated HTML (gitignored) |
| `./examples` | `/wiki/examples` (read-only) | Demo sessions + config templates |

## Publishing your own image

Only the repo maintainer can publish to `ghcr.io/pratiyush/llm-wiki`.
To publish under your own namespace:

```bash
docker build -t ghcr.io/<your-user>/llm-wiki:latest .
docker push ghcr.io/<your-user>/llm-wiki:latest
```

Or fork the repo and the release workflow will publish under your
fork's namespace automatically on tag push.

## Privacy

The container reads from your bind-mounted directories. Nothing leaves
the container — no telemetry, no external API calls. Same privacy
guarantees as the CLI version.

## Troubleshooting

### "Permission denied" on mounted volumes

The container runs as UID 1000. If your host user is a different UID,
either match UIDs in the Dockerfile or change host ownership:

```bash
sudo chown -R 1000:1000 raw/ wiki/ site/
```

### Can't pull from ghcr.io

The GitHub Container Registry requires authentication for private
images. For this repo (public), pulls should work without auth. If
you see 404s, the image hasn't been published yet — fall back to
local build:

```bash
docker compose build && docker compose up -d
```

### Port 8765 already in use

Change the host port in `docker-compose.yml`:

```yaml
ports:
  - "9999:8765"  # access at http://localhost:9999
```

## Related docs

- [GitHub Pages deployment](github-pages.md) — static hosting instead of container
- [GitLab Pages deployment](gitlab-pages.md)
- [Vercel / Netlify](vercel-netlify.md)
