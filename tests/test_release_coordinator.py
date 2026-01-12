from __future__ import annotations

import json
from pathlib import Path

from agenttalk.heartbeat.state import InputIndexEntryFile, update_input_index
from agenttalk.release.app import run_release_coordinator_once
from agenttalk.router.app import RouterConfig, RouterContext, tick
from agenttalk.router.io import AgentsPaths, SystemPaths, file_sha256
from agenttalk.router.schema import SchemaRegistry


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_plan_dag(system_runtime: Path, plan_id: str, dag: dict) -> str:
    plan_dir = system_runtime / "plans" / plan_id
    write_json(plan_dir / "task_dag.json", dag)
    dag_sha = file_sha256(plan_dir / "task_dag.json")
    write_json(
        plan_dir / "active_dag_ref.json",
        {"schema_version": "1.0", "plan_id": plan_id, "dag_kind": "meta", "task_dag_sha256": dag_sha, "updated_at": None},
    )
    return dag_sha


def ensure_agent(agents_root: Path, agent_id: str) -> Path:
    root = agents_root / agent_id
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "outbox").mkdir(parents=True, exist_ok=True)
    (root / "workspace").mkdir(parents=True, exist_ok=True)
    return root


def test_release_coordinator_rejects_when_missing_required_evidence(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_rel_1"
    agent_id = "agent_release_engineer"
    ensure_agent(agents_root, agent_id)

    # plan_manifest defines required evidence
    write_json(
        system_runtime / "plans" / plan_id / "plan_manifest.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "created_at": "2026-01-01T00:00:00Z",
            "agents": [{"agent_id": agent_id, "required": True}],
            "deliverables": [{"name": "x"}],
            "policies": {"release_gates_required": ["build_validation_result.json", "smoke_test_result.json"]},
        },
    )

    # only build_validation_result exists in workspace inputs
    inputs_dir = agents_root / agent_id / "workspace" / plan_id / "inputs"
    stored = inputs_dir / "task_build" / "build" / "build_validation_result.json"
    write_json(
        stored,
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "validation_id": "build_1",
            "validator_agent_id": "agent_build",
            "validated_at": "2026-01-01T00:01:00Z",
            "subject": {},
            "decision": "PASS",
        },
    )
    sha = "sha256:" + __import__("hashlib").sha256(stored.read_bytes()).hexdigest()
    update_input_index(
        inputs_dir,
        plan_id=plan_id,
        agent_id=agent_id,
        message_id="msg_1",
        task_id="task_build",
        output_name="build",
        received_at="2026-01-01T00:02:00Z",
        files=[InputIndexEntryFile(path="build_validation_result.json", sha256=sha, stored_at=str(stored.as_posix()))],
        updated_at="2026-01-01T00:02:00Z",
    )

    manifest_path, decision_path = run_release_coordinator_once(
        plan_id=plan_id,
        agent_id=agent_id,
        agents_root=agents_root,
        system_runtime=system_runtime,
        release_id="release_1",
        schema_validation_enabled=True,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["decision"] == "REJECT"
    assert "smoke_test_result.json" in (manifest.get("notes") or "")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert decision["decision_type"] == "RELEASE"
    assert decision["decision"] == "REJECT"


def test_release_coordinator_approves_when_all_required_evidence_passes_and_router_archives(tmp_path: Path):
    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    plan_id = "plan_rel_2"
    agent_id = "agent_release_engineer"
    ensure_agent(agents_root, agent_id)
    ensure_agent(agents_root, "agent_human_gateway")

    write_json(
        system_runtime / "plans" / plan_id / "plan_manifest.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "created_at": "2026-01-01T00:00:00Z",
            "agents": [{"agent_id": agent_id, "required": True}],
            "deliverables": [{"name": "x"}],
            "policies": {"release_gates_required": ["build_validation_result.json", "smoke_test_result.json"]},
        },
    )

    inputs_dir = agents_root / agent_id / "workspace" / plan_id / "inputs"
    build = inputs_dir / "task_build" / "build" / "build_validation_result.json"
    smoke = inputs_dir / "task_smoke" / "smoke" / "smoke_test_result.json"
    write_json(
        build,
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "validation_id": "build_1",
            "validator_agent_id": "agent_build",
            "validated_at": "2026-01-01T00:01:00Z",
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
            "validated_at": "2026-01-01T00:02:00Z",
            "decision": "PASS",
        },
    )
    sha_build = "sha256:" + __import__("hashlib").sha256(build.read_bytes()).hexdigest()
    sha_smoke = "sha256:" + __import__("hashlib").sha256(smoke.read_bytes()).hexdigest()
    update_input_index(
        inputs_dir,
        plan_id=plan_id,
        agent_id=agent_id,
        message_id="msg_1",
        task_id="task_build",
        output_name="build",
        received_at="2026-01-01T00:02:00Z",
        files=[InputIndexEntryFile(path="build_validation_result.json", sha256=sha_build, stored_at=str(build.as_posix()))],
        updated_at="2026-01-01T00:02:00Z",
    )
    update_input_index(
        inputs_dir,
        plan_id=plan_id,
        agent_id=agent_id,
        message_id="msg_2",
        task_id="task_smoke",
        output_name="smoke",
        received_at="2026-01-01T00:03:00Z",
        files=[InputIndexEntryFile(path="smoke_test_result.json", sha256=sha_smoke, stored_at=str(smoke.as_posix()))],
        updated_at="2026-01-01T00:03:00Z",
    )

    manifest_path, _ = run_release_coordinator_once(
        plan_id=plan_id,
        agent_id=agent_id,
        agents_root=agents_root,
        system_runtime=system_runtime,
        release_id="release_2",
        schema_validation_enabled=True,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["decision"] == "APPROVE"

    # Router archives decision record + release manifest into system_runtime
    ctx = RouterContext(
        agents=AgentsPaths(agents_root=agents_root),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=SchemaRegistry(schemas_base_dir=Path("doc/rule/templates/schemas")),
        config=RouterConfig(poll_interval_seconds=1, schema_validation_enabled=False),
    )
    # minimal DAG so router doesn't abort before reaching other code paths
    write_plan_dag(
        system_runtime,
        plan_id,
        {"schema_version": "1.1", "plan_id": plan_id, "nodes": [{"task_id": "t", "assigned_agent_id": agent_id, "depends_on": [], "outputs": []}]},
    )
    tick(ctx)

    assert (system_runtime / "plans" / plan_id / "release_manifest.json").exists()
    releases = list((system_runtime / "plans" / plan_id / "releases").glob("release_manifest_*.json"))
    assert releases
    decisions = list((system_runtime / "plans" / plan_id / "decisions").glob("decision_record_*.json"))
    assert decisions

