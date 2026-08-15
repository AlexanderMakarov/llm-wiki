"""Keep the llmwiki source checkout from being used as a knowledge vault (#109).

A git clone of llmwiki carries :data:`SOURCE_CHECKOUT_MARKER` at its root. The
CLI resolves an unnamed vault to that root, so a bare ``llmwiki init`` /
``sync`` / ``synth`` / ``build`` inside a clone scatters ``raw/``, ``wiki/`` and
``site/`` working folders across the source tree. Commands that write vault
content therefore call :func:`ensure_not_source_checkout` on the directory they
are about to write into, and stop with a message naming ``--vault`` and the
in-repo ``demo/`` vault.

Scope of the guard:

- **Installed distributions are unaffected.** pip and Homebrew unpack the
  package under ``site-packages``, whose parent carries no marker, so the guard
  never fires for a real user.
- **Naming a vault always wins.** ``--vault PATH`` on the command line, or
  ``vault.default_path`` in ``config.json``, resolves the content root away
  from the checkout before the guard is consulted.
"""

from __future__ import annotations

from pathlib import Path

#: Filename that identifies a directory as the llmwiki source tree.
SOURCE_CHECKOUT_MARKER = ".llmwiki-source-checkout"


class SourceCheckoutError(RuntimeError):
    """A vault-writing command was pointed at the llmwiki source checkout."""


def is_source_checkout(path: Path) -> bool:
    """Return ``True`` when ``path`` carries the source-checkout marker file."""
    return (Path(path) / SOURCE_CHECKOUT_MARKER).is_file()


def source_checkout_message(path: Path, command: str) -> str:
    """Return the refusal text shown when ``command`` targets ``path``."""
    return (
        f"error: {path} is the llmwiki source checkout, not a knowledge vault.\n"
        f"  Name the vault to work on:  llmwiki {command} --vault <path>\n"
        f"  Or set vault.default_path in config.json.\n"
        f"  To work on the example vault that ships with the repository:  "
        f"llmwiki {command} --vault demo"
    )


def ensure_not_source_checkout(path: Path, command: str) -> None:
    """Raise :class:`SourceCheckoutError` when ``path`` is a source checkout.

    ``command`` is the subcommand name, quoted back in the message so the
    suggested fix is a command the caller can paste.
    """
    if is_source_checkout(path):
        raise SourceCheckoutError(source_checkout_message(path, command))
