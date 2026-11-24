"""API helpers for site-link runs — shared builder lives in network_checks."""

from __future__ import annotations

from pathlib import Path

from network_checks.from_url import (
    normalize_target_url,
    profile_from_url as adhoc_profile_from_url,
    write_targets_from_url,
)

__all__ = [
    "normalize_target_url",
    "adhoc_profile_from_url",
    "write_adhoc_targets",
]


def write_adhoc_targets(raw: str, path: Path) -> tuple[str, str]:
    """Write dynamic targets YAML. Returns (profile_name, health_url)."""
    return write_targets_from_url(raw, path, profile_name="site")
