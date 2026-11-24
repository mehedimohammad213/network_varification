"""Timing budget and a hard stop on retries.

Retries exist for tests marked transient. The helper never loops past
`attempts`, including the first call.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from network_checks.http_client import HttpResult, http_get

T = TypeVar("T")

TRANSIENT = (TimeoutError, OSError, ConnectionError)


def measure_get(url: str, timeout: float) -> tuple[HttpResult, float]:
    """GET url and return the result plus end-to-end milliseconds."""
    started = time.perf_counter()
    result = http_get(url, timeout=timeout, follow_redirects=True)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return result, elapsed_ms


def run_with_limit(operation: Callable[[], T], attempts: int) -> T:
    """Call operation up to `attempts` times. The last error is re-raised."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return operation()
        except TRANSIENT as exc:
            last_error = exc
    assert last_error is not None
    raise last_error
