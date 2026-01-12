from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from agenttalk.heartbeat.schema import SchemaRegistry
from agenttalk.heartbeat.state import build_input_lookup
from agenttalk.heartbeat.io import atomic_write_json


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


EVIDENCE_SCHEMA_BY_FILENAME: dict[str, str] = {
    "build_validation_result.json": "build_validation_result.schema.json",
    "deploy_validation_result.json": "deploy_validation_result.schema.json",
    "smoke_test_result.json": "smoke_test_result.schema.json",
    "e2e_test_result.json": "e2e_test_result.schema.json",
    "security_scan_result.json": "security_scan_result.schema.json",
}


@dataclass(frozen=True)
class ReleaseGateResult:
    decision: str  # APPROVE|REJECT
    evidence_required: list[str]
    evidence_refs: list[dict]
    missing_evidence: list[str]
    rejected_evidence: list[str]


def evaluate_release_gates(
    *,
    plan_id: str,
    agent_workspace_inputs_dir: Path,
    evidence_required: list[str],
    schemas: SchemaRegistry,
    schema_validation_enabled: bool = True,
) -> ReleaseGateResult:
    lookup = build_input_lookup(agent_workspace_inputs_dir)

    required = []
    for name in evidence_required:
        if name in ("release_manifest.json", "decision_record.json"):
            continue
        if name not in required:
            required.append(name)

    evidence_refs: list[dict] = []
    missing: list[str] = []
    rejected: list[str] = []
    for name in required:
        stored_at = lookup.get(name)
        if not stored_at:
            missing.append(name)
            continue
        p = Path(stored_at)
        if not p.exists():
            missing.append(name)
            continue
        sha = _file_sha256(p)
        evidence_refs.append({"name": name, "sha256": sha})
        schema = EVIDENCE_SCHEMA_BY_FILENAME.get(name)
        try:
            obj = _read_json(p)
            if schema and schema_validation_enabled:
                schemas.validate(obj, schema)
            if str(obj.get("plan_id") or "") and str(obj.get("plan_id")) != plan_id:
                rejected.append(name)
                continue
            decision = str(obj.get("decision") or "")
            if decision != "PASS":
                rejected.append(name)
        except Exception:
            rejected.append(name)

    decision = "APPROVE" if not missing and not rejected else "REJECT"
    return ReleaseGateResult(
        decision=decision,
        evidence_required=required,
        evidence_refs=evidence_refs,
        missing_evidence=missing,
        rejected_evidence=rejected,
    )


def run_release_coordinator_once(
    *,
    plan_id: str,
    agent_id: str,
    agents_root: Path,
    system_runtime: Path,
    release_id: str,
    schema_validation_enabled: bool = True,
) -> tuple[Path, Path]:
    """
    Reads plan_manifest for required gates, checks evidence in agent workspace inputs,
    and writes release_manifest + decision_record to agent outbox.

    Returns:
      (release_manifest_path, decision_record_path)
    """
    schemas = SchemaRegistry(Path("doc/rule/templates/schemas"))
    plan_dir = system_runtime / "plans" / plan_id
    plan_manifest_path = plan_dir / "plan_manifest.json"
    if not plan_manifest_path.exists():
        raise RuntimeError(f"missing plan_manifest.json: {plan_manifest_path}")
    plan_manifest = _read_json(plan_manifest_path)
    if schema_validation_enabled:
        schemas.validate(plan_manifest, "plan_manifest.schema.json")
    policies = plan_manifest.get("policies") or {}
    evidence_required = list(policies.get("release_gates_required") or [])
    if not evidence_required:
        # fall back to common set
        evidence_required = list(EVIDENCE_SCHEMA_BY_FILENAME.keys())

    agent_root = agents_root / agent_id
    workspace_inputs_dir = agent_root / "workspace" / plan_id / "inputs"
    outbox_plan = agent_root / "outbox" / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)

    gate = evaluate_release_gates(
        plan_id=plan_id,
        agent_workspace_inputs_dir=workspace_inputs_dir,
        evidence_required=evidence_required,
        schemas=schemas,
        schema_validation_enabled=schema_validation_enabled,
    )

    now = datetime.now(timezone.utc)
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "release_id": release_id,
        "plan_id": plan_id,
        "created_at": _iso_z(now),
        "release_manager_agent_id": agent_id,
        "artifacts": None,
        "evidence_required": gate.evidence_required,
        "evidence_refs": gate.evidence_refs,
        "decision": gate.decision,
        "notes": None,
    }
    if gate.missing_evidence:
        manifest["notes"] = f"missing evidence: {gate.missing_evidence}"
    elif gate.rejected_evidence:
        manifest["notes"] = f"rejected evidence: {gate.rejected_evidence}"
    else:
        manifest["notes"] = "all required evidence present and PASS"

    manifest_path = outbox_plan / f"release_manifest_{release_id}.json"
    atomic_write_json(manifest_path, manifest)
    if schema_validation_enabled:
        schemas.validate(_read_json(manifest_path), "release_manifest.schema.json")
    manifest_sha = _file_sha256(manifest_path)

    decision_id = f"dec_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    decision_record: dict[str, Any] = {
        "schema_version": "1.0",
        "decision_id": decision_id,
        "plan_id": plan_id,
        "decision_type": "RELEASE",
        "decision": gate.decision,
        "decided_by_agent_id": agent_id,
        "created_at": _iso_z(now),
        "subject": {"kind": "release", "ref_sha256": manifest_sha, "ref_revision": None, "task_id": None, "output_name": None},
        "missing_participants": None,
        "evidence_files": gate.evidence_required,
        "notes": "release decision derived from required evidence files",
    }

    decision_path = outbox_plan / f"decision_record_{decision_id}.json"
    atomic_write_json(decision_path, decision_record)
    if schema_validation_enabled:
        schemas.validate(_read_json(decision_path), "decision_record.schema.json")
    return manifest_path, decision_path
