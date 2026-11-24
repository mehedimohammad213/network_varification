"""Build one site profile dynamically from a URL.

Same shape for CLI (`TARGET_URL`) and the browser UI. No product-specific
YAML blocks — one condition works for any host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


def normalize_target_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Set TARGET_URL, for example https://example.com/")
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Link must start with http:// or https://")
    if not parsed.hostname:
        raise ValueError("Could not read a hostname from that link.")
    return text


def profile_from_url(raw: str) -> dict[str, Any]:
    """Return a full site profile block for any pasted or exported URL."""
    text = normalize_target_url(raw)
    parsed = urlparse(text)
    host = parsed.hostname
    assert host is not None
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = "/" + path

    if parsed.port:
        netloc = f"{host}:{parsed.port}"
        critical = int(parsed.port)
    else:
        netloc = host
        critical = 443 if parsed.scheme == "https" else 80

    base = f"{parsed.scheme}://{netloc}"
    http_origin = f"http://{netloc}/"
    return {
        "description": f"Dynamic check for {text}",
        "readOnly": True,
        "hosts": [host],
        "ports": [critical],
        "criticalPort": critical,
        "latencyMs": 3000,
        "timeoutSec": 5,
        "http": {
            "baseUrl": base,
            "healthPath": path,
            "expectedStatus": [200],
            "notFoundPath": "/net-h05-missing-path",
            "redirectUrl": http_origin,
            "expectedHeaders": ["content-type"],
        },
        "dns": {
            "multiAHost": host,
            "minAddresses": 1,
        },
        "overlays": [],
    }


def write_targets_from_url(raw: str, path: Path, *, profile_name: str = "site") -> tuple[str, str]:
    """Write a one-profile YAML. Returns (profile_name, health_url)."""
    profile = profile_from_url(raw)
    document = {profile_name: profile}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    base = str(profile["http"]["baseUrl"]).rstrip("/")
    health = base + str(profile["http"]["healthPath"])
    return profile_name, health
