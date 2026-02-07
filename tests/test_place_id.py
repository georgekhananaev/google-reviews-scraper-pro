"""Tests for place ID extraction from various URL formats."""

import pytest

from modules.place_id import extract_place_id, canonicalize_url


class TestExtractPlaceId:
    """Tests for extract_place_id()."""

    def test_short_link(self):
        result = extract_place_id(
            "https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9",
            "https://www.google.com/maps/place/Some+Place/@33.1,-117.3,17z"
        )
        # resolved URL has no CID or hex, but original is short link
        # hex extraction from resolved takes priority if present
        assert result  # should return a valid ID

    def test_cid_url(self):
        result = extract_place_id(
            "https://www.google.com/maps?cid=12345678",
            "https://www.google.com/maps?cid=12345678"
        )
        assert result == "cid:12345678"

    def test_hex_place_id(self):
        url = "https://www.google.com/maps/place/Thai+Tours/@13.7,100.5,17z/data=!4m8!3m7!1s0x80dcb8f3015f:0x123abc"
        result = extract_place_id(url, url)
        assert result.startswith("0x")

    def test_short_link_only(self):
        original = "https://maps.app.goo.gl/ABC123"
        resolved = "https://www.google.com/maps/place/Test/@33.1,-117.3"
        result = extract_place_id(original, resolved)
        # No hex ID in resolved, should fall back to short link
        assert "ABC123" in result or result.startswith("hash:")

    def test_fallback_to_hash(self):
        result = extract_place_id(
            "https://www.google.com/maps/search/random+place/",
            "https://www.google.com/maps/search/random+place/"
        )
        assert result.startswith("hash:")

    def test_empty_urls(self):
        result = extract_place_id("", "")
        assert result.startswith("hash:")

    def test_resolved_url_takes_priority(self):
        original = "https://maps.app.goo.gl/SHORT123"
        resolved = "https://www.google.com/maps?cid=99999"
        result = extract_place_id(original, resolved)
        assert result == "cid:99999"

    def test_cid_with_spaces(self):
        result = extract_place_id(
            "https://www.google.com/maps?cid= 12345 ",
            "https://www.google.com/maps?cid= 12345 "
        )
        assert result == "cid:12345"


class TestCanonicalizeUrl:
    """Tests for canonicalize_url()."""

    def test_lowercase_host(self):
        result = canonicalize_url("https://WWW.GOOGLE.COM/maps/place/Test")
        assert "www.google.com" in result

    def test_strip_trailing_slash(self):
        result = canonicalize_url("https://google.com/maps/place/Test/")
        assert not result.endswith("/") or result.endswith("Test")

    def test_remove_utm_params(self):
        result = canonicalize_url(
            "https://google.com/maps?q=test&utm_source=share&utm_medium=web"
        )
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "q=test" in result

    def test_remove_fbclid(self):
        result = canonicalize_url(
            "https://google.com/maps?q=test&fbclid=abc123"
        )
        assert "fbclid" not in result

    def test_sort_query_params(self):
        result = canonicalize_url("https://google.com/maps?z=1&a=2&m=3")
        assert result.index("a=2") < result.index("m=3") < result.index("z=1")

    def test_empty_url(self):
        assert canonicalize_url("") == ""

    def test_preserves_path(self):
        result = canonicalize_url(
            "https://google.com/maps/place/Thai+Tours/@13.7,100.5"
        )
        assert "Thai+Tours" in result

    def test_strips_fragment(self):
        result = canonicalize_url("https://google.com/maps#section")
        assert "#" not in result
