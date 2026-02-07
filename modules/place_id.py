"""
Place ID extraction and URL canonicalization for Google Maps URLs.

Extracts stable place identifiers from various Google Maps URL formats.
Must be called AFTER browser navigation resolves redirects.
"""

import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


# Tracking params to strip during canonicalization
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "fbclid", "gclid", "dclid", "msclkid", "twclid",
    "igshid", "mc_cid", "mc_eid", "ref", "source",
})


def extract_place_id(original_url: str, resolved_url: str) -> str:
    """
    Extract a stable place identifier from a Google Maps URL.

    MUST be called AFTER navigation resolves (pass driver.current_url as resolved_url).

    Priority (applied to resolved_url first, then original_url):
    1. CID from query param (?cid=...)
    2. Hex place ID from /data= param (!1s0x...)
    3. Short link path segment (maps.app.goo.gl/...)
    4. SHA-256 hash of resolved_url as fallback
    """
    # Try resolved URL first, then original
    for url in (resolved_url, original_url):
        if not url:
            continue

        # 1. CID from query param
        cid = _extract_cid(url)
        if cid:
            return f"cid:{cid}"

        # 2. Hex place ID from data param
        hex_id = _extract_hex_id(url)
        if hex_id:
            return hex_id

    # 3. Short link path segment
    short_id = _extract_short_link_id(original_url)
    if short_id:
        return f"short:{short_id}"

    # 4. Fallback: SHA-256 hash of canonicalized resolved URL
    canon = canonicalize_url(resolved_url or original_url)
    return f"hash:{hashlib.sha256(canon.encode()).hexdigest()[:16]}"


def _extract_cid(url: str) -> str:
    """Extract CID from ?cid= query parameter."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    cid_values = params.get("cid", [])
    if cid_values and cid_values[0].strip():
        return cid_values[0].strip()
    return ""


def _extract_hex_id(url: str) -> str:
    """Extract hex place ID from /data= param in URL (e.g., !1s0x80dc...)."""
    match = re.search(r"!1s(0x[0-9a-fA-F]+:[0-9a-fA-F]+)", url)
    if match:
        return match.group(1)
    # Also try the shorter form without colon
    match = re.search(r"!1s(0x[0-9a-fA-F]{8,})", url)
    if match:
        return match.group(1)
    return ""


def _extract_short_link_id(url: str) -> str:
    """Extract path segment from maps.app.goo.gl short links."""
    parsed = urlparse(url)
    if "maps.app.goo.gl" in parsed.netloc or "goo.gl" in parsed.netloc:
        segments = [s for s in parsed.path.split("/") if s]
        if segments:
            return segments[-1]
    return ""


def canonicalize_url(url: str) -> str:
    """
    Normalize a URL for alias matching:
    - Lowercase host
    - Strip trailing slash
    - Remove tracking params (utm_*, fbclid, etc.)
    - Sort remaining query params
    """
    if not url:
        return ""

    parsed = urlparse(url)

    # Lowercase host
    netloc = parsed.netloc.lower()

    # Strip trailing slash from path
    path = parsed.path.rstrip("/") or "/"

    # Filter and sort query params
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {
        k: v for k, v in params.items()
        if k.lower() not in _TRACKING_PARAMS
    }
    sorted_query = urlencode(sorted(filtered.items()), doseq=True) if filtered else ""

    return urlunparse((
        parsed.scheme,
        netloc,
        path,
        parsed.params,
        sorted_query,
        "",  # strip fragment
    ))
