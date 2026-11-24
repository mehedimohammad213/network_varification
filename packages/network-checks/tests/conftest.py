"""Session evidence: profile, targets file, runner, and timestamp.

The HTML report picks up the same fields when pytest-metadata is installed.
Results rows include Expected and Actual columns for each case.
"""

from __future__ import annotations

import json
import platform
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import pytest

from network_checks.load_config import health_url, load_profile, project_root

# Friendly labels for the browser UI (and JSON export).
TEST_TITLES: dict[str, str] = {
    "NET_C01": "TCP reachability",
    "NET_C02": "Critical port open",
    "NET_C03": "Unreachable host times out",
    "NET_C04": "Wrong port is closed",
    "NET_D01": "Resolve primary host",
    "NET_D02": "NXDOMAIN for bad name",
    "NET_D03": "Multiple DNS addresses",
    "NET_D04": "Bad resolver times out",
    "NET_D05": "Resolved addresses on allowlist",
    "NET_H01": "Health check (HTTPS GET)",
    "NET_H02": "TLS handshake",
    "NET_H03": "HTTP redirects to HTTPS",
    "NET_H04": "Expected response headers",
    "NET_H05": "Unknown path returns 4xx",
    "NET_H06": "Certificate not expiring soon",
    "NET_H07": "Header value contains",
    "NET_M01": "mTLS client handshake",
    "NET_P01": "Latency within SLA",
    "NET_P02": "Soft timeout on blackhole",
    "NET_P03": "Retry budget is limited",
    "NET_N01": "HTTP upgrades to HTTPS",
    "NET_N02": "Bad certificate fails closed",
    "NET_N03": "Slow response times out",
    "NET_N04": "SNI mismatch fails closed",
    "overlay_endpoints_reachable": "Overlay endpoints reachable",
}

# Catalog expected outcomes for the HTML Expected column.
TEST_EXPECTED: dict[str, str] = {
    "NET_C01": "TCP connection succeeds within timeoutSec",
    "NET_C02": "Critical port accepts a connection",
    "NET_C03": "Not open; error is timeout; elapsed within budget+2s",
    "NET_C04": "Connection does not succeed; returns within budget",
    "NET_D01": "At least one address for the primary host",
    "NET_D02": "DNSError kind nxdomain",
    "NET_D03": "Unique address count >= dns.minAddresses",
    "NET_D04": "TimeoutError within negativeTimeoutSec",
    "NET_D05": "Every resolved address is in dns.expectedAddresses",
    "NET_H01": "Status in expectedStatus; final URL is https",
    "NET_H02": "TLS 1.2 or 1.3 with a negotiated cipher",
    "NET_H03": "Final URL is https and status < 400",
    "NET_H04": "Each listed expectedHeaders name is present",
    "NET_H05": "Status is 400–499",
    "NET_H06": "Peer cert days remaining >= tls.minDaysRemaining",
    "NET_H07": "Each http.headerContains substring is present",
    "NET_M01": "mTLS handshake TLS 1.2/1.3 with client cert",
    "NET_P01": "Acceptable status and elapsed_ms <= latencyMs",
    "NET_P02": "httpx.TimeoutException within budget+2s",
    "NET_P03": "Failing op called 3 times; recovering op stops after success",
    "NET_N01": "Redirect status; Location starts with https://",
    "NET_N02": "TlsError kind verify (certificate rejected)",
    "NET_N03": "httpx.TimeoutException within short budget+3s",
    "NET_N04": "TlsError kind verify (SNI mismatch)",
    "overlay_endpoints_reachable": "Each overlay host:port accepts TCP",
    "target_url_builds_one_site_profile": "Dynamic site profile from TARGET_URL",
    "target_url_wins_over_yaml": "TARGET_URL host wins over YAML",
    "yaml_site_fallback_without_target_url": "YAML site profile when TARGET_URL unset",
    "unknown_profile_rejected": "ConfigError mentioning known profiles",
    "missing_local_file_uses_the_example": "usingExampleTargets True; example path",
    "targets_file_override": "TARGETS_FILE path used; not example",
    "bad_target_url_rejected": "ConfigError for non-http(s) TARGET_URL",
}

_CASE_ID = re.compile(r"test_(NET_[A-Z]\d{2})")
_case_key = pytest.StashKey["CaseResult"]()
_ui_rows_key = pytest.StashKey[list]()


@dataclass
class CaseResult:
    expected: str = ""
    actual: str = ""


def case_key_for(item: pytest.Item) -> str:
    name = item.name.split("[", 1)[0]
    match = _CASE_ID.search(name)
    if match:
        return match.group(1)
    return name.removeprefix("test_")


def default_expected(item: pytest.Item) -> str:
    return TEST_EXPECTED.get(case_key_for(item), "")


def title_for(item: pytest.Item) -> str:
    key = case_key_for(item)
    base = TEST_TITLES.get(key, key.replace("_", " "))
    if "[" in item.name and item.name.endswith("]"):
        param = item.name[item.name.index("[") + 1 : -1]
        return f"{base} ({param})"
    return base


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "target_host" in metafunc.fixturenames:
        profile = load_profile()
        metafunc.parametrize("target_host", profile["hosts"], ids=list(profile["hosts"]))


@pytest.fixture(scope="session")
def profile():
    return load_profile()


@pytest.fixture
def case(request: pytest.FixtureRequest) -> CaseResult:
    """Record expected/actual for the HTML report columns."""
    bag = CaseResult(expected=default_expected(request.node))
    request.node.stash[_case_key] = bag
    return bag


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    bag = item.stash.get(_case_key, None)
    expected = bag.expected if bag else default_expected(item)
    actual = bag.actual if bag and bag.actual else ""
    if not actual and report.when == "call":
        if report.skipped:
            actual = str(report.longrepr) if report.longrepr else "skipped"
        elif report.failed:
            actual = _failure_summary(report)
        elif report.passed:
            actual = "matched expected"
    report.expected = expected  # type: ignore[attr-defined]
    report.actual = actual  # type: ignore[attr-defined]

    if report.when == "call" or (
        report.when in {"setup", "teardown"} and report.outcome != "passed"
    ):
        if _ui_rows_key not in item.config.stash:
            item.config.stash[_ui_rows_key] = []
        rows = item.config.stash[_ui_rows_key]
        rows.append(
            {
                "id": case_key_for(item),
                "title": title_for(item),
                "nodeid": report.nodeid,
                "result": report.outcome,
                "expected": expected,
                "actual": actual,
                "duration_sec": round(getattr(report, "duration", 0.0) or 0.0, 3),
            }
        )


def _failure_summary(report) -> str:
    text = str(report.longrepr) if report.longrepr else "failed"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("E ") or "AssertionError" in line or "Error" in line:
            return line.removeprefix("E ").strip()[:200]
    return (lines[-1] if lines else "failed")[:200]


def pytest_html_results_table_header(cells: list[str]) -> None:
    # Replace Links with Expected + Actual.
    cells[-1] = '<th class="sortable" data-column-type="expected">Expected</th>'
    cells.append('<th class="sortable" data-column-type="actual">Actual</th>')


def pytest_html_results_table_row(report, cells: list[str]) -> None:
    expected = escape(getattr(report, "expected", "") or "")
    actual = escape(getattr(report, "actual", "") or "")
    cells[-1] = f'<td class="col-expected">{expected}</td>'
    cells.append(f'<td class="col-actual">{actual}</td>')


def pytest_sessionstart(session: pytest.Session) -> None:
    root = project_root()
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    try:
        loaded = load_profile()
    except Exception as exc:  # evidence should still explain a broken profile
        loaded = {
            "name": "unavailable",
            "targetsFile": "",
            "usingExampleTargets": False,
            "error": str(exc),
        }
    lines = [
        f"profile={loaded.get('name', '')}",
        f"targets_file={loaded.get('targetsFile', '')}",
        f"using_example_targets={loaded.get('usingExampleTargets', False)}",
        f"timestamp_utc={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"runner={socket.gethostname()}",
        f"python={platform.python_version()}",
        "note=DEV-LAB example targets are not staging evidence."
        if loaded.get("usingExampleTargets")
        else "note=targets.yaml loaded; record whether this runner is local or CI.",
    ]
    if loaded.get("error"):
        lines.append(f"config_error={loaded['error']}")
    path = reports / "evidence.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    session.config._network_evidence_path = path  # type: ignore[attr-defined]

    try:
        from pytest_metadata.plugin import metadata_key

        metadata = session.config.stash[metadata_key]
        metadata["Network profile"] = loaded.get("name", "")
        metadata["Targets file"] = loaded.get("targetsFile", "")
        metadata["Example targets"] = str(loaded.get("usingExampleTargets", False))
        metadata["Runner"] = socket.gethostname()
        if not loaded.get("error"):
            try:
                metadata["Health URL"] = health_url(loaded)
            except Exception:
                pass
    except Exception:
        return


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    path = getattr(session.config, "_network_evidence_path", None)
    if path is None:
        path = Path(project_root() / "reports" / "evidence.txt")
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"exit_status={exitstatus}\n")
        handle.write(f"collected={session.testscollected}\n")

    rows = session.config.stash.get(_ui_rows_key, [])
    passed = sum(1 for row in rows if row["result"] == "passed")
    failed = sum(1 for row in rows if row["result"] == "failed")
    skipped = sum(1 for row in rows if row["result"] == "skipped")
    payload = {
        "exit_status": exitstatus,
        "collected": session.testscollected,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "tests": rows,
    }
    ui_path = project_root() / "reports" / "ui_results.json"
    ui_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
