"""`llmwiki add` — universal document intake (issue #16).

Converts URLs / files / folders to Markdown and lands them under
raw/docs/ in the exact layout kbbuilder's async add-doc worker
produces (dir per doc, section-aware chunks), so a machine running
both never sees format drift. Spec:
docs/superpowers/specs/2026-07-04-llmwiki-add-design.md

Security posture ported from kbbuilder src/wiki-convert.ts: SSRF
egress guard (scheme + every resolved address + every redirect hop)
and a sensitive-path denylist for local reads.
"""

from __future__ import annotations

import ipaddress
import re as _re  # aliased: `re` is shadowed by hot loop locals in later sections
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

__all__ = [
    "AddError",
    "FetchResult",
    "assert_public_url",
    "guarded_fetch",
    "DEFAULT_CHUNK_MAX_CHARS",
    "MarkdownChunk",
    "chunk_markdown_by_sections",
]


class AddError(Exception):
    """User-facing failure adding one source (bad URL, blocked address,
    unreadable path, missing optional converter)."""


# ── SSRF egress guard ────────────────────────────────────────────────
# `llmwiki add <url>` fetches from the local machine; kbbuilder may
# later shell out to it with queue-supplied URLs, so an internal URL
# could reach cloud metadata (169.254.169.254), localhost services, or
# tailnet hosts (100.64/10). Validate scheme + every resolved address,
# and re-validate across redirect hops.

# NAT64 well-known prefix — embedded IPv4 must itself be public.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _is_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(addr, ipaddress.IPv6Address):
        mapped = addr.ipv4_mapped
        if mapped is not None:
            return _is_blocked(mapped)
        if addr in _NAT64:
            embedded = ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
            return _is_blocked(embedded)
    # is_global is False for private/loopback/link-local/CGNAT(100.64/10)/
    # unique-local/unspecified/reserved; multicast is excluded explicitly
    # for older Pythons where ff00::/8 slips through is_global.
    return not addr.is_global or addr.is_multicast


def assert_public_url(raw: str) -> None:
    """Raise AddError unless `raw` is an http(s) URL whose host resolves
    only to public addresses."""
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise AddError(f"blocked URL scheme {parsed.scheme!r} (only http/https allowed): {raw}")
    host = parsed.hostname
    if not host:
        raise AddError(f"invalid URL: {raw}")
    try:
        infos = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as exc:
        raise AddError(f"could not resolve host {host}: {exc}") from exc
    if not infos:
        raise AddError(f"could not resolve host: {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked(ip):
            raise AddError(f"refusing to fetch non-public address {ip} for host {host}")


@dataclass
class FetchResult:
    url: str  # final URL after redirects
    status: int
    content_type: str
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None  # surface 3xx as HTTPError so we can re-validate the hop


_OPENER = urllib.request.build_opener(_NoRedirect)


def guarded_fetch(url: str, headers: dict[str, str], timeout: int = 30) -> FetchResult:
    """Fetch with manual redirect handling (<=5 hops), re-validating every
    hop against the SSRF guard. Returns non-2xx statuses as FetchResult
    (callers decide on retries) rather than raising."""
    current = url
    for _hop in range(5):
        assert_public_url(current)
        req = urllib.request.Request(current, headers=headers)
        try:
            resp = _OPENER.open(req, timeout=timeout)
        except urllib.error.HTTPError as err:
            if err.code in (301, 302, 303, 307, 308):
                loc = err.headers.get("Location")
                if not loc:
                    raise AddError(f"redirect ({err.code}) without Location from {current}") from err
                current = urljoin(current, loc)
                continue
            body = err.read().decode("utf-8", errors="replace") if err.fp else ""
            return FetchResult(
                url=current,
                status=err.code,
                content_type=err.headers.get("Content-Type", ""),
                headers=dict(err.headers.items()),
                body=body,
            )
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise AddError(f"fetch failed for {current}: {exc}") from exc
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return FetchResult(
            url=current,
            status=resp.status,
            content_type=ctype,
            headers=dict(resp.headers.items()),
            body=raw.decode(charset, errors="replace"),
        )
    raise AddError(f"too many redirects fetching {url}")


# ── section chunking (port of kbbuilder chunkMarkdownBySections) ─────
# Synthesis distills ONE input file into ONE wiki page per pass. A large
# document overflows the model context in that single pass, so we split
# by section at WRITE time — each chunk becomes one synthesis input that
# fits. 7000 chars keeps a chunk inside the agent-delegate synthesizer's
# raw_body[:8000] prompt embed (llmwiki/synth/agent_delegate.py) with
# headroom for frontmatter + breadcrumb. The cap is soft: splits happen
# at heading, then paragraph boundaries; a hard slice only ever hits a
# single paragraph longer than the whole budget.

DEFAULT_CHUNK_MAX_CHARS = 7000

_FENCE_RE = _re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass
class MarkdownChunk:
    index: int          # 1-based position within the document
    total: int
    heading: str        # first heading inside the chunk ('' if none)
    body: str           # verbatim slice, newline-terminated


def _first_heading_line(body: str) -> str:
    fence = None
    for line in body.split("\n"):
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
            continue
        if fence is not None:
            continue
        h = _re.match(r"^#{1,6}\s+(.*)$", line.lstrip())
        if h:
            return h.group(1).strip()
    return ""


def _split_sections(text: str, levels: tuple[int, ...]) -> list[str]:
    lines = text.split("\n")
    sections: list[str] = []
    buf: list[str] = []
    fence = None
    for line in lines:
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
        h = _re.match(r"^(#{1,6})\s", line)
        if fence is None and h and len(h.group(1)) in levels and buf:
            sections.append("\n".join(buf) + "\n")
            buf = []
        buf.append(line)
    if buf:
        sections.append("\n".join(buf) + "\n")
    return sections


def _split_oversized(section: str, max_chars: int) -> list[str]:
    paras = _re.split(r"\n{2,}", section)
    out: list[str] = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            out.append(cur.rstrip("\n") + "\n")
        cur = ""

    for p in paras:
        if len(p) > max_chars:
            flush()
            for i in range(0, len(p), max_chars):
                piece = p[i:i + max_chars].strip()
                if piece:
                    out.append(piece + "\n")
            continue
        if cur and len(cur) + len(p) + 2 > max_chars:
            flush()
        cur += ("\n\n" if cur else "") + p
    flush()
    return out


def chunk_markdown_by_sections(
    markdown: str,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    heading_levels: tuple[int, ...] = (1, 2),
) -> list[MarkdownChunk]:
    """Split a Markdown document into section-aligned chunks ≤ max_chars.
    Sections pack greedily; an oversized section splits on blank-line
    paragraph boundaries, hard-slicing only as a last resort. Heading
    detection is fence-aware. A document within budget returns whole."""
    text = markdown.replace("\r\n", "\n")
    sections = _split_sections(text, heading_levels)
    bodies: list[str] = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            bodies.append(cur.rstrip("\n") + "\n")
        cur = ""

    for sec in sections:
        if len(sec) > max_chars:
            flush()
            bodies.extend(_split_oversized(sec, max_chars))
            continue
        if cur and len(cur) + len(sec) > max_chars:
            flush()
        cur += sec
    flush()

    if not bodies:
        body = text.strip()
        if not body:
            return []
        return [MarkdownChunk(1, 1, _first_heading_line(body), body + "\n")]
    total = len(bodies)
    return [MarkdownChunk(i + 1, total, _first_heading_line(b), b) for i, b in enumerate(bodies)]
