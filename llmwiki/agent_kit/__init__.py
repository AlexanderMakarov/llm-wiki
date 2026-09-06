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

# Dest-relative posix paths the kit no longer ships, each mapped to the
# sha256 digests of every revision llmwiki authored for that path.
# ``install-agent-kit`` deletes such a file only when its content still
# hashes to one of these, so an agent directory populated by an older
# install stops offering retired commands while anything else at the same
# name — a user's own file, or a customised copy — is left alone.
RETIRED_PATHS: dict[str, frozenset[str]] = {
    "commands/wiki-export-marp.md": frozenset(
        {"9b19ceb4215f31c1f13594fc7df89cb8c7652ec025b324e79cbdd15c56b59d80"}
    ),
    "commands/wiki-synthesize.md": frozenset(
        {
            "4bd59c443f5f848ab143e891c19e4c1a638f8326974cc5aceb6be03da159c3b7",
            "26eb59910f3a6903c21bea59cca2c7256ae6a5faa12f755553371a9706c5a927",
            "283a8e6f90915ce193cbec0b65950c2d6c1415e9b7e96f85513de3123c94ef1f",
            "4fdaa1a4296feb774ecbed40f830889ba112afe7f7191aacb3e03771dc74b279",
            "fa3595550e73a84f5b76188f60830757c69391213d190c9dcf77639b09cb5bf2",
        }
    ),
}
