"""llmwiki — LLM-powered knowledge base from Claude Code, Codex CLI, Cursor,
Gemini CLI, and Obsidian sessions.

Follows Andrej Karpathy's LLM Wiki pattern:
    https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Public API:
    - llmwiki.cli.main()              — the command-line entry point
    - llmwiki.convert.convert_all()   — .jsonl → markdown
    - llmwiki.build.build_site()      — markdown → HTML
    - llmwiki.serve.serve_site()      — local HTTP server
    - llmwiki.graph.build_and_report() — knowledge graph
    - llmwiki.exporters.export_all()  — AI-consumable exports
    - llmwiki.adapters.REGISTRY       — adapter registry
    - llmwiki.mcp.server.main()       — MCP server (stdio)
"""

__version__ = "1.3.82"
__author__ = "Pratiyush"
__license__ = "MIT"

import os
from pathlib import Path

# Repo root (llmwiki/ clone), resolved from this file's location.
# Override with the LLMWIKI_ROOT env var to point content reads (the MCP
# server's wiki_query / wiki_search / wiki_read_page, etc.) at an external
# vault that holds the real wiki/ + raw/ instead of the repo's own example
# data. PACKAGE_ROOT stays pinned to the installed package so bundled
# templates/assets still resolve. The build pipeline (cli.py/build.py) does
# not set this var, so it keeps writing relative to the clone as before.
_REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
_LLMWIKI_ROOT_ENV = os.environ.get("LLMWIKI_ROOT")
REPO_ROOT = (
    Path(_LLMWIKI_ROOT_ENV).expanduser().resolve()
    if _LLMWIKI_ROOT_ENV
    else _REPO_ROOT_DEFAULT
)
PACKAGE_ROOT = Path(__file__).resolve().parent

# #arch-m4 (#617): the docstring above promised a "public API" but
# nothing was actually exported. Wire the listed symbols up as real
# re-exports so `from llmwiki import build_site` etc. actually works.
# Lazy via __getattr__ so importing llmwiki itself stays cheap (most
# CLI invocations don't touch the public API surface, just REPO_ROOT).
__all__ = [
    "REPO_ROOT",
    "PACKAGE_ROOT",
    "__version__",
    "main",
    "convert_all",
    "build_site",
    "serve_site",
    "build_and_report",
    "export_all",
    "REGISTRY",
]


def __getattr__(name: str):
    """PEP 562 module-level lazy attribute access.

    Lets `from llmwiki import build_site` resolve without paying for
    the full transitive import graph at `import llmwiki` time.
    """
    if name == "main":
        from llmwiki.cli import main
        return main
    if name == "convert_all":
        from llmwiki.convert import convert_all
        return convert_all
    if name == "build_site":
        from llmwiki.build import build_site
        return build_site
    if name == "serve_site":
        from llmwiki.serve import serve_site
        return serve_site
    if name == "build_and_report":
        from llmwiki.graph import build_and_report
        return build_and_report
    if name == "export_all":
        from llmwiki.exporters import export_all
        return export_all
    if name == "REGISTRY":
        from llmwiki.adapters import REGISTRY
        return REGISTRY
    raise AttributeError(f"module 'llmwiki' has no attribute {name!r}")
