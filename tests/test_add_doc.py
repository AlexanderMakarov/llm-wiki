"""Tests for llmwiki.add_doc — llmwiki add pipeline (issue #16). Offline only."""

from __future__ import annotations

import pytest

from llmwiki.add_doc import AddError, assert_public_url

# ── SSRF guard (port of kbbuilder wiki-convert.ts assertPublicUrl) ──

@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "file:///etc/passwd",
    "gopher://example.com",
])
def test_blocked_schemes(url):
    with pytest.raises(AddError, match="scheme"):
        assert_public_url(url)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x",
    "http://10.1.2.3/x",
    "http://192.168.1.1/x",
    "http://172.16.0.1/x",
    "http://169.254.169.254/latest/meta-data",   # cloud metadata
    "http://100.64.0.1/x",                        # CGNAT / tailnet
    "http://0.0.0.0/x",
    "http://[::1]/x",
    "http://[::ffff:127.0.0.1]/x",                # v4-mapped loopback
    "http://[64:ff9b::7f00:1]/x",                 # NAT64 loopback
    "http://[fe80::1]/x",
    "http://[fd00::1]/x",                          # unique-local
])
def test_blocked_addresses(url):
    with pytest.raises(AddError, match="non-public|resolve"):
        assert_public_url(url)


def test_public_ip_literal_allowed():
    assert_public_url("https://1.1.1.1/")  # must not raise


def test_invalid_url_rejected():
    with pytest.raises(AddError):
        assert_public_url("not a url at all")
