from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agenttalk.monitor.app import MonitorConfig, MonitorContext, run_once as monitor_run_once
from agenttalk.heartbeat.schema import SchemaRegistry as HeartbeatSchemas
from agenttalk.router.app import RouterConfig, RouterContext, tick as router_tick
from agenttalk.router.io import AgentsPaths, SystemPaths, file_sha256
from agenttalk.router.schema import SchemaRegistry as RouterSchemas
from agenttalk.release.app import run_release_coordinator_once


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


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
        {"schema_version": "1.0", "plan_id": plan_id, "dag_kind": "business", "task_dag_sha256": dag_sha, "updated_at": None},
    )
    return dag_sha


def test_end_to_end_dag_review_revision_release_manifest(tmp_path: Path):
    """
    Scenario C (minimal):
      - reviewers produce dag_review_result (REVISE)
      - coordinator issues decision_record (REVISE), then later APPROVE
      - release coordinator checks evidence and produces release_manifest APPROVE
      - router archives decisions/releases and refreshes release_manifest.json pointer
      - monitor produces agent_status snapshot (observability)
    """
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_c"
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    ensure_agent(agents_root, "agent_architecture_expert")
    ensure_agent(agents_root, "agent_security_manager")
    ensure_agent(agents_root, "agent_dag_review_coordinator")
    ensure_agent(agents_root, "agent_release_engineer")
    ensure_agent(agents_root, "agent_human_gateway")

    # Minimal DAG + deliveries
    dag = {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": "agent_release_engineer", "depends_on": [], "outputs": []}]}
    write_plan_dag(system_runtime, plan_id, dag)
    write_jsonl(system_runtime / "plans" / plan_id / "deliveries.jsonl", [])

    # Reviewers produce dag_review_result artifacts (not routed here; coordinator reads via external means in real system)
    # For MVP: coordinator directly emits decision_record for timeline.
    outbox_coordinator = agents_root / "agent_dag_review_coordinator" / "outbox" / plan_id
    outbox_coordinator.mkdir(parents=True, exist_ok=True)

    write_json(
        outbox_coordinator / "decision_record_dec_rev.json",
        {
            "schema_version": "1.0",
            "decision_id": "dec_rev",
            "plan_id": plan_id,
            "decision_type": "DAG_REVIEW",
            "decision": "REVISE",
            "decided_by_agent_id": "agent_dag_review_coordinator",
            "created_at": "2026-01-01T00:10:00Z",
            "subject": {"kind": "task_dag", "ref_sha256": "sha256:x", "ref_revision": 1},
            "missing_participants": ["agent_security_manager"],
            "evidence_files": ["dag_review_result_round1_arch.json"],
            "notes": "needs revision",
        },
    )

    write_json(
        outbox_coordinator / "decision_record_dec_app.json",
        {
            "schema_version": "1.0",
            "decision_id": "dec_app",
            "plan_id": plan_id,
            "decision_type": "DAG_REVIEW",
            "decision": "APPROVE",
            "decided_by_agent_id": "agent_dag_review_coordinator",
            "created_at": "2026-01-01T00:20:00Z",
            "subject": {"kind": "task_dag", "ref_sha256": "sha256:y", "ref_revision": 2},
            "missing_participants": None,
            "evidence_files": ["dag_review_result_round2_arch.json", "dag_review_result_round2_sec.json"],
            "notes": "approved",
        },
    )

    # Prepare plan_manifest and evidence in release engineer workspace inputs
    write_json(
        system_runtime / "plans" / plan_id / "plan_manifest.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "created_at": "2026-01-01T00:00:00Z",
            "agents": [{"agent_id": "agent_release_engineer", "required": True}],
            "deliverables": [{"name": "x"}],
            "policies": {"release_gates_required": ["build_validation_result.json", "smoke_test_result.json"]},
        },
    )

    inputs_dir = agents_root / "agent_release_engineer" / "workspace" / plan_id / "inputs"
    (inputs_dir / "task_build" / "build").mkdir(parents=True, exist_ok=True)
    (inputs_dir / "task_smoke" / "smoke").mkdir(parents=True, exist_ok=True)
    build = inputs_dir / "task_build" / "build" / "build_validation_result.json"
    smoke = inputs_dir / "task_smoke" / "smoke" / "smoke_test_result.json"
    write_json(
        build,
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "validation_id": "build_1",
            "validator_agent_id": "agent_build",
            "validated_at": "2026-01-01T00:30:00Z",
            "subject": {},
            "decision": "PASS",
        },
    )
    write_json(
        smoke,
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "validation_id": "smoke_1",
            "validator_agent_id": "agent_sre",
            "validated_at": "2026-01-01T00:31:00Z",
            "decision": "PASS",
        },
    )

    # Build minimal input_index lookup entries
    from agenttalk.heartbeat.state import InputIndexEntryFile, update_input_index

    sha_build = "sha256:" + __import__("hashlib").sha256(build.read_bytes()).hexdigest()
    sha_smoke = "sha256:" + __import__("hashlib").sha256(smoke.read_bytes()).hexdigest()
    update_input_index(
        inputs_dir,
        plan_id=plan_id,
        agent_id="agent_release_engineer",
        message_id="msg_build",
        task_id="task_build",
        output_name="build",
        received_at="2026-01-01T00:30:10Z",
        files=[InputIndexEntryFile(path="build_validation_result.json", sha256=sha_build, stored_at=str(build.as_posix()))],
        updated_at="2026-01-01T00:30:10Z",
    )
    update_input_index(
        inputs_dir,
        plan_id=plan_id,
        agent_id="agent_release_engineer",
        message_id="msg_smoke",
        task_id="task_smoke",
        output_name="smoke",
        received_at="2026-01-01T00:31:10Z",
        files=[InputIndexEntryFile(path="smoke_test_result.json", sha256=sha_smoke, stored_at=str(smoke.as_posix()))],
        updated_at="2026-01-01T00:31:10Z",
    )

    # Release coordinator emits release_manifest + decision_record(RELEASE)
    run_release_coordinator_once(
        plan_id=plan_id,
        agent_id="agent_release_engineer",
        agents_root=agents_root,
        system_runtime=system_runtime,
        release_id="release_1",
        schema_validation_enabled=True,
    )

    # Router archives decision records + release manifests
    router_ctx = RouterContext(
        agents=AgentsPaths(agents_root=agents_root),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=RouterSchemas(schemas_base_dir=Path("doc/rule/templates/schemas")),
        config=RouterConfig(poll_interval_seconds=1, schema_validation_enabled=False),
    )
    router_tick(router_ctx)

    assert (system_runtime / "plans" / plan_id / "decisions" / "decision_record_dec_rev.json").exists()
    assert (system_runtime / "plans" / plan_id / "decisions" / "decision_record_dec_app.json").exists()
    assert (system_runtime / "plans" / plan_id / "release_manifest.json").exists()

    # Monitor collects agent status snapshot (use a minimal status_heartbeat file)
    write_json(
        agents_root / "agent_release_engineer" / "status_heartbeat.json",
        {
            "schema_version": "1.0",
            "agent_id": "agent_release_engineer",
            "last_heartbeat": "2026-01-01T00:40:00Z",
            "health": "HEALTHY",
            "status": "RUNNING",
            "uptime_seconds": None,
            "current_plan_ids": [plan_id],
            "current_task_ids": None,
            "resource_usage": None,
            "last_error": None,
        },
    )
    monitor_ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=HeartbeatSchemas(Path("doc/rule/templates/schemas")),
        config=MonitorConfig(schema_validation_enabled=False),
    )
    monitor_run_once(monitor_ctx)
    assert (system_runtime / "agent_status" / "agent_release_engineer.json").exists()
