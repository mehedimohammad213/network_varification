# Network test catalog

Stable IDs. Automation uses the same ID in the test name and a `net_*` marker, so a JUnit failure maps back to one row.

Priority: P0 blocks release traffic. P1 is the full suite. Smoke is every P0 case plus NET-P01, because the gate's critical path includes the latency budget.

Lab oracles (not the product under test):

| Key | Default | Used by |
|-----|---------|---------|
| `unreachableHost` | `192.0.2.1` | NET-C03, NET-P02 |
| `dns.nxdomainHost` | `net-d02-does-not-exist.invalid` | NET-D02 |
| `dns.badResolver` | `192.0.2.1:53` | NET-D04 |
| `tls.badCertHost` | `expired.badssl.com` | NET-N02 |
| `tls.sniMismatchHost` | `wrong.host.badssl.com` | NET-N04 |
| `negative.slowUrl` | `https://httpbin.org/delay/8` | NET-N03 |

`http.redirectUrl` is never defaulted to a public site. Set it to the product's plaintext URL. The example file uses `http://one.one.one.one/` only so DEV-LAB has a real redirect.

## Connectivity (P0)

| ID | Priority | Suite | Preconditions | Steps | Expected | Automated |
|----|----------|-------|---------------|-------|----------|-----------|
| NET-C01 | P0 | smoke | Profile host and `criticalPort`; runner has a route | Open TCP to each `hosts[]` entry on `criticalPort` within `timeoutSec` | Connection succeeds | `test_NET_C01_tcp_reachability` |
| NET-C02 | P0 | smoke | `criticalPort` is listed in `ports` | Open TCP to the primary host on `criticalPort` | That port accepts a connection | `test_NET_C02_critical_port_open` |
| NET-C03 | P0 | smoke | `unreachableHost` is TEST-NET-1, not a product host | Open TCP to `unreachableHost` with `negativeTimeoutSec` | Not open; error is a timeout; elapsed stays inside the budget plus 2s | `test_NET_C03_unreachable_host_times_out` |
| NET-C04 | P0 | smoke | `closedPort` is a port the product must not serve (example: 81) | Open TCP to the primary host on `closedPort` | Connection does not succeed, and the client returns inside the budget | `test_NET_C04_wrong_port_is_closed` |

Manual oracle: `nc -vz -w <seconds> <host> <port>`.

Overlay endpoints in the profile use the same TCP helper. `test_overlay_endpoints_reachable` runs in the full suite, not in smoke.

## DNS (P0 / P1)

| ID | Priority | Suite | Preconditions | Steps | Expected | Automated |
|----|----------|-------|---------------|-------|----------|-----------|
| NET-D01 | P0 | smoke, transient | System resolver can reach DNS | Resolve the primary host. One extra attempt only if the first raises a timeout or OS error | At least one address | `test_NET_D01_resolve_fqdn` |
| NET-D02 | P0 | smoke | `dns.nxdomainHost` is a name that must not exist | Resolve that name | `DNSError` with kind `nxdomain` | `test_NET_D02_nxdomain` |
| NET-D03 | P1 | full | `dns.multiAHost` and `dns.minAddresses` match the DNS design. Example lab: `one.one.one.one` and 2. A product with one address sets `minAddresses: 1` or publishes the real count | Resolve `multiAHost` | Unique address count is at least `minAddresses` | `test_NET_D03_multi_a` |
| NET-D04 | P1 | full | `dns.badResolver` does not answer (default TEST-NET-1) | Send one UDP DNS A query to that resolver | `TimeoutError` inside `negativeTimeoutSec` | `test_NET_D04_bad_resolver_times_out` |

Manual oracle: `getent hosts <name>`. NXDOMAIN should exit non-zero.

## HTTP and TLS (P0)

| ID | Priority | Suite | Preconditions | Steps | Expected | Automated |
|----|----------|-------|---------------|-------|----------|-----------|
| NET-H01 | P0 | smoke | `http.baseUrl` + `http.healthPath` is a read-only health or GraphQL endpoint. `expectedStatus` may include 401 when the route is auth-gated on purpose | GET the health URL with TLS verification on | Final status is in `expectedStatus`; final URL is `https` | `test_NET_H01_health_get` |
| NET-H02 | P0 | smoke | Port 443 presents the real certificate | Handshake with default trust and SNI equal to the host | Protocol is TLS 1.2 or 1.3 and a cipher is negotiated | `test_NET_H02_tls_handshake` |
| NET-H03 | P0 | smoke | `http.redirectUrl` is the product's `http://` URL | GET it and follow redirects | Final URL is `https` and status is below 400 | `test_NET_H03_redirect_completes` |
| NET-H04 | P0 | smoke | `http.expectedHeaders` lists names the origin actually sends | GET the health URL | Each listed header is present, compared case-insensitively | `test_NET_H04_response_headers` |
| NET-H05 | P0 | smoke | `http.notFoundPath` is a path that must not return 200. SPAs that answer 200 for unknown paths need a real 4xx route here | GET `baseUrl` + `notFoundPath` | Status is 400–499 | `test_NET_H05_client_error_status` |

Manual oracle: `curl -sS -D - -o /dev/null --max-time <timeout> <url>`.

## Latency and resilience (P1)

| ID | Priority | Suite | Preconditions | Steps | Expected | Automated |
|----|----------|-------|---------------|-------|----------|-----------|
| NET-P01 | P1 | smoke | `latencyMs` is the staging or lab budget, not a content-test threshold. DEV-LAB example uses 3000. A CMS staging budget of 800 belongs in `targets.yaml` | GET the health URL and time the client | Status is acceptable and elapsed milliseconds are at or under `latencyMs` | `test_NET_P01_latency_within_sla` |
| NET-P02 | P1 | full | Uses the blackhole host, not the product | HTTPS GET `unreachableHost` with `negativeTimeoutSec` | `httpx.TimeoutException`, and the call returns inside the budget plus 2s | `test_NET_P02_soft_timeout` |
| NET-P03 | P1 | full | No network. The limit is the unit under test | Invoke a failing operation with `attempts=3`, then one that succeeds on the second call | The failing operation is called exactly 3 times. The recovering operation is not called after it returns | `test_NET_P03_limited_retries` |

Only NET-D01 is marked transient. NET-P03 is what keeps every other retry from growing.

## Negative and edge (P1 / P2)

| ID | Priority | Suite | Preconditions | Steps | Expected | Automated |
|----|----------|-------|---------------|-------|----------|-----------|
| NET-N01 | P1 | full | Same `http.redirectUrl` as NET-H03, without following | GET the plaintext URL | Status is 301, 302, 303, 307, or 308, and `Location` starts with `https://` | `test_NET_N01_http_upgrades_to_https` |
| NET-N02 | P1 | full | Lab host with an expired certificate, default `expired.badssl.com` | Handshake with default trust | `TlsError` kind `verify`. The client must not accept the certificate | `test_NET_N02_bad_cert_fails_closed` |
| NET-N03 | P1 | full | `negative.slowUrl` answers slower than `negative.slowTimeoutSec` | GET that URL with the short timeout | `httpx.TimeoutException` inside the short budget plus 3s | `test_NET_N03_slow_response_times_out` |
| NET-N04 | P2 | full | Lab host whose certificate does not match the name, default `wrong.host.badssl.com` | Handshake with SNI equal to that host | `TlsError` kind `verify` | `test_NET_N04_sni_mismatch_fails_closed` |

Do not set `verify=False` to make N02 or N04 pass.

## Domain overlays

Overlays are extra TCP endpoints on the same profile. They do not add business assertions. Put a host in `hosts` as well when it must join the smoke path.

### Ecommerce

| Overlay | What to put in the profile | Case that covers it |
|---------|----------------------------|---------------------|
| Storefront and CDN | `hosts` plus an overlay `cdn` on 443 | NET-C01, NET-H01 |
| Checkout API | Overlay `checkout-api`, health path of the API, expected 200 or 401 | NET-H01, NET-H05 |
| HTTP storefront | `http.redirectUrl` on port 80 | NET-H03, NET-N01 |

Do not encode cart or payment rules here.

### ERP

| Overlay | What to put in the profile | Case that covers it |
|---------|----------------------------|---------------------|
| ERP API / SOAP front door | Private hostname, port 443, VPN required before the run | NET-D01, NET-C01, NET-H02 |
| Database listener | Only from a runner on the app subnet, as an overlay port. Leave it out of DEV-LAB | Overlay TCP check |

A closed database port from a laptop off the subnet is a path finding, not an app defect. Confirm VPN and source address before filing it.

### CMS

| Overlay | What to put in the profile | Case that covers it |
|---------|----------------------------|---------------------|
| GraphQL or REST origin | `http.baseUrl`, `healthPath` (`/health` or the GraphQL path), `expectedStatus` 200 or 401 | NET-H01 |
| Preview / draft host | Extra `hosts` entry | NET-C01, NET-H02 |
| Media CDN | Overlay `media-cdn` | Overlay TCP check |
| Auth host | Reachability only. No client secret in the YAML | NET-C01 |
| Webhook receiver | TCP overlay if the runner is allowed to touch it | Overlay TCP check |

Admin publish flows, content rules, and permissions are a different suite.

### Fintech

| Overlay | What to put in the profile | Case that covers it |
|---------|----------------------------|---------------------|
| Payment gateway | 443 overlay. Read-only | NET-C01, NET-H02 |
| Webhook receiver | TCP overlay from the allowlisted runner | Overlay TCP check |
| mTLS | Not automated in v1. A green TCP check does not prove the client certificate | Manual follow-up |

`readOnly: true` is the default. The HTTP helper implements GET only. Do not store gateway credentials in the targets file.

## Traceability

| Profile switch | Test |
|----------------|------|
| All four names load | `test_profile_switch` |
| Overlay name stays with its product | `test_each_profile_keeps_its_overlay` |
| Unknown name fails with the known list | `test_unknown_profile_rejected` |
| `TARGETS_FILE` overrides the example | `test_targets_file_override` |
| A minimal block does not gain a public redirect URL | `test_minimal_profile_does_not_invent_a_public_url` |
