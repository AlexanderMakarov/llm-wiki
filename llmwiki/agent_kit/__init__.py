"""Packaged user-facing agent commands and skills (#109).

Slash commands live in ``commands/`` and skills in ``skills/``. They ship
inside the installable package so a pip or Homebrew install can copy them
into any agent directory with ``llmwiki install-agent-kit --dest PATH``.
Contributor-only commands and skills stay in the source checkout's
``.claude/`` tree and are not part of this kit.
"""

from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent
COMMANDS_DIR = KIT_ROOT / "commands"
SKILLS_DIR = KIT_ROOT / "skills"
