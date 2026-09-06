#!/usr/bin/env python3
"""Assert that a live llmwiki site serves the version we think it does (#213).

`llmwiki build` stamps `site/manifest.json` with `llmwiki.__version__`, so the
manifest is the one thing on a deployed site that says which build is live.
Nothing ever read it back, which is how the demo site sat four releases stale:
`pages.yml` had no tag trigger, and no check compared the published site with
the code that was supposed to be on it.

Two callers:

    # after a deploy — page_url ends with "/", manifest.json is appended
    python3 scripts/check_live_version.py --url "$PAGE_URL" --attempts 6 --delay 15

    # weekly freshness guard against the published demo
    python3 scripts/check_live_version.py --url https://example.github.io/llm-wiki/manifest.json

The expected version defaults to `__version__` in the checked-out tree, which
makes the assertion identical for a tag push and a manual dispatch. Pass
`--expected` to compare against something else (e.g. a tag name — a leading
"v" is stripped).

`--url` retries cover the full check (fetch → parse → compare), not just
transport failures: GitHub Pages often returns HTTP 200 with the previous
`manifest.json` until the CDN updates, so a version mismatch or an HTML-as-200
body also sleeps `--delay` and tries again until `--attempts` is exhausted.
`--manifest-json` is a single-shot offline path (no retry loop) for fixtures
and unit tests.

Exit codes are distinct so a workflow log says *why* it failed:

    0  live version matches
    1  mismatch — the site is stale (or ahead of) the expected version
    2  unreachable — the manifest could not be fetched
    3  malformed — the response was not JSON, or carried no version

Stdlib only. The comparison helpers are importable and pure, so tests exercise
them against fixtures without touching the network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_UNREACHABLE = 2
EXIT_MALFORMED = 3

MANIFEST_NAME = "manifest.json"
DEFAULT_TIMEOUT = 30.0

REPO_ROOT = Path(__file__).resolve().parent.parent

_VERSION_LINE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


class ManifestError(Exception):
    """The manifest was fetched but could not be read as a version."""


class UnreachableError(Exception):
    """The manifest could not be fetched at all."""


def manifest_url(url: str) -> str:
    """Return the manifest URL for `url`, which may be a site root or the file.

    `actions/deploy-pages` hands back a `page_url` ending in "/", but a human
    running this by hand naturally pastes the manifest link itself. Accept both
    rather than making the caller remember which one this wants.
    """
    stripped = url.strip()
    if not stripped:
        raise ValueError("empty URL")
    if stripped.rsplit("/", 1)[-1] == MANIFEST_NAME:
        return stripped
    return f"{stripped.rstrip('/')}/{MANIFEST_NAME}"


def normalise_version(version: str) -> str:
    """Strip surrounding whitespace and a tag's leading "v" ("v2.1.0" → "2.1.0")."""
    cleaned = version.strip()
    if cleaned[:1] in {"v", "V"}:
        cleaned = cleaned[1:]
    return cleaned


def parse_manifest_version(payload: str) -> str:
    """Pull `version` out of a manifest document.

    Raises `ManifestError` when the payload is not JSON, is not an object, or
    carries no usable version — all three mean "we cannot tell what is live",
    which must fail loudly rather than pass as a non-match.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError(f"response is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"manifest is a {type(data).__name__}, expected an object")
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ManifestError("manifest has no usable 'version' field")
    return version.strip()


def versions_match(live: str, expected: str) -> bool:
    """Compare two versions ignoring surrounding whitespace and a leading "v"."""
    return normalise_version(live) == normalise_version(expected)


def package_version(repo_root: Path = REPO_ROOT) -> str:
    """Read `__version__` from the checked-out tree.

    Read as text rather than imported: the freshness workflow installs no
    dependencies, and importing the package would pull in `markdown` for the
    sake of one string. Falls back to an import when the source file is not
    where we expect it (an installed copy, say).
    """
    init_py = repo_root / "llmwiki" / "__init__.py"
    if init_py.is_file():
        found = _VERSION_LINE.search(init_py.read_text(encoding="utf-8"))
        if found:
            return found.group(1)
    # Deferred: only reached when this runs outside a source checkout.
    from llmwiki import __version__

    return __version__


def fetch_manifest(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Fetch `url` once. Raises `UnreachableError` on transport failure."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "llmwiki-check-live-version"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UnreachableError(f"could not fetch {url}: {exc}") from exc


def check_url(
    url: str,
    expected: str,
    attempts: int = 1,
    delay: float = 10.0,
    timeout: float = DEFAULT_TIMEOUT,
) -> int:
    """Fetch → parse → compare `url` against `expected`, retrying until exhausted.

    GitHub Pages often returns HTTP 200 with the previous manifest until the CDN
    updates, so version mismatches and HTML-as-200 bodies retry the same way
    transient fetch failures do. Only after `--attempts` is spent do we return
    EXIT_MISMATCH / EXIT_MALFORMED / EXIT_UNREACHABLE for the last outcome.
    """
    source = manifest_url(url)
    budget = max(attempts, 1)
    last_code = EXIT_UNREACHABLE
    last_detail = f"could not fetch {source}"

    for attempt in range(1, budget + 1):
        try:
            payload = fetch_manifest(source, timeout=timeout)
        except UnreachableError as exc:
            last_code = EXIT_UNREACHABLE
            last_detail = str(exc)
            print(f"attempt {attempt}/{budget}: {source} not readable yet ({exc})", file=sys.stderr)
            if attempt < budget:
                time.sleep(delay)
            continue

        try:
            live = parse_manifest_version(payload)
        except ManifestError as exc:
            last_code = EXIT_MALFORMED
            last_detail = f"{source}: {exc}"
            print(f"attempt {attempt}/{budget}: {source} not a usable manifest yet ({exc})", file=sys.stderr)
            if attempt < budget:
                time.sleep(delay)
            continue

        if versions_match(live, expected):
            print(f"OK: {source} serves version {live}")
            return EXIT_OK

        last_code = EXIT_MISMATCH
        last_detail = (
            f"{source} serves version {live}, expected {normalise_version(expected)}."
        )
        print(f"attempt {attempt}/{budget}: {last_detail}", file=sys.stderr)
        if attempt < budget:
            time.sleep(delay)

    print(f"ERROR: {last_detail}", file=sys.stderr)
    if last_code == EXIT_MISMATCH:
        print("The published site does not match this commit — republish it (#213).", file=sys.stderr)
    return last_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare the version a live llmwiki site serves with the version it should serve.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="site root or manifest.json URL (a site root gets /manifest.json appended)")
    source.add_argument(
        "--manifest-json",
        help="read the manifest from this file instead of the network ('-' for stdin)",
    )
    parser.add_argument(
        "--expected",
        help="version the site should serve (default: __version__ in the checked-out tree; a leading 'v' is stripped)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="fetch→parse→compare attempts before giving up when using --url (default: 1; ignored for --manifest-json)",
    )
    parser.add_argument("--delay", type=float, default=10.0, help="seconds between --url attempts (default: 10)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="per-request timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    expected = args.expected or package_version()

    if args.url:
        try:
            return check_url(
                args.url,
                expected,
                attempts=args.attempts,
                delay=args.delay,
                timeout=args.timeout,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return EXIT_UNREACHABLE

    # --manifest-json: single-shot offline path (no retry loop).
    if args.manifest_json == "-":
        payload = sys.stdin.read()
        source = "<stdin>"
    else:
        source = args.manifest_json
        try:
            payload = Path(args.manifest_json).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot read {source}: {exc}", file=sys.stderr)
            return EXIT_UNREACHABLE

    try:
        live = parse_manifest_version(payload)
    except ManifestError as exc:
        print(f"ERROR: {source}: {exc}", file=sys.stderr)
        return EXIT_MALFORMED

    if not versions_match(live, expected):
        print(f"ERROR: {source} serves version {live}, expected {normalise_version(expected)}.", file=sys.stderr)
        print("The published site does not match this commit — republish it (#213).", file=sys.stderr)
        return EXIT_MISMATCH

    print(f"OK: {source} serves version {live}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
