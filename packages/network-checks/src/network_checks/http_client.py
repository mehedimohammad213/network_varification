"""Read-only HTTP. This package does not send POST, PUT, PATCH, or DELETE."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class HttpResult:
    status: int
    url: str
    headers: dict[str, str]
    elapsed_ms: float
    location: str = ""


def http_get(url: str, timeout: float, follow_redirects: bool = True, verify: bool = True) -> HttpResult:
    timeout_cfg = httpx.Timeout(connect=timeout, read=timeout, write=timeout, pool=timeout)
    with httpx.Client(
        timeout=timeout_cfg,
        follow_redirects=follow_redirects,
        verify=verify,
        headers={"User-Agent": "network-checks/1.0"},
    ) as client:
        response = client.get(url)
    headers = {key.lower(): value for key, value in response.headers.items()}
    elapsed = response.elapsed.total_seconds() * 1000 if response.elapsed is not None else 0.0
    return HttpResult(
        status=response.status_code,
        url=str(response.url),
        headers=headers,
        elapsed_ms=elapsed,
        location=headers.get("location", ""),
    )
