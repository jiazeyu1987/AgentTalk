from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agenttalk.heartbeat.app import AppContext, tick_plan
from agenttalk.heartbeat.config import HeartbeatConfig
from agenttalk.heartbeat.ids import IdGenerator
from agenttalk.heartbeat.io import AgentPaths
from agenttalk.heartbeat.schema import SchemaRegistry
from agenttalk.heartbeat.timeutil import Clock, iso_z
from agenttalk.router.app import RouterConfig, RouterContext, tick as router_tick
from agenttalk.router.io import AgentsPaths, SystemPaths, file_sha256
from agenttalk.router.schema import SchemaRegistry as RouterSchemas
from agenttalk.command_runner.dummy_handler import handler as dummy_handler


class FixedClock(Clock):
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:  # type: ignore[override]
        return self._now


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def test_end_to_end_command_produces_artifact_and_router_delivers(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_1"

    # agents
    agent_exec = agents_root / "agent_exec"
    agent_consumer = agents_root / "agent_consumer"
    for a in (agent_exec, agent_consumer):
        (a / "inbox" / plan_id).mkdir(parents=True, exist_ok=True)
        (a / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)
        (a / "workspace" / plan_id).mkdir(parents=True, exist_ok=True)

    # system dag: task_exec outputs deliver_to consumer
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {
                "task_id": "task_exec",
                "assigned_agent_id": "agent_exec",
                "depends_on": [],
                "outputs": [{"name": "o", "deliver_to": ["agent_consumer"], "idempotency_key": "k"}],
            }
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "dag_kind": "meta", "task_dag_sha256": dag_sha, "updated_at": iso_z(now)},
    )

    # deliver command into agent_exec inbox (as if router already did)
    cmd_env = {
        "schema_version": "1.0",
        "message_id": "msg_cmd_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_planner",
        "type": "command",
        "created_at": iso_z(now),
        "task_id": "task_exec",
        "command_id": "cmd_task_exec_001",
        "payload": {
            "command": {
                "schema_version": "1.0",
                "command_id": "cmd_task_exec_001",
                "plan_id": plan_id,
                "task_id": "task_exec",
                "command_seq": 1,
                "dag_ref": {"sha256": dag_sha},
                "prompt": "hello",
                "required_inputs": [],
                "resolved_inputs": None,
                "produces": [{"output_name": "o", "files": [{"path": "out.txt", "content_type": "text/plain"}]}],
                "wait_for_inputs": False,
                "score_required": False,
                "timeout": 60,
            }
        },
    }
    write_json(agent_exec / "inbox" / plan_id / "cmd.msg.json", cmd_env)

    hb_ctx = AppContext(
        agent_paths=AgentPaths(agent_root=agent_exec),
        config=HeartbeatConfig(
            schema_version="1.0",
            agent_id="agent_exec",
            poll_interval_seconds=1,
            max_new_messages_per_tick=50,
            max_resume_messages_per_tick=10,
            scan_mode="allowlist_only",
            allowlist=[plan_id],
            schema_validation_enabled=False,
            schemas_base_dir=Path("doc/rule/templates/schemas"),
        ),
        schema_registry=SchemaRegistry(Path("doc/rule/templates/schemas")),
        clock=FixedClock(now),
        ids=IdGenerator(),
        handler=dummy_handler,
    )
    tick_plan(hb_ctx, plan_id)
    assert list((agent_exec / "outbox" / plan_id).glob("artifact_*.msg.json")), "expected artifact envelope in outbox"
    assert (agent_exec / "outbox" / plan_id / "out.txt").exists()

    router_ctx = RouterContext(
        agents=AgentsPaths(agents_root=agents_root),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=RouterSchemas(schemas_base_dir=Path("doc/rule/templates/schemas")),
        config=RouterConfig(poll_interval_seconds=1, schema_validation_enabled=False),
    )
    router_tick(router_ctx)

    inbox_consumer = agent_consumer / "inbox" / plan_id
    assert (inbox_consumer / "out.txt").exists()
    assert any(p.name.endswith(".msg.json") for p in inbox_consumer.iterdir())

