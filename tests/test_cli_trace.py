"""CLI surface for ``llmwiki trace`` (#122).

Focused parser + ``cmd_trace`` tests against a tmp vault — matches the
walker chain on stdout and exit codes for unresolvable vs partial miss.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.cli import build_parser, cmd_trace
from llmwiki.trace import trace_page


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True)
    return vault


def test_parser_registers_trace_with_vault() -> None:
    args = build_parser().parse_args(
        ["trace", "Demo", "--vault", "/tmp/example-vault"],
    )
    assert args.func is cmd_trace
    assert args.page == "Demo"
    assert args.vault == Path("/tmp/example-vault")


def test_cmd_trace_prints_full_chain(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    _write(
        vault / "raw" / "sessions" / "kickoff.md",
        '---\ntitle: "Kickoff transcript"\n---\n\nbody\n',
    )
    _write(
        vault / "wiki" / "sources" / "kickoff.md",
        (
            '---\ntitle: "Kickoff session"\ntype: source\n'
            "source_file: raw/sessions/kickoff.md\n---\n\n## Summary\n\nok\n"
        ),
    )
    _write(
        vault / "wiki" / "entities" / "Demo.md",
        (
            '---\ntitle: "Demo"\ntype: entity\nsources: [kickoff]\n'
            "---\n\n# Demo\n"
        ),
    )

    args = build_parser().parse_args(
        ["trace", "wiki/entities/Demo.md", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out

    assert rc == 0
    walker = trace_page(vault, "wiki/entities/Demo.md")
    for hop in walker.hops:
        assert hop.role in out
        assert hop.title in out
        assert hop.location in out
    assert "body" not in out
    assert "(missing)" not in out


def test_cmd_trace_exit_0_on_missing_hop(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "Orphan.md",
        (
            '---\ntitle: "Orphan"\ntype: entity\n'
            "sources: [gone-slug]\n---\n\n# Orphan\n"
        ),
    )

    args = build_parser().parse_args(
        ["trace", "Orphan", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "(missing)" in out
    assert "gone-slug" in out


def test_cmd_trace_exit_1_when_page_missing(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    _write(vault / "wiki" / "index.md", "# Wiki Index\n")

    args = build_parser().parse_args(
        ["trace", "DoesNotExist", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    err = capsys.readouterr().err

    assert rc == 1
    assert "error:" in err
    assert "page not found" in err


def test_cmd_trace_no_provenance_note(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "Bare.md",
        '---\ntitle: "Bare"\ntype: entity\n---\n\n# Bare\n',
    )

    args = build_parser().parse_args(
        ["trace", "Bare", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "wiki/entities/Bare.md" in out
    assert "(no further provenance)" in out
