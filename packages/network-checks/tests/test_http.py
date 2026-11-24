"""NET-H01 through NET-H07. Health checks are GET only."""

import pytest

from network_checks.http_client import http_get
from network_checks.load_config import health_url
from network_checks.tls_check import days_remaining_for_host, mtls_handshake, tls_handshake

pytestmark = [pytest.mark.http]

ACCEPTED_TLS = {"TLSv1.2", "TLSv1.3"}


@pytest.mark.smoke
@pytest.mark.net_h01
def test_NET_H01_health_get(profile, case) -> None:
    result = http_get(health_url(profile), timeout=profile["timeoutSec"])
    case.actual = f"status={result.status}; url={result.url}"
    assert result.status in profile["http"]["expectedStatus"]
    assert result.url.startswith("https://")


@pytest.mark.smoke
@pytest.mark.net_h02
def test_NET_H02_tls_handshake(profile, case) -> None:
    tls = profile["tls"]
    handshake = tls_handshake(tls["host"], tls["port"], profile["timeoutSec"])
    case.actual = f"protocol={handshake.protocol}; cipher={handshake.cipher}"
    assert handshake.protocol in ACCEPTED_TLS
    assert handshake.cipher


@pytest.mark.smoke
@pytest.mark.net_h03
def test_NET_H03_redirect_completes(profile, case) -> None:
    url = profile["http"].get("redirectUrl")
    assert url, "Set http.redirectUrl to the plaintext URL that must end on HTTPS"
    result = http_get(url, timeout=profile["timeoutSec"], follow_redirects=True)
    case.actual = f"status={result.status}; url={result.url}"
    assert result.url.startswith("https://")
    assert result.status < 400


@pytest.mark.smoke
@pytest.mark.net_h04
def test_NET_H04_response_headers(profile, case) -> None:
    result = http_get(health_url(profile), timeout=profile["timeoutSec"])
    missing = [name for name in profile["http"]["expectedHeaders"] if name not in result.headers]
    present = [name for name in profile["http"]["expectedHeaders"] if name in result.headers]
    case.actual = f"present={present}; missing={missing or '-'}"
    assert not missing, f"missing headers: {missing}"


@pytest.mark.smoke
@pytest.mark.net_h05
def test_NET_H05_client_error_status(profile, case) -> None:
    base = str(profile["http"]["baseUrl"]).rstrip("/")
    path = str(profile["http"]["notFoundPath"])
    if not path.startswith("/"):
        path = "/" + path
    result = http_get(base + path, timeout=profile["timeoutSec"])
    case.actual = f"status={result.status}; url={result.url}"
    assert 400 <= result.status <= 499


@pytest.mark.smoke
@pytest.mark.net_h06
def test_NET_H06_cert_not_expiring_soon(profile, case) -> None:
    tls = profile["tls"]
    minimum = tls["minDaysRemaining"]
    days = days_remaining_for_host(tls["host"], tls["port"], profile["timeoutSec"])
    case.actual = f"days_remaining={days:.1f}; minDaysRemaining={minimum}"
    assert days >= minimum, f"certificate expires in {days:.1f} days (need >= {minimum})"


@pytest.mark.net_h07
def test_NET_H07_header_values(profile, case) -> None:
    required = profile["http"]["headerContains"]
    if not required:
        pytest.skip("http.headerContains is empty; set e.g. strict-transport-security: max-age=")
    result = http_get(health_url(profile), timeout=profile["timeoutSec"])
    failures = []
    for name, needle in required.items():
        value = result.headers.get(name, "")
        if needle.lower() not in value.lower():
            failures.append(f"{name} missing {needle!r} (got {value!r})")
    case.actual = f"checked={list(required)}; failures={failures or '-'}"
    assert not failures


@pytest.mark.net_m01
def test_NET_M01_mtls_handshake(profile, case) -> None:
    mtls = profile["tls"]["mtls"]
    if not mtls["certFile"] or not mtls["keyFile"]:
        pytest.skip("tls.mtls.certFile/keyFile not set; TCP overlay is not mTLS proof")
    handshake = mtls_handshake(
        mtls["host"],
        mtls["port"],
        profile["timeoutSec"],
        cert_file=mtls["certFile"],
        key_file=mtls["keyFile"],
        ca_file=mtls["caFile"] or None,
    )
    case.actual = (
        f"host={mtls['host']}; protocol={handshake.protocol}; cipher={handshake.cipher}"
    )
    assert handshake.protocol in ACCEPTED_TLS
    assert handshake.cipher
