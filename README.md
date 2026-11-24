# Network quality gate

Reusable DNS, TCP, TLS, HTTP, and latency checks for ecommerce, ERP, CMS, and fintech. Point the suite at a product by editing a profile. The cases themselves stay in this repo.

This is a client-side probe. It does not open a browser, and it does not post, pay, or publish.

| Document | Contents |
|----------|----------|
| [docs/network_test_strategy.md](docs/network_test_strategy.md) | Objectives, environments, entry and exit, risks |
| [docs/test_cases.md](docs/test_cases.md) | `NET-*` catalog and domain overlays |

## Setup

Python 3.11 or newer (3.12 in CI).

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config/targets.example.yaml config/targets.yaml
cp .env.example .env
```

If `python3 -m venv` stops because `ensurepip` is missing, install the distro `python3-venv` package, or run `python3 -m venv .venv --without-pip` and bootstrap pip with `get-pip.py` inside that environment.

### Config vs `.env`

| File | Purpose | Committed? |
|------|---------|------------|
| `config/targets.yaml` | Hosts, `baseUrl`, ports, latency, overlays | No (gitignored) |
| `config/targets.example.yaml` | Safe public-lab sample | Yes |
| `.env` | `NETWORK_PROFILE` and optional `TARGETS_FILE` only | No (gitignored) |
| `.env.example` | Same keys, no secrets | Yes |

Do not put URLs in `.env`. Edit the YAML profile for those. Shell and CI exports still win over `.env`.

```bash
# .env
NETWORK_PROFILE=cms
# TARGETS_FILE=config/targets.yaml
```

If `targets.yaml` is missing, the loader uses the example and the report marks the run as DEV-LAB.

## Browser UI (for non-tech clients)

Python stays on the machine that hosts the app. Clients only open a browser.

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --app-dir packages/network-api --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Paste a site link **or** pick a profile, click **Run check**, and read Expected vs Actual. The same run still writes `reports/smoke.html` (or `full.html`).

API cheat sheet: `GET /api/profiles`, `POST /api/runs`, `GET /api/runs/{id}`, `GET /docs`.

## Smoke and full (CLI)

Run from the repository root (`.env` supplies the profile if you do not export it):

```bash
pytest -m smoke --html=reports/smoke.html --self-contained-html
```

Full suite, after smoke is green:

```bash
pytest --html=reports/full.html --self-contained-html --junitxml=reports/junit.xml
```

Override for one run:

```bash
NETWORK_PROFILE=ecommerce pytest -m smoke
pytest -m net_c03
```

Profiles that share the example file hit the same public lab, so any of `ecommerce`, `erp`, `cms`, or `fintech` can prove the suite. Change hosts in `targets.yaml` before treating a green run as product evidence.

## Reports

| Artifact | What it is |
|----------|------------|
| `reports/smoke.html` or `reports/full.html` | pytest-html, self-contained |
| `reports/junit.xml` | JUnit, when you pass `--junitxml` |
| `reports/evidence.txt` | Profile, targets path, example-file flag, UTC time, hostname, exit status |
| `reports/ui_results.json` | JSON for the browser UI (Expected / Actual rows) |

The HTML environment table repeats the profile and the targets file. The Results table includes **Expected** and **Actual** columns for each case. A row that says example targets are in use is not a staging result. `reports/` is gitignored except for `.gitkeep`.

## Add a product profile

1. Copy an existing block in `config/targets.yaml` (start from the example if the local file does not exist yet).
2. Name it, or reuse `ecommerce`, `erp`, `cms`, or `fintech`.
3. Set `hosts`, `ports`, `http.baseUrl`, `http.healthPath`, `http.expectedStatus`, `latencyMs`, and `timeoutSec`.
4. Set `http.redirectUrl` to that product's `http://` URL. The loader will not substitute a public URL.
5. Set `dns.multiAHost` and `dns.minAddresses` to the DNS design. Use `1` when the name has a single address.
6. Add overlays for extra ports (CDN, GraphQL origin, ERP API, payment gateway). They run in the full suite through the same TCP check as NET-C01.
7. Keep tokens, client certificates, and production credentials out of the file.
8. Run smoke against DEV-LAB first, then point the same keys at staging.

Minimal block:

```yaml
cms:
  hosts:
    - api.cms.staging.example.com
  ports: [443]
  http:
    baseUrl: https://api.cms.staging.example.com
    healthPath: /health
    expectedStatus: [200]    # or [401] when the route is gated on purpose
    redirectUrl: http://cms.staging.example.com/
  latencyMs: 800
  timeoutSec: 5
  overlays:
    - name: media-cdn
      host: cdn.cms.staging.example.com
      port: 443
```

`expectedStatus` may be 401 when a health or GraphQL route is supposed to demand auth. That is still a reachability result, not an auth test.

## CMS walkthrough

Network probing of the CMS, not the editor UI.

1. List endpoints: API or GraphQL origin, preview host, media CDN, webhook receiver, auth host.
2. Fill the `cms` profile. Auth host is reachability only.
3. Start the local CMS, or use staging URLs and connect VPN when the names are private.
4. Run the smoke command above.
5. Triage with the table below.
6. Run the full command once smoke is green.
7. Keep `reports/` with the ticket, and write down local vs staging. Check `using_example_targets` before you trust the run.

Not in this suite: publish flows, content rules, permissions.

## Triage

| First failure | Look at | Usually |
|---------------|---------|---------|
| NET-D01 / NET-D02 | Name, search suffix, VPN, resolver | DNS or path |
| NET-C01 / NET-C03 / NET-C04 | Port, firewall, wrong profile, host down | Routing or the process not listening |
| NET-H02 / NET-N02 / NET-N04 | Certificate, SNI, CDN, intercepting proxy | TLS. Do not disable verification |
| NET-H01 status 5xx | App health, not the test client | Application |
| NET-H01 status unexpected 401 | `expectedStatus` omits an intentional auth gate | Config |
| NET-H05 got 200 | SPA fallback. Point `notFoundPath` at a real 4xx | Config or origin |
| NET-P01 | `latencyMs` vs the network, not page content | SLA |
| NET-N03 only | Lab slow URL (`httpbin`) unreachable | Full-suite oracle, not the product |
| One smoke case, then green on rerun | NET-D01 is the only case allowed a second attempt | Flake if it stays rare. File it if it repeats |

Gate on smoke. Run the full suite nightly. Split the ticket into infra, application, DNS, TLS, or flake before changing a threshold.

## CI

`.github/workflows/network-checks.yml`

| Event | Suite | Profile |
|-------|-------|---------|
| Pull request | Smoke | `cms` |
| Nightly 02:00 UTC, and manual dispatch | Full | `cms` |

The job fails when smoke fails. HTML and JUnit are uploaded as artifacts. Point `NETWORK_PROFILE` and the runner's network at staging when the example lab is no longer the target. Private ERP and fintech production need a runner that is already allowlisted; do not put credentials in the workflow.

## Layout

Monorepo with three packages (shared `config/`, `docs/`, `reports/` at the root):

```
packages/network-checks/   probe library + pytest suite (NET-* cases)
  src/network_checks/
  tests/
  pytest.ini
packages/network-api/      FastAPI runner for the browser UI
packages/network-web/      HTML / CSS / JS client page
config/                    targets.example.yaml (+ local targets.yaml)
docs/
reports/                   created at run time
pytest.ini                 root convenience config (points at network-checks)
```

## Out of scope

Browser automation, load generation, database writes, and payment or CMS business rules. Later work, only if a defect needs it: packet capture, path MTU, multi-region runners, mTLS.
