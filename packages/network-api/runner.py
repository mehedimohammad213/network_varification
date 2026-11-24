"""Run pytest from the API process. One run at a time."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from network_checks.load_config import ConfigError, health_url, list_profiles, load_profile, project_root
from target_url import write_adhoc_targets

Suite = Literal["smoke", "full"]


@dataclass
class RunState:
    id: str
    profile: str
    suite: Suite
    status: Literal["queued", "running", "passed", "failed", "error"] = "queued"
    started_at: str = ""
    finished_at: str = ""
    health_url: str = ""
    target_url: str = ""
    using_example_targets: bool = False
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_sec: float = 0.0
    report_html: str = ""
    report_url: str = ""
    error: str = ""
    tests: list[dict[str, Any]] = field(default_factory=list)


class RunManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False
        self._runs: dict[str, RunState] = {}
        self._latest_id: str | None = None

    def list_available_profiles(self) -> list[dict[str, Any]]:
        return list_profiles()

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def latest(self) -> RunState | None:
        if self._latest_id is None:
            return None
        return self._runs.get(self._latest_id)

    def start(
        self,
        profile: str | None,
        suite: Suite,
        target_url: str | None = None,
    ) -> RunState:
        root = project_root()
        targets_override: str | None = None
        display_profile: str
        health: str
        using_example = False
        pasted = (target_url or "").strip()

        if pasted:
            adhoc_path = root / "reports" / "adhoc_targets.yaml"
            display_profile, health = write_adhoc_targets(pasted, adhoc_path)
            targets_override = str(adhoc_path)
            # Validate load works before starting the thread.
            try:
                load_profile(display_profile, targets_file=targets_override)
            except ConfigError as exc:
                raise ValueError(str(exc)) from exc
        else:
            if not profile:
                raise ValueError("Choose a profile or paste a site link.")
            display_profile = profile
            try:
                loaded = load_profile(profile)
            except ConfigError as exc:
                raise ValueError(str(exc)) from exc
            health = health_url(loaded)
            using_example = bool(loaded.get("usingExampleTargets"))

        with self._lock:
            if self._busy:
                raise RuntimeError("A check is already running. Wait for it to finish.")
            self._busy = True
            run_id = uuid.uuid4().hex[:12]
            run = RunState(
                id=run_id,
                profile=display_profile,
                suite=suite,
                status="queued",
                health_url=health,
                target_url=pasted,
                using_example_targets=using_example,
                report_html=f"reports/{'smoke' if suite == 'smoke' else 'full'}.html",
                report_url=f"/reports/{'smoke' if suite == 'smoke' else 'full'}.html",
            )
            self._runs[run_id] = run
            self._latest_id = run_id

        thread = threading.Thread(
            target=self._execute,
            args=(run_id, display_profile, suite, root, targets_override),
            daemon=True,
            name=f"network-run-{run_id}",
        )
        thread.start()
        return run

    def _execute(
        self,
        run_id: str,
        profile: str,
        suite: Suite,
        root: Path,
        targets_override: str | None,
    ) -> None:
        run = self._runs[run_id]
        run.status = "running"
        run.started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        started = datetime.now(timezone.utc)

        checks_root = root / "packages" / "network-checks"
        reports = root / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        html_name = "smoke.html" if suite == "smoke" else "full.html"
        html_path = reports / html_name
        junit_path = reports / "junit.xml"
        ui_json = reports / "ui_results.json"
        if ui_json.exists():
            ui_json.unlink()

        cmd = [sys.executable, "-m", "pytest"]
        if suite == "smoke":
            cmd.extend(["-m", "smoke"])
        cmd.extend(
            [
                f"--html={html_path}",
                "--self-contained-html",
                f"--junitxml={junit_path}",
            ]
        )

        env = os.environ.copy()
        env["NETWORK_PROFILE"] = profile
        if targets_override:
            env["TARGETS_FILE"] = targets_override
        env["PYTHONPATH"] = os.pathsep.join(
            [str(checks_root / "src"), env.get("PYTHONPATH", "")]
        )

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(checks_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            run.duration_sec = round(
                (datetime.now(timezone.utc) - started).total_seconds(), 2
            )
            run.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            if ui_json.is_file():
                data = json.loads(ui_json.read_text(encoding="utf-8"))
                run.passed = int(data.get("passed", 0))
                run.failed = int(data.get("failed", 0))
                run.skipped = int(data.get("skipped", 0))
                run.tests = list(data.get("tests") or [])

            if completed.returncode == 0:
                run.status = "passed"
            else:
                run.status = "failed"
                if not run.tests:
                    tail = (completed.stderr or completed.stdout or "").strip()[-800:]
                    run.error = tail or f"pytest exited with code {completed.returncode}"
        except subprocess.TimeoutExpired:
            run.status = "error"
            run.error = "Check timed out after 10 minutes."
            run.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as exc:  # noqa: BLE001 — surface to UI
            run.status = "error"
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        finally:
            with self._lock:
                self._busy = False


manager = RunManager()
