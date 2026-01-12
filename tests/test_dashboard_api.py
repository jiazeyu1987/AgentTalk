from __future__ import annotations

import json
from pathlib import Path

import pytest


pytest.importorskip("fastapi")


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_dashboard_endpoints(tmp_path: Path):
    from fastapi.testclient import TestClient

    from agenttalk.dashboard.app import create_app

    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_1"
    plan_dir = system_runtime / "plans" / plan_id
    write_json(
        plan_dir / "plan_status.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "active_task_dag_sha256": "sha256:dag",
            "updated_at": "2026-01-01T00:00:00Z",
            "blocked_summary": {"INPUT": 0, "REVIEW": 0, "HUMAN": 0},
            "tasks": [{"task_id": "task_1", "assigned_agent_id": "agent_a", "state": "RUNNING", "updated_at": None, "blocking": None}],
        },
    )
    write_jsonl(
        plan_dir / "deliveries.jsonl",
        [
            {
                "schema_version": "1.0",
                "delivery_id": "del_1",
                "plan_id": plan_id,
                "message_id": "msg_1",
                "envelope_sha256": "sha256:e",
                "task_id": "task_1",
                "command_id": None,
                "output_name": None,
                "from_agent_id": "a",
                "to_agent_id": "b",
                "delivered_at": "2026-01-01T00:00:01Z",
                "status": "DELIVERED",
                "payload": {"files": []},
            }
        ],
    )
    write_json(plan_dir / "decisions" / "d1.json", {"decision_id": "d1", "created_at": "2026-01-01T00:00:02Z"})
    write_json(plan_dir / "acks" / "ack_msg_1.json", {"message_id": "msg_1", "status": "CONSUMED", "consumed_at": "2026-01-01T00:00:03Z"})
    write_json(plan_dir / "release_manifest.json", {"release_id": "release_1", "created_at": "2026-01-01T00:00:04Z"})

    write_json(system_runtime / "agent_status" / "agent_a.json", {"agent_id": "agent_a", "last_heartbeat": "2026-01-01T00:00:00Z"})

    app = create_app(system_runtime=system_runtime)
    client = TestClient(app)

    assert client.get("/api/plans").status_code == 200
    status = client.get(f"/api/plans/{plan_id}/status").json()
    assert status["plan_id"] == plan_id

    deliveries = client.get(f"/api/plans/{plan_id}/deliveries?limit=1&offset=0").json()
    assert deliveries["total"] == 1

    decisions = client.get(f"/api/plans/{plan_id}/decisions").json()
    assert decisions["total"] == 1

    acks = client.get(f"/api/plans/{plan_id}/acks").json()
    assert acks["total"] == 1

    release = client.get(f"/api/plans/{plan_id}/release_manifest").json()
    assert release["release_id"] == "release_1"

    agents = client.get("/api/agents").json()
    assert agents and agents[0]["agent_id"] == "agent_a"
    assert client.get("/api/agents/agent_a").status_code == 200


def test_dashboard_deliveries_filter_and_release_manifest_404(tmp_path: Path):
    from fastapi.testclient import TestClient

    from agenttalk.dashboard.app import create_app

    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_1"
    plan_dir = system_runtime / "plans" / plan_id
    write_json(
        plan_dir / "plan_status.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "active_task_dag_sha256": "sha256:dag",
            "updated_at": "2026-01-01T00:00:00Z",
            "blocked_summary": {"INPUT": 0, "REVIEW": 0, "HUMAN": 0},
            "tasks": [],
        },
    )
    write_jsonl(
        plan_dir / "deliveries.jsonl",
        [
            {
                "schema_version": "1.0",
                "delivery_id": "del_1",
                "plan_id": plan_id,
                "message_id": "msg_1",
                "envelope_sha256": "sha256:e",
                "task_id": "task_1",
                "command_id": None,
                "output_name": None,
                "from_agent_id": "a",
                "to_agent_id": "b",
                "delivered_at": "2026-01-01T00:00:01Z",
                "status": "DELIVERED",
                "payload": {"files": []},
            },
            {
                "schema_version": "1.0",
                "delivery_id": "del_2",
                "plan_id": plan_id,
                "message_id": "msg_1",
                "envelope_sha256": "sha256:e",
                "task_id": "task_1",
                "command_id": None,
                "output_name": None,
                "from_agent_id": "a",
                "to_agent_id": "b",
                "delivered_at": "2026-01-01T00:00:02Z",
                "status": "SKIPPED_DUPLICATE",
                "payload": {"files": []},
            },
        ],
    )

    app = create_app(system_runtime=system_runtime)
    client = TestClient(app)

    deliveries_default = client.get(f"/api/plans/{plan_id}/deliveries").json()
    assert deliveries_default["total"] == 1
    assert deliveries_default["items"][0]["status"] == "DELIVERED"

    deliveries_all = client.get(f"/api/plans/{plan_id}/deliveries?include_skipped=true").json()
    assert deliveries_all["total"] == 2

    assert client.get(f"/api/plans/{plan_id}/release_manifest").status_code == 404
