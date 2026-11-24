"""NET-P01 through NET-P03."""

import time

import httpx
import pytest

from network_checks.http_client import http_get
from network_checks.latency import measure_get, run_with_limit
from network_checks.load_config import health_url

pytestmark = [pytest.mark.perf]


@pytest.mark.smoke
@pytest.mark.net_p01
def test_NET_P01_latency_within_sla(profile, case) -> None:
    result, elapsed_ms = measure_get(health_url(profile), timeout=profile["timeoutSec"])
    case.actual = (
        f"status={result.status}; elapsed_ms={elapsed_ms:.0f}; "
        f"sla_ms={profile['latencyMs']}"
    )
    assert result.status in profile["http"]["expectedStatus"]
    assert elapsed_ms <= profile["latencyMs"]


@pytest.mark.net_p02
def test_NET_P02_soft_timeout(profile, case) -> None:
    """A blackholed address must surface as a timeout, not a hung client."""
    timeout = profile["negativeTimeoutSec"]
    started = time.perf_counter()
    with pytest.raises(httpx.TimeoutException) as caught:
        http_get(
            f"https://{profile['unreachableHost']}/",
            timeout=timeout,
        )
    elapsed = time.perf_counter() - started
    case.actual = f"raised={type(caught.value).__name__}; elapsed_s={elapsed:.2f}"
    assert elapsed < timeout + 2


@pytest.mark.net_p03
def test_NET_P03_limited_retries(case) -> None:
    calls = {"n": 0}

    def always_down() -> None:
        calls["n"] += 1
        raise TimeoutError("downstream timeout")

    with pytest.raises(TimeoutError):
        run_with_limit(always_down, attempts=3)
    fail_calls = calls["n"]
    assert fail_calls == 3

    calls["n"] = 0

    def recovers() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("once")
        return "ok"

    assert run_with_limit(recovers, attempts=3) == "ok"
    case.actual = f"failing_calls={fail_calls}; recovering_calls={calls['n']}"
    assert calls["n"] == 2
