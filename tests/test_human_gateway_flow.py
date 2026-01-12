from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agenttalk.heartbeat.app import AppContext, tick_plan
from agenttalk.heartbeat.config import HeartbeatConfig
from agenttalk.heartbeat.handlers import CommandResult, DefaultCommandHandler
from agenttalk.heartbeat.ids import IdGenerator
from agenttalk.heartbeat.io import AgentPaths
from agenttalk.heartbeat.schema import SchemaRegistry as HeartbeatSchemas
from agenttalk.heartbeat.timeutil import Clock, iso_z
from agenttalk.router.app import RouterConfig, RouterContext, tick
from agenttalk.router.io import AgentsPaths, SystemPaths, file_sha256
from agenttalk.router.schema import SchemaRegistry as RouterSchemas


class FixedClock(Clock):
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:  # type: ignore[override]
        return self._now


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_agent(tmp_path: Path, agent_id: str) -> Path:
    root = tmp_path / "agents" / agent_id
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "outbox").mkdir(parents=True, exist_ok=True)
    (root / "workspace").mkdir(parents=True, exist_ok=True)
    return root


def write_plan_dag(system_runtime: Path, plan_id: str, dag: dict) -> str:
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "dag_kind": "meta", "task_dag_sha256": dag_sha, "updated_at": None},
    )
    return dag_sha


def heartbeat_ctx(tmp_path: Path, *, agent_id: str, now: datetime) -> AppContext:
    agent_root = tmp_path / "agents" / agent_id
    cfg = HeartbeatConfig(
        schema_version="1.0",
        agent_id=agent_id,
        poll_interval_seconds=1,
        max_new_messages_per_tick=50,
        max_resume_messages_per_tick=10,
        scan_mode="auto",
        allowlist=None,
        schema_validation_enabled=False,
        schemas_base_dir=Path("doc/rule/templates/schemas"),
    )
    return AppContext(
        agent_paths=AgentPaths(agent_root=agent_root),
        config=cfg,
        schema_registry=HeartbeatSchemas(Path("doc/rule/templates/schemas")),
        clock=FixedClock(now),
        ids=IdGenerator(),
        handler=DefaultCommandHandler(),
    )


def test_human_gateway_request_to_response_injects_artifact_to_target_agent(tmp_path: Path):
    # Agents
    ensure_agent(tmp_path, "agent_prod")
    ensure_agent(tmp_path, "agent_human_gateway")
    ensure_agent(tmp_path, "agent_target")

    system_runtime = tmp_path / "system_runtime"

    # Router context
    ctx = RouterContext(
        agents=AgentsPaths(agents_root=tmp_path / "agents"),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=RouterSchemas(schemas_base_dir=Path("doc/rule/templates/schemas")),
        config=RouterConfig(poll_interval_seconds=1, schema_validation_enabled=False),
    )

    plan_id = "plan_human_1"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [{"task_id": "task_1", "assigned_agent_id": "agent_target", "depends_on": [], "outputs": []}],
    }
    write_plan_dag(system_runtime, plan_id, dag)

    # 1) Agent writes human_intervention_request
    request_id = "human_req_20260101T000000Z_0001"
    req = {
        "schema_version": "1.0",
        "request_id": request_id,
        "plan_id": plan_id,
        "created_at": "2026-01-01T00:00:00Z",
        "created_by": {"agent_id": "agent_prod", "task_id": "task_1", "command_id": "cmd_task_1_001"},
        "severity": "HIGH",
        "type": "MISSING_FILE",
        "title": "Need requirements.md",
        "blocking": {"status": "BLOCKED_WAITING_HUMAN"},
        "needed": {
            "files": [
                {
                    "name": "requirements.md",
                    "description": "Requirements document",
                    "sensitivity": "PUBLIC",
                    "deliver_to_agent_id": "agent_target",
                }
            ]
        },
        "deadline": None,
        "context_refs": None,
    }
    req_path = tmp_path / "agents" / "agent_prod" / "outbox" / plan_id / f"human_intervention_request_{request_id}.json"
    write_json(req_path, req)

    tick(ctx)

    delivered_req = tmp_path / "agents" / "agent_human_gateway" / "inbox" / plan_id / req_path.name
    assert delivered_req.exists()
    assert (system_runtime / "plans" / plan_id / "human_requests" / req_path.name).exists()

    # 2) Human gateway writes response + attachment in its outbox
    gw_outbox_plan = tmp_path / "agents" / "agent_human_gateway" / "outbox" / plan_id
    gw_outbox_plan.mkdir(parents=True, exist_ok=True)
    (gw_outbox_plan / "requirements.md").write_text("REQ", encoding="utf-8")
    sha = "sha256:" + __import__("hashlib").sha256(b"REQ").hexdigest()
    resp = {
        "schema_version": "1.0",
        "request_id": request_id,
        "plan_id": plan_id,
        "responded_at": "2026-01-01T00:10:00Z",
        "decision": "PROVIDE",
        "provided_files": [{"name": "requirements.md", "sha256": sha, "deliver_to_agent_id": "agent_target"}],
    }
    resp_path = gw_outbox_plan / f"human_intervention_response_{request_id}.json"
    write_json(resp_path, resp)

    tick(ctx)

    target_inbox_plan = tmp_path / "agents" / "agent_target" / "inbox" / plan_id
    assert (target_inbox_plan / "requirements.md").exists()
    msg_files = list(target_inbox_plan.glob("msg_human_*.msg.json"))
    assert msg_files, "expected injected artifact envelope"
    assert (system_runtime / "plans" / plan_id / "human_responses" / resp_path.name).exists()
    assert (system_runtime / "plans" / plan_id / "human_responses" / ".processed" / f"{request_id}.json").exists()

    # 3) Target agent heartbeat ingests injected artifact and indexes it as an input
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    hb = heartbeat_ctx(tmp_path, agent_id="agent_target", now=now)
    tick_plan(hb, plan_id)

    input_index = hb.agent_paths.workspace / plan_id / "inputs" / "input_index.json"
    assert input_index.exists()
    idx = json.loads(input_index.read_text(encoding="utf-8"))
    assert any(
        any(f.get("path") == "requirements.md" for f in (e.get("files") or [])) for e in (idx.get("entries") or [])
    )

