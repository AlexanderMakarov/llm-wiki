# Demo wiki sources

Pre-synthesized `wiki/sources/` for the GitHub Pages demo (16 pages: 4 product docs + 12 demo/fixture sessions).

Generated with `llmwiki synthesize --force` against the demo seed corpus using the maintainer's Claude backend (`haiku`). CI copies these files as-is so deploys stay free, deterministic, and secret-free.

To refresh:

```bash
STAGE=$(mktemp -d)
python3 -m llmwiki init --vault "$STAGE"
mkdir -p "$STAGE/raw/docs" "$STAGE/raw/sessions"
cp -a examples/demo-docs/. "$STAGE/raw/docs/"
cp -a examples/demo-sessions/. "$STAGE/raw/sessions/"
cp -a tests/fixtures/demo/. "$STAGE/raw/sessions/"
python3 -m llmwiki synthesize --vault "$STAGE" --force
rm -rf examples/demo-wiki/sources
mkdir -p examples/demo-wiki/sources
cp -a "$STAGE/wiki/sources/." examples/demo-wiki/sources/
```

Estimate (haiku): ~$0.15 for all 16 sources.
