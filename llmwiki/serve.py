"""Local HTTP server for the built llmwiki site.

Uses only Python stdlib. Binds to 127.0.0.1 by default so nothing is exposed
to the network unless the user explicitly passes --host 0.0.0.0.

Also hosts ``POST /api/candidates`` for the #97 review UI — same library
paths as ``llmwiki candidates …``. Wiki root is inferred as
``<site>/../wiki`` (vault layout).
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
from llmwiki.candidates import (
    KeyFactsBackendError,
    apply_review_summary_to_pipeline,
    discard,
    flip_and_promote,
    merge,
    promote,
)
from llmwiki.candidates_site import candidates_payload
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

        action = str(data.get("action") or "").strip()
        slug = str(data.get("slug") or "").strip()
        kind = data.get("kind")
        kind_s = str(kind).strip() if kind else None
        into = str(data.get("into") or "").strip()
        reason = str(data.get("reason") or "").strip()

        try:
            backend = resolve_backend(_load_sessions_config())
            if action == "promote":
                if not slug:
                    raise ValueError("--slug is required")
                path = promote(slug, wiki_dir, kind=kind_s, synthesizer=backend)
            elif action == "flip-promote":
                if not slug:
                    raise ValueError("--slug is required")
                path = flip_and_promote(
                    slug, wiki_dir, kind=kind_s, synthesizer=backend,
                )
            elif action == "discard":
                if not slug:
                    raise ValueError("--slug is required")
                path = discard(slug, wiki_dir, reason=reason, kind=kind_s)
            elif action == "merge":
                if not slug or not into:
                    raise ValueError("both slug and into are required")
                path = merge(slug, wiki_dir, into_slug=into, kind=kind_s)
            else:
                self._json_response(400, {"error": f"unknown action {action!r}"})
                return
        except FileNotFoundError as exc:
            self._json_response(404, {"error": str(exc)})
            return
        except KeyFactsBackendError as exc:
            self._json_response(400, {"error": str(exc)})
            return
        except (ValueError, FileExistsError) as exc:
            self._json_response(400, {"error": str(exc)})
            return
        except OSError as exc:
            self._json_response(500, {"error": str(exc)})
            return

        _refresh_review_counts_for_wiki(wiki_dir)
        site_dir = Path(getattr(self, "directory", ".") or ".")
        try:
            render_candidates_page(wiki_dir, site_dir)
        except Exception as exc:  # noqa: BLE001 — still return ok; UI can rebuild
            self._json_response(
                200,
                {
                    "ok": True,
                    "path": str(path),
                    "rewrote_page": False,
                    "warning": f"could not rewrite candidates.html: {exc}",
                    **candidates_payload(wiki_dir),
                },
            )
            return

        self._json_response(
            200,
            {
                "ok": True,
                "path": str(path),
                "rewrote_page": True,
                **candidates_payload(wiki_dir),
            },
        )


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
