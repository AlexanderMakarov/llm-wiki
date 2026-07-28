"""Allow `python3 -m llmwiki` to invoke the CLI."""
import sys

from llmwiki.cli import main

if __name__ == "__main__":
    sys.exit(main())
