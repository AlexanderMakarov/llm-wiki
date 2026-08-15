Regenerate the static HTML site for the llmwiki.

Usage: /wiki-build [--synthesize]

Run:

```bash
python3 -m llmwiki build $ARGUMENTS
```

The `--synthesize` flag (optional) calls the `claude` CLI once to generate an Overview paragraph for the home page.

Report the output directory (default: `site/`), the total number of HTML files, and total size.

Remind the user they can browse the result by opening `site/index.html` in a browser — it is plain files, nothing needs to be running.
