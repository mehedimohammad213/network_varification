"""NET-N01 through NET-N04. Certificates fail closed."""

import time

import httpx
import pytest

from network_checks.http_client import http_get
from network_checks.tls_check import TlsError, tls_handshake

pytestmark = [pytest.mark.negative]


@pytest.mark.net_n01
def test_NET_N01_http_upgrades_to_https(profile, case) -> None:
    url = profile["http"].get("redirectUrl")
    assert url, "Set http.redirectUrl to the plaintext URL that must redirect to HTTPS"
    assert url.startswith("http://")
    result = http_get(url, timeout=profile["timeoutSec"], follow_redirects=False)
    case.actual = f"status={result.status}; location={result.location or '-'}"
    assert result.status in {301, 302, 303, 307, 308}
    assert result.location.startswith("https://")


@pytest.mark.net_n02
def test_NET_N02_bad_cert_fails_closed(profile, case) -> None:
    host = profile["tls"]["badCertHost"]
    with pytest.raises(TlsError) as caught:
        tls_handshake(host, 443, profile["timeoutSec"])
    case.actual = f"kind={caught.value.kind}; host={host}"
    assert caught.value.kind == "verify"


@pytest.mark.net_n03
def test_NET_N03_slow_response_times_out(profile, case) -> None:
    timeout = profile["negative"]["slowTimeoutSec"]
    started = time.perf_counter()
    with pytest.raises(httpx.TimeoutException) as caught:
        http_get(profile["negative"]["slowUrl"], timeout=timeout)
    elapsed = time.perf_counter() - started
    case.actual = f"raised={type(caught.value).__name__}; elapsed_s={elapsed:.2f}"
    assert elapsed < timeout + 3


@pytest.mark.net_n04
def test_NET_N04_sni_mismatch_fails_closed(profile, case) -> None:
    host = profile["tls"]["sniMismatchHost"]
    with pytest.raises(TlsError) as caught:
        tls_handshake(host, 443, profile["timeoutSec"])
    case.actual = f"kind={caught.value.kind}; host={host}"
    assert caught.value.kind == "verify"
