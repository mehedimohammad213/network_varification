"""Load one site profile — dynamically from TARGET_URL, or from YAML.

Primary path: set TARGET_URL (CLI) or paste a site link (UI). One condition
builds hosts, baseUrl, ports, and redirect for any site.

Fallback: a single `site` block in config/targets.yaml (or the example file)
when TARGET_URL is unset. Optional TARGETS_FILE overrides the YAML path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from network_checks.from_url import profile_from_url

CODE_DEFAULTS: dict[str, Any] = {
    "readOnly": True,
    "criticalPort": None,
    "unreachableHost": "192.0.2.1",
    "closedPort": 81,
    "negativeTimeoutSec": 3,
    "dns": {
        "nxdomainHost": "net-d02-does-not-exist.invalid",
        "minAddresses": 1,
        "badResolver": "192.0.2.1",
        "resolverPort": 53,
        # Empty = NET-D05 skipped.
        "expectedAddresses": [],
    },
    "http": {
        "notFoundPath": "/net-h05-missing-path",
        "expectedHeaders": ["content-type"],
        # Empty = NET-H07 skipped.
        "headerContains": {},
    },
    "tls": {
        "badCertHost": "expired.badssl.com",
        "sniMismatchHost": "wrong.host.badssl.com",
        "minDaysRemaining": 14,
        "mtls": {
            "certFile": "",
            "keyFile": "",
            "caFile": "",
            "host": "",
            "port": None,
        },
    },
    "negative": {
        "slowUrl": "https://httpbin.org/delay/8",
        "slowTimeoutSec": 2,
    },
    "overlays": [],
}

RESERVED_KEYS = {"defaults"}
DEFAULT_PROFILE = "site"


class ConfigError(Exception):
    """The targets file or selected profile cannot be used."""


def project_root() -> Path:
    """Monorepo root (contains config/, packages/, reports/)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config").is_dir() and (parent / "packages").is_dir():
            return parent
    return here.parents[4]


def resolve_targets_path(explicit: str | None = None) -> Path:
    root = project_root()
    candidate = explicit if explicit is not None else os.environ.get("TARGETS_FILE")
    if candidate:
        path = Path(candidate)
        if not path.is_absolute():
            from_cwd = (Path.cwd() / path).resolve()
            path = from_cwd if from_cwd.is_file() else (root / path).resolve()
        return path
    local = root / "config" / "targets.yaml"
    if local.is_file():
        return local
    return root / "config" / "targets.example.yaml"


def list_profiles(targets_file: str | None = None) -> list[dict[str, Any]]:
    """Return profile names and short descriptions (YAML fallback only)."""
    path = resolve_targets_path(targets_file)
    if not path.is_file():
        raise ConfigError(f"Targets file not found: {path}.")
    document = _read_yaml(path)
    profiles = []
    for name, block in document.items():
        if name in RESERVED_KEYS or not isinstance(block, dict):
            continue
        profiles.append(
            {
                "name": name,
                "description": str(block.get("description") or name),
            }
        )
    return profiles


def load_profile(
    profile: str | None = None,
    targets_file: str | None = None,
    target_url: str | None = None,
) -> dict[str, Any]:
    """Return one profile with defaults filled in and the name attached.

    Prefer TARGET_URL / target_url (dynamic). Otherwise load the YAML `site`
    profile (or NETWORK_PROFILE if set).
    """
    url = (target_url if target_url is not None else os.environ.get("TARGET_URL") or "").strip()
    if url:
        try:
            block = profile_from_url(url)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        return _finalize(
            DEFAULT_PROFILE,
            block,
            targets_file="(dynamic from TARGET_URL)",
            using_example=False,
            file_defaults={},
        )

    path = resolve_targets_path(targets_file)
    if not path.is_file():
        raise ConfigError(
            f"Targets file not found: {path}. Set TARGET_URL=https://your-site.com/ "
            "or copy config/targets.example.yaml to config/targets.yaml."
        )
    document = _read_yaml(path)
    name = profile or os.environ.get("NETWORK_PROFILE") or DEFAULT_PROFILE
    known = [key for key in document if key not in RESERVED_KEYS]
    if name not in document or name in RESERVED_KEYS:
        raise ConfigError(
            f"Unknown NETWORK_PROFILE {name!r}. Choose one of: {', '.join(known) or '(none)'} "
            "or set TARGET_URL."
        )
    return _finalize(
        name,
        document[name],
        targets_file=str(path),
        using_example=path.name == "targets.example.yaml",
        file_defaults=document.get("defaults") or {},
    )


def health_url(profile: dict[str, Any]) -> str:
    base = str(profile["http"]["baseUrl"]).rstrip("/")
    path = str(profile["http"]["healthPath"])
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _finalize(
    name: str,
    block: dict[str, Any],
    *,
    targets_file: str,
    using_example: bool,
    file_defaults: dict[str, Any],
) -> dict[str, Any]:
    merged = _merge(CODE_DEFAULTS, file_defaults)
    merged = _merge(merged, block)
    _validate(name, merged)
    merged["name"] = name
    merged["targetsFile"] = targets_file
    merged["usingExampleTargets"] = using_example
    merged["criticalPort"] = int(
        merged["criticalPort"] if merged["criticalPort"] is not None else merged["ports"][0]
    )
    merged["ports"] = [int(port) for port in merged["ports"]]
    merged["latencyMs"] = int(merged["latencyMs"])
    merged["timeoutSec"] = float(merged["timeoutSec"])
    merged["negativeTimeoutSec"] = float(merged["negativeTimeoutSec"])
    merged["closedPort"] = int(merged["closedPort"])
    merged["http"]["expectedStatus"] = [int(code) for code in merged["http"]["expectedStatus"]]
    merged["http"]["expectedHeaders"] = [
        str(header).lower() for header in merged["http"]["expectedHeaders"]
    ]
    header_contains = merged["http"].get("headerContains") or {}
    if not isinstance(header_contains, dict):
        raise ConfigError(f"Profile {name!r} http.headerContains must be a mapping of header to substring.")
    merged["http"]["headerContains"] = {
        str(key).lower(): str(value) for key, value in header_contains.items() if str(value)
    }
    merged["dns"]["minAddresses"] = int(merged["dns"]["minAddresses"])
    merged["dns"]["resolverPort"] = int(merged["dns"]["resolverPort"])
    expected_addresses = merged["dns"].get("expectedAddresses") or []
    if not isinstance(expected_addresses, list):
        raise ConfigError(f"Profile {name!r} dns.expectedAddresses must be a list.")
    merged["dns"]["expectedAddresses"] = [str(addr) for addr in expected_addresses if str(addr)]
    if not merged["dns"].get("multiAHost"):
        merged["dns"]["multiAHost"] = merged["hosts"][0]
    merged["tls"]["host"] = merged["tls"].get("host") or merged["hosts"][0]
    merged["tls"]["port"] = int(merged["tls"].get("port") or merged["criticalPort"])
    merged["tls"]["minDaysRemaining"] = int(merged["tls"].get("minDaysRemaining") or 14)
    mtls = merged["tls"].get("mtls") or {}
    if not isinstance(mtls, dict):
        raise ConfigError(f"Profile {name!r} tls.mtls must be a mapping.")
    cert_file = str(mtls.get("certFile") or "").strip()
    key_file = str(mtls.get("keyFile") or "").strip()
    ca_file = str(mtls.get("caFile") or "").strip()
    mtls_host = str(mtls.get("host") or "").strip() or merged["tls"]["host"]
    mtls_port = mtls.get("port")
    merged["tls"]["mtls"] = {
        "certFile": cert_file,
        "keyFile": key_file,
        "caFile": ca_file,
        "host": mtls_host,
        "port": int(mtls_port) if mtls_port not in (None, "") else merged["tls"]["port"],
    }
    merged["negative"]["slowTimeoutSec"] = float(merged["negative"]["slowTimeoutSec"])
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path} must be a mapping of profile names.")
    return loaded


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate(name: str, profile: dict[str, Any]) -> None:
    hosts = profile.get("hosts")
    if not isinstance(hosts, list) or not hosts or not all(isinstance(host, str) and host for host in hosts):
        raise ConfigError(f"Profile {name!r} needs a non-empty hosts list.")
    ports = profile.get("ports")
    if not isinstance(ports, list) or not ports:
        raise ConfigError(f"Profile {name!r} needs a non-empty ports list.")
    http = profile.get("http")
    if not isinstance(http, dict):
        raise ConfigError(f"Profile {name!r} needs an http mapping.")
    for key in ("baseUrl", "healthPath", "expectedStatus"):
        if not http.get(key):
            raise ConfigError(f"Profile {name!r} is missing http.{key}.")
    if not str(http["baseUrl"]).startswith(("http://", "https://")):
        raise ConfigError(f"Profile {name!r} http.baseUrl must start with http:// or https://.")
    for key in ("latencyMs", "timeoutSec"):
        if profile.get(key) in (None, ""):
            raise ConfigError(f"Profile {name!r} is missing {key}.")
