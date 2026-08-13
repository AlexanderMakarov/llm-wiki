"""#97 candidates page: per-row decisions, and the batch Apply assembles.

Deciding is DOM state, so the page needs nothing running; only executing the
decisions is a command-line step. The tests below cover both halves — the
rendered controls in Python, and the batch the page's own script builds, run
under `node` with a stub DOM (skipped when node is absent).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki.build import render_candidates_page
from llmwiki.candidates_site import (
    _REVIEW_SCRIPT,  # noqa: PLC2701
    _VALID_ACTIONS,  # noqa: PLC2701
    apply_candidate_actions,
    apply_command_prefix,
    candidates_payload,
    cli_command_for_action,
    cli_command_for_actions,
    merge_targets,
    render_candidates_body,
    vault_display_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not on PATH"
)


def _js_block(js: str, marker: str) -> str:
    """The declaration starting at `marker`, up to its balanced closing brace."""
    start = js.index(marker)
    depth = 0
    for i in range(start, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
    raise AssertionError(f"unbalanced braces after {marker!r}")


_ROW_STUB = """
function mkRow(spec) {
  return {
    getAttribute: function (name) {
      return name === "data-slug" ? spec.slug : spec.kind;
    },
    querySelector: function (sel) {
      if (sel === ".cand-decision") return { value: spec.decision || "" };
      if (sel === ".cand-merge-into") return { value: spec.into || "" };
      if (sel === ".cand-discard-reason") return { value: spec.reason || "" };
      return null;
    }
  };
}
"""


def _collect_actions(
    specs: list[dict[str, str]],
    tmp_path: Path,
    targets: dict[str, list[str]] | None = None,
) -> dict:
    """Run the page's own `collectActions()` over `specs` under node.

    `targets` is the per-kind merge target list the page embeds; by default
    every named target is offered, so a test opts in to the unlisted case.
    """
    if targets is None:
        targets = {}
        for spec in specs:
            if spec.get("into"):
                targets.setdefault(spec["kind"], []).append(spec["into"])
    script = tmp_path / "collect.js"
    script.write_text(
        "\n".join([
            _ROW_STUB,
            f"var ROWS = {json.dumps(specs)}.map(mkRow);",
            f"var TARGETS = {json.dumps(targets)};",
            'var document = { querySelectorAll: function () { return ROWS; } };',
            _js_block(_REVIEW_SCRIPT, "function decisionOf(wrap) {"),
            _js_block(_REVIEW_SCRIPT, "function rows() {"),
            _js_block(_REVIEW_SCRIPT, "function fieldValue(wrap, sel) {"),
            _js_block(_REVIEW_SCRIPT, "function targetsFor(kind, ownSlug) {"),
            _js_block(_REVIEW_SCRIPT, "function isKnownTarget(kind, value, ownSlug) {"),
            _js_block(_REVIEW_SCRIPT, "function rowProblem(wrap) {"),
            _js_block(_REVIEW_SCRIPT, "function collectActions() {"),
            "try { console.log(JSON.stringify({ok: true, actions: collectActions()})); }",
            "catch (e) { console.log(JSON.stringify({ok: false, error: e.message})); }",
        ]),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def _filter_targets(names: list[str], query: str, tmp_path: Path) -> list[str]:
    """Run the dropdown's own `filterTargets()` over `names` under node."""
    script = tmp_path / "filter.js"
    script.write_text(
        "\n".join([
            _js_block(_REVIEW_SCRIPT, "function filterTargets(list, query) {"),
            f"console.log(JSON.stringify(filterTargets({json.dumps(names)},"
            f" {json.dumps(query)})));",
        ]),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


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
    # One field, not two: the batch goes inside the command the page emits.
    assert 'id="cand-actions"' not in html_out
    payload = candidates_payload(wiki)
    assert payload["summary"]["to_review"] == 2


def test_each_table_has_name_description_and_decision(tmp_path: Path) -> None:
    # @regression
    """Reviewing means judging a row, so every row carries a Decision cell."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "concepts", "Beta")

    html_out = render_candidates_body(wiki)

    header = "<tr><th>Name</th><th>Description</th><th>Decision</th></tr>"
    assert html_out.count(header) == 2
    assert html_out.count('class="cand-decision"') == 2
    assert html_out.count('class="cand-merge-into"') == 2
    assert html_out.count('class="cand-discard-reason"') == 2
    assert 'id="cand-apply"' in html_out


def test_decision_vocabulary_matches_what_the_cli_accepts(tmp_path: Path) -> None:
    # @regression
    """A decision the page offers that `candidates apply` rejects is a dead end."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")

    html_out = render_candidates_body(wiki)
    cell = html_out[html_out.index('class="cand-decision"'):]
    cell = cell[: cell.index("</select>")]
    offered = set(re.findall(r'<option value="([^"]*)"', cell))

    assert offered == {"", *_VALID_ACTIONS}


def test_no_row_starts_out_decided(tmp_path: Path) -> None:
    # @regression
    """A pre-filled decision turns the review gate into a rubber stamp."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "concepts", "Beta")

    html_out = render_candidates_body(wiki)

    # The first option of every select is the one a browser selects, and it
    # carries no action — so nothing is in the batch until a reviewer picks.
    for cell in html_out.split('class="cand-decision"')[1:]:
        select = cell[: cell.index("</select>")]
        first = re.search(r"<option value=\"([^\"]*)\"", select)
        assert first is not None
        assert first.group(1) == ""
        assert "selected" not in select
    assert 'id="cand-command"></pre>' in html_out


def test_the_page_reaches_no_server(tmp_path: Path) -> None:
    # @regression
    """Deciding is DOM state: nothing is posted, nothing is fetched."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")

    html_out = render_candidates_body(wiki)

    assert "fetch(" not in html_out
    assert "XMLHttpRequest" not in html_out
    assert "/api/candidates" not in html_out
    assert "https://" not in html_out


def test_merge_targets_offer_trusted_pages_then_peers(tmp_path: Path) -> None:
    """`merge --into` resolves a trusted page first, then a same-table stub."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "Existing.md").write_text("# Existing\n", encoding="utf-8")
    (wiki / "entities" / "_context.md").write_text("folder note\n", encoding="utf-8")
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "concepts", "Beta")
    rows = candidates_payload(wiki)["candidates"]

    assert merge_targets(wiki, "entities", rows) == ["Existing", "Alpha"]
    assert merge_targets(wiki, "concepts", rows) == ["Beta"]

    html_out = render_candidates_body(wiki)
    assert 'id="cand-targets-entities"' in html_out
    assert 'id="cand-targets-concepts"' in html_out


def test_every_row_gets_a_dropdown_over_the_valid_targets(tmp_path: Path) -> None:
    # @regression
    """Merge targets are picked from the offered list, not typed blind."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "Existing.md").write_text("# Existing\n", encoding="utf-8")
    _write_candidate(wiki, "entities", "Alpha")
    _write_candidate(wiki, "entities", "Beta")
    _write_candidate(wiki, "concepts", "Gamma")

    html_out = render_candidates_body(wiki)
    rows = candidates_payload(wiki)["candidates"]

    # One list per kind, holding exactly the slugs `merge --into` resolves …
    for kind in ("entities", "concepts"):
        island = re.search(
            r'<script type="application/json" class="cand-targets"'
            rf' id="cand-targets-{kind}" data-kind="{kind}">(.*?)</script>',
            html_out,
        )
        assert island is not None, kind
        assert json.loads(island.group(1)) == merge_targets(wiki, kind, rows)

    # … and every row drives its own listbox off it, openable without typing.
    assert html_out.count('role="combobox"') == 3
    assert html_out.count('class="cand-combo-open"') == 3
    list_ids = re.findall(r'aria-controls="(cand-target-list-[^"]+)"', html_out)
    assert len(set(list_ids)) == 3
    for list_id in list_ids:
        assert f'<ul class="cand-combo-list" id="{list_id}" role="listbox"' in html_out


def test_the_target_list_is_embedded_once_however_many_rows(tmp_path: Path) -> None:
    """A vault with a long backlog must not repeat the target names per row."""
    wiki = _mk_wiki(tmp_path)
    for n in range(12):
        _write_candidate(wiki, "entities", f"Cand{n}")

    html_out = render_candidates_body(wiki)

    assert html_out.count('class="cand-targets"') == 2
    # The only <option> elements left are the decisions themselves; the target
    # names live in the two lists, not once per row.
    assert html_out.count("<option ") == 12 * (len(_VALID_ACTIONS) + 1)


def test_discard_asks_for_the_reason_it_archives(tmp_path: Path) -> None:
    # @regression
    """`discard` files the reason beside the archived stub, so it is required."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")

    html_out = render_candidates_body(wiki)

    assert 'class="cand-discard-reason" type="text" aria-required="true"' in html_out
    assert 'placeholder="why it is rejected"' in html_out
    assert "optional" not in html_out


def test_render_candidates_body_command_names_the_vault(tmp_path: Path) -> None:
    # @regression
    """Without --vault the printed command only ever hits the default vault."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")

    html_out = render_candidates_body(wiki)

    vault = vault_display_path(wiki)
    # The prefix is injected into the page script as a JSON string literal;
    # Apply appends the shell-quoted batch to it.
    assert json.dumps(apply_command_prefix(vault)) in html_out
    assert vault in html_out


def test_apply_command_prefix_names_the_vault_and_stops_before_the_batch() -> None:
    """The page appends the shell-quoted batch, so a reviewer copies one line."""
    assert apply_command_prefix("demo") == "llmwiki candidates apply --vault 'demo'"


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


def test_render_candidates_body_prints_the_command_it_hands_off_to(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha")
    html_out = render_candidates_body(wiki)
    assert "candidates apply" in html_out
    # The command element is filled by Apply, not pre-rendered: the batch is
    # only known once a reviewer has decided something.
    assert 'id="cand-command"></pre>' in html_out
    assert apply_command_prefix(vault_display_path(wiki)).split(" --vault ")[0] in html_out


# ─── the batch Apply assembles ───────────────────────────────────────────


@needs_node
def test_apply_batches_only_the_rows_a_reviewer_decided(tmp_path: Path) -> None:
    # @regression
    """A row left at "No decision" is absent from the batch and stays pending."""
    out = _collect_actions([
        {"slug": "Alpha", "kind": "entities", "decision": "promote"},
        {"slug": "Untouched", "kind": "entities", "decision": ""},
        {"slug": "Beta", "kind": "concepts", "decision": "flip-promote"},
        {"slug": "AlsoUntouched", "kind": "concepts", "decision": ""},
    ], tmp_path)

    assert out["ok"], out.get("error")
    assert out["actions"] == [
        {"action": "promote", "slug": "Alpha", "kind": "entities"},
        {"action": "flip-promote", "slug": "Beta", "kind": "concepts"},
    ]


@needs_node
def test_apply_carries_the_field_each_action_needs(tmp_path: Path) -> None:
    out = _collect_actions([
        {"slug": "Dupe", "kind": "entities", "decision": "merge", "into": "Target"},
        {"slug": "Noise", "kind": "entities", "decision": "discard", "reason": "junk"},
        {"slug": "Quiet", "kind": "concepts", "decision": "discard", "reason": "off topic"},
    ], tmp_path)

    assert out["ok"], out.get("error")
    assert out["actions"] == [
        {"action": "merge", "slug": "Dupe", "kind": "entities", "into": "Target"},
        {"action": "discard", "slug": "Noise", "kind": "entities", "reason": "junk"},
        {"action": "discard", "slug": "Quiet", "kind": "concepts", "reason": "off topic"},
    ]


@needs_node
def test_apply_refuses_a_merge_with_no_target(tmp_path: Path) -> None:
    out = _collect_actions([
        {"slug": "Dupe", "kind": "entities", "decision": "merge"},
    ], tmp_path)
    assert not out["ok"]
    assert "Dupe" in out["error"]


@needs_node
def test_typing_narrows_the_targets_case_insensitively(tmp_path: Path) -> None:
    names = ["Claude Code", "Codex CLI", "Obsidian", "Prompt Caching"]

    assert _filter_targets(names, "", tmp_path) == names
    assert _filter_targets(names, "codex", tmp_path) == ["Codex CLI"]
    assert _filter_targets(names, "CODEX", tmp_path) == ["Codex CLI"]
    assert _filter_targets(names, "cod", tmp_path) == ["Claude Code", "Codex CLI"]
    assert _filter_targets(names, "  caching  ", tmp_path) == ["Prompt Caching"]
    assert _filter_targets(names, "zzz", tmp_path) == []


@needs_node
def test_apply_refuses_a_merge_into_a_page_that_is_not_offered(tmp_path: Path) -> None:
    # @regression
    """An unlisted target fails at the CLI, so it never reaches the batch."""
    specs = [
        {"slug": "Alpha", "kind": "entities", "decision": "promote"},
        {"slug": "Dupe", "kind": "entities", "decision": "merge", "into": "Typo"},
        {"slug": "Untouched", "kind": "entities", "decision": ""},
    ]

    out = _collect_actions(specs, tmp_path, targets={"entities": ["Target"]})

    assert not out["ok"]
    assert "Dupe" in out["error"]
    assert "Typo" in out["error"]

    # Choosing an offered page is all it takes.
    specs[1]["into"] = "Target"
    fixed = _collect_actions(specs, tmp_path, targets={"entities": ["Target"]})
    assert fixed["ok"], fixed.get("error")
    assert fixed["actions"] == [
        {"action": "promote", "slug": "Alpha", "kind": "entities"},
        {"action": "merge", "slug": "Dupe", "kind": "entities", "into": "Target"},
    ]


@needs_node
def test_apply_refuses_a_discard_with_no_reason(tmp_path: Path) -> None:
    # @regression
    """The reason is archived beside the stub — a blank one loses the decision."""
    out = _collect_actions([
        {"slug": "Alpha", "kind": "entities", "decision": "promote"},
        {"slug": "Noise", "kind": "entities", "decision": "discard"},
    ], tmp_path)

    assert not out["ok"]
    assert "Noise" in out["error"]
    assert "reason" in out["error"]


@needs_node
def test_apply_refuses_an_empty_batch(tmp_path: Path) -> None:
    out = _collect_actions([
        {"slug": "Alpha", "kind": "entities", "decision": ""},
    ], tmp_path)
    assert not out["ok"]
    assert "Decision" in out["error"]


@needs_node
def test_the_assembled_batch_is_what_apply_executes(tmp_path: Path) -> None:
    # @regression
    """End to end: the page's own batch runs through the apply path unedited."""
    wiki = _mk_wiki(tmp_path)
    for slug in ("Keep", "Drop", "Dupe", "Target"):
        _write_candidate(wiki, "entities", slug)

    out = _collect_actions([
        {"slug": "Keep", "kind": "entities", "decision": "promote"},
        {"slug": "Skipped", "kind": "entities", "decision": ""},
        {"slug": "Drop", "kind": "entities", "decision": "discard", "reason": "noise"},
        {"slug": "Target", "kind": "entities", "decision": "promote"},
        {"slug": "Dupe", "kind": "entities", "decision": "merge", "into": "Target"},
    ], tmp_path)
    assert out["ok"], out.get("error")

    # The batch the page prints is the batch the CLI validates.
    assert cli_command_for_actions(out["actions"], vault="demo").startswith(
        "llmwiki candidates apply --vault 'demo' --actions '"
    )
    results = apply_candidate_actions(wiki, out["actions"])

    assert all(r["ok"] for r in results), results
    assert (wiki / "entities" / "Keep.md").is_file()
    assert (wiki / "entities" / "Target.md").is_file()
    assert not (wiki / "candidates" / "entities" / "Drop.md").exists()
    assert not (wiki / "candidates" / "entities" / "Dupe.md").exists()


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
    assert "cand-command" in text
    assert 'class="nav' in text or "candidates.html" in text
