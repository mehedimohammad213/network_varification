"""Build a one-off targets YAML from a pasted site URL."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml


def normalize_target_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Paste a site link, for example https://example.com/")
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Link must start with http:// or https://")
    if not parsed.hostname:
        raise ValueError("Could not read a hostname from that link.")
    return text


def adhoc_profile_from_url(raw: str) -> dict:
    """Return an adhoc profile block suitable for targets YAML."""
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

    https_base = f"https://{netloc}"
    http_origin = f"http://{netloc}/"
    # Prefer the pasted path as health; keep an http redirect oracle on the same host.
    return {
        "description": f"Ad-hoc check for {text}",
        "hosts": [host],
        "ports": [critical],
        "criticalPort": critical,
        "latencyMs": 3000,
        "timeoutSec": 5,
        "http": {
            "baseUrl": https_base if parsed.scheme == "https" else f"http://{netloc}",
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


def write_adhoc_targets(raw: str, path: Path) -> tuple[str, str]:
    """Write targets YAML with profile name adhoc. Returns (profile_name, health_url)."""
    profile = adhoc_profile_from_url(raw)
    document = {"adhoc": profile}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    base = str(profile["http"]["baseUrl"]).rstrip("/")
    health = base + str(profile["http"]["healthPath"])
    return "adhoc", health
