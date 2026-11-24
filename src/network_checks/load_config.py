"""Load a product profile from targets YAML.

NETWORK_PROFILE selects ecommerce, erp, cms, or fintech.
TARGETS_FILE overrides the YAML path. A gitignored config/targets.yaml wins
over the committed example so real URLs never have to be committed.

.env may set NETWORK_PROFILE and TARGETS_FILE only. Hosts and baseUrl stay
in YAML. Already-exported shell or CI variables win over .env.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

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
    },
    "http": {
        "notFoundPath": "/net-h05-missing-path",
        "expectedHeaders": ["content-type"],
    },
    "tls": {
        "badCertHost": "expired.badssl.com",
        "sniMismatchHost": "wrong.host.badssl.com",
    },
    "negative": {
        "slowUrl": "https://httpbin.org/delay/8",
        "slowTimeoutSec": 2,
    },
    "overlays": [],
}

RESERVED_KEYS = {"defaults"}
_DOTENV_LOADED = False


class ConfigError(Exception):
    """The targets file or selected profile cannot be used."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_runner_env(env_file: str | Path | None = None, *, force: bool = False) -> Path | None:
    """Load .env for NETWORK_PROFILE / TARGETS_FILE. Does not override the shell."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED and not force and env_file is None:
        return project_root() / ".env"
    path = Path(env_file) if env_file is not None else project_root() / ".env"
    if path.is_file():
        load_dotenv(path, override=False)
    if env_file is None:
        _DOTENV_LOADED = True
    return path if path.is_file() else None


def resolve_targets_path(explicit: str | None = None) -> Path:
    load_runner_env()
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


def load_profile(profile: str | None = None, targets_file: str | None = None) -> dict[str, Any]:
    """Return one profile with defaults filled in and the name attached."""
    load_runner_env()
    path = resolve_targets_path(targets_file)
    if not path.is_file():
        raise ConfigError(
            f"Targets file not found: {path}. Copy config/targets.example.yaml "
            "to config/targets.yaml and set NETWORK_PROFILE."
        )
    document = _read_yaml(path)
    name = profile or os.environ.get("NETWORK_PROFILE") or "cms"
    known = [key for key in document if key not in RESERVED_KEYS]
    if name not in document or name in RESERVED_KEYS:
        raise ConfigError(
            f"Unknown NETWORK_PROFILE {name!r}. Choose one of: {', '.join(known) or '(none)'}."
        )
    merged = _merge(CODE_DEFAULTS, document.get("defaults") or {})
    merged = _merge(merged, document[name])
    _validate(name, merged)
    merged["name"] = name
    merged["targetsFile"] = str(path)
    merged["usingExampleTargets"] = path.name == "targets.example.yaml"
    merged["criticalPort"] = int(merged["criticalPort"] if merged["criticalPort"] is not None else merged["ports"][0])
    merged["ports"] = [int(port) for port in merged["ports"]]
    merged["latencyMs"] = int(merged["latencyMs"])
    merged["timeoutSec"] = float(merged["timeoutSec"])
    merged["negativeTimeoutSec"] = float(merged["negativeTimeoutSec"])
    merged["closedPort"] = int(merged["closedPort"])
    merged["http"]["expectedStatus"] = [int(code) for code in merged["http"]["expectedStatus"]]
    merged["http"]["expectedHeaders"] = [str(header).lower() for header in merged["http"]["expectedHeaders"]]
    merged["dns"]["minAddresses"] = int(merged["dns"]["minAddresses"])
    merged["dns"]["resolverPort"] = int(merged["dns"]["resolverPort"])
    if not merged["dns"].get("multiAHost"):
        merged["dns"]["multiAHost"] = merged["hosts"][0]
    merged["tls"]["host"] = merged["tls"].get("host") or merged["hosts"][0]
    merged["tls"]["port"] = int(merged["tls"].get("port") or merged["criticalPort"])
    merged["negative"]["slowTimeoutSec"] = float(merged["negative"]["slowTimeoutSec"])
    return merged


def health_url(profile: dict[str, Any]) -> str:
    base = str(profile["http"]["baseUrl"]).rstrip("/")
    path = str(profile["http"]["healthPath"])
    if not path.startswith("/"):
        path = "/" + path
    return base + path


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
