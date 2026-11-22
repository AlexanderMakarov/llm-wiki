"""Static candidates review page + JSON payload helpers (#97).

Build emits ``site/candidates.html``: two tables (entities, concepts) with a
**Decision** control on every row — promote, flip-promote, merge into a named
page, or discard with a reason (optionally redirecting its links to an
existing page). A separate **Possible duplicate pages** section (#365) lists
live curated/project pairs with merge / keep-distinct controls. Decisions are
DOM state, so the page needs nothing running. **Apply** assembles the chosen
rows (stubs + pairs) into a ready-to-paste
``llmwiki candidates apply --vault … --actions -`` command plus the JSON batch
to pipe into it. Rows left at "No decision" stay out of the batch and stay
pending.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from llmwiki.candidates import (
    Candidate,
    DiscardBatch,
    DiscardResult,
    KeyFactsBackendError,
    candidate_review_summary,
    discard,
    flip_and_promote,
    list_candidates,
    merge,
    promote,
)
from llmwiki.candidates_near_match import (
    format_dismissal_reason,
    reuse_discard_reason,
)
from llmwiki.dismissal_ledger import ledger_path, upsert_keep_distinct
from llmwiki.page_merge import merge_pages
from llmwiki.synth.base import BaseSynthesizer
from llmwiki.topics import (
    DuplicatePagePair,
    DuplicatePageSide,
    detect_duplicate_pairs,
    topic_slug,
)
from llmwiki.wikilinks import norm_page_key

_HEADING_RE = re.compile(r"^#+\s+.*$", re.MULTILINE)

#: Harvest-stub review verbs (Decision column on pending rows; require ``slug``).
_STUB_ACTIONS = frozenset({"promote", "flip-promote", "discard", "merge"})
#: Live curated-page verbs (#365); use ``from``/``into`` or ``a``/``b``, not stub ``slug``.
_PAGE_ACTIONS = frozenset({"merge-pages", "keep-distinct"})
_VALID_ACTIONS = _STUB_ACTIONS | _PAGE_ACTIONS
# Stub actions that conflict with a stub ``merge`` target slug in the same batch.
_BATCH_PEER_ACTIONS = _STUB_ACTIONS


def check_redirect_action(action: str, redirect: str, *, where: str = "") -> None:
    """Refuse a ``redirect`` on any action but ``discard``.

    Only a discard has links to move, so a redirect anywhere else is a
    mistake the caller should hear about rather than a field to drop. Shared
    by the one-off CLI line, the batch line, and batch validation so all
    three refuse the same combination.
    """
    if redirect and action != "discard":
        prefix = f"{where}: " if where else ""
        raise ValueError(
            f"{prefix}redirect applies only to discard, not {action!r}"
        )


def candidate_description(cand: Candidate) -> str:
    """Short prose for the Description column — enough to decide without opening the file."""
    preview = (cand.get("body_preview") or "").strip()
    preview = _HEADING_RE.sub("", preview).strip()
    preview = re.sub(r"\n{2,}", " ", preview)
    preview = re.sub(r"\s+", " ", preview).strip()
    if not preview:
        return "(no description yet — see evidence under ## Connections)"
    if len(preview) > 160:
        return preview[:157].rstrip() + "…"
    return preview


def _duplicate_page_href(kind: str, title: str, slug: str) -> str:
    """Site-root-relative URL for one side of a duplicate pair.

    Projects compile under ``projects/``; entities and concepts surface as
    topic pages under ``topics/``.
    """
    if kind == "projects":
        return f"projects/{slug}.html"
    return f"topics/{topic_slug(title or slug)}.html"


def duplicate_pair_payload(pair: DuplicatePagePair) -> dict[str, Any]:
    """JSON shape for one suspected duplicate pair on the review page / API."""

    def _side(side: DuplicatePageSide) -> dict[str, Any]:
        return {
            "title": side.title,
            "kind": side.kind,
            "slug": side.slug,
            "path": side.path,
            "session_count": side.session_count,
            "href": _duplicate_page_href(side.kind, side.title, side.slug),
        }

    return {
        "a": _side(pair.a),
        "b": _side(pair.b),
        "description": pair.description,
        "suspicion": pair.suspicion,
        "paths": sorted(pair.paths),
    }


def candidates_payload(wiki_dir: Path) -> dict[str, Any]:
    """JSON-serialisable list + summary for the review page / API responses.

    Near-match annotations come from :func:`list_candidates` (``prior_dismissals``);
    the page does not re-match dismissals in the browser. ``duplicate_pairs``
    comes from :func:`detect_duplicate_pairs` (#365).
    """
    items = list_candidates(wiki_dir)
    rows = []
    for c in items:
        row: dict[str, Any] = {
            "slug": c["slug"],
            "kind": c["kind"],
            "title": c["title"],
            "age_days": c["age_days"],
            "created": c["created"],
            "description": candidate_description(c),
        }
        priors = c.get("prior_dismissals") or (
            [c["prior_dismissal"]] if c.get("prior_dismissal") else []
        )
        if priors:
            row["prior_dismissals"] = [
                {
                    "name": p["name"],
                    "reason": p["reason"],
                    "ratio": p["ratio"],
                }
                for p in priors
            ]
            row["prior_dismissal"] = row["prior_dismissals"][0]
        rows.append(row)
    pairs = [duplicate_pair_payload(p) for p in detect_duplicate_pairs(wiki_dir)]
    return {
        "candidates": rows,
        "duplicate_pairs": pairs,
        "summary": candidate_review_summary(wiki_dir),
    }


def _shell_single_quote(s: str) -> str:
    """Quote ``s`` for POSIX shells (safe inside single quotes)."""
    return "'" + s.replace("'", "'\\''") + "'"


def cli_command_for_action(item: dict[str, Any]) -> str:
    """One shell line for a single review intent (legacy one-off CLI).

    Live-page verbs (``merge-pages``, ``keep-distinct``) have no one-off
    subcommand — use :func:`cli_command_for_actions` / ``candidates apply``.
    """
    action = str(item.get("action") or "").strip()
    if not action:
        raise ValueError("action is required")
    if action not in _VALID_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    if action in _PAGE_ACTIONS:
        raise ValueError(
            f"{action} is only valid in a candidates apply batch"
        )
    slug = str(item.get("slug") or "").strip()
    kind = str(item.get("kind") or "").strip()
    into = str(item.get("into") or "").strip()
    reason = str(item.get("reason") or "").strip()
    redirect = str(item.get("redirect") or "").strip()
    if not slug:
        raise ValueError("action and slug are required")
    check_redirect_action(action, redirect)
    kind_flag = f" --kind {kind}" if kind else ""
    if action == "promote":
        return f"llmwiki candidates promote --slug {_shell_single_quote(slug)}{kind_flag}"
    if action == "flip-promote":
        return (
            f"llmwiki candidates flip-promote --slug {_shell_single_quote(slug)}"
            f"{kind_flag}"
        )
    if action == "discard":
        reason_flag = (
            f" --reason {_shell_single_quote(reason)}" if reason else ""
        )
        redirect_flag = (
            f" --redirect {_shell_single_quote(redirect)}" if redirect else ""
        )
        return (
            f"llmwiki candidates discard --slug {_shell_single_quote(slug)}"
            f"{kind_flag}{reason_flag}{redirect_flag}"
        )
    if not into:
        raise ValueError("merge requires into")
    return (
        f"llmwiki candidates merge --slug {_shell_single_quote(slug)}"
        f" --into {_shell_single_quote(into)}{kind_flag}"
    )


def _validate_batch_action_fields(item: dict[str, Any]) -> None:
    """Refuse a single batch row with unknown action or missing required fields."""
    action = str(item.get("action") or "").strip()
    if action not in _VALID_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    if action == "merge-pages":
        if not str(item.get("from") or "").strip():
            raise ValueError("merge-pages requires from")
        if not str(item.get("into") or "").strip():
            raise ValueError("merge-pages requires into")
    elif action == "keep-distinct":
        if not str(item.get("a") or "").strip():
            raise ValueError("keep-distinct requires a")
        if not str(item.get("b") or "").strip():
            raise ValueError("keep-distinct requires b")
    else:
        if not str(item.get("slug") or "").strip():
            raise ValueError("slug is required")
        if action == "merge" and not str(item.get("into") or "").strip():
            raise ValueError("merge requires into")
    check_redirect_action(action, str(item.get("redirect") or "").strip())


def cli_command_for_actions(
    actions: list[dict[str, Any]], *, vault: str | None = None,
) -> str:
    """One pasteable ``candidates apply --actions`` line for a batch.

    ``vault`` names the knowledge base the batch applies to; omit it only
    when the caller has already selected one another way. Empty list raises.
    Stub rows need ``slug``; ``merge-pages`` / ``keep-distinct`` do not.
    """
    if not actions:
        raise ValueError("actions must be non-empty")
    # Validate each item the same way one-offs are validated.
    for item in actions:
        if not isinstance(item, dict):
            raise ValueError("each action must be an object")
        _validate_batch_action_fields(item)
    payload = json.dumps(actions, ensure_ascii=False, separators=(",", ":"))
    vault_flag = f" --vault {_shell_single_quote(vault)}" if vault else ""
    return f"llmwiki candidates apply{vault_flag} --actions {_shell_single_quote(payload)}"


def vault_display_path(wiki_dir: Path | None) -> str:
    """The ``--vault`` value to print for the knowledge base holding ``wiki_dir``.

    Relative to the current directory when the vault sits under it — that is
    the form the operator typed (``--vault demo``) and it is identical on
    every machine — and absolute otherwise.
    """
    if wiki_dir is None:
        return "."
    root = wiki_dir.parent
    try:
        rel = root.resolve().relative_to(Path.cwd().resolve())
    except (ValueError, OSError):
        return str(root)
    return str(rel) if str(rel) != "." else "."


def _norm_pair_identity(left: str, right: str) -> frozenset[str] | None:
    """Unordered ``norm_page_key`` pair, or ``None`` when either side is empty/same."""
    a, b = norm_page_key(left), norm_page_key(right)
    if not a or not b or a == b:
        return None
    return frozenset({a, b})


def validate_candidate_batch(actions: list[dict[str, Any]]) -> None:
    """Refuse a batch before mutation when it cannot run as written.

    A ``redirect`` on any row but a ``discard`` is refused. A stub ``merge`` with
    ``into=T`` conflicts with another row whose ``slug`` is ``T`` and whose
    ``action`` is promote, flip-promote, discard, or merge. Slugs and ``into``
    values for stub merge are normalised the same way ``apply`` passes them to
    ``merge()`` — stripped strings, exact match.

    Live-page rows (#365): ``merge-pages`` and ``keep-distinct`` on the same
    unordered pair conflict; two ``merge-pages`` rows conflict when they share a
    loser, or when a page is both a loser and a survivor in the batch (conflicting
    chain). Pair identity uses :func:`norm_page_key`.
    """
    merge_page_rows: list[tuple[int, str, str, str, str, frozenset[str]]] = []
    keep_distinct_rows: list[tuple[int, str, str, frozenset[str]]] = []

    for i, raw in enumerate(actions):
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("action") or "").strip()
        check_redirect_action(
            action, str(raw.get("redirect") or "").strip(), where=f"batch row {i}",
        )
        if action == "merge":
            merge_slug = str(raw.get("slug") or "").strip()
            into = str(raw.get("into") or "").strip()
            if not merge_slug or not into:
                continue
            for j, other in enumerate(actions):
                if i == j or not isinstance(other, dict):
                    continue
                other_action = str(other.get("action") or "").strip()
                other_slug = str(other.get("slug") or "").strip()
                if other_slug != into or other_action not in _BATCH_PEER_ACTIONS:
                    continue
                raise ValueError(
                    f"batch conflict: merge {merge_slug!r} into {into!r} "
                    f"conflicts with {other_action} {other_slug!r} in the same batch"
                )
            continue
        if action == "merge-pages":
            from_name = str(raw.get("from") or "").strip()
            into = str(raw.get("into") or "").strip()
            pair = _norm_pair_identity(from_name, into)
            if pair is None:
                continue
            from_key, into_key = norm_page_key(from_name), norm_page_key(into)
            merge_page_rows.append(
                (i, from_name, into, from_key, into_key, pair),
            )
            continue
        if action == "keep-distinct":
            a = str(raw.get("a") or "").strip()
            b = str(raw.get("b") or "").strip()
            pair = _norm_pair_identity(a, b)
            if pair is None:
                continue
            keep_distinct_rows.append((i, a, b, pair))

    for _mi, from_name, into, _fk, _ik, mpair in merge_page_rows:
        for _ki, a, b, kpair in keep_distinct_rows:
            if mpair != kpair:
                continue
            raise ValueError(
                f"batch conflict: merge-pages {from_name!r} into {into!r} "
                f"conflicts with keep-distinct {a!r} / {b!r} in the same batch"
            )

    # Conflicting merge-pages chains: same loser twice, or a page both loser and survivor.
    loser_to_survivor: dict[str, tuple[str, str, str]] = {}
    survivor_keys: set[str] = set()
    for _i, from_name, into, from_key, into_key, _pair in merge_page_rows:
        prior = loser_to_survivor.get(from_key)
        if prior is not None and prior[0] != into_key:
            raise ValueError(
                f"batch conflict: merge-pages {from_name!r} into {into!r} "
                f"conflicts with merge-pages {prior[1]!r} into {prior[2]!r} "
                f"(same loser, different survivors)"
            )
        if prior is None:
            loser_to_survivor[from_key] = (into_key, from_name, into)
        survivor_keys.add(into_key)

    for _i, from_name, into, from_key, into_key, _pair in merge_page_rows:
        if from_key not in survivor_keys and into_key not in loser_to_survivor:
            continue
        raise ValueError(
            f"batch conflict: merge-pages {from_name!r} into {into!r} "
            f"conflicts with another merge-pages row "
            f"(page is both loser and survivor in the same batch)"
        )


def apply_candidate_actions(
    wiki_dir: Path,
    actions: list[dict[str, Any]],
    *,
    synthesizer: BaseSynthesizer | None = None,
) -> list[dict[str, Any]]:
    """Run a batch of review actions in order. Returns one result dict per item.

    Each result is ``{"ok": True, "slug": …, "action": …, "path": …}`` or
    ``{"ok": False, "slug": …, "action": …, "error": …}``. Processing continues
    after failures so one bad row does not hide the rest. For ``merge-pages``,
    ``slug`` is the loser (``from``); for ``keep-distinct``, ``slug`` is
    ``a|b``.

    Raises ``ValueError`` before any mutation when :func:`validate_candidate_batch`
    finds a stub merge target that another row in the batch also promotes,
    flip-promotes, discards, or merges away, or a live-page
    ``merge-pages`` / ``keep-distinct`` conflict (#365).

    Every discard in the batch shares one :class:`DiscardBatch`, so the wiki
    is scanned once for the live-page index and rewritten once for all their
    links instead of twice per row. Each row still reports its own link count
    and changed pages, filled in when the shared pass runs.
    """
    validate_candidate_batch(actions)
    results: list[dict[str, Any]] = []
    batch: DiscardBatch | None = None
    discarded: list[tuple[dict[str, Any], DiscardResult]] = []
    for raw in actions:
        if not isinstance(raw, dict):
            results.append({
                "ok": False, "slug": "", "action": "",
                "error": "each action must be an object",
            })
            continue
        action = str(raw.get("action") or "").strip()
        slug = str(raw.get("slug") or "").strip()
        kind = raw.get("kind")
        kind_s = str(kind).strip() if kind else None
        into = str(raw.get("into") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        redirect = str(raw.get("redirect") or "").strip() or None
        entry: dict[str, Any] = {"ok": False, "slug": slug, "action": action}
        try:
            if action not in _VALID_ACTIONS:
                raise ValueError(f"unknown action {action!r}")
            if action == "merge-pages":
                from_name = str(raw.get("from") or "").strip()
                if not from_name or not into:
                    raise ValueError("merge-pages requires from and into")
                entry["slug"] = from_name
                path = merge_pages(from_name, wiki_dir, into=into)
            elif action == "keep-distinct":
                a = str(raw.get("a") or "").strip()
                b = str(raw.get("b") or "").strip()
                why = str(raw.get("why") or "").strip()
                if not a or not b:
                    raise ValueError("keep-distinct requires a and b")
                entry["slug"] = f"{a}|{b}"
                upsert_keep_distinct(wiki_dir, a=a, b=b, why=why)
                path = ledger_path(wiki_dir)
            elif not slug:
                raise ValueError("slug is required")
            elif action == "promote":
                path = promote(slug, wiki_dir, kind=kind_s, synthesizer=synthesizer)
            elif action == "flip-promote":
                path = flip_and_promote(
                    slug, wiki_dir, kind=kind_s, synthesizer=synthesizer,
                )
            elif action == "discard":
                if batch is None:
                    batch = DiscardBatch(wiki_dir)
                result = discard(
                    slug, wiki_dir, reason=reason, kind=kind_s, redirect=redirect,
                    batch=batch,
                )
                path = result.path
                discarded.append((entry, result))
                if result.redirect:
                    entry["redirect"] = result.redirect
            else:
                if not into:
                    raise ValueError("merge requires into")
                path = merge(slug, wiki_dir, into_slug=into, kind=kind_s)
            entry["ok"] = True
            entry["path"] = str(path)
        except (
            FileNotFoundError,
            FileExistsError,
            ValueError,
            KeyFactsBackendError,
            OSError,
        ) as exc:
            entry["error"] = str(exc)
        results.append(entry)
    if batch is not None:
        batch.flush()
        for entry, result in discarded:
            entry["links_rewritten"] = result.links_rewritten
            if result.skipped:
                entry["skipped"] = list(result.skipped)
    return results


def merge_targets(wiki_dir: Path, kind: str, rows: list[dict[str, Any]]) -> list[str]:
    """Slugs ``merge --into`` accepts for ``kind``: trusted pages, then peers.

    ``merge()`` resolves a target under ``wiki/<kind>/`` first and falls back to
    another pending stub in the same table, so the suggestion list offers both.
    """
    trusted = []
    folder = wiki_dir / kind
    if folder.is_dir():
        trusted = sorted(
            p.stem for p in folder.glob("*.md") if not p.name.startswith("_")
        )
    peers = sorted(r["slug"] for r in rows if r["kind"] == kind)
    seen: set[str] = set()
    out: list[str] = []
    for slug in trusted + peers:
        if slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


#: Decision vocabulary, mirroring the ``action`` values ``llmwiki candidates
#: apply`` parses (see ``_VALID_ACTIONS``). The empty value is the default and
#: keeps the row out of the batch.
_DECISION_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "No decision"),
    ("promote", "Promote"),
    ("flip-promote", "Flip and promote"),
    ("merge", "Merge into…"),
    ("discard", "Discard"),
)

#: Extra Decision when the row near-matches at least one prior dismissal (#146).
_DISCARD_PRIOR_CHOICE = ("discard-prior", "Discard with prior reason")

#: Duplicate-pair Decision values (#365). Separate from stub ``_DECISION_CHOICES``;
#: Apply maps these to ``merge-pages`` / ``keep-distinct`` (not stub verbs).
_DUP_DECISION_UNDECIDED = ("", "No decision")
_DUP_DECISION_MERGE_A_INTO_B = "merge-a-into-b"
_DUP_DECISION_MERGE_B_INTO_A = "merge-b-into-a"
_DUP_DECISION_KEEP_DISTINCT = "keep-distinct"


def _row_priors(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalize ``prior_dismissals`` / legacy singular ``prior_dismissal``."""
    priors = row.get("prior_dismissals")
    if isinstance(priors, list) and priors:
        return [p for p in priors if isinstance(p, dict)]
    prior = row.get("prior_dismissal")
    if isinstance(prior, dict):
        return [prior]
    return []


def _decision_controls_html(row: dict[str, Any], kind: str, index: int) -> str:
    """The Decision cell: an action select plus the field that action needs.

    *Merge into…* reveals a combobox over the merge targets for ``kind``, and
    *Discard* reveals the reason plus an optional redirect. When the row has
    prior dismissals, *Discard with prior reason* reuses the best match's
    reason without retyping it (#146).
    """
    slug = html.escape(row["slug"])
    kind_esc = html.escape(kind)
    list_id = f"cand-target-list-{kind_esc}-{index}"
    priors = _row_priors(row)
    choices = list(_DECISION_CHOICES)
    prior_attr = ""
    if priors:
        # Insert before plain Discard so the reuse path is easy to spot.
        discard_idx = next(
            (i for i, (value, _) in enumerate(choices) if value == "discard"),
            len(choices),
        )
        choices.insert(discard_idx, _DISCARD_PRIOR_CHOICE)
        prior_reason = reuse_discard_reason(priors[0])
        prior_attr = f' data-prior-reason="{html.escape(prior_reason, quote=True)}"'
    options = "".join(
        f'<option value="{html.escape(value)}">{html.escape(label)}</option>'
        for value, label in choices
    )
    return (
        f'<div class="cand-intent" data-slug="{slug}" data-kind="{kind_esc}"'
        f"{prior_attr}>"
        f'<label class="muted">Decision '
        f'<select class="cand-decision" aria-label="Decision for {slug}">'
        f"{options}</select></label>"
        f'<span class="cand-merge-wrap muted" hidden>Into '
        f'<span class="cand-combo" data-kind="{kind_esc}">'
        f'<input class="cand-merge-into" type="text" role="combobox"'
        f' autocomplete="off" aria-autocomplete="list" aria-expanded="false"'
        f' aria-controls="{list_id}" aria-label="Merge {slug} into"'
        f' placeholder="Choose a page">'
        f'<button type="button" class="cand-combo-open" tabindex="-1"'
        f' aria-label="Show pages {slug} can merge into">\u25be</button>'
        f'<ul class="cand-combo-list" id="{list_id}" role="listbox"'
        f' aria-label="Pages {slug} can merge into" hidden></ul>'
        f'<span class="cand-combo-empty" hidden></span>'
        "</span></span>"
        f'<label class="cand-reason-wrap muted" hidden>Reason '
        f'<input class="cand-discard-reason" type="text" aria-required="true"'
        f' placeholder="why it is rejected"'
        f' aria-label="Reason for discarding {slug}"></label>'
        f'<label class="cand-redirect-wrap muted" hidden>Redirect links to '
        f'<input class="cand-discard-redirect" type="text"'
        f' placeholder="leave empty to unlink"'
        f' aria-label="Existing page to redirect links to {slug} to"></label>'
        "</div>"
    )


def _targets_data_html(wiki_dir: Path | None, kind: str,
                       rows: list[dict[str, Any]]) -> str:
    """The merge targets for ``kind`` as inline JSON, once for the whole page.

    Every row's combobox is filled and filtered from this one list, so a vault
    with many pending stubs still carries a single copy of the target names.
    """
    slugs = merge_targets(wiki_dir, kind, rows) if wiki_dir else []
    payload = json.dumps(slugs, ensure_ascii=False).replace("<", "\\u003c")
    return (
        f'<script type="application/json" class="cand-targets"'
        f' id="cand-targets-{html.escape(kind)}"'
        f' data-kind="{html.escape(kind)}">{payload}</script>'
    )


def _prior_dismissals_html(priors: list[dict[str, Any]]) -> str:
    """Muted Name-cell list of near-match prior dismissals (#146)."""
    if not priors:
        return ""
    items: list[str] = []
    for prior in priors:
        name = html.escape(str(prior.get("name") or ""))
        reason = html.escape(format_dismissal_reason(prior.get("reason")))
        items.append(f"<li>&quot;{name}&quot; \u2014 {reason}</li>")
    return (
        '<div class="muted cand-prior-dismissals">'
        "<div>Prior dismissals:</div>"
        f"<ul class=\"cand-prior-dismissals-list\">{''.join(items)}</ul>"
        "</div>"
    )


def _name_meta_html(title: str, slug: str, age: str) -> str:
    """Age line under the title; omit a redundant slug when it equals the title."""
    age_esc = html.escape(age)
    if slug == title:
        return f'<div class="muted">{age_esc}</div>'
    return (
        f'<div class="muted"><code>{html.escape(slug)}</code> \u00b7 '
        f"{age_esc}</div>"
    )


def _table_rows_html(rows: list[dict[str, Any]], kind: str) -> str:
    kind_rows = [r for r in rows if r["kind"] == kind]
    if not kind_rows:
        return (
            f'<tr><td colspan="3" class="muted">No pending {html.escape(kind)} '
            "candidates.</td></tr>"
        )
    out: list[str] = []
    for index, r in enumerate(kind_rows):
        age = f'{r["age_days"]}d' if r.get("created") else "\u2014"
        title = str(r["title"])
        slug = str(r["slug"])
        prior_html = _prior_dismissals_html(_row_priors(r))
        out.append(
            "<tr>"
            f"<td><strong>{html.escape(title)}</strong>"
            f"{_name_meta_html(title, slug, age)}"
            f"{prior_html}</td>"
            f'<td>{html.escape(r["description"])}</td>'
            f'<td class="cand-actions">{_decision_controls_html(r, kind, index)}</td>'
            "</tr>"
        )
    return "\n".join(out)


def _dup_side_cell_html(side: Mapping[str, Any]) -> str:
    """One page in a duplicate pair: linked title, kind, session count."""
    title = str(side.get("title") or side.get("slug") or "")
    kind = str(side.get("kind") or "")
    slug = str(side.get("slug") or "")
    href = str(side.get("href") or _duplicate_page_href(kind, title, slug))
    sessions = side.get("session_count")
    try:
        n = int(sessions) if sessions is not None else 0
    except (TypeError, ValueError):
        n = 0
    sess_label = f"{n} session" if n == 1 else f"{n} sessions"
    title_esc = html.escape(title)
    kind_esc = html.escape(kind)
    href_esc = html.escape(href, quote=True)
    return (
        f'<a href="{href_esc}"><strong>{title_esc}</strong></a>'
        f'<div class="muted">[{kind_esc}] · {html.escape(sess_label)}</div>'
    )


def _dup_decision_controls_html(pair: Mapping[str, Any], index: int) -> str:
    """Separate Decision select for a duplicate pair (not the stub dropdown)."""
    a = pair.get("a") if isinstance(pair.get("a"), Mapping) else {}
    b = pair.get("b") if isinstance(pair.get("b"), Mapping) else {}
    a_title = str(a.get("title") or a.get("slug") or "")
    b_title = str(b.get("title") or b.get("slug") or "")
    a_esc = html.escape(a_title, quote=True)
    b_esc = html.escape(b_title, quote=True)
    a_label = html.escape(a_title)
    b_label = html.escape(b_title)
    choices = (
        _DUP_DECISION_UNDECIDED,
        (
            _DUP_DECISION_MERGE_A_INTO_B,
            f"Merge {a_title} → {b_title}",
        ),
        (
            _DUP_DECISION_MERGE_B_INTO_A,
            f"Merge {b_title} → {a_title}",
        ),
        (_DUP_DECISION_KEEP_DISTINCT, "Keep distinct"),
    )
    options = "".join(
        f'<option value="{html.escape(value)}">{html.escape(label)}</option>'
        for value, label in choices
    )
    aria = f"Decision for duplicate pair {a_label} and {b_label}"
    return (
        f'<div class="cand-dup-intent" data-a="{a_esc}" data-b="{b_esc}"'
        f' data-pair-index="{index}">'
        f'<label class="muted">Decision '
        f'<select class="cand-dup-decision" aria-label="{aria}">'
        f"{options}</select></label>"
        "</div>"
    )


def _duplicate_pair_rows_html(pairs: list[dict[str, Any]]) -> str:
    """Table body rows for the Possible duplicate pages section (#365)."""
    if not pairs:
        return (
            '<tr><td colspan="3" class="muted">No suspected duplicate pages.'
            "</td></tr>"
        )
    out: list[str] = []
    for index, pair in enumerate(pairs):
        a = pair.get("a") if isinstance(pair.get("a"), Mapping) else {}
        b = pair.get("b") if isinstance(pair.get("b"), Mapping) else {}
        desc = str(pair.get("description") or "").strip()
        suspicion = str(pair.get("suspicion") or "").strip()
        if not desc and suspicion:
            desc = suspicion
        if not desc:
            desc = "(no vocabulary description)"
        out.append(
            "<tr>"
            f"<td>{_dup_side_cell_html(a)}"
            '<div class="muted cand-dup-vs">\u2194</div>'
            f"{_dup_side_cell_html(b)}</td>"
            f"<td>{html.escape(desc)}</td>"
            f'<td class="cand-actions">{_dup_decision_controls_html(pair, index)}</td>'
            "</tr>"
        )
    return "\n".join(out)


def _duplicate_pairs_section_html(pairs: list[dict[str, Any]]) -> str:
    """Full Possible duplicate pages block (heading + table)."""
    n = len(pairs)
    headers = "<tr><th>Pages</th><th>Description</th><th>Decision</th></tr>"
    body = _duplicate_pair_rows_html(pairs)
    return f"""    <h2>Possible duplicate pages ({n})</h2>
    <p class="muted">Live curated or project pages the vocabulary treats as the same topic. Merge one into the other, or mark them keep-distinct so the pair stays off this list. Decisions join the same Apply batch as stub rows above.</p>
    <div class="state-table-wrap cand-table-wrap" tabindex="0" role="region" aria-label="Possible duplicate pages">
      <table class="state-pipeline-table cand-review-table" id="cand-table-duplicates">
        <thead>{headers}</thead>
        <tbody>
{body}
        </tbody>
      </table>
    </div>"""


def apply_command_prefix(vault: str) -> str:
    """Everything before ``--actions`` in the line the page emits for ``vault``.

    The page appends the shell-quoted batch, so what a reviewer copies is one
    line they can paste. Reading a decision back out of a separate JSON block
    is not something a terminal can do for them.
    """
    return f"llmwiki candidates apply --vault {_shell_single_quote(vault)}"


_REVIEW_SCRIPT = """<script>
  var APPLY_PREFIX = __APPLY_PREFIX__;
(function () {
  var panel = document.getElementById("cand-apply-panel");
  if (!panel) return;
  var errEl = document.getElementById("cand-error");
  var outEl = document.getElementById("cand-output");
  var commandEl = document.getElementById("cand-command");
  var countEl = document.getElementById("cand-decision-count");
  var applyBtn = document.getElementById("cand-apply");
  var copyCmdBtn = document.getElementById("cand-copy-command");
  var TARGETS = readTargets();

  // One inline JSON island per kind holds every page `merge --into` resolves.
  function readTargets() {
    var map = {};
    Array.prototype.forEach.call(
      document.querySelectorAll("script.cand-targets"),
      function (el) {
        var kind = el.getAttribute("data-kind");
        try {
          map[kind] = JSON.parse(el.textContent || "[]");
        } catch (e) {
          map[kind] = [];
          if (window.__llmwikiReportError) {
            window.__llmwikiReportError(
              "Merge targets for " + kind + " unreadable", e
            );
          }
        }
      }
    );
    return map;
  }
  function targetsFor(kind, ownSlug) {
    // A candidate cannot be merged into itself: `merge` resolves the target
    // and would archive the row into its own page.
    var all = TARGETS[kind] || [];
    if (!ownSlug) return all;
    return all.filter(function (slug) { return slug !== ownSlug; });
  }
  // Typing narrows the list: case-insensitive substring, order preserved.
  function filterTargets(list, query) {
    var q = String(query == null ? "" : query).trim().toLowerCase();
    if (!q) return list.slice();
    return list.filter(function (slug) {
      return slug.toLowerCase().indexOf(q) !== -1;
    });
  }
  function isKnownTarget(kind, value, ownSlug) {
    return targetsFor(kind, ownSlug).indexOf(String(value)) !== -1;
  }

  function showError(msg) {
    errEl.hidden = !msg;
    errEl.textContent = msg || "";
  }
  // Stub harvest rows (.cand-intent). Duplicate pairs use .cand-dup-intent
  // with a separate Decision select — not the stub promote/merge/discard list.
  function rows() {
    return Array.prototype.slice.call(document.querySelectorAll(".cand-intent"));
  }
  function dupRows() {
    return Array.prototype.slice.call(
      document.querySelectorAll(".cand-dup-intent")
    );
  }
  function decisionOf(wrap) {
    var sel = wrap.querySelector(".cand-decision");
    return sel ? sel.value : "";
  }
  function dupDecisionOf(wrap) {
    var sel = wrap.querySelector(".cand-dup-decision");
    return sel ? sel.value : "";
  }
  function fieldValue(wrap, sel) {
    var el = wrap.querySelector(sel);
    return el ? (el.value || "").trim() : "";
  }
  function markField(el, bad) {
    if (!el) return;
    el.setAttribute("data-invalid", bad ? "yes" : "no");
    el.setAttribute("aria-invalid", bad ? "true" : "false");
  }
  // What a decided row still needs before it can run. Merge needs a page from
  // the list; discard needs a free-text reason (stored in dismissals.json).
  // "" means the row is ready.
  function rowProblem(wrap) {
    var action = decisionOf(wrap);
    var slug = wrap.getAttribute("data-slug");
    if (action === "merge") {
      var into = fieldValue(wrap, ".cand-merge-into");
      if (!into) return slug + " (choose a page to merge into)";
      if (!isKnownTarget(wrap.getAttribute("data-kind"), into, slug)) {
        return slug + " (no page named " + into + " to merge into)";
      }
    } else if (action === "discard" && !fieldValue(wrap, ".cand-discard-reason")) {
      return slug + " (give a reason for discarding)";
    } else if (action === "discard-prior") {
      var priorReason = (wrap.getAttribute("data-prior-reason") || "").trim();
      if (!priorReason) return slug + " (no prior dismissal reason to reuse)";
    }
    return "";
  }
  // Text naming no page is wrong the moment it is typed; an empty field is
  // merely unfinished, so it is flagged when Apply asks for it.
  function markTyping(wrap) {
    var mergeEl = wrap.querySelector(".cand-merge-into");
    if (mergeEl) {
      var into = (mergeEl.value || "").trim();
      markField(
        mergeEl,
        into !== "" && !isKnownTarget(wrap.getAttribute("data-kind"), into, wrap.getAttribute("data-slug"))
      );
    }
    var reasonEl = wrap.querySelector(".cand-discard-reason");
    if (reasonEl && (reasonEl.value || "").trim()) markField(reasonEl, false);
  }
  function flagUnfinished() {
    var first = null;
    rows().forEach(function (wrap) {
      var action = decisionOf(wrap);
      var bad = action ? rowProblem(wrap) : "";
      var field = wrap.querySelector(
        action === "merge" ? ".cand-merge-into" : ".cand-discard-reason"
      );
      if (action === "merge" || action === "discard") markField(field, Boolean(bad));
      if (bad && !first) first = field;
    });
    if (first && first.focus) first.focus();
  }
  function isDiscardAction(value) {
    return value === "discard" || value === "discard-prior";
  }
  function syncRow(wrap) {
    var value = decisionOf(wrap);
    var mergeWrap = wrap.querySelector(".cand-merge-wrap");
    var reasonWrap = wrap.querySelector(".cand-reason-wrap");
    var redirectWrap = wrap.querySelector(".cand-redirect-wrap");
    if (mergeWrap) {
      mergeWrap.hidden = value !== "merge";
      var combo = mergeWrap.querySelector(".cand-combo");
      if (combo && combo.llmwikiClose && value !== "merge") combo.llmwikiClose();
    }
    // discard-prior reuses data-prior-reason — no typed reason field.
    if (reasonWrap) reasonWrap.hidden = value !== "discard";
    if (redirectWrap) redirectWrap.hidden = !isDiscardAction(value);
    if (value !== "merge") markField(wrap.querySelector(".cand-merge-into"), false);
    if (value !== "discard") {
      markField(wrap.querySelector(".cand-discard-reason"), false);
    }
    wrap.setAttribute("data-decided", value ? "yes" : "no");
  }
  function refreshCount() {
    var n = rows().filter(function (w) { return decisionOf(w); }).length
      + dupRows().filter(function (w) { return dupDecisionOf(w); }).length;
    countEl.textContent = n === 0
      ? "No decisions set"
      : n + (n === 1 ? " decision set" : " decisions set");
  }
  function syncDupRow(wrap) {
    wrap.setAttribute("data-decided", dupDecisionOf(wrap) ? "yes" : "no");
  }
  // Rows left at "No decision" are absent from the batch, so Apply never
  // promotes anything the reviewer did not choose. A row that was decided but
  // is not executable holds the whole batch back rather than going out broken.
  // Stub rows emit promote/flip-promote/discard/merge; duplicate-pair rows emit
  // merge-pages / keep-distinct into the same actions array.
  function collectActions() {
    var actions = [];
    var unfinished = [];
    rows().forEach(function (wrap) {
      var action = decisionOf(wrap);
      if (!action) return;
      var problem = rowProblem(wrap);
      if (problem) { unfinished.push(problem); return; }
      var item = {
        action: action,
        slug: wrap.getAttribute("data-slug"),
        kind: wrap.getAttribute("data-kind")
      };
      if (action === "merge") {
        item.into = fieldValue(wrap, ".cand-merge-into");
      } else if (action === "discard") {
        item.reason = fieldValue(wrap, ".cand-discard-reason");
        var redirect = fieldValue(wrap, ".cand-discard-redirect");
        if (redirect) item.redirect = redirect;
      } else if (action === "discard-prior") {
        // Apply only understands discard — map the UX shortcut here.
        item.action = "discard";
        item.reason = (wrap.getAttribute("data-prior-reason") || "").trim();
        var priorRedirect = fieldValue(wrap, ".cand-discard-redirect");
        if (priorRedirect) item.redirect = priorRedirect;
      }
      actions.push(item);
    });
    // Inline query (not dupRows()) so node harness extracts of collectActions()
    // stay self-contained when only this function is copied out.
    Array.prototype.slice.call(
      document.querySelectorAll(".cand-dup-intent")
    ).forEach(function (wrap) {
      var dupSel = wrap.querySelector(".cand-dup-decision");
      var decision = dupSel ? dupSel.value : "";
      if (!decision) return;
      var aName = (wrap.getAttribute("data-a") || "").trim();
      var bName = (wrap.getAttribute("data-b") || "").trim();
      if (!aName || !bName) {
        unfinished.push("duplicate pair (missing page names)");
        return;
      }
      if (decision === "merge-a-into-b") {
        actions.push({ action: "merge-pages", from: aName, into: bName });
      } else if (decision === "merge-b-into-a") {
        actions.push({ action: "merge-pages", from: bName, into: aName });
      } else if (decision === "keep-distinct") {
        actions.push({ action: "keep-distinct", a: aName, b: bName });
      } else {
        unfinished.push(
          aName + " / " + bName + " (unknown duplicate decision)"
        );
      }
    });
    if (unfinished.length) {
      var err = new Error("Finish these rows before Apply: " + unfinished.join("; "));
      err.reviewerFixable = true;
      throw err;
    }
    if (!actions.length) {
      var none = new Error("Set at least one Decision before Apply.");
      none.reviewerFixable = true;
      throw none;
    }
    var peerActions = {promote: true, "flip-promote": true, discard: true, merge: true};
    for (var i = 0; i < actions.length; i++) {
      var mergeItem = actions[i];
      if (mergeItem.action !== "merge") continue;
      var into = String(mergeItem.into || "").trim();
      var mergeSlug = String(mergeItem.slug || "").trim();
      if (!into || !mergeSlug) continue;
      for (var j = 0; j < actions.length; j++) {
        if (i === j) continue;
        var other = actions[j];
        var otherAction = String(other.action || "").trim();
        var otherSlug = String(other.slug || "").trim();
        if (otherSlug !== into || !peerActions[otherAction]) continue;
        var conflict = new Error(
          "batch conflict: merge '" + mergeSlug + "' into '" + into + "' "
          + "conflicts with " + otherAction + " '" + otherSlug + "' in the same batch"
        );
        conflict.reviewerFixable = true;
        throw conflict;
      }
    }
    // Live-page rows: refuse merge-pages + keep-distinct on the same pair.
    // ASCII-safe stand-in for Python norm_page_key; Apply re-validates.
    function unorderedPairId(left, right) {
      function norm(name) {
        return String(name == null ? "" : name)
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "");
      }
      var a = norm(left);
      var b = norm(right);
      if (!a || !b || a === b) return "";
      return a < b ? a + "|" + b : b + "|" + a;
    }
    var mergePagePairs = [];
    var keepDistinctPairs = [];
    for (var mi = 0; mi < actions.length; mi++) {
      var row = actions[mi];
      if (row.action === "merge-pages") {
        var mpid = unorderedPairId(row.from, row.into);
        if (mpid) mergePagePairs.push({ id: mpid, from: row.from, into: row.into });
      } else if (row.action === "keep-distinct") {
        var kpid = unorderedPairId(row.a, row.b);
        if (kpid) keepDistinctPairs.push({ id: kpid, a: row.a, b: row.b });
      }
    }
    for (var mp = 0; mp < mergePagePairs.length; mp++) {
      for (var kd = 0; kd < keepDistinctPairs.length; kd++) {
        if (mergePagePairs[mp].id !== keepDistinctPairs[kd].id) continue;
        var pairConflict = new Error(
          "batch conflict: merge-pages '" + mergePagePairs[mp].from
          + "' into '" + mergePagePairs[mp].into
          + "' conflicts with keep-distinct '" + keepDistinctPairs[kd].a
          + "' / '" + keepDistinctPairs[kd].b + "' in the same batch"
        );
        pairConflict.reviewerFixable = true;
        throw pairConflict;
      }
    }
    return actions;
  }
  function apply() {
    showError("");
    var actions;
    try {
      actions = collectActions();
    } catch (e) {
      showError(e.message || String(e));
      if (e.reviewerFixable) {
        flagUnfinished();
      } else if (window.__llmwikiReportError) {
        window.__llmwikiReportError("Candidates Apply failed", e);
      }
      return;
    }
    commandEl.textContent = applyCommand(actions);
    outEl.hidden = false;
    copyCmdBtn.hidden = false;
    outEl.scrollIntoView({ block: "nearest" });
  }
  function shellQuote(s) {
    // Single-quote for POSIX shells: close, escape, reopen. Mirrors
    // _shell_single_quote so the page and the CLI agree on one line.
    return "'" + String(s).split("'").join("'\\''") + "'";
  }
  function applyCommand(actions) {
    var payload = JSON.stringify(actions);
    return APPLY_PREFIX + " --actions " + shellQuote(payload);
  }
  function copyFrom(btn) {
    var src = document.getElementById(btn.getAttribute("data-copy-target"));
    var text = src ? (src.textContent || "") : "";
    if (!text) {
      showError("Nothing to copy yet — press Apply first.");
      return;
    }
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      showError("Clipboard unavailable — select the text and copy manually.");
      return;
    }
    var label = btn.textContent;
    navigator.clipboard.writeText(text).then(function () {
      showError("");
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = label; }, 1500);
    }).catch(function (e) {
      showError("Could not copy — select the text and copy manually.");
      if (window.__llmwikiReportError) {
        window.__llmwikiReportError("Candidates copy failed", e);
      }
    });
  }

  // A filterable dropdown over the merge targets: the text box narrows the
  // list, the button opens it whole for a reviewer who knows no names yet.
  function setupCombo(combo) {
    var input = combo.querySelector(".cand-merge-into");
    var list = combo.querySelector(".cand-combo-list");
    var emptyEl = combo.querySelector(".cand-combo-empty");
    var toggle = combo.querySelector(".cand-combo-open");
    var wrap = combo.closest(".cand-intent");
    var kind = combo.getAttribute("data-kind");
    var ownSlug = wrap ? wrap.getAttribute("data-slug") : null;
    var options = [];
    var active = -1;

    function isOpen() { return !list.hidden; }
    function setActive(i) {
      active = i;
      options.forEach(function (li, n) {
        li.setAttribute("aria-selected", n === i ? "true" : "false");
        li.className = n === i
          ? "cand-combo-option is-active"
          : "cand-combo-option";
      });
      if (i >= 0 && options[i]) {
        input.setAttribute("aria-activedescendant", options[i].id);
        if (options[i].scrollIntoView) {
          options[i].scrollIntoView({ block: "nearest" });
        }
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }
    function render() {
      var typed = (input.value || "").trim();
      var all = targetsFor(kind, ownSlug);
      var matches = filterTargets(all, typed);
      while (list.firstChild) list.removeChild(list.firstChild);
      options = matches.map(function (slug, i) {
        var li = document.createElement("li");
        li.className = "cand-combo-option";
        li.id = list.id + "-o" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = slug;
        list.appendChild(li);
        return li;
      });
      emptyEl.textContent = all.length
        ? "No page matches — clear the text to see all " + all.length + "."
        : "No pages to merge into yet.";
      emptyEl.hidden = matches.length > 0;
      list.hidden = matches.length === 0;
      var exact = matches.indexOf(typed);
      setActive(exact >= 0 ? exact : (typed && matches.length ? 0 : -1));
    }
    function open() {
      render();
      input.setAttribute("aria-expanded", isOpen() ? "true" : "false");
    }
    function close() {
      list.hidden = true;
      emptyEl.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }
    function choose(i) {
      if (i < 0 || i >= options.length) return;
      input.value = options[i].textContent;
      close();
      markField(input, false);
      if (input.focus) input.focus();
    }
    function step(delta) {
      if (!options.length) return;
      var next = active + delta;
      if (next < 0) next = options.length - 1;
      if (next >= options.length) next = 0;
      setActive(next);
    }

    input.addEventListener("input", function () {
      open();
      if (wrap) markTyping(wrap);
    });
    input.addEventListener("keydown", function (ev) {
      var key = ev.key;
      if (key === "ArrowDown" || key === "ArrowUp") {
        ev.preventDefault();
        if (!isOpen()) {
          open();
          if (key === "ArrowUp") setActive(options.length - 1);
          else if (active < 0) setActive(0);
          return;
        }
        step(key === "ArrowDown" ? 1 : -1);
        return;
      }
      if (!isOpen()) return;
      if (key === "Home") { ev.preventDefault(); setActive(0); return; }
      if (key === "End") { ev.preventDefault(); setActive(options.length - 1); return; }
      if (key === "Enter" && active >= 0) { ev.preventDefault(); choose(active); return; }
      if (key === "Escape") { ev.preventDefault(); close(); return; }
      if (key === "Tab") close();
    });
    toggle.addEventListener("click", function (ev) {
      ev.preventDefault();
      if (input.focus) input.focus();
      if (isOpen()) { close(); } else { open(); }
    });
    // mousedown default would blur the input before the click lands.
    list.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
    list.addEventListener("click", function (ev) {
      var li = ev.target.closest ? ev.target.closest(".cand-combo-option") : null;
      if (li) choose(options.indexOf(li));
    });
    combo.addEventListener("focusout", function (ev) {
      if (ev.relatedTarget && combo.contains(ev.relatedTarget)) return;
      close();
      if (wrap) markTyping(wrap);
    });
    combo.llmwikiClose = close;
  }

  try {
    document.addEventListener("change", function (ev) {
      var wrap = ev.target.closest && ev.target.closest(".cand-intent");
      if (wrap) {
        syncRow(wrap);
        refreshCount();
        return;
      }
      var dup = ev.target.closest && ev.target.closest(".cand-dup-intent");
      if (dup) {
        syncDupRow(dup);
        refreshCount();
      }
    });
    document.addEventListener("input", function (ev) {
      var wrap = ev.target.closest && ev.target.closest(".cand-intent");
      if (wrap) markTyping(wrap);
    });
    document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
      btn.addEventListener("click", function () { copyFrom(btn); });
    });
    document.querySelectorAll(".cand-combo").forEach(setupCombo);
    applyBtn.addEventListener("click", apply);
    rows().forEach(syncRow);
    dupRows().forEach(syncDupRow);
    refreshCount();
  } catch (e) {
    if (window.__llmwikiReportError) {
      window.__llmwikiReportError("Candidates review controls unavailable", e);
    }
  }
})();
</script>
"""


def _apply_bar_html(*, has_review_work: bool) -> str:
    """The Apply control. Sits above the tables so it is never buried."""
    if not has_review_work:
        return (
            '<p class="muted">Nothing pending. New stubs appear here after '
            "<code>llmwiki synth</code> harvests them; suspected duplicate "
            "pages appear after vocabulary folds two live titles together.</p>"
        )
    return """<div class="cand-apply-panel" id="cand-apply-panel">
      <div class="cand-apply-bar">
        <button type="button" id="cand-apply" class="cand-apply-btn cand-apply-primary">Apply</button>
        <span class="muted" id="cand-decision-count" aria-live="polite">No decisions set</span>
        <span class="cand-apply-spacer"></span>
        <button type="button" class="cand-apply-btn" id="cand-copy-command" data-copy-target="cand-command" hidden>Copy command</button>
      </div>
    </div>"""


def _apply_output_html(*, has_review_work: bool, vault: str) -> str:
    """The command Apply writes, placed after the tables.

    One line, with the batch already inside it, so it pastes into a terminal
    as-is. The tables stay on screen above it: the decisions are the thing
    being reviewed, and reading them back out of JSON is not review.
    """
    if not has_review_work:
        return ""
    return f"""<div class="cand-output" id="cand-output" hidden>
      <p class="muted">Run this:</p>
      <pre class="cand-cli" id="cand-command"></pre>
      <p class="muted">Then <code>llmwiki build --vault {html.escape(vault)}</code> to refresh these counts.</p>
    </div>"""


def render_candidates_body(wiki_dir: Path | None) -> str:
    """Inner HTML for ``candidates.html`` — review tables + the Apply panel."""
    if wiki_dir and wiki_dir.is_dir():
        payload = candidates_payload(wiki_dir)
    else:
        payload = {
            "candidates": [],
            "duplicate_pairs": [],
            "summary": {"to_review": 0},
        }
    rows = payload["candidates"]
    pairs = list(payload.get("duplicate_pairs") or [])
    n = int(payload["summary"].get("to_review") or 0)
    p = len(pairs)
    has_review_work = bool(rows) or bool(pairs)
    vault = vault_display_path(wiki_dir)
    entities = _table_rows_html(rows, "entities")
    concepts = _table_rows_html(rows, "concepts")
    targets = _targets_data_html(wiki_dir, "entities", rows) + _targets_data_html(
        wiki_dir, "concepts", rows,
    )
    headers = "<tr><th>Name</th><th>Description</th><th>Decision</th></tr>"
    status_bits = [f"{n} pending candidate(s)"]
    if p:
        status_bits.append(
            f"{p} possible duplicate pair(s)" if p != 1
            else "1 possible duplicate pair"
        )
    status = (
        "; ".join(status_bits)
        + ". Set a Decision on the rows you have judged, then <strong>Apply</strong>"
        " — it writes the command and JSON batch to run. Rows left at "
        "<em>No decision</em> stay pending."
    )
    return f"""<section class="section">
  <div class="container">
    <p class="muted" id="cand-status">{status}</p>
    <p id="cand-error" class="error-banner" hidden role="alert"></p>
    {_apply_bar_html(has_review_work=has_review_work)}
    <h2>Entities (pending)</h2>
    <div class="state-table-wrap cand-table-wrap" tabindex="0" role="region" aria-label="Pending entity candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-entities">
        <thead>{headers}</thead>
        <tbody>{entities}</tbody>
      </table>
    </div>
    <h2>Concepts (pending)</h2>
    <div class="state-table-wrap cand-table-wrap" tabindex="0" role="region" aria-label="Pending concept candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-concepts">
        <thead>{headers}</thead>
        <tbody>{concepts}</tbody>
      </table>
    </div>
{_duplicate_pairs_section_html(pairs)}
    {_apply_output_html(has_review_work=has_review_work, vault=vault)}
    {targets}
  </div>
</section>
{_REVIEW_SCRIPT.replace('__APPLY_PREFIX__', json.dumps(apply_command_prefix(vault)))}"""
