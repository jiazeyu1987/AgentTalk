from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .storage import RuntimePaths, paginate, read_json, read_jsonl, safe_listdir, sort_by_created_at_then_name


def _plan_dir(paths: RuntimePaths, plan_id: str) -> Path:
    return paths.plans / plan_id


def _load_plan_status(paths: RuntimePaths, plan_id: str) -> dict:
    p = _plan_dir(paths, plan_id) / "plan_status.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="plan_status.json not found")
    return read_json(p)

def _load_release_manifest(paths: RuntimePaths, plan_id: str) -> dict:
    p = _plan_dir(paths, plan_id) / "release_manifest.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="release_manifest.json not found")
    return read_json(p)


def _plan_stats_from_status(status: dict) -> dict[str, int]:
    stats = {"RUNNING": 0, "BLOCKED": 0, "COMPLETED": 0, "FAILED": 0, "OTHER": 0}
    for t in status.get("tasks", []) or []:
        s = str(t.get("state") or "")
        if s == "RUNNING":
            stats["RUNNING"] += 1
        elif s.startswith("BLOCKED_"):
            stats["BLOCKED"] += 1
        elif s == "COMPLETED":
            stats["COMPLETED"] += 1
        elif s == "FAILED":
            stats["FAILED"] += 1
        else:
            stats["OTHER"] += 1
    return stats


def create_app(*, system_runtime: Path) -> FastAPI:
    paths = RuntimePaths(system_runtime=system_runtime)
    app = FastAPI(title="AgentTalk Dashboard API", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
<!doctype html>
<html>
  <head><meta charset="utf-8"/><title>AgentTalk Dashboard (MVP)</title></head>
  <body>
    <h1>AgentTalk Dashboard (MVP)</h1>
    <p>API: <a href="/api/plans">/api/plans</a></p>
  </body>
</html>
"""

    @app.get("/api/plans")
    def list_plans() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for plan_path in safe_listdir(paths.plans):
            if not plan_path.is_dir():
                continue
            plan_id = plan_path.name
            status_path = plan_path / "plan_status.json"
            updated_at = None
            stats = None
            if status_path.exists():
                status = read_json(status_path)
                updated_at = status.get("updated_at")
                stats = _plan_stats_from_status(status)
            items.append({"plan_id": plan_id, "updated_at": updated_at, "stats": stats})
        return sorted(items, key=lambda x: x["plan_id"])

    @app.get("/api/plans/{plan_id}/status")
    def get_plan_status(plan_id: str) -> dict:
        return _load_plan_status(paths, plan_id)

    @app.get("/api/plans/{plan_id}/deliveries")
    def get_deliveries(
        plan_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=500),
        message_id: str | None = None,
        task_id: str | None = None,
        include_skipped: bool = False,
    ) -> dict:
        p = _plan_dir(paths, plan_id) / "deliveries.jsonl"
        rows = read_jsonl(p)
        if message_id:
            rows = [r for r in rows if r.get("message_id") == message_id]
        if task_id:
            rows = [r for r in rows if r.get("task_id") == task_id]
        if not include_skipped:
            rows = [r for r in rows if not str(r.get("status", "")).startswith("SKIPPED_")]
        return paginate(rows, offset=offset, limit=limit)

    @app.get("/api/plans/{plan_id}/decisions")
    def get_decisions(plan_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)) -> dict:
        decisions_dir = _plan_dir(paths, plan_id) / "decisions"
        files = [p for p in safe_listdir(decisions_dir) if p.is_file() and p.suffix == ".json"]
        ordered = sort_by_created_at_then_name(files)
        items = []
        for p in ordered:
            try:
                items.append(read_json(p))
            except Exception:
                continue
        return paginate(items, offset=offset, limit=limit)

    @app.get("/api/plans/{plan_id}/acks")
    def get_acks(plan_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)) -> dict:
        acks_dir = _plan_dir(paths, plan_id) / "acks"
        files = [p for p in safe_listdir(acks_dir) if p.is_file() and p.suffix == ".json"]
        ordered = sort_by_created_at_then_name(files)
        items = []
        for p in ordered:
            try:
                items.append(read_json(p))
            except Exception:
                continue
        return paginate(items, offset=offset, limit=limit)

    @app.get("/api/plans/{plan_id}/release_manifest")
    def get_release_manifest(plan_id: str) -> dict:
        return _load_release_manifest(paths, plan_id)

    @app.get("/api/agents")
    def list_agents() -> list[dict]:
        items = []
        for p in safe_listdir(paths.agent_status):
            if not p.is_file() or p.suffix != ".json":
                continue
            try:
                items.append(read_json(p))
            except Exception:
                continue
        return sorted(items, key=lambda x: str(x.get("agent_id") or ""))

    @app.get("/api/agents/{agent_id}")
    def get_agent(agent_id: str) -> dict:
        p = paths.agent_status / f"{agent_id}.json"
        if not p.exists():
            raise HTTPException(status_code=404, detail="agent not found")
        return read_json(p)

    return app
