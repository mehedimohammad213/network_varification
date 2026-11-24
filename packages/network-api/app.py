"""FastAPI app: serve the browser UI and run network checks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

_API_DIR = Path(__file__).resolve().parent
_REPO = _API_DIR.parents[1]
_CHECKS_SRC = _REPO / "packages" / "network-checks" / "src"
for _path in (_API_DIR, _CHECKS_SRC, _REPO):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from runner import manager
from network_checks.load_config import ConfigError, health_url, load_profile, project_root

ROOT = project_root()
WEB = ROOT / "packages" / "network-web"
REPORTS = ROOT / "reports"

app = FastAPI(title="Network Verification", version="1.0.0")


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response


app.add_middleware(NoCacheStaticMiddleware)


class StartRunBody(BaseModel):
    profile: str | None = Field(default=None, description="Saved product profile")
    suite: Literal["smoke", "full"] = "smoke"
    target_url: str | None = Field(
        default=None,
        description="Optional pasted site link; overrides profile when set",
    )


def _run_payload(run) -> dict:
    return {
        "id": run.id,
        "profile": run.profile,
        "suite": run.suite,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "health_url": run.health_url,
        "target_url": getattr(run, "target_url", "") or "",
        "using_example_targets": run.using_example_targets,
        "passed": run.passed,
        "failed": run.failed,
        "skipped": run.skipped,
        "duration_sec": run.duration_sec,
        "report_url": run.report_url if (ROOT / run.report_html).is_file() else "",
        "error": run.error,
        "tests": run.tests,
    }


@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True}


@app.get("/api/profiles")
def api_profiles() -> dict:
    try:
        profiles = manager.list_available_profiles()
    except ConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    enriched = []
    for item in profiles:
        try:
            loaded = load_profile(item["name"])
            enriched.append(
                {
                    **item,
                    "health_url": health_url(loaded),
                    "using_example_targets": bool(loaded.get("usingExampleTargets")),
                }
            )
        except ConfigError:
            enriched.append({**item, "health_url": "", "using_example_targets": False})
    return {"profiles": enriched}


@app.post("/api/runs")
def api_start_run(body: StartRunBody) -> dict:
    try:
        run = manager.start(body.profile, body.suite, target_url=body.target_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _run_payload(run)


@app.get("/api/runs/latest")
def api_latest_run() -> dict:
    run = manager.latest()
    if run is None:
        raise HTTPException(status_code=404, detail="No runs yet.")
    return _run_payload(run)


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: str) -> dict:
    run = manager.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_payload(run)


REPORTS.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS)), name="reports")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=str(WEB)), name="static")
