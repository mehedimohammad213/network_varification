"""NET-D01 through NET-D05."""

import pytest

from network_checks.dns import DNSError, query_resolver, resolve
from network_checks.latency import run_with_limit

pytestmark = [pytest.mark.dns]


@pytest.mark.smoke
@pytest.mark.transient
@pytest.mark.net_d01
def test_NET_D01_resolve_fqdn(profile, case) -> None:
    host = profile["hosts"][0]

    def lookup():
        return resolve(host)

    answer = run_with_limit(lookup, attempts=2)
    case.actual = f"name={answer.name}; addresses={list(answer.addresses)}"
    assert answer.addresses
    assert answer.name == host


@pytest.mark.smoke
@pytest.mark.net_d02
def test_NET_D02_nxdomain(profile, case) -> None:
    name = profile["dns"]["nxdomainHost"]
    with pytest.raises(DNSError) as caught:
        resolve(name)
    case.actual = f"kind={caught.value.kind}; name={name}"
    assert caught.value.kind == "nxdomain"


@pytest.mark.net_d03
def test_NET_D03_multi_a(profile, case) -> None:
    dns = profile["dns"]
    answer = resolve(dns["multiAHost"])
    case.actual = (
        f"host={dns['multiAHost']}; count={len(answer.addresses)}; "
        f"min={dns['minAddresses']}; addresses={list(answer.addresses)}"
    )
    assert len(answer.addresses) >= dns["minAddresses"]


@pytest.mark.net_d04
def test_NET_D04_bad_resolver_times_out(profile, case) -> None:
    dns = profile["dns"]
    with pytest.raises(TimeoutError) as caught:
        query_resolver(
            profile["hosts"][0],
            dns["badResolver"],
            dns["resolverPort"],
            profile["negativeTimeoutSec"],
        )
    case.actual = f"raised={type(caught.value).__name__}: {caught.value}"


@pytest.mark.net_d05
def test_NET_D05_expected_addresses(profile, case) -> None:
    expected = profile["dns"]["expectedAddresses"]
    if not expected:
        pytest.skip("dns.expectedAddresses is empty; pin gateway IPs for fintech staging")
    host = profile["hosts"][0]
    answer = resolve(host)
    unexpected = [addr for addr in answer.addresses if addr not in expected]
    missing = [addr for addr in expected if addr not in answer.addresses]
    case.actual = (
        f"resolved={list(answer.addresses)}; expected={expected}; "
        f"unexpected={unexpected or '-'}; missing_ok={missing or '-'}"
    )
    # Every resolved address must be on the allowlist. Missing allowlist entries are OK
    # (anycast / regional subsets) as long as nothing outside the list appears.
    assert not unexpected, f"addresses outside allowlist: {unexpected}"
