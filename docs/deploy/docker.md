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

# 3. Compile the site
docker compose run --rm llmwiki build

# 4. Open ./site/index.html in a browser
```

The site is plain files. `site/` is bind-mounted, so the pages land on the
host and open straight from disk — nothing keeps running afterwards.

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
docker compose run --rm llmwiki build
```

This uses the repo `Dockerfile` and re-builds the image on every code change.

## Image details

- **Base:** `python:3.12-slim` (~45 MB)
- **Runtime deps:** `markdown` only (stdlib + optional `graphifyy` extra)
- **User:** non-root (`app`, UID 1000) — mounted volumes stay host-owned
- **Ports:** none — the container runs commands, it hosts nothing
- **Entrypoint:** `python -m llmwiki`
- **Default CMD:** `build`
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
docker compose build && docker compose run --rm llmwiki build
```

## Related docs

- [GitHub Pages deployment](github-pages.md) — publish the built site to the web
- [GitLab Pages deployment](gitlab-pages.md)
- [Vercel / Netlify](vercel-netlify.md)
