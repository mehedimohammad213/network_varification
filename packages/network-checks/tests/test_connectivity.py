"""NET-C01 through NET-C04. TCP only; ping is not part of the gate."""

import pytest

from network_checks.tcp import check_tcp

pytestmark = [pytest.mark.connectivity]


@pytest.mark.smoke
@pytest.mark.net_c01
def test_NET_C01_tcp_reachability(profile, target_host: str, case) -> None:
    result = check_tcp(target_host, profile["criticalPort"], profile["timeoutSec"])
    case.actual = (
        f"open={result.open}; elapsed_ms={result.elapsed_ms:.0f}; error={result.error or '-'}"
    )
    assert result.open, result.error
    assert result.elapsed_ms < profile["timeoutSec"] * 1000


@pytest.mark.smoke
@pytest.mark.net_c02
def test_NET_C02_critical_port_open(profile, case) -> None:
    host = profile["hosts"][0]
    port = profile["criticalPort"]
    assert port in profile["ports"]
    result = check_tcp(host, port, profile["timeoutSec"])
    case.actual = f"port={result.port}; open={result.open}; error={result.error or '-'}"
    assert result.open, result.error
    assert result.port == port


@pytest.mark.smoke
@pytest.mark.net_c03
def test_NET_C03_unreachable_host_times_out(profile, case) -> None:
    timeout = profile["negativeTimeoutSec"]
    result = check_tcp(profile["unreachableHost"], profile["criticalPort"], timeout)
    case.actual = (
        f"open={result.open}; elapsed_ms={result.elapsed_ms:.0f}; error={result.error or '-'}"
    )
    assert result.open is False
    assert "timed out" in result.error.lower()
    assert result.elapsed_ms < (timeout + 2) * 1000


@pytest.mark.smoke
@pytest.mark.net_c04
def test_NET_C04_wrong_port_is_closed(profile, case) -> None:
    timeout = profile["negativeTimeoutSec"]
    result = check_tcp(profile["hosts"][0], profile["closedPort"], timeout)
    case.actual = (
        f"open={result.open}; elapsed_ms={result.elapsed_ms:.0f}; error={result.error or '-'}"
    )
    assert result.open is False
    assert result.elapsed_ms < (timeout + 2) * 1000


@pytest.mark.connectivity
def test_overlay_endpoints_reachable(profile, case) -> None:
    """Same TCP check as NET-C01, applied to profile overlays. Not a smoke case."""
    if not profile["overlays"]:
        pytest.skip("no overlays configured")
    failures = []
    ok = []
    for item in profile["overlays"]:
        result = check_tcp(item["host"], int(item["port"]), profile["timeoutSec"])
        if result.open:
            ok.append(item["name"])
        else:
            failures.append(f"{item['name']} {result.error}")
    case.actual = f"open={ok or '-'}; failed={failures or '-'}"
    assert not failures
