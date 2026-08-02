"""#97 candidates review page + serve batch API."""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from llmwiki.build import render_candidates_page
from llmwiki.candidates_site import (
    apply_candidate_actions,
    candidates_payload,
    cli_command_for_action,
    cli_command_for_actions,
    render_candidates_body,
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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_accepting(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def test_render_candidates_body_intent_and_apply(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "concepts", "Beta")

    html_out = render_candidates_body(wiki)

    assert "cand-table-entities" in html_out
    assert "cand-table-concepts" in html_out
    assert "cand-decision" in html_out
    assert 'id="cand-apply"' in html_out
    assert "Flip and promote" in html_out
    assert "cand-merge-into" in html_out
    assert "/api/candidates" in html_out
    assert "Copy CLI" in html_out
    assert "Alpha" in html_out
    assert "Beta" in html_out
    # No per-row action buttons anymore.
    assert 'data-action="promote"' not in html_out
    payload = candidates_payload(wiki)
    assert payload["summary"]["to_review"] == 2


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


def test_render_candidates_body_emits_apply_actions_cli(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    html_out = render_candidates_body(wiki)
    assert "candidates apply --actions" in html_out
    assert "cliForBatch" in html_out


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
    assert "cand-apply" in text
    assert 'class="nav' in text or "candidates.html" in text


def test_serve_api_batch_promote_round_trip(tmp_path: Path) -> None:
    """POST /api/candidates with actions[] promote with sibling wiki/."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "PromoMe")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    render_candidates_page(wiki, site)

    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "llmwiki", "serve",
            "--dir", str(site),
            "--port", str(port),
            "--host", "127.0.0.1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
    )
    try:
        assert _wait_until_accepting(port), f"serve did not bind :{port}"
        body = json.dumps({
            "actions": [
                {"action": "promote", "slug": "PromoMe", "kind": "entities"},
            ],
        }).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/candidates",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        conn.close()
        assert resp.status == 200, raw
        data = json.loads(raw)
        assert data.get("ok") is True
        assert data["results"][0]["ok"] is True
        assert data["summary"]["to_review"] == 0
        assert (wiki / "entities" / "PromoMe.md").is_file()
        assert not (wiki / "candidates" / "entities" / "PromoMe.md").exists()
    finally:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
