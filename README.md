# Network quality gate

Reusable DNS, TCP, TLS, HTTP, and latency checks. Point the suite at any site with one URL — same checks for every product. The cases themselves stay in this repo.

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
```

If `python3 -m venv` stops because `ensurepip` is missing, install the distro `python3-venv` package, or run `python3 -m venv .venv --without-pip` and bootstrap pip with `get-pip.py` inside that environment.

### Config

One dynamic condition: the site URL. Hosts, ports, health path, and HTTP→HTTPS redirect are built from it.

| Input | Purpose |
|-------|---------|
| `TARGET_URL` | CLI / CI — preferred |
| UI site link | Browser runner — same builder |
| `config/targets.yaml` | Optional fallback when `TARGET_URL` is unset (gitignored) |
| `config/targets.example.yaml` | Public lab sample if no local YAML (committed) |

## Browser UI (for non-tech clients)

Python stays on the machine that hosts the app. Clients only open a browser.

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --app-dir packages/network-api --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Paste a site link, choose smoke or full, click **Run check**, and read Expected vs Actual. The same run still writes `reports/smoke.html` (or `full.html`).

API cheat sheet: `POST /api/runs`, `GET /api/runs/{id}`, `GET /docs`.

## Smoke and full (CLI)

```bash
TARGET_URL=https://your-site.com/ pytest -m smoke --html=reports/smoke.html --self-contained-html
```

Full suite, after smoke is green:

```bash
TARGET_URL=https://your-site.com/ pytest --html=reports/full.html --self-contained-html --junitxml=reports/junit.xml
```

One case:

```bash
TARGET_URL=https://your-site.com/ pytest -m net_c03
```

Without `TARGET_URL`, the loader uses the single `site` block in `config/targets.yaml` (or the example lab).

## Reports

| Artifact | What it is |
|----------|------------|
| `reports/smoke.html` or `reports/full.html` | pytest-html, self-contained |
| `reports/junit.xml` | JUnit, when you pass `--junitxml` |
| `reports/evidence.txt` | Profile, targets path, example-file flag, UTC time, hostname, exit status |
| `reports/ui_results.json` | JSON for the browser UI (Expected / Actual rows) |

The HTML environment table repeats the profile and the targets file. The Results table includes **Expected** and **Actual** columns for each case. A row that says example targets are in use is not a staging result. `reports/` is gitignored except for `.gitkeep`.

## Point at a site

Prefer the URL — no YAML edit required:

```bash
TARGET_URL=https://api.staging.example.com/health pytest -m smoke
```

Optional YAML fallback (single `site` block only) when you want fixed hosts without exporting `TARGET_URL` every time. Overlays remain supported in that file for extra TCP endpoints in the full suite.

## CMS walkthrough

Network probing of the CMS, not the editor UI.

1. List endpoints: API or GraphQL origin, preview host, media CDN, webhook receiver, auth host.
2. Set `TARGET_URL` to the primary HTTPS origin (auth host is reachability only if you add it as an overlay later).
3. Start the local CMS, or use staging URLs and connect VPN when the names are private.
4. Run the smoke command above.
5. Triage with the table below.
6. Run the full command once smoke is green.
7. Keep `reports/` with the ticket, and write down local vs staging.

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

| Event | Suite | Target |
|-------|-------|--------|
| Pull request | Smoke | `TARGET_URL=https://example.com/` |
| Nightly 02:00 UTC, and manual dispatch | Full | `TARGET_URL=https://example.com/` |

The job fails when smoke fails. HTML and JUnit are uploaded as artifacts. Point `TARGET_URL` and the runner's network at staging when the example lab is no longer the target. Private production hosts need a runner that is already allowlisted; do not put credentials in the workflow.

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

Browser automation, load generation, database writes, and payment or CMS business rules. Later work, only if a defect needs it: packet capture, path MTU, multi-region runners. Fintech extras (cert expiry, HSTS value checks, IP allowlist, mTLS) are optional profile keys — see `docs/test_cases.md`.
