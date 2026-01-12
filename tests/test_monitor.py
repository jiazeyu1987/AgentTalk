from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agenttalk.monitor.app import MonitorConfig, MonitorContext, run_once
from agenttalk.monitor.io import file_sha256
from agenttalk.heartbeat.schema import SchemaRegistry


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_monitor_marks_ready_when_deps_done_and_input_delivered(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_1"
    # agents
    (agents_root / "agent_a" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)
    (agents_root / "agent_b" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    # task1 completed via task_state
    write_json(
        agents_root / "agent_a" / "outbox" / plan_id / "task_state_task_1.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "task_id": "task_1",
            "agent_id": "agent_a",
            "state": "COMPLETED",
            "updated_at": "2026-01-01T00:00:00Z",
            "message_id": None,
            "command_id": None,
            "command_seq": None,
            "blocking": None,
            "progress": None,
            "result": None,
        },
    )

    # DAG: task2 depends on task1 and requires input file
    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {
                "task_id": "task_1",
                "assigned_agent_id": "agent_a",
                "depends_on": [],
                "outputs": [{"name": "requirements", "deliver_to": ["agent_b"], "idempotency_key": "k"}],
            },
            {
                "task_id": "task_2",
                "assigned_agent_id": "agent_b",
                "depends_on": ["task_1"],
                "required_inputs": ["requirements.md"],
                "outputs": [],
            },
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )

    # deliveries include artifact with payload file name
    deliveries = [
        {
            "schema_version": "1.0",
            "delivery_id": "del_1",
            "plan_id": plan_id,
            "message_id": "msg_art_1",
            "envelope_sha256": "sha256:x",
            "task_id": "task_1",
            "command_id": None,
            "output_name": "requirements",
            "from_agent_id": "agent_a",
            "to_agent_id": "agent_b",
            "delivered_at": "2026-01-01T00:00:01Z",
            "status": "DELIVERED",
            "payload": {"files": [{"path": "requirements.md", "sha256": "sha256:y"}]},
        }
    ]
    write_jsonl(plan_dir / "deliveries.jsonl", deliveries)

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t2 = next(t for t in status["tasks"] if t["task_id"] == "task_2")
    assert t2["state"] == "READY"


def test_monitor_marks_blocked_waiting_input_from_latest_command(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_2"
    (agents_root / "agent_exec" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_1", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )

    # latest command in archive waits for missing file
    cmd_env = {
        "schema_version": "1.0",
        "message_id": "msg_cmd_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_planner",
        "type": "command",
        "created_at": "2026-01-01T00:00:00Z",
        "task_id": "task_1",
        "command_id": "cmd_task_1_001",
        "payload": {
            "command": {
                "schema_version": "1.0",
                "command_id": "cmd_task_1_001",
                "plan_id": plan_id,
                "task_id": "task_1",
                "command_seq": 1,
                "dag_ref": {"sha256": dag_sha},
                "prompt": "do it",
                "required_inputs": ["missing.txt"],
                "resolved_inputs": None,
                "wait_for_inputs": True,
                "score_required": False,
                "timeout": 60,
            }
        },
    }
    write_json(plan_dir / "commands" / "msg_cmd_1__cmd.msg.json", cmd_env)

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t1 = next(t for t in status["tasks"] if t["task_id"] == "task_1")
    assert t1["state"] == "BLOCKED_WAITING_INPUT"


def test_monitor_schema_validation_enabled_writes_plan_status(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_schema"
    (agents_root / "agent_a" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [{"task_id": "task_1", "assigned_agent_id": "agent_a", "depends_on": [], "outputs": []}],
    }
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
    write_jsonl(plan_dir / "deliveries.jsonl", [])

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=True),
    )
    run_once(ctx)
    assert (plan_dir / "plan_status.json").exists()


def test_monitor_collects_agent_status_snapshot(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_0"
    (agents_root / "agent_a" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)
    (agents_root / "agent_a").mkdir(parents=True, exist_ok=True)

    # minimal plan so monitor runs
    dag = {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": "agent_a", "depends_on": [], "outputs": []}]}
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )
    write_jsonl(plan_dir / "deliveries.jsonl", [])

    # agent reports status_heartbeat
    write_json(
        agents_root / "agent_a" / "status_heartbeat.json",
        {
            "schema_version": "1.0",
            "agent_id": "agent_a",
            "last_heartbeat": "2026-01-01T00:00:00Z",
            "health": "HEALTHY",
            "status": "RUNNING",
            "uptime_seconds": None,
            "current_plan_ids": [plan_id],
            "current_task_ids": None,
            "resource_usage": None,
            "last_error": None,
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)

    snapshot = system_runtime / "agent_status" / "agent_a.json"
    assert snapshot.exists()
    obj = json.loads(snapshot.read_text(encoding="utf-8"))
    assert obj["agent_id"] == "agent_a"
    assert obj["last_heartbeat"] == "2026-01-01T00:00:00Z"
    assert "collected_at" in obj


def test_monitor_schema_validation_skips_invalid_agent_status(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_schema_skip"
    (agents_root / "agent_a" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    # minimal plan with schema-valid active_dag_ref when schema validation is enabled
    dag = {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": "agent_a", "depends_on": [], "outputs": []}]}
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "dag_kind": "meta", "task_dag_sha256": dag_sha, "updated_at": "2026-01-01T00:00:00Z"},
    )
    write_jsonl(plan_dir / "deliveries.jsonl", [])

    # Invalid status_heartbeat (missing required last_heartbeat)
    write_json(
        agents_root / "agent_a" / "status_heartbeat.json",
        {
            "schema_version": "1.0",
            "agent_id": "agent_a",
            "health": "HEALTHY",
            "status": "RUNNING",
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=True),
    )
    run_once(ctx)

    # plan_status is still produced; agent_status snapshot is skipped due to schema validation failure
    assert (plan_dir / "plan_status.json").exists()
    assert not (system_runtime / "agent_status" / "agent_a.json").exists()


def test_monitor_uses_archived_ack_to_mark_task_completed(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_ack"
    (agents_root / "agent_exec" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_1", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )

    write_jsonl(
        plan_dir / "deliveries.jsonl",
        [
            {
                "schema_version": "1.0",
                "delivery_id": "del_1",
                "plan_id": plan_id,
                "message_id": "msg_cmd_1",
                "envelope_sha256": "sha256:x",
                "task_id": "task_1",
                "command_id": "cmd_task_1_001",
                "output_name": None,
                "from_agent_id": "agent_planner",
                "to_agent_id": "agent_exec",
                "delivered_at": "2026-01-01T00:00:00Z",
                "status": "DELIVERED",
                "payload": {"files": []},
            }
        ],
    )

    write_json(
        plan_dir / "acks" / "ack_msg_cmd_1.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "message_id": "msg_cmd_1",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "command_seq": 1,
            "consumer_agent_id": "agent_exec",
            "status": "SUCCEEDED",
            "consumed_at": "2026-01-01T00:00:01Z",
            "finished_at": "2026-01-01T00:00:02Z",
            "result": {"ok": True},
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t1 = next(t for t in status["tasks"] if t["task_id"] == "task_1")
    assert t1["state"] == "COMPLETED"


def test_monitor_falls_back_to_agent_outbox_ack_when_no_archive(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_ack_fallback"
    outbox_plan = agents_root / "agent_exec" / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_1", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )

    write_jsonl(
        plan_dir / "deliveries.jsonl",
        [
            {
                "schema_version": "1.0",
                "delivery_id": "del_1",
                "plan_id": plan_id,
                "message_id": "msg_cmd_1",
                "envelope_sha256": "sha256:x",
                "task_id": "task_1",
                "command_id": "cmd_task_1_001",
                "output_name": None,
                "from_agent_id": "agent_planner",
                "to_agent_id": "agent_exec",
                "delivered_at": "2026-01-01T00:00:00Z",
                "status": "DELIVERED",
                "payload": {"files": []},
            }
        ],
    )

    write_json(
        outbox_plan / "ack_msg_cmd_1.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "message_id": "msg_cmd_1",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "command_seq": 1,
            "consumer_agent_id": "agent_exec",
            "status": "FAILED",
            "consumed_at": "2026-01-01T00:00:01Z",
            "finished_at": "2026-01-01T00:00:02Z",
            "result": {"ok": False},
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t1 = next(t for t in status["tasks"] if t["task_id"] == "task_1")
    assert t1["state"] == "FAILED"


def test_monitor_maps_message_id_to_task_id_from_command_archive_when_delivery_missing_fields(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_map_fallback"
    (agents_root / "agent_exec" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_1", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )

    # delivery is missing task_id/command_id (legacy/partial log)
    write_jsonl(
        plan_dir / "deliveries.jsonl",
        [
            {
                "schema_version": "1.0",
                "delivery_id": "del_1",
                "plan_id": plan_id,
                "message_id": "msg_cmd_1",
                "envelope_sha256": "sha256:x",
                "task_id": None,
                "command_id": None,
                "output_name": None,
                "from_agent_id": "agent_planner",
                "to_agent_id": "agent_exec",
                "delivered_at": "2026-01-01T00:00:00Z",
                "status": "DELIVERED",
                "payload": {"files": []},
            }
        ],
    )

    # command archive provides mapping
    write_json(
        plan_dir / "commands" / "msg_cmd_1__cmd.msg.json",
        {
            "schema_version": "1.0",
            "message_id": "msg_cmd_1",
            "plan_id": plan_id,
            "producer_agent_id": "agent_planner",
            "type": "command",
            "created_at": "2026-01-01T00:00:00Z",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "payload": {
                "command": {
                    "schema_version": "1.0",
                    "command_id": "cmd_task_1_001",
                    "plan_id": plan_id,
                    "task_id": "task_1",
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
        },
    )

    write_json(
        plan_dir / "acks" / "ack_msg_cmd_1.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "message_id": "msg_cmd_1",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "command_seq": 1,
            "consumer_agent_id": "agent_exec",
            "status": "SUCCEEDED",
            "consumed_at": "2026-01-01T00:00:01Z",
            "finished_at": "2026-01-01T00:00:02Z",
            "result": {"ok": True},
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t1 = next(t for t in status["tasks"] if t["task_id"] == "task_1")
    assert t1["state"] == "COMPLETED"


def test_monitor_ignores_inconsistent_command_archive_and_alerts(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_inconsistent"
    (agents_root / "agent_exec" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_1", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )
    write_jsonl(plan_dir / "deliveries.jsonl", [])

    # command archive is inconsistent: envelope.task_id != payload.command.task_id
    write_json(
        plan_dir / "commands" / "msg_cmd_bad__cmd.msg.json",
        {
            "schema_version": "1.0",
            "message_id": "msg_cmd_bad",
            "plan_id": plan_id,
            "producer_agent_id": "agent_planner",
            "type": "command",
            "created_at": "2026-01-01T00:00:00Z",
            "task_id": "task_X",
            "command_id": "cmd_task_1_001",
            "payload": {
                "command": {
                    "schema_version": "1.0",
                    "command_id": "cmd_task_1_001",
                    "plan_id": plan_id,
                    "task_id": "task_1",
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
        },
    )

    # even if ack exists, mapping should not use this message
    write_json(
        plan_dir / "acks" / "ack_msg_cmd_bad.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "message_id": "msg_cmd_bad",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "command_seq": 1,
            "consumer_agent_id": "agent_exec",
            "status": "SUCCEEDED",
            "consumed_at": "2026-01-01T00:00:01Z",
            "finished_at": "2026-01-01T00:00:02Z",
            "result": {"ok": True},
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t1 = next(t for t in status["tasks"] if t["task_id"] == "task_1")
    assert t1["state"] == "READY"

    alert_dir = system_runtime / "alerts" / plan_id
    assert alert_dir.exists()
    alerts = [json.loads(p.read_text(encoding="utf-8")) for p in alert_dir.glob("alert_*.json")]
    assert any(a.get("type") == "COMMAND_ARCHIVE_INCONSISTENT" for a in alerts)


def test_monitor_marks_running_timeout_when_consumed_too_long(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_timeout"
    (agents_root / "agent_exec" / "outbox" / plan_id).mkdir(parents=True, exist_ok=True)

    dag = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "nodes": [
            {"task_id": "task_1", "assigned_agent_id": "agent_exec", "depends_on": [], "outputs": []}
        ],
    }
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "task_dag_sha256": dag_sha, "updated_at": None},
    )
    write_jsonl(
        plan_dir / "deliveries.jsonl",
        [
            {
                "schema_version": "1.0",
                "delivery_id": "del_1",
                "plan_id": plan_id,
                "message_id": "msg_cmd_1",
                "envelope_sha256": "sha256:x",
                "task_id": "task_1",
                "command_id": "cmd_task_1_001",
                "output_name": None,
                "from_agent_id": "agent_planner",
                "to_agent_id": "agent_exec",
                "delivered_at": "2026-01-01T00:00:00Z",
                "status": "DELIVERED",
                "payload": {"files": []},
            }
        ],
    )

    write_json(
        plan_dir / "commands" / "msg_cmd_1__cmd.msg.json",
        {
            "schema_version": "1.0",
            "message_id": "msg_cmd_1",
            "plan_id": plan_id,
            "producer_agent_id": "agent_planner",
            "type": "command",
            "created_at": "2026-01-01T00:00:00Z",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "payload": {
                "command": {
                    "schema_version": "1.0",
                    "command_id": "cmd_task_1_001",
                    "plan_id": plan_id,
                    "task_id": "task_1",
                    "command_seq": 1,
                    "dag_ref": {"sha256": dag_sha},
                    "prompt": "do it",
                    "required_inputs": [],
                    "resolved_inputs": None,
                    "wait_for_inputs": False,
                    "score_required": False,
                    "timeout": 1,
                }
            },
        },
    )

    # consumed_at is far in the past; should trigger timeout alert and blocking marker.
    write_json(
        plan_dir / "acks" / "ack_msg_cmd_1.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "message_id": "msg_cmd_1",
            "task_id": "task_1",
            "command_id": "cmd_task_1_001",
            "command_seq": 1,
            "consumer_agent_id": "agent_exec",
            "status": "CONSUMED",
            "consumed_at": "2000-01-01T00:00:00Z",
            "finished_at": None,
            "result": None,
        },
    )

    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=SchemaRegistry(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    run_once(ctx)
    status = json.loads((plan_dir / "plan_status.json").read_text(encoding="utf-8"))
    t1 = next(t for t in status["tasks"] if t["task_id"] == "task_1")
    assert t1["state"] == "RUNNING"
    assert (t1.get("blocking") or {}).get("reason") == "TIMEOUT"

    alert_dir = system_runtime / "alerts" / plan_id
    alerts = [json.loads(p.read_text(encoding="utf-8")) for p in alert_dir.glob("alert_*.json")]
    assert any(a.get("type") == "COMMAND_ACK_TIMEOUT" for a in alerts)
