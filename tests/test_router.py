from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agenttalk.router.app import RouterConfig, RouterContext, tick
from agenttalk.router.io import AgentsPaths, SystemPaths, file_sha256
from agenttalk.router.schema import SchemaRegistry


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_ctx(tmp_path: Path) -> tuple[RouterContext, Path, Path]:
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    ctx = RouterContext(
        agents=AgentsPaths(agents_root=agents_root),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=SchemaRegistry(schemas_base_dir=Path("doc/rule/templates/schemas")),
        config=RouterConfig(poll_interval_seconds=1, schema_validation_enabled=False),
    )
    return ctx, agents_root, system_runtime


def ensure_agent(agents_root: Path, agent_id: str) -> None:
    (agents_root / agent_id / "inbox").mkdir(parents=True, exist_ok=True)
    (agents_root / agent_id / "outbox").mkdir(parents=True, exist_ok=True)
    (agents_root / agent_id / "workspace").mkdir(parents=True, exist_ok=True)


def write_plan_dag(system_runtime: Path, plan_id: str, dag: dict) -> str:
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "dag_kind": "meta",
            "task_dag_sha256": dag_sha,
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )
    return dag_sha


def test_router_delivers_artifact_payload_then_envelope(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_consumer")

    plan_id = "plan_1"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {
                "task_id": "task_src",
                "assigned_agent_id": "agent_prod",
                "depends_on": [],
                "outputs": [
                    {"name": "requirements", "deliver_to": ["agent_consumer"], "idempotency_key": "k1"}
                ],
            }
        ],
    }
    write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    payload_path = outbox_plan / "requirements.md"
    payload_path.write_text("hi", encoding="utf-8")
    import hashlib

    sha = "sha256:" + hashlib.sha256(b"hi").hexdigest()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    env = {
        "schema_version": "1.0",
        "message_id": "msg_art_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_prod",
        "type": "artifact",
        "created_at": now,
        "task_id": "task_src",
        "output_name": "requirements",
        "payload": {"files": [{"path": "requirements.md", "sha256": sha}]},
    }
    write_json(outbox_plan / "artifact.msg.json", env)

    tick(ctx)

    inbox_plan = agents_root / "agent_consumer" / "inbox" / plan_id
    assert (inbox_plan / "requirements.md").exists()
    assert (inbox_plan / "artifact.msg.json").exists()

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "DELIVERED" and d["to_agent_id"] == "agent_consumer" for d in deliveries)


def test_router_command_superseded_only_latest_delivered(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_exec")

    plan_id = "plan_2"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_exec", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    dag_sha = write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    def cmd_env(message_id: str, command_id: str, seq: int) -> dict:
        return {
            "schema_version": "1.0",
            "message_id": message_id,
            "plan_id": plan_id,
            "producer_agent_id": "agent_prod",
            "type": "command",
            "created_at": now,
            "task_id": "task_exec",
            "command_id": command_id,
            "payload": {
                "command": {
                    "schema_version": "1.0",
                    "command_id": command_id,
                    "plan_id": plan_id,
                    "task_id": "task_exec",
                    "command_seq": seq,
                    "dag_ref": {"sha256": dag_sha},
                    "prompt": "do it",
                    "required_inputs": [],
                    "resolved_inputs": None,
                    "wait_for_inputs": False,
                    "score_required": False,
                    "timeout": 60,
                }
            },
        }

    write_json(outbox_plan / "c1.msg.json", cmd_env("msg_c1", "cmd_task_exec_001", 1))
    write_json(outbox_plan / "c2.msg.json", cmd_env("msg_c2", "cmd_task_exec_002", 2))

    tick(ctx)

    inbox_plan = agents_root / "agent_exec" / "inbox" / plan_id
    assert (inbox_plan / "c2.msg.json").exists()
    assert not (inbox_plan / "c1.msg.json").exists()

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "DELIVERED" and d["command_id"] == "cmd_task_exec_002" for d in deliveries)
    assert any(d["status"] == "SKIPPED_SUPERSEDED" and d.get("superseded") is True for d in deliveries)


def test_router_dedupe_skips_duplicate_message(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_consumer")

    plan_id = "plan_3"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {
                "task_id": "task_src",
                "assigned_agent_id": "agent_prod",
                "depends_on": [],
                "outputs": [{"name": "o", "deliver_to": ["agent_consumer"], "idempotency_key": "k"}],
            }
        ],
    }
    write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    payload_path = outbox_plan / "f.txt"
    payload_path.write_text("x", encoding="utf-8")
    import hashlib

    sha = "sha256:" + hashlib.sha256(b"x").hexdigest()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    env = {
        "schema_version": "1.0",
        "message_id": "msg_dup",
        "plan_id": plan_id,
        "producer_agent_id": "agent_prod",
        "type": "artifact",
        "created_at": now,
        "task_id": "task_src",
        "output_name": "o",
        "payload": {"files": [{"path": "f.txt", "sha256": sha}]},
    }
    write_json(outbox_plan / "d.msg.json", env)

    tick(ctx)
    tick(ctx)

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "SKIPPED_DUPLICATE" for d in deliveries)


def test_router_archives_ack_from_agent_outbox(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    plan_id = "plan_ack"
    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)

    # minimal dag so router doesn't early-exit due to missing DAG
    dag = {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": "agent_prod", "depends_on": [], "outputs": []}]}
    write_plan_dag(system_runtime, plan_id, dag)

    ack = {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "message_id": "msg_1",
        "consumer_agent_id": "agent_prod",
        "status": "SUCCEEDED",
        "consumed_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "result": {"ok": True},
    }
    write_json(outbox_plan / "ack_msg_1.json", ack)
    tick(ctx)
    archived = system_runtime / "plans" / plan_id / "acks" / "ack_msg_1.json"
    assert archived.exists()


def test_router_ack_conflict_deadletters_and_alerts(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    plan_id = "plan_ack_conflict"
    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    dag = {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": "agent_prod", "depends_on": [], "outputs": []}]}
    write_plan_dag(system_runtime, plan_id, dag)

    ack1 = {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "message_id": "msg_x",
        "consumer_agent_id": "agent_prod",
        "status": "CONSUMED",
        "consumed_at": "2026-01-01T00:00:00Z",
    }
    ack2 = dict(ack1)
    ack2["status"] = "FAILED"
    write_json(outbox_plan / "ack_msg_x.json", ack1)
    tick(ctx)
    write_json(outbox_plan / "ack_msg_x_2.json", ack2)
    tick(ctx)

    deadletters = list((system_runtime / "deadletter" / plan_id).glob("*.json"))
    assert deadletters, "expected a deadletter entry for ack conflict"
    alerts = list((system_runtime / "alerts" / plan_id).glob("*.json"))
    assert alerts, "expected an alert for ack conflict"


def test_router_deadletters_when_artifact_deliver_to_empty(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_consumer")

    plan_id = "plan_dlq_no_target"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {
                "task_id": "task_src",
                "assigned_agent_id": "agent_prod",
                "depends_on": [],
                "outputs": [{"name": "o", "deliver_to": [], "idempotency_key": "k"}],
            }
        ],
    }
    write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    payload_path = outbox_plan / "f.txt"
    payload_path.write_text("x", encoding="utf-8")
    import hashlib

    sha = "sha256:" + hashlib.sha256(b"x").hexdigest()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    env = {
        "schema_version": "1.0",
        "message_id": "msg_art_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_prod",
        "type": "artifact",
        "created_at": now,
        "task_id": "task_src",
        "output_name": "o",
        "payload": {"files": [{"path": "f.txt", "sha256": sha}]},
    }
    write_json(outbox_plan / "a.msg.json", env)

    tick(ctx)

    dlq = list((system_runtime / "deadletter" / plan_id).glob("*.json"))
    assert dlq, "expected a deadletter entry"
    dlq_obj = json.loads(dlq[0].read_text(encoding="utf-8"))
    assert dlq_obj["reason"]["code"] == "ROUTING_NO_TARGET"

    alerts = list((system_runtime / "alerts" / plan_id).glob("*.json"))
    assert alerts, "expected an alert entry"
    alert_obj = json.loads(alerts[0].read_text(encoding="utf-8"))
    assert alert_obj["type"] == "ROUTING_NO_TARGET"

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "DEADLETTERED" and d["message_id"] == "msg_art_1" for d in deliveries)


def test_router_deadletters_unsupported_schema_version(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_exec")

    plan_id = "plan_dlq_schema"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [{"task_id": "task_exec", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}],
    }
    dag_sha = write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    env = {
        "schema_version": "2.0",
        "message_id": "msg_bad_schema",
        "plan_id": plan_id,
        "producer_agent_id": "agent_prod",
        "type": "command",
        "created_at": now,
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
                "prompt": "do it",
                "required_inputs": [],
                "resolved_inputs": None,
                "wait_for_inputs": False,
                "score_required": False,
                "timeout": 60,
            }
        },
    }
    write_json(outbox_plan / "bad.msg.json", env)

    tick(ctx)

    dlq = list((system_runtime / "deadletter" / plan_id).glob("*.json"))
    assert dlq, "expected a deadletter entry"
    dlq_obj = json.loads(dlq[0].read_text(encoding="utf-8"))
    assert dlq_obj["reason"]["code"] == "SCHEMA_VERSION_UNSUPPORTED"

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "DEADLETTERED" and d["message_id"] == "msg_bad_schema" for d in deliveries)


def test_router_deadletters_invalid_json_envelope(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_exec")

    plan_id = "plan_dlq_json"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [{"task_id": "task_exec", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}],
    }
    write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    (outbox_plan / "broken.msg.json").write_text("{", encoding="utf-8")

    tick(ctx)

    dlq = list((system_runtime / "deadletter" / plan_id).glob("*.json"))
    assert dlq, "expected a deadletter entry"
    dlq_obj = json.loads(dlq[0].read_text(encoding="utf-8"))
    assert dlq_obj["reason"]["code"] == "ENVELOPE_PARSE_ERROR"

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "DEADLETTERED" and d["message_id"] == "broken.msg" for d in deliveries)


def test_router_schema_validation_deadletters_invalid_command_payload(tmp_path: Path):
    # schema_validation_enabled=True should validate message_envelope + command.schema (via $ref), without network.
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    ensure_agent(agents_root, "agent_prod")
    ensure_agent(agents_root, "agent_exec")

    ctx = RouterContext(
        agents=AgentsPaths(agents_root=agents_root),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=SchemaRegistry(schemas_base_dir=Path("doc/rule/templates/schemas")),
        config=RouterConfig(poll_interval_seconds=1, schema_validation_enabled=True),
    )

    plan_id = "plan_schema_dlq"
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [{"task_id": "task_exec", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}],
    }
    dag_sha = write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_prod" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    # Invalid command: missing required field `timeout`
    env = {
        "schema_version": "1.0",
        "message_id": "msg_bad_cmd",
        "plan_id": plan_id,
        "producer_agent_id": "agent_prod",
        "type": "command",
        "created_at": now,
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
                "prompt": "do it",
                "required_inputs": [],
                "resolved_inputs": None,
                "wait_for_inputs": False,
                "score_required": False,
                # timeout missing on purpose
            }
        },
    }
    write_json(outbox_plan / "bad.msg.json", env)

    tick(ctx)

    dlq = list((system_runtime / "deadletter" / plan_id).glob("*.json"))
    assert dlq, "expected deadletter for invalid schema"
    dlq_obj = json.loads(dlq[0].read_text(encoding="utf-8"))
    assert dlq_obj["reason"]["code"] == "SCHEMA_INVALID"

    deliveries = read_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl")
    assert any(d["status"] == "DEADLETTERED" and d["message_id"] == "msg_bad_cmd" for d in deliveries)


def test_router_refreshes_latest_release_manifest_pointer(tmp_path: Path):
    ctx, agents_root, system_runtime = make_ctx(tmp_path)
    ensure_agent(agents_root, "agent_release_engineer")
    ensure_agent(agents_root, "agent_human_gateway")

    plan_id = "plan_release_ptr"
    dag = {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": "agent_release_engineer", "depends_on": [], "outputs": []}]}
    write_plan_dag(system_runtime, plan_id, dag)

    outbox_plan = agents_root / "agent_release_engineer" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)

    write_json(
        outbox_plan / "release_manifest_r1.json",
        {
            "schema_version": "1.0",
            "release_id": "release_1",
            "plan_id": plan_id,
            "created_at": "2026-01-01T00:00:01Z",
            "release_manager_agent_id": "agent_release_engineer",
            "decision": "REJECT",
        },
    )
    write_json(
        outbox_plan / "release_manifest_r2.json",
        {
            "schema_version": "1.0",
            "release_id": "release_2",
            "plan_id": plan_id,
            "created_at": "2026-01-02T00:00:01Z",
            "release_manager_agent_id": "agent_release_engineer",
            "decision": "APPROVE",
        },
    )

    tick(ctx)

    ptr = system_runtime / "plans" / plan_id / "release_manifest.json"
    assert ptr.exists()
    obj = json.loads(ptr.read_text(encoding="utf-8"))
    assert obj["release_id"] == "release_2"
