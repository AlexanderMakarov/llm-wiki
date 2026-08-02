"""Local HTTP server for the built llmwiki site.

Uses only Python stdlib. Binds to 127.0.0.1 by default so nothing is exposed
to the network unless the user explicitly passes --host 0.0.0.0.

Also hosts ``POST /api/candidates`` for the #97 review UI — batch of
promote / flip-promote / merge / discard via the same library paths as
``llmwiki candidates apply --actions`` (and the one-off subcommands).
Wiki root is inferred as ``<site>/../wiki`` (vault layout).
"""

from __future__ import annotations

import json
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from typing import Any
from urllib.parse import urlparse

from llmwiki.build import render_candidates_page
from llmwiki.candidates import apply_review_summary_to_pipeline
from llmwiki.candidates_site import apply_candidate_actions, candidates_payload
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.state_store import update_state
from llmwiki.synth.pipeline import resolve_backend


class _QuietHandler(SimpleHTTPRequestHandler):
    """Like SimpleHTTPRequestHandler but with prettier logs and a branded
    404 response that pulls ``site/404.html`` (closes #387 U8) instead of
    falling back to the stdlib's plain-text error page."""

    wiki_dir: Path | None = None  # set on the class by serve_site()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Suppress per-request logs for a cleaner terminal.
        return

    def send_error(self, code: int, message: str | None = None,
                   explain: str | None = None) -> None:
        """Override the default error page so 404s pick up the branded
        ``404.html`` shipped by ``llmwiki build``. We deliberately keep the
        404 status code intact — the page is the *body* of the 404 response,
        not a redirect — so crawlers still see the right HTTP code.

        Falls back to the stdlib default for anything other than 404, or
        when ``404.html`` is missing (e.g. a partially-built site)."""
        if code == 404:
            try:
                # #py-m2 (#588): no longer relies on os.chdir(). The
                # SimpleHTTPRequestHandler's `directory` arg holds the
                # site root; we read 404.html from there explicitly.
                site_root = getattr(self, "directory", None)
                err_page = (Path(site_root) / "404.html") if site_root else Path("404.html")
                with open(err_page, "rb") as f:
                    body = f.read()
                self.send_response(404, message)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except (FileNotFoundError, OSError):
                # 404.html doesn't exist — fall through to default behavior.
                pass
        super().send_error(code, message, explain)

    def do_POST(self) -> None:  # noqa: N802 — stdlib naming
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/api/candidates":
            self.send_error(404, "Not Found")
            return
        self._handle_candidates_api()

    def _json_response(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_candidates_api(self) -> None:
        wiki_dir = self.wiki_dir
        if wiki_dir is None or not wiki_dir.is_dir():
            self._json_response(
                503,
                {
                    "error": (
                        "wiki/ not found next to the served site/ — "
                        "serve a vault site (…/vault/site) so …/vault/wiki exists"
                    )
                },
            )
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(400, {"error": "invalid JSON body"})
            return
        if not isinstance(data, dict):
            self._json_response(400, {"error": "JSON object required"})
            return

        raw_actions = data.get("actions")
        if raw_actions is None:
            self._json_response(
                400,
                {"error": "actions array required (batch-only API)"},
            )
            return
        if not isinstance(raw_actions, list):
            self._json_response(400, {"error": "actions must be an array"})
            return
        # Empty list is a probe from the review page (API present?).
        if not raw_actions:
            self._json_response(
                200,
                {"ok": True, "results": [], **candidates_payload(wiki_dir)},
            )
            return

        backend = resolve_backend(_load_sessions_config())
        results = apply_candidate_actions(
            wiki_dir, raw_actions, synthesizer=backend,
        )
        any_ok = any(r.get("ok") for r in results)
        if any_ok:
            _refresh_review_counts_for_wiki(wiki_dir)

        site_dir = Path(getattr(self, "directory", ".") or ".")
        rewrote = False
        warning = None
        try:
            render_candidates_page(wiki_dir, site_dir)
            rewrote = True
        except Exception as exc:  # noqa: BLE001 — still return results
            warning = f"could not rewrite candidates.html: {exc}"

        payload: dict[str, Any] = {
            "ok": all(r.get("ok") for r in results),
            "results": results,
            "rewrote_page": rewrote,
            **candidates_payload(wiki_dir),
        }
        if warning:
            payload["warning"] = warning
        self._json_response(200, payload)


def _refresh_review_counts_for_wiki(wiki_dir: Path) -> None:
    """Mirror ``cli._refresh_review_counts`` without importing cli."""
    state_file = wiki_dir.parent / "llmwiki-state.json"
    if not state_file.is_file():
        return

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        pipeline = synth.get("pipeline")
        if not isinstance(pipeline, dict):
            pipeline = {"stages": ["raw", "synthesized"], "rows": []}
        synth["pipeline"] = apply_review_summary_to_pipeline(pipeline, wiki_dir)
        return s

    update_state(_mut, state_file)


class _ReusableTCPServer(TCPServer):
    allow_reuse_address = True


def serve_site(
    directory: Path,
    port: int = 8765,
    host: str = "127.0.0.1",
    open_browser: bool = False,
    wiki_dir: Path | None = None,
) -> int:
    directory = directory.expanduser().resolve()
    if not directory.exists():
        print(f"error: {directory} does not exist. Run `llmwiki build` first.")
        return 2

    resolved_wiki = wiki_dir
    if resolved_wiki is None:
        sibling = directory.parent / "wiki"
        if sibling.is_dir():
            resolved_wiki = sibling

    # Bind wiki_dir onto the handler class for this serve session.
    handler_wiki = resolved_wiki

    def handler_factory(*a, **kw):
        handler = _QuietHandler(*a, directory=str(directory), **kw)
        return handler

    # Class attribute so all request handlers see the same wiki root.
    _QuietHandler.wiki_dir = handler_wiki

    url = f"http://{host}:{port}/"
    print(f"==> Serving {directory} at {url}")
    if handler_wiki is not None:
        print(f"    candidates API → wiki {handler_wiki}")
    else:
        print("    candidates API disabled (no sibling wiki/)")
    print("    Press Ctrl+C to stop.")
    try:
        with _ReusableTCPServer((host, port), handler_factory) as httpd:
            if open_browser:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n  stopped.")
    except OSError as e:
        print(f"error: could not bind {host}:{port}: {e}")
        return 1
    return 0
