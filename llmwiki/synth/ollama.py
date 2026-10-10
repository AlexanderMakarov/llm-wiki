"""Ollama backend for local LLM synthesis (v1.1.0 · #35).

Provides ``OllamaSynthesizer``, a stdlib-only HTTP client for Ollama's
``/api/generate`` endpoint. The dependency is **optional**: the default
llmwiki install stays on stdlib + ``markdown``, and this module only
touches ``urllib`` (also stdlib), so there is nothing extra to install.

Ollama must be running locally — by default at ``http://127.0.0.1:11434``.
This keeps synthesis private by default (no data ever leaves the box).

Design notes
------------
- **Privacy by default**: ``base_url`` defaults to 127.0.0.1. If the user
  points the backend at a remote host we log a warning once so they
  know they've left the local-only path.
- **Graceful fallback**: ``is_available()`` probes ``/api/tags`` with a
  short timeout. If the server is down ``synthesize_source_page()`` raises
  ``OllamaUnavailableError``; the caller (``pipeline.synthesize_new_sessions``)
  catches that, logs a warning, and skips the file without crashing the
  sync.
- **Retries**: transient 5xx or ``socket.timeout`` errors retry with
  exponential backoff (default 3 attempts, 0.5/1.0/2.0s). Connection
  refused errors short-circuit — the server is simply not running.
- **No streaming**: we send ``stream: false`` because callers want the
  complete synthesised page back, not a token stream. Streaming can land
  later if a use case for it appears.

Configuration (``sessions_config.json`` / ``config.json``)::

    "synthesis": {
      "backend": "ollama",
      "model":  "llama3.1:8b",
      "base_url": "http://127.0.0.1:11434",
      "timeout": 60,
      "max_retries": 3
    }

Document chunking (#311) uses a usable-body budget: ``synthesis.ollama.usable_body_chars``
or ``context_window_tokens``, else the model's ``num_ctx`` auto-detected from
``/api/show``, else a documented default window for *budget math only*.
``options.num_ctx`` is sent on page calls only when the window came from
config or a Modelfile ``num_ctx`` — never from the assumed default, so a
server-level context (``OLLAMA_CONTEXT_LENGTH`` or the runtime default) is
not silently shrunk.

Config parsing is done in :func:`load_ollama_config` so the CLI can
surface readable errors instead of stack traces.
"""

from __future__ import annotations

import json
import logging
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from llmwiki.synth.base import (
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    OLLAMA_BUDGET,
    SESSION_BODY_SEND_CAP_CHARS,
    BaseSynthesizer,
    BodyBudgetConfig,
    load_body_budget_config,
    resolve_usable_body_chars,
    split_prompt_template,
    usage_limit_from_text,
    window_tokens_for_body_chars,
)

# ─── Constants ─────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_TIMEOUT = 60           # seconds, per HTTP call
DEFAULT_MAX_RETRIES = 3        # includes the first attempt
DEFAULT_BACKOFF_BASE = 0.5     # seconds; doubles each retry

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

#: ``/api/show`` is a quick metadata read; never let it stall a run.
_SHOW_TIMEOUT = 2
_NUM_CTX_RE = re.compile(r"^\s*num_ctx\s+(\d+)\s*$", re.MULTILINE)

logger = logging.getLogger(__name__)


# ─── Exceptions ────────────────────────────────────────────────────────


class OllamaError(RuntimeError):
    """Base class for Ollama backend failures."""


class OllamaUnavailableError(OllamaError):
    """Raised when the Ollama server is unreachable (connection refused,
    DNS failure, or health check fails)."""


class OllamaHTTPError(OllamaError):
    """Raised when the server returns a non-2xx after exhausting retries."""

    def __init__(self, status: int, body: str):
        super().__init__(f"Ollama returned HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


# ─── Config ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OllamaConfig:
    """Resolved configuration for :class:`OllamaSynthesizer`."""

    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base: float = DEFAULT_BACKOFF_BASE
    body_budget: BodyBudgetConfig = BodyBudgetConfig()

    @property
    def show_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/show"

    @property
    def generate_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/generate"

    @property
    def tags_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/tags"

    @property
    def is_local(self) -> bool:
        """True if base_url resolves to localhost (privacy check)."""
        try:
            host = urllib.parse.urlparse(self.base_url).hostname or ""
        except ValueError:
            return False
        return host in LOCAL_HOSTS


def load_ollama_config(cfg: dict[str, Any] | None) -> OllamaConfig:
    """Build an :class:`OllamaConfig` from the ``synthesis`` block of
    ``sessions_config.json``.

    Missing keys fall back to the module-level defaults so first-time
    users don't have to configure anything to try it out::

        { "synthesis": { "backend": "ollama" } }

    is enough to reach a working local default.
    """
    synth = (cfg or {}).get("synthesis", {}) or {}
    # Documented shape is the nested `synthesis.ollama` block. The flat
    # `synthesis.*` layout is the legacy one and still works, but it shares a
    # namespace with the other backends' keys — a flat `timeout` meant for
    # Ollama was silently shortening the claude backend's per-page budget.
    # Nested wins; flat is the fallback so existing configs keep working.
    nested = synth.get("ollama") or {}
    if not isinstance(nested, dict):
        nested = {}

    def _key(name: str) -> Any:
        """Value for ``name``, nested block first, then the legacy flat key."""
        if name in nested:
            return nested[name]
        return synth.get(name)

    def _has(name: str) -> bool:
        return name in nested or name in synth

    # Use `in` checks (not `or`) so an explicit 0 fails validation instead
    # of being silently swapped for the default.
    model = _key("model") or DEFAULT_MODEL
    base_url = _key("base_url") or DEFAULT_BASE_URL
    timeout = int(_key("timeout")) if _has("timeout") else DEFAULT_TIMEOUT
    max_retries = (
        int(_key("max_retries")) if _has("max_retries") else DEFAULT_MAX_RETRIES
    )
    backoff_base = (
        float(_key("backoff_base"))
        if _has("backoff_base")
        else DEFAULT_BACKOFF_BASE
    )

    if timeout <= 0:
        raise ValueError(f"synthesis.timeout must be positive, got {timeout}")
    if max_retries < 1:
        raise ValueError(
            f"synthesis.max_retries must be >= 1, got {max_retries}"
        )

    resolved = OllamaConfig(
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        backoff_base=backoff_base,
        body_budget=load_body_budget_config(nested, "ollama"),
    )

    if not resolved.is_local:
        logger.warning(
            "Ollama backend pointed at non-local host %s — transcript data "
            "will leave this machine. Set synthesis.base_url to http://127.0.0.1:11434 "
            "to restore privacy-by-default.",
            resolved.base_url,
        )

    return resolved


# ─── Synthesizer ───────────────────────────────────────────────────────


class OllamaSynthesizer(BaseSynthesizer):
    """Synthesize wiki source pages via a local Ollama HTTP server.

    The implementation uses only ``urllib`` so no third-party HTTP client
    is required. Test injection uses the ``http_post`` / ``http_get``
    kwargs so ``unittest.mock`` or a hand-rolled fake can substitute the
    transport layer without a real socket.
    """

    def __init__(
        self,
        config: OllamaConfig | None = None,
        *,
        http_post: Any | None = None,
        http_get: Any | None = None,
    ):
        self.config = config or OllamaConfig()
        self._http_post = http_post or _urlopen_post
        self._http_get = http_get or _urlopen_get
        self._detect_lock = threading.Lock()
        self._detected = False
        self._detected_window: int | None = None
        self._modelfile_num_ctx: int | None = None

    # ---- context window / body budget (#311) ----------------------

    def _probe_show(self) -> None:
        """Fill ``_detected_window`` / ``_modelfile_num_ctx`` once per instance."""
        with self._detect_lock:
            if self._detected:
                return
            self._detected = True
            try:
                status, body = self._http_post(
                    self.config.show_url,
                    {"model": self.config.model},
                    timeout=min(self.config.timeout, _SHOW_TIMEOUT),
                )
                info = json.loads(body) if 200 <= status < 300 else None
            except Exception as exc:  # noqa: BLE001 — detection must never break a run
                logger.debug("Ollama /api/show probe failed: %s", exc)
                return
            if not isinstance(info, dict):
                return
            num_ctx = None
            params = info.get("parameters")
            if isinstance(params, str):
                m = _NUM_CTX_RE.search(params)
                num_ctx = int(m.group(1)) if m else None
            trained = None
            model_info = info.get("model_info")
            if isinstance(model_info, dict):
                for key, value in model_info.items():
                    if key.endswith(".context_length") and isinstance(value, int) and value > 0:
                        trained = value
                        break
            if num_ctx:
                capped = min(num_ctx, trained) if trained else num_ctx
                self._modelfile_num_ctx = capped
                self._detected_window = capped
            elif trained:
                # Trained max alone is not what the server loads — only cap the
                # assumed default for *budget* math; never send it as num_ctx.
                self._detected_window = min(DEFAULT_CONTEXT_WINDOW_TOKENS, trained)

    def _detect_context_window(self) -> int | None:
        """Window (tokens) from ``/api/show`` for budget math; ``None`` if unknown.

        Uses the model's Modelfile ``num_ctx`` when set. Otherwise a trained
        maximum only caps the assumed default for the budget — it is never
        treated as the window the server loads, and is never sent as
        ``options.num_ctx``.
        """
        self._probe_show()
        return self._detected_window

    def usable_body_chars(self) -> int:
        """Document-chunk budget: config, else derived from the context window (#311)."""
        return resolve_usable_body_chars(
            self.config.body_budget,
            known_window_tokens=self._detect_context_window,
            budget_class=OLLAMA_BUDGET,
        )

    def context_window_tokens(self) -> int:
        """Window the document budget assumes (config, detected, or default).

        Raised, if needed, to fit an explicit ``usable_body_chars`` plus the
        scaffolding, prompt, output and working-margin reserves. This value is
        *not* always sent as ``options.num_ctx`` — see :meth:`request_num_ctx`.
        """
        budget = self.config.body_budget
        window = (
            budget.context_window_tokens
            or self._detect_context_window()
            or DEFAULT_CONTEXT_WINDOW_TOKENS
        )
        if budget.usable_body_chars:
            window = max(window, window_tokens_for_body_chars(budget.usable_body_chars, OLLAMA_BUDGET))
        return window

    def request_num_ctx(self) -> int | None:
        """``options.num_ctx`` for a page call, or ``None`` to leave the server default.

        Sent only when the window came from config (``context_window_tokens`` /
        ``usable_body_chars``) or a Modelfile ``num_ctx`` from ``/api/show``.
        The assumed 8,192-token budget fallback is never forced onto the server.
        """
        budget = self.config.body_budget
        if budget.context_window_tokens or budget.usable_body_chars:
            return self.context_window_tokens()
        self._probe_show()
        return self._modelfile_num_ctx

    def synthesize_document_chunk(
        self,
        chunk: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        return self.synthesize_source_page(
            chunk, meta, prompt_template, body_cap=self.usable_body_chars()
        )

    # ---- BaseSynthesizer interface --------------------------------

    def is_available(self) -> bool:
        """Probe ``/api/tags`` with a 2-second timeout.

        Returns True iff the server responds 2xx. Any exception
        (connection refused, DNS failure, HTTP 5xx, etc.) is swallowed
        and returns False — callers should branch on this before calling
        :meth:`synthesize_source_page`.
        """
        try:
            status, _ = self._http_get(
                self.config.tags_url, timeout=min(self.config.timeout, 2)
            )
            return 200 <= status < 300
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            logger.debug("Ollama availability probe failed: %s", exc)
            return False

    def overview_completion(
        self, prompt: str, *, model: str | None = None
    ) -> str:
        """Site-overview one-shot via ``/api/generate`` (full capped prompt)."""
        if not self.is_available():
            raise OllamaUnavailableError(
                f"Ollama is not reachable at {self.config.base_url}"
            )
        use_model = model or self.config.model
        data = self._call_generate(
            {
                "model": use_model,
                "prompt": prompt,
                "stream": False,
            }
        )
        response = data.get("response", "")
        if not isinstance(response, str):
            raise OllamaError(
                f"Ollama returned non-string response: {type(response).__name__}"
            )
        text = response.strip()
        if not text:
            raise OllamaError("Ollama returned an empty completion")
        return text

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
        *,
        body_cap: int = SESSION_BODY_SEND_CAP_CHARS,
    ) -> str:
        """Render ``prompt_template`` with the session body + metadata
        and send it to Ollama. Returns the model's raw completion text.

        Raises
        ------
        OllamaUnavailableError
            The server could not be reached at all (connection refused,
            DNS failure, etc.). Callers should skip synthesis and move on.
        OllamaHTTPError
            The server returned a non-2xx response after all retries.
        BackendUsageLimitError
            That non-2xx response's body reports an exhausted account quota.
        """
        # Sessions / evidence keep the historical cap; a document chunk
        # arrives already within usable_body_chars and is sent whole (#311).
        # #py-h7 (#585): we own the prompt render (body + meta placeholders).
        truncated_body = raw_body[:body_cap] if raw_body else ""
        # Ollama bills nothing, but it does keep a KV cache keyed on the
        # prompt prefix: passing the run-stable half as `system` keeps that
        # prefix identical across pages, so only the per-page tail is
        # re-evaluated. Same split every backend uses, different mechanism.
        stable, per_page = split_prompt_template(prompt_template)
        prompt = _render_prompt(per_page, raw_body=truncated_body, meta=meta)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }
        # Only force num_ctx when we know it (config or Modelfile) — never the
        # assumed budget default, which would shrink a larger server context.
        num_ctx = self.request_num_ctx()
        if num_ctx is not None:
            payload["options"] = {"num_ctx": num_ctx}
        if stable:
            payload["system"] = stable

        data = self._call_generate(payload)
        response = data.get("response", "")
        if not isinstance(response, str):
            raise OllamaError(
                f"Ollama returned non-string response: {type(response).__name__}"
            )
        return response.strip()

    # ---- internals -----------------------------------------------

    def _call_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to /api/generate with retry + backoff."""
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                status, body = self._http_post(
                    self.config.generate_url,
                    payload,
                    timeout=self.config.timeout,
                )
            except OllamaUnavailableError:
                # Connection refused / DNS failure — don't retry. The
                # server simply isn't listening; retrying wastes time.
                raise
            except (TimeoutError, urllib.error.URLError) as exc:
                last_exc = exc
                logger.warning(
                    "Ollama request attempt %d/%d failed: %s",
                    attempt,
                    self.config.max_retries,
                    exc,
                )
                if attempt == self.config.max_retries:
                    raise OllamaError(f"Ollama call failed: {exc}") from exc
                time.sleep(self.config.backoff_base * (2 ** (attempt - 1)))
                continue

            if 200 <= status < 300:
                try:
                    return json.loads(body)
                except ValueError as exc:
                    raise OllamaError(
                        f"Ollama returned non-JSON body: {exc}"
                    ) from exc

            if 500 <= status < 600 and attempt < self.config.max_retries:
                logger.warning(
                    "Ollama %s returned %d; retrying (%d/%d)",
                    self.config.generate_url,
                    status,
                    attempt,
                    self.config.max_retries,
                )
                time.sleep(self.config.backoff_base * (2 ** (attempt - 1)))
                continue

            # A quota message in the error body (a hosted model's weekly
            # limit, say) stops the run; a bare 429 is a per-page error.
            limit = usage_limit_from_text(body, label="Ollama")
            if limit is not None:
                raise limit
            raise OllamaHTTPError(status, body)

        # Unreachable if max_retries >= 1, but keep the type checker honest
        raise OllamaError(f"Ollama call failed after retries: {last_exc}")


# ─── HTTP transport (stdlib) ──────────────────────────────────────────


def _urlopen_post(
    url: str, payload: dict[str, Any], *, timeout: float
) -> tuple[int, str]:
    """POST JSON and return (status, body) as text. Raises
    :class:`OllamaUnavailableError` on connection refused / DNS failure."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # Server responded, but with an error code — treat as protocol
        # failure and return the status/body so retry logic can decide.
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            raise OllamaUnavailableError(
                f"Ollama server refused connection at {url}. "
                "Is `ollama serve` running?"
            ) from exc
        if isinstance(reason, socket.gaierror):
            raise OllamaUnavailableError(
                f"Ollama host DNS lookup failed for {url}: {reason}"
            ) from exc
        raise


def _urlopen_get(url: str, *, timeout: float) -> tuple[int, str]:
    """GET and return (status, body). Same error-mapping rules as POST."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            raise OllamaUnavailableError(
                f"Ollama server refused connection at {url}."
            ) from exc
        if isinstance(reason, socket.gaierror):
            raise OllamaUnavailableError(
                f"Ollama host DNS lookup failed for {url}: {reason}"
            ) from exc
        raise


# ─── Prompt rendering ─────────────────────────────────────────────────


def _render_prompt(
    template: str, *, raw_body: str, meta: dict[str, Any]
) -> str:
    """Substitute ``{body}`` and ``{meta}`` placeholders in the template.

    We deliberately use ``str.replace`` (not ``.format``) because session
    bodies contain ``{}`` in code blocks — calling ``.format`` there would
    raise ``KeyError``.
    """
    meta_dump = json.dumps(meta, indent=2, default=str, sort_keys=True)
    return template.replace("{body}", raw_body).replace("{meta}", meta_dump)
