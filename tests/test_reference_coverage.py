"""Guardrail: every shipped command must be documented (v1.2.0 · #265).

- Every CLI subcommand registered in ``llmwiki.cli.build_parser`` must
  appear as an ``## subcommand`` heading in ``docs/reference/cli.md``.
- Every user-facing ``llmwiki/agent_kit/commands/*.md`` file must appear
  as a ``### /slash-command`` heading in
  ``docs/reference/slash-commands.md``; every contributor
  ``.claude/commands/*.md`` file must appear the same way in
  ``docs/maintainers/slash-commands.md``.
- Every top-level nav item in ``llmwiki/build.py`` must appear as a
  row in ``docs/reference/ui.md``.

When a maintainer adds a new subcommand / slash command / nav tab, these
tests fail with a clear message pointing at the missing entry.
"""

from __future__ import annotations

import re
from pathlib import Path

from llmwiki import REPO_ROOT
from llmwiki.cli import build_parser

CLI_REF = REPO_ROOT / "docs" / "reference" / "cli.md"
SLASH_REF = REPO_ROOT / "docs" / "reference" / "slash-commands.md"
MAINTAINER_SLASH_REF = REPO_ROOT / "docs" / "maintainers" / "slash-commands.md"
UI_REF = REPO_ROOT / "docs" / "reference" / "ui.md"
CLAUDE_CMDS_DIR = REPO_ROOT / ".claude" / "commands"
AGENT_KIT_CMDS_DIR = REPO_ROOT / "llmwiki" / "agent_kit" / "commands"
BUILD_PY = REPO_ROOT / "llmwiki" / "build.py"


# ─── CLI coverage ─────────────────────────────────────────────────────


def _all_cli_subcommands() -> set[str]:
    """Walk the argparse tree + return every subcommand name."""

    parser = build_parser()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            return set(action.choices.keys())
    raise AssertionError("no subparsers found on the CLI parser")


def test_cli_reference_covers_every_subcommand():
    cli_text = CLI_REF.read_text(encoding="utf-8")

    # CLI reference uses `## <subcommand> — …` headings.
    documented = set(
        re.findall(r"^##\s+`([A-Za-z0-9_-]+)`\s*—", cli_text, re.MULTILINE)
    )
    live = _all_cli_subcommands()

    missing = live - documented
    assert not missing, (
        f"docs/reference/cli.md is missing entries for these shipped "
        f"subcommands: {sorted(missing)}. Add a `## \\`name\\` — …` heading."
    )

    # Warn on documented-but-removed entries (catches drift the other way).
    orphaned = documented - live
    assert not orphaned, (
        f"docs/reference/cli.md documents these subcommands but "
        f"build_parser no longer registers them: {sorted(orphaned)}"
    )


def test_every_cli_subcommand_gets_an_example():
    """Every documented subcommand section must contain at least one
    fenced-bash example — pure prose docs are useless without a
    runnable example."""
    cli_text = CLI_REF.read_text(encoding="utf-8")
    sections = re.split(
        r"^##\s+`([A-Za-z0-9_-]+)`\s*—", cli_text, flags=re.MULTILINE
    )
    # sections = [preamble, name1, body1, name2, body2, …]
    pairs = list(zip(sections[1::2], sections[2::2], strict=True))
    missing_examples: list[str] = []
    for name, body in pairs:
        # Every section must have at least one ```bash fence
        if "```bash" not in body:
            missing_examples.append(name)
    assert not missing_examples, (
        f"docs/reference/cli.md subcommand sections missing a ```bash "
        f"example: {missing_examples}"
    )


# ─── Slash command coverage ───────────────────────────────────────────


def _commands_in(folder: Path) -> set[str]:
    if not folder.is_dir():
        return set()
    return {p.stem for p in folder.glob("*.md")}


def _documented_slash_order(ref: Path) -> list[str]:
    """Slash names carrying an h3 heading in ``ref``, in page order.

    Accepts ``### /name``, ``### `/name` `` and ``### `/name <arg>` ``;
    returns the bare name (no backticks, no slash, no args).
    """
    return re.findall(
        r"^###\s+`?/([a-z][a-z0-9-]*)",
        ref.read_text(encoding="utf-8"),
        re.MULTILINE,
    )


def _documented_slashes(ref: Path) -> set[str]:
    """Set of slash names carrying an h3 heading in ``ref``."""
    return set(_documented_slash_order(ref))


def _summary_table_slash_order(ref: Path) -> list[str]:
    """Slash names listed in the `| Command | What it does |` table, in row order.

    Parsed tolerantly — every ``/wiki-…`` token inside the table block,
    regardless of column layout — so reformatting the table does not
    break the check.
    """
    names: list[str] = []
    inside = False
    for line in ref.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*Command\s*\|\s*What it does\s*\|", line):
            inside = True
            continue
        if inside:
            if not line.lstrip().startswith("|"):
                break
            names.extend(re.findall(r"/(wiki-[a-z0-9-]+)", line))
    return names


def _summary_table_slashes(ref: Path) -> set[str]:
    """Set of slash names listed in the summary table."""
    return set(_summary_table_slash_order(ref))


def test_slash_reference_covers_every_vault_command():
    missing = _commands_in(AGENT_KIT_CMDS_DIR) - _documented_slashes(SLASH_REF)
    assert not missing, (
        f"docs/reference/slash-commands.md is missing entries for these "
        f"shipped commands: {sorted(missing)}"
    )


def test_maintainer_reference_covers_every_contributor_command():
    missing = (
        _commands_in(CLAUDE_CMDS_DIR)
        - _documented_slashes(MAINTAINER_SLASH_REF)
    )
    assert not missing, (
        f"docs/maintainers/slash-commands.md is missing entries for these "
        f"contributor commands: {sorted(missing)}"
    )


def test_slash_reference_documents_only_shipped_vault_commands():
    """Reverse parity for the vault slash reference (regression for #214).

    ``/wiki-export-marp`` outlived its CLI subcommand in this doc because
    only the shipped-but-undocumented direction was asserted. Guard the
    other direction too.
    """
    orphaned = _documented_slashes(SLASH_REF) - _commands_in(AGENT_KIT_CMDS_DIR)
    assert not orphaned, (
        f"docs/reference/slash-commands.md documents these slash commands "
        f"but llmwiki/agent_kit/commands/ ships no such file: "
        f"{sorted(orphaned)}. The doc sends users to a slash command that "
        f"will not exist on their machine after `llmwiki install-agent-kit` "
        f"— drop the section or ship the command."
    )


def test_maintainer_reference_documents_only_shipped_contributor_commands():
    """Reverse parity for the maintainer slash reference (#214).

    Same shape as the vault check so neither half of the split reference
    can drift into advertising a command that no longer exists.
    """
    orphaned = (
        _documented_slashes(MAINTAINER_SLASH_REF)
        - _commands_in(CLAUDE_CMDS_DIR)
    )
    assert not orphaned, (
        f"docs/maintainers/slash-commands.md documents these slash commands "
        f"but .claude/commands/ holds no such file: {sorted(orphaned)}. The "
        f"doc points contributors at a command that will not exist — drop "
        f"the section or add the command."
    )


def test_slash_reference_summary_table_matches_sections():
    """The summary table and the `###` write-ups are two surfaces for the
    same 12 commands — keep them in step, in the same order (#214).

    The table is what carried the wrong command count when
    ``/wiki-export-marp`` was removed, so drift here is the exact failure
    mode this guards. The table also promises "in the order you meet
    them", so the sequences — not just the sets — must agree.
    """
    tabled_order = _summary_table_slash_order(SLASH_REF)
    assert tabled_order, (
        "docs/reference/slash-commands.md should carry a "
        "`| Command | What it does |` summary table"
    )
    sectioned_order = _documented_slash_order(SLASH_REF)
    tabled, sectioned = set(tabled_order), set(sectioned_order)
    assert tabled_order == sectioned_order, (
        f"docs/reference/slash-commands.md summary table and `### /…` "
        f"sections disagree — in the table only: "
        f"{sorted(tabled - sectioned)}; in the sections only: "
        f"{sorted(sectioned - tabled)}; table order: {tabled_order}; "
        f"section order: {sectioned_order}"
    )


def test_slash_reference_counts_correctly():
    """The summary at the top of the slash ref claims a total count —
    keep it honest."""
    slash_text = SLASH_REF.read_text(encoding="utf-8")
    live_count = len(_commands_in(AGENT_KIT_CMDS_DIR))
    # Look for `**N commands in` — the summary line.
    m = re.search(r"\*\*(\d+)\s+commands?\s+in", slash_text)
    assert m, "slash-commands.md should have a `**N commands in …**` summary"
    claimed = int(m.group(1))
    assert claimed == live_count, (
        f"slash-commands.md says {claimed} commands but there are "
        f"actually {live_count} .md files in llmwiki/agent_kit/commands/"
    )


# ─── UI coverage ─────────────────────────────────────────────────────


# Nav entries we declared in build.py. Adding a `{link(…)}` that isn't
# listed here will fail — update the list AND the UI reference.
EXPECTED_NAV_KEYS = {
    "home", "raw", "candidates", "graph", "projects",
    "sessions", "analytics", "docs",
}


def test_build_py_nav_keys_match_expected_set():
    """The UI reference table is ordered by these keys — if build.py
    adds or removes a link, the check below flags it so we update
    both sides of the contract."""
    src = BUILD_PY.read_text(encoding="utf-8")
    # Matches {link("…", "…", "<key>")}
    keys = set(
        re.findall(r'\{link\("[^"]+",\s*"[^"]+",\s*"([^"]+)"\)\}', src)
    )
    missing = EXPECTED_NAV_KEYS - keys
    extra = keys - EXPECTED_NAV_KEYS
    assert not missing, (
        f"build.py nav lost these keys (also update docs/reference/ui.md): {missing}"
    )
    assert not extra, (
        f"build.py nav added new keys — document them in "
        f"docs/reference/ui.md + update this test: {extra}"
    )


def test_ui_reference_lists_every_nav_item():
    ui_text = UI_REF.read_text(encoding="utf-8")
    for label in (
        "Home", "Raw", "Candidates", "Graph", "Projects", "Sessions", "Analytics",
        "Models", "Docs", "Prototypes",
    ):
        assert f"**{label}**" in ui_text, (
            f"docs/reference/ui.md missing nav entry for `{label}`"
        )


def test_ui_reference_documents_command_palette():
    ui_text = UI_REF.read_text(encoding="utf-8")
    # The palette is the most-used UI feature; guard it explicitly.
    for keyword in ("⌘K", "command palette", "fuzzy"):
        assert keyword.lower() in ui_text.lower(), (
            f"ui.md should document the command palette ({keyword})"
        )


def test_ui_reference_documents_keyboard_shortcuts():
    ui_text = UI_REF.read_text(encoding="utf-8")
    for shortcut in ("g h", "g p", "g s", "⌘K"):
        assert shortcut in ui_text, (
            f"ui.md should document keyboard shortcut `{shortcut}`"
        )


# ─── Cross-linking ───────────────────────────────────────────────────


def test_hub_links_to_all_three_new_references():
    hub = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for target in (
        "reference/cli.md",
        "reference/mcp.md",
        "reference/slash-commands.md",
        "reference/ui.md",
    ):
        assert target in hub, (
            f"docs/index.md should link to {target}"
        )
