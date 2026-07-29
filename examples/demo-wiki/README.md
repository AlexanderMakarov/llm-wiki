# Demo wiki sources

Pre-synthesized `wiki/sources/` pages for the GitHub Pages demo.

Generated locally with `llmwiki synthesize --docs-only` against `examples/demo-docs/` using the maintainer's Claude backend. CI copies these files as-is so deploys stay free, deterministic, and secret-free.

To refresh after editing docs:

```bash
STAGE=$(mktemp -d)
python3 -m llmwiki init --vault "$STAGE"
mkdir -p "$STAGE/raw/docs"
cp -a examples/demo-docs/. "$STAGE/raw/docs/"
python3 -m llmwiki synthesize --docs-only --vault "$STAGE" --force
cp -a "$STAGE/wiki/sources/llm-wiki" examples/demo-wiki/sources/
```
