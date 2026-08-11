"""#97 candidates page + the command line it hands off to."""

from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

from llmwiki.build import render_candidates_page
from llmwiki.candidates_site import (
    actions_template,
    apply_candidate_actions,
    candidates_payload,
    cli_command_for_action,
    cli_command_for_actions,
    render_candidates_body,
    vault_display_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _mk_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    for kind in ("entities", "concepts"):
        (wiki / kind).mkdir(parents=True, exist_ok=True)
        (wiki / "candidates" / kind).mkdir(parents=True, exist_ok=True)
    return wiki


def _write_candidate(wiki: Path, kind: str, slug: str, *, body: str = "") -> Path:
    path = wiki / "candidates" / kind / f"{slug}.md"
    body_text = body or f"# {slug}\n\nShort blurb about {slug}."
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: {kind[:-1]}\nstatus: candidate\n'
        f"last_updated: 2026-04-17\n---\n\n{body_text}\n",
        encoding="utf-8",
    )
    return path


def test_render_candidates_body_lists_pending_and_offers_the_batch(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "concepts", "Beta")

    html_out = render_candidates_body(wiki)

    assert "cand-table-entities" in html_out
    assert "cand-table-concepts" in html_out
    assert "Alpha" in html_out
    assert "Beta" in html_out
    assert 'id="cand-command"' in html_out
    assert 'id="cand-actions"' in html_out
    payload = candidates_payload(wiki)
    assert payload["summary"]["to_review"] == 2


def test_render_candidates_body_offers_no_controls_it_cannot_honour(tmp_path: Path) -> None:
    # @regression
    """The page is a listing: no decision widgets, no requests of any kind."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")

    html_out = render_candidates_body(wiki)

    assert "fetch(" not in html_out
    assert "/api/candidates" not in html_out
    assert "cand-decision" not in html_out
    assert "cand-merge-into" not in html_out
    assert 'id="cand-apply"' not in html_out


def test_render_candidates_body_command_names_the_vault(tmp_path: Path) -> None:
    # @regression
    """Without --vault the printed command only ever hits the default vault."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")

    html_out = render_candidates_body(wiki)

    vault = vault_display_path(wiki)
    assert f"llmwiki candidates apply --vault &#x27;{vault}&#x27; --actions -" in html_out


def test_actions_template_covers_every_listed_candidate(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "concepts", "Beta")

    rows = candidates_payload(wiki)["candidates"]
    batch = actions_template(rows)

    assert {a["slug"] for a in batch} == {"Alpha", "Beta"}
    assert {a["action"] for a in batch} == {"promote"}
    assert {a["kind"] for a in batch} == {"entities", "concepts"}


def test_vault_display_path_is_relative_when_the_vault_is_under_cwd(
    tmp_path: Path, monkeypatch,
) -> None:
    """A relative value is what the operator typed and is machine-independent."""
    vault = tmp_path / "demo"
    (vault / "wiki").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert vault_display_path(vault / "wiki") == "demo"


def test_cli_command_for_action_shapes() -> None:
    assert cli_command_for_action({
        "action": "promote", "slug": "Foo", "kind": "entities",
    }) == "llmwiki candidates promote --slug 'Foo' --kind entities"
    assert "flip-promote" in cli_command_for_action({
        "action": "flip-promote", "slug": "Bar", "kind": "concepts",
    })
    assert "--into 'Baz'" in cli_command_for_action({
        "action": "merge", "slug": "Dup", "into": "Baz", "kind": "entities",
    })


def test_cli_command_for_actions_batch_one_line() -> None:
    cmd = cli_command_for_actions([
        {"action": "promote", "slug": "Obsidian", "kind": "entities"},
        {"action": "promote", "slug": "Prompt Caching", "kind": "concepts"},
    ])
    assert cmd.startswith("llmwiki candidates apply --actions '")
    assert "Prompt Caching" in cmd
    assert "\n" not in cmd
    # Payload is valid JSON when unquoted.
    start = cmd.index("'") + 1
    end = cmd.rindex("'")
    payload = json.loads(cmd[start:end])
    assert len(payload) == 2
    assert payload[0]["slug"] == "Obsidian"


def test_apply_candidate_actions_batch(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Keep")
    _write_candidate(wiki, "entities", "Drop")
    results = apply_candidate_actions(wiki, [
        {"action": "promote", "slug": "Keep", "kind": "entities"},
        {"action": "discard", "slug": "Drop", "kind": "entities"},
    ])
    assert all(r["ok"] for r in results)
    assert (wiki / "entities" / "Keep.md").is_file()
    assert not (wiki / "candidates" / "entities" / "Keep.md").exists()
    assert not (wiki / "candidates" / "entities" / "Drop.md").exists()


def test_cli_candidates_apply_batch(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Keep")
    _write_candidate(wiki, "entities", "Drop")
    payload = json.dumps([
        {"action": "promote", "slug": "Keep", "kind": "entities"},
        {"action": "discard", "slug": "Drop", "kind": "entities"},
    ])
    proc = subprocess.run(
        [
            sys.executable, "-m", "llmwiki", "candidates", "apply",
            "--actions", payload,
            "--wiki-dir", str(wiki),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (wiki / "entities" / "Keep.md").is_file()
    assert not (wiki / "candidates" / "entities" / "Drop.md").exists()


def test_render_candidates_body_emits_a_pasteable_json_batch(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    html_out = render_candidates_body(wiki)
    assert "candidates apply" in html_out
    assert "--actions -" in html_out
    start = html_out.index('id="cand-actions">') + len('id="cand-actions">')
    batch = json.loads(
        html.unescape(html_out[start:html_out.index("</pre>", start)])
    )
    assert batch == [{"action": "promote", "slug": "Alpha", "kind": "entities"}]


def test_candidate_description_truncates(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    long = "word " * 80
    _write_candidate(wiki, "entities", "LongOne", body=f"# LongOne\n\n{long}")
    rows = candidates_payload(wiki)["candidates"]
    desc = rows[0]["description"]
    assert desc.endswith("…")
    assert len(desc) <= 160


def test_render_candidates_page_writes_html(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Gamma")
    out = tmp_path / "site"
    out.mkdir()
    path = render_candidates_page(wiki, out)
    assert path == out / "candidates.html"
    text = path.read_text(encoding="utf-8")
    assert "Gamma" in text
    assert "cand-actions" in text
    assert 'class="nav' in text or "candidates.html" in text
