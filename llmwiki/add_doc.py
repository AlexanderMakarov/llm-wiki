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
import json
import re as _re  # aliased: `re` is shadowed by hot loop locals in later sections
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

from llmwiki import __version__
from llmwiki.htmlmd import html_to_markdown
from llmwiki.slugs import derive_title, slugify

__all__ = [
    "AddError",
    "FetchResult",
    "assert_public_url",
    "guarded_fetch",
    "DEFAULT_CHUNK_MAX_CHARS",
    "MarkdownChunk",
    "chunk_markdown_by_sections",
    "ConvertedDoc",
    "assert_readable_path",
    "convert_path",
    "AGENT_UA",
    "BROWSER_UA",
    "CHALLENGE_MARKERS",
    "convert_url",
    "write_raw_doc",
    "add_sources",
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
    headers: dict[str, str] = field(default_factory=dict)  # keys lowercased
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
                headers={k.lower(): v for k, v in err.headers.items()},
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
            headers={k.lower(): v for k, v in resp.headers.items()},
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


# ── local file / folder conversion ───────────────────────────────────

TEXTUAL_EXT = {
    ".md", ".markdown", ".txt", ".rst", ".org",
    ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java", ".c", ".h", ".cpp",
    ".json", ".yaml", ".yml", ".toml", ".sh", ".sql", ".html", ".css",
}

# Extensions markitdown converts that are worth supporting; anything
# else binary is refused with a clear message.
_MARKITDOWN_EXT = {".pdf", ".docx", ".pptx", ".xlsx", ".epub"}

# Paths that almost always hold secrets — never ingest, ever.
# Port of kbbuilder SENSITIVE_PATH_PATTERNS (wiki-convert.ts).
_SENSITIVE_RES = [
    _re.compile(r"(^|[\\/])\.env(\.[^\\/]*)?$", _re.I),
    _re.compile(r"(^|[\\/])\.ssh([\\/]|$)", _re.I),
    _re.compile(r"(^|[\\/])\.aws([\\/]|$)", _re.I),
    _re.compile(r"(^|[\\/])\.gnupg([\\/]|$)", _re.I),
    _re.compile(r"(^|[\\/])\.netrc$", _re.I),
    _re.compile(r"(^|[\\/])id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$", _re.I),
    _re.compile(r"\.(pem|key|p12|pfx|keystore|jks)$", _re.I),
    _re.compile(r"(^|[\\/])(credentials|secret|secrets)(\.[^\\/]*)?$", _re.I),
    _re.compile(r"(^|[\\/])shadow$", _re.I),
]


def _is_sensitive(path: str) -> bool:
    return any(rx.search(path) for rx in _SENSITIVE_RES)


try:  # optional [add] extra — used for PDF/docx/pptx/xlsx/epub
    from markitdown import MarkItDown as _MarkItDown

    def _markitdown_convert(path: Path) -> str:
        return _MarkItDown().convert(str(path)).text_content
except ImportError:  # pragma: no cover — exercised via monkeypatch in tests
    _markitdown_convert = None


@dataclass
class ConvertedDoc:
    """One source converted to markdown, before slug/title finalization."""
    title: str                       # provisional (filename/URL); finalized by the writer
    markdown: str
    source_label: str                # original URL or absolute path, for frontmatter
    html_title: str | None = None  # <title> when the source was an HTML page
    url: str | None = None
    path_name: str | None = None   # filename/dirname for title fallback
    warnings: list[str] = field(default_factory=list)


def assert_readable_path(value: str) -> Path:
    """Path-traversal / secret-read guard. Rejects literal '..' segments,
    resolves symlinks, and refuses known-sensitive paths. Returns the
    resolved path. (No allowlist roots: the CLI runs as the user who
    typed the path — unlike kbbuilder's queue-driven worker.)"""
    if ".." in _re.split(r"[\\/]", value):
        raise AddError(f'path must not contain ".." segments: {value}')
    try:
        real = Path(value).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AddError(f"cannot resolve path: {value}") from exc
    if _is_sensitive(str(real)) or _is_sensitive(value):
        raise AddError(f"refusing to read sensitive path: {value}")
    return real


def _fence_code(text: str, ext: str) -> str:
    lang = ext.lstrip(".")
    return f"```{lang}\n" + text.replace("```", "`​``").rstrip() + "\n```"


def _note_header(note: str | None) -> str:
    return f"> {note.strip()}\n\n" if note and note.strip() else ""


def _walk_folder(dir_path: Path, depth: int = 0) -> str:
    """Concatenate a folder's textual files as '## name' sections.
    Depth-capped, sorted, dotfiles/node_modules skipped, symlinks never
    followed (they can escape the directory), sensitive paths skipped."""
    if depth > 6:
        return ""
    out: list[str] = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: p.name):
        if entry.name.startswith(".") or entry.name == "node_modules":
            continue
        if entry.is_symlink():
            continue
        if _is_sensitive(str(entry)):
            continue
        if entry.is_dir():
            nested = _walk_folder(entry, depth + 1)
            if nested:
                out.append(nested)
        elif entry.is_file() and entry.suffix.lower() in TEXTUAL_EXT:
            text = entry.read_text(encoding="utf-8", errors="replace")
            ext = entry.suffix.lower()
            body = text.strip() if ext in (".md", ".markdown") else _fence_code(text, ext)
            out.append(f"## {entry.name}\n\n{body}\n")
    return "\n".join(p for p in out if p)


def convert_path(value: str, note: str | None = None) -> ConvertedDoc:
    """Convert a local file or folder to one markdown document."""
    real = assert_readable_path(value)
    label = str(real)
    if real.is_dir():
        title = real.name
        body = _walk_folder(real)
        markdown = _note_header(note) + f"# {title}\n\n" + body
        return ConvertedDoc(title=title, markdown=markdown, source_label=label,
                            path_name=real.name)
    ext = real.suffix.lower()
    if ext in (".md", ".markdown"):
        text = real.read_text(encoding="utf-8", errors="replace")
        return ConvertedDoc(title=real.stem, markdown=_note_header(note) + text.strip() + "\n",
                            source_label=label, path_name=real.name)
    if ext in _MARKITDOWN_EXT:
        if _markitdown_convert is None:
            raise AddError(
                f"converting {ext} needs markitdown — install the optional extra: "
                "pip install 'llm-notebook[add]'"
            )
        text = _markitdown_convert(real)
        return ConvertedDoc(title=real.stem, markdown=_note_header(note) + text.strip() + "\n",
                            source_label=label, path_name=real.name)
    # Any other extension: treat as text, fenced as code.
    text = real.read_text(encoding="utf-8", errors="replace")
    body = _fence_code(text, ext or ".txt")
    markdown = _note_header(note) + f"# {real.name}\n\n" + body + "\n"
    return ConvertedDoc(title=real.stem, markdown=markdown, source_label=label,
                        path_name=real.name)


# ── layered URL pipeline ─────────────────────────────────────────────
# Layer 1: content negotiation — Accept: text/markdown unlocks
#   Cloudflare "Markdown for Agents" / Read the Docs served markdown.
# Layer 2: static HTML extraction — trafilatura when installed (pullmd's
#   base extraction library; [add] extra), stdlib htmlmd otherwise.
# Quality gate: thin/challenge output ⇒ the page is JS-rendered or
#   bot-walled ⇒ Layer 3.
# Layer 3: headless render via playwright when importable ([e2e] extra).

AGENT_UA = f"llmwiki-add/{__version__} (+https://github.com/AlexanderMakarov/llm-wiki)"
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CHALLENGE_MARKERS = ("just a moment", "enable javascript", "checking your browser",
                     "attention required", "verify you are human")

_MIN_TEXT_CHARS = 200


def _looks_challenged(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in CHALLENGE_MARKERS)


def _quality_ok(text: str, html: str) -> bool:
    if _looks_challenged(text):
        return False
    stripped = text.strip()
    if len(stripped) < _MIN_TEXT_CHARS:
        return False
    if len(html) > 20_000 and len(stripped) < len(html) // 100:
        return False
    return True


def _extract_html(html: str) -> tuple[str, str]:
    """(title, markdown) via trafilatura when available, stdlib otherwise."""
    try:
        import trafilatura
    except ImportError:
        return html_to_markdown(html)
    md = trafilatura.extract(html, output_format="markdown",
                             include_links=True, include_formatting=True)
    title = ""
    try:
        meta = trafilatura.extract_metadata(html)
        title = (meta.title or "") if meta else ""
    except Exception:  # noqa: BLE001 — metadata is best-effort
        pass
    if not md:
        return html_to_markdown(html)
    return title, md


def _default_renderer() -> object | None:
    """Playwright-backed renderer, or None when playwright is absent."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    def render(url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=BROWSER_UA)
                page.goto(url, wait_until="networkidle", timeout=60_000)
                return page.content()
            finally:
                browser.close()

    return render


_RENDER_HINT = ("content may be a JS shell — install the render layer: "
                "pip install 'llm-notebook[e2e]' && playwright install chromium, "
                "or re-run with --render")


def convert_url(
    url: str,
    note: str | None = None,
    *,
    fetch=None,
    renderer=None,
    render: str = "auto",
) -> ConvertedDoc:
    """Convert a URL to one markdown document via the layered pipeline."""
    do_fetch = fetch or guarded_fetch
    headers = {"Accept": "text/markdown, text/html;q=0.9, */*;q=0.5",
               "User-Agent": AGENT_UA}
    resp = do_fetch(url, headers)

    # Anti-bot posture: honest agent headers first (unlocks markdown
    # negotiation); one retry with a browser UA on 403 / challenge body.
    if resp.status == 403 or (resp.status == 200 and _looks_challenged(resp.body)):
        headers = dict(headers)
        headers["User-Agent"] = BROWSER_UA
        resp = do_fetch(url, headers)

    if resp.status != 200:
        raise AddError(f"fetch {url} failed: HTTP {resp.status}")

    ctype = resp.content_type.lower()
    header = f"> Source: <{url}>\n\n"
    warnings: list[str] = []

    if ctype.startswith("text/markdown"):
        saved = resp.headers.get("x-markdown-tokens")
        if saved:
            warnings.append(f"server-side markdown: ~{saved} tokens "
                            f"(original ~{resp.headers.get('x-original-tokens', '?')})")
        body = resp.body.strip()
        return ConvertedDoc(title="", markdown=_note_header(note) + header + body + "\n",
                            source_label=url, url=url,
                            warnings=warnings)

    is_html = "html" in ctype or _re.match(r"^\s*<(!doctype|html)", resp.body, _re.I)
    if not is_html:
        body = resp.body.strip()
        return ConvertedDoc(title="", markdown=_note_header(note) + header + body + "\n",
                            source_label=url, url=url)

    html = resp.body
    title, md = _extract_html(html)

    needs_render = render == "force" or (render == "auto" and not _quality_ok(md, html))
    if needs_render and render != "never":
        active_renderer = renderer if renderer is not None else _default_renderer()
        if active_renderer is not None:
            try:
                rendered_html = active_renderer(url)
            except Exception:  # noqa: BLE001 — a broken renderer degrades to a warning, not a crash
                active_renderer = None
            else:
                r_title, r_md = _extract_html(rendered_html)
                if len(r_md.strip()) > len(md.strip()):
                    title, md = (r_title or title), r_md
                if not _quality_ok(md, rendered_html):
                    warnings.append(_RENDER_HINT)
        if active_renderer is None:
            warnings.append(_RENDER_HINT)
    elif not _quality_ok(md, html):
        warnings.append(_RENDER_HINT)

    return ConvertedDoc(title="", markdown=_note_header(note) + header + md.strip() + "\n",
                        source_label=url, url=url, html_title=title or None,
                        warnings=warnings)


# ── raw-doc writer (byte-compatible with kbbuilder makeRawDocWriter) ─

def _dedupe(base: str, exists) -> str:
    """First of base, base-2, base-3, … for which exists() is False."""
    if not exists(base):
        return base
    n = 2
    while exists(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"


def _frontmatter(title: str, slug: str, project: str, tags: tuple[str, ...],
                 today: str, source: str) -> str:
    tag_list = ", ".join(("wiki-add", "raw-doc") + tags)
    return (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"slug: {slug}\n"
        f"project: {project}\n"
        "type: source\n"
        f"tags: [{tag_list}]\n"
        f"date: {today}\n"
        f"source: {json.dumps(source, ensure_ascii=False)}\n"
        "---\n\n"
    )


def write_raw_doc(
    doc: ConvertedDoc,
    docs_dir: Path,
    *,
    explicit_title: str | None = None,
    project: str | None = None,
    extra_tags: tuple[str, ...] = (),
    today: str | None = None,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
) -> list[Path]:
    """Write one converted doc under raw/docs/<project>/, chunked by
    section when large. Never overwrites (raw/ immutability): the doc
    slug is suffixed -2, -3, … on collision. Returns written paths."""
    title = derive_title(explicit=explicit_title, markdown=doc.markdown,
                         html_title=doc.html_title, url=doc.url,
                         path_name=doc.path_name)
    base_slug = slugify(title) or "untitled"
    day = today or date.today().isoformat()
    chunks = chunk_markdown_by_sections(doc.markdown, max_chars=chunk_max_chars)
    if not chunks:
        raise AddError(f"nothing to write for {doc.source_label} (empty document)")
    multi = len(chunks) > 1

    def slug_taken(target_dir: Path, s: str) -> bool:
        # Shape-independent probe: an earlier doc with the same slug may be a
        # single file (<s>.md) or chunked (<s>-NN.md) — the new doc's own
        # chunk count says nothing about what's already on disk.
        if (target_dir / f"{s}.md").exists():
            return True
        return any(target_dir.glob(f"{s}-[0-9][0-9].md"))

    if project:
        proj = slugify(project) or project
        target = docs_dir / proj
        slug = _dedupe(base_slug, lambda s: slug_taken(target, s))
    else:
        slug = _dedupe(base_slug, lambda s: (docs_dir / s).exists())
        proj = slug
        target = docs_dir / proj

    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for c in chunks:
        chunk_slug = f"{slug}-{c.index:02d}" if multi else slug
        sub = c.heading if (c.heading and c.heading != title) else ""
        if multi:
            chunk_title = f"{title} (part {c.index}/{c.total}" + (f": {sub}" if sub else "") + ")"
            breadcrumb = f"> Part {c.index} of {c.total} of **{title}**" + (f" — {sub}" if sub else "") + ".\n\n"
        else:
            chunk_title, breadcrumb = title, ""
        fm = _frontmatter(chunk_title, chunk_slug, proj, extra_tags, day, doc.source_label)
        path = target / f"{chunk_slug}.md"
        if path.exists():  # belt-and-braces: raw/ is immutable
            raise AddError(f"refusing to overwrite existing raw file {path}")
        path.write_text(fm + breadcrumb + c.body, encoding="utf-8")
        written.append(path)
    return written


def add_sources(
    sources: list[str],
    docs_dir: Path,
    *,
    title: str | None = None,
    project: str | None = None,
    tags: tuple[str, ...] = (),
    note: str | None = None,
    render: str = "auto",
    dry_run: bool = False,
    fetch=None,
    renderer=None,
    today: str | None = None,
) -> dict:
    """Convert + write a batch of sources. Post-steps (synthesize/build)
    are the CLI's job — this function only lands raw docs. Per-source
    failures are collected, not fatal: the rest of the batch lands."""
    written: list[Path] = []
    titles: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    for src in sources:
        try:
            if _re.match(r"^https?://", src):
                doc = convert_url(src, note, fetch=fetch, renderer=renderer, render=render)
            else:
                doc = convert_path(src, note)
            final_title = derive_title(explicit=title, markdown=doc.markdown,
                                       html_title=doc.html_title, url=doc.url,
                                       path_name=doc.path_name)
            titles.append(final_title)
            warnings.extend(f"{src}: {w}" for w in doc.warnings)
            if dry_run:
                chunks = chunk_markdown_by_sections(doc.markdown)
                slug = slugify(final_title) or "untitled"
                proj = slugify(project) if project else slug
                names = ([f"{slug}.md"] if len(chunks) <= 1
                         else [f"{slug}-{c.index:02d}.md" for c in chunks])
                warnings.append(f"{src}: dry-run — would write "
                                f"{', '.join(str(docs_dir / proj / n) for n in names)}")
                continue
            written.extend(write_raw_doc(doc, docs_dir, explicit_title=title,
                                         project=project, extra_tags=tags, today=today))
        except AddError as exc:
            errors.append(f"{src}: {exc}")
    return {"written": written, "titles": titles, "warnings": warnings, "errors": errors}
