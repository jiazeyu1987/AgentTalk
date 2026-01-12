from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .dag import Dag, parse_active_dag_ref, parse_dag
from .delivery_log import DeliveryLog, delivered_index
from .errors import DagInvalid, EnvelopeInvalid, RoutingNoTarget, RouterError
from .io import AgentsPaths, SystemPaths, atomic_copy, atomic_write_json, file_sha256, read_json
from .schema import SchemaRegistry
from agenttalk.heartbeat.errors import SchemaInvalid


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _delivery_id(now: datetime) -> str:
    return f"del_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"


@dataclass(frozen=True)
class RouterConfig:
    poll_interval_seconds: int = 2
    schema_validation_enabled: bool = True


@dataclass(frozen=True)
class RouterContext:
    agents: AgentsPaths
    system: SystemPaths
    schemas: SchemaRegistry
    config: RouterConfig


def _alert(ctx: RouterContext, *, plan_id: str, alert_type: str, message: str, details: dict | None = None) -> None:
    now = datetime.now(timezone.utc)
    alert_id = f"alert_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "alert_id": alert_id,
        "plan_id": plan_id,
        "severity": "HIGH",
        "type": alert_type,
        "created_at": _iso_z(now),
        "source": {"agent_id": "agent_system_router"},
        "message": message,
        "details": details,
    }
    atomic_write_json(ctx.system.alerts / plan_id / f"{alert_id}.json", payload)


def _deadletter(
    ctx: RouterContext,
    *,
    plan_id: str,
    reason_code: str,
    reason: str,
    original_file: str,
    message_id: str | None = None,
    producer_agent_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    dlq_id = f"dlq_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "deadletter_id": dlq_id,
        "created_at": _iso_z(now),
        "reason": {"code": reason_code, "message": reason},
        "original": {"file_name": original_file, "message_id": message_id, "producer_agent_id": producer_agent_id},
        "actions": {"retriable": False, "suggested_next": "alert"},
    }
    atomic_write_json(ctx.system.deadletter / plan_id / f"{dlq_id}.json", payload)


def _plan_paths(ctx: RouterContext, plan_id: str) -> dict[str, Path]:
    base = ctx.system.plans / plan_id
    return {
        "base": base,
        "deliveries": base / "deliveries.jsonl",
        "commands": base / "commands",
        "decisions": base / "decisions",
        "acks": base / "acks",
        "human_requests": base / "human_requests",
        "human_responses": base / "human_responses",
        "releases": base / "releases",
        "dag_history": base / "dag_history",
        "task_dag": base / "task_dag.json",
        "active_dag_ref": base / "active_dag_ref.json",
    }


def _load_current_dag(ctx: RouterContext, plan_id: str) -> tuple[Dag, str]:
    paths = _plan_paths(ctx, plan_id)
    if not paths["task_dag"].exists():
        raise DagInvalid(code="DAG_MISSING", message=f"missing task_dag.json for plan {plan_id}")
    dag_obj = read_json(paths["task_dag"])
    if ctx.config.schema_validation_enabled:
        ctx.schemas.validate(dag_obj, "task_dag.schema.json")
    dag = parse_dag(dag_obj)
    dag_sha = file_sha256(paths["task_dag"])
    if paths["active_dag_ref"].exists():
        ref = read_json(paths["active_dag_ref"])
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(ref, "active_dag_ref.schema.json")
        _, ref_sha = parse_active_dag_ref(ref)
        if ref_sha != dag_sha:
            raise DagInvalid(code="ACTIVE_DAG_REF_MISMATCH", message=f"{ref_sha} != {dag_sha}")
    return dag, dag_sha


def _discover_agents(agents_root: Path) -> list[str]:
    if not agents_root.exists():
        return []
    return sorted([p.name for p in agents_root.iterdir() if p.is_dir() and not p.name.startswith(".")])


def _discover_outbox_envelopes(agent_outbox_plan: Path) -> list[Path]:
    if not agent_outbox_plan.exists():
        return []
    envs = [
        p
        for p in agent_outbox_plan.iterdir()
        if p.is_file() and p.name.endswith(".msg.json") and not p.name.endswith(".tmp")
    ]
    return sorted(envs, key=lambda p: p.name)

def _discover_outbox_acks(agent_outbox_plan: Path) -> list[Path]:
    if not agent_outbox_plan.exists():
        return []
    acks = [p for p in agent_outbox_plan.glob("ack_*.json") if p.is_file() and not p.name.endswith(".tmp")]
    return sorted(acks, key=lambda p: p.name)


def _discover_outbox_human_requests(agent_outbox_plan: Path) -> list[Path]:
    if not agent_outbox_plan.exists():
        return []
    reqs = [
        p
        for p in agent_outbox_plan.glob("human_intervention_request_*.json")
        if p.is_file() and not p.name.endswith(".tmp")
    ]
    return sorted(reqs, key=lambda p: p.name)


def _discover_outbox_human_responses(agent_outbox_plan: Path) -> list[Path]:
    if not agent_outbox_plan.exists():
        return []
    resps = [
        p
        for p in agent_outbox_plan.glob("human_intervention_response_*.json")
        if p.is_file() and not p.name.endswith(".tmp")
    ]
    return sorted(resps, key=lambda p: p.name)


def _discover_outbox_decision_records(agent_outbox_plan: Path) -> list[Path]:
    if not agent_outbox_plan.exists():
        return []
    items = [p for p in agent_outbox_plan.glob("decision_record_*.json") if p.is_file() and not p.name.endswith(".tmp")]
    return sorted(items, key=lambda p: p.name)


def _discover_outbox_release_manifests(agent_outbox_plan: Path) -> list[Path]:
    if not agent_outbox_plan.exists():
        return []
    items = [p for p in agent_outbox_plan.glob("release_manifest_*.json") if p.is_file() and not p.name.endswith(".tmp")]
    return sorted(items, key=lambda p: p.name)


def _safe_relpath(rel: str) -> Path:
    rel_path = Path(rel)
    if rel_path.is_absolute():
        raise EnvelopeInvalid(code="UNSAFE_PATH", message=f"absolute path is not allowed: {rel}")
    if any(part in ("..",) for part in rel_path.parts):
        raise EnvelopeInvalid(code="UNSAFE_PATH", message=f"path traversal is not allowed: {rel}")
    return rel_path


def _archive_ack(ctx: RouterContext, *, plan_id: str, ack_path: Path) -> None:
    paths = _plan_paths(ctx, plan_id)
    try:
        ack_obj = read_json(ack_path)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(ack_obj, "ack.schema.json")
        message_id = str(ack_obj.get("message_id") or "")
        if not message_id:
            raise EnvelopeInvalid(code="ACK_MISSING_MESSAGE_ID", message="ack missing message_id")
    except Exception as e:
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="ACK_SCHEMA_INVALID",
            reason=str(e),
            original_file=ack_path.name,
            message_id=None,
            producer_agent_id=None,
        )
        _alert(ctx, plan_id=plan_id, alert_type="ACK_SCHEMA_INVALID", message=str(e), details={"file": ack_path.name})
        return

    dst = paths["acks"] / f"ack_{message_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if file_sha256(dst) == file_sha256(ack_path):
            return
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="ACK_ID_REUSED_WITH_DIFFERENT_CONTENT",
            reason=f"ack_{message_id}.json differs from existing archived content",
            original_file=ack_path.name,
            message_id=message_id,
            producer_agent_id=str(ack_obj.get("consumer_agent_id") or ""),
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="ACK_ID_REUSED_WITH_DIFFERENT_CONTENT",
            message=f"ack_{message_id}.json differs from existing archived content",
            details={"file": ack_path.name, "archived": dst.name},
        )
        return
    atomic_copy(ack_path, dst)


def _archive_human_request(ctx: RouterContext, *, plan_id: str, request_path: Path) -> dict | None:
    paths = _plan_paths(ctx, plan_id)
    try:
        req = read_json(request_path)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(req, "human_intervention_request.schema.json")
        request_id = str(req.get("request_id") or "")
        if not request_id:
            raise EnvelopeInvalid(code="HUMAN_REQUEST_MISSING_REQUEST_ID", message="human request missing request_id")
    except Exception as e:
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="HUMAN_REQUEST_SCHEMA_INVALID",
            reason=str(e),
            original_file=request_path.name,
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="HUMAN_REQUEST_SCHEMA_INVALID",
            message=str(e),
            details={"file": request_path.name},
        )
        return None

    dst = paths["human_requests"] / f"human_intervention_request_{request_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if file_sha256(dst) == file_sha256(request_path):
            return req
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="HUMAN_REQUEST_ID_REUSED_WITH_DIFFERENT_CONTENT",
            reason=f"human_intervention_request_{request_id}.json differs from archived content",
            original_file=request_path.name,
            message_id=None,
            producer_agent_id=str(req.get("created_by", {}).get("agent_id") or ""),
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="HUMAN_REQUEST_ID_REUSED_WITH_DIFFERENT_CONTENT",
            message=f"human_intervention_request_{request_id}.json differs from archived content",
            details={"file": request_path.name, "archived": dst.name},
        )
        return None
    atomic_copy(request_path, dst)
    return req


def _archive_human_response(ctx: RouterContext, *, plan_id: str, response_path: Path) -> dict | None:
    paths = _plan_paths(ctx, plan_id)
    try:
        resp = read_json(response_path)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(resp, "human_intervention_response.schema.json")
        request_id = str(resp.get("request_id") or "")
        if not request_id:
            raise EnvelopeInvalid(code="HUMAN_RESPONSE_MISSING_REQUEST_ID", message="human response missing request_id")
    except Exception as e:
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="HUMAN_RESPONSE_SCHEMA_INVALID",
            reason=str(e),
            original_file=response_path.name,
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="HUMAN_RESPONSE_SCHEMA_INVALID",
            message=str(e),
            details={"file": response_path.name},
        )
        return None

    dst = paths["human_responses"] / f"human_intervention_response_{request_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if file_sha256(dst) == file_sha256(response_path):
            return resp
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="HUMAN_RESPONSE_ID_REUSED_WITH_DIFFERENT_CONTENT",
            reason=f"human_intervention_response_{request_id}.json differs from archived content",
            original_file=response_path.name,
            message_id=None,
            producer_agent_id="agent_human_gateway",
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="HUMAN_RESPONSE_ID_REUSED_WITH_DIFFERENT_CONTENT",
            message=f"human_intervention_response_{request_id}.json differs from archived content",
            details={"file": response_path.name, "archived": dst.name},
        )
        return None
    atomic_copy(response_path, dst)
    return resp


def _archive_decision_record(ctx: RouterContext, *, plan_id: str, decision_path: Path) -> dict | None:
    paths = _plan_paths(ctx, plan_id)
    try:
        obj = read_json(decision_path)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(obj, "decision_record.schema.json")
        decision_id = str(obj.get("decision_id") or "")
        if not decision_id:
            raise EnvelopeInvalid(code="DECISION_MISSING_DECISION_ID", message="decision_record missing decision_id")
    except Exception as e:
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="DECISION_SCHEMA_INVALID",
            reason=str(e),
            original_file=decision_path.name,
        )
        _alert(ctx, plan_id=plan_id, alert_type="DECISION_SCHEMA_INVALID", message=str(e), details={"file": decision_path.name})
        return None

    dst = paths["decisions"] / f"decision_record_{decision_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if file_sha256(dst) == file_sha256(decision_path):
            return obj
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="DECISION_ID_REUSED_WITH_DIFFERENT_CONTENT",
            reason=f"decision_record_{decision_id}.json differs from archived content",
            original_file=decision_path.name,
            message_id=None,
            producer_agent_id=str(obj.get("decided_by_agent_id") or ""),
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="DECISION_ID_REUSED_WITH_DIFFERENT_CONTENT",
            message=f"decision_record_{decision_id}.json differs from archived content",
            details={"file": decision_path.name, "archived": dst.name},
        )
        return None

    atomic_copy(decision_path, dst)
    return obj


def _archive_release_manifest(ctx: RouterContext, *, plan_id: str, manifest_path: Path) -> dict | None:
    paths = _plan_paths(ctx, plan_id)
    try:
        obj = read_json(manifest_path)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(obj, "release_manifest.schema.json")
        release_id = str(obj.get("release_id") or "")
        if not release_id:
            raise EnvelopeInvalid(code="RELEASE_MISSING_RELEASE_ID", message="release_manifest missing release_id")
    except Exception as e:
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="RELEASE_MANIFEST_SCHEMA_INVALID",
            reason=str(e),
            original_file=manifest_path.name,
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="RELEASE_MANIFEST_SCHEMA_INVALID",
            message=str(e),
            details={"file": manifest_path.name},
        )
        return None

    dst = paths["releases"] / f"release_manifest_{release_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if file_sha256(dst) == file_sha256(manifest_path):
            return obj
        _deadletter(
            ctx,
            plan_id=plan_id,
            reason_code="RELEASE_ID_REUSED_WITH_DIFFERENT_CONTENT",
            reason=f"release_manifest_{release_id}.json differs from archived content",
            original_file=manifest_path.name,
            message_id=None,
            producer_agent_id=str(obj.get("release_manager_agent_id") or ""),
        )
        _alert(
            ctx,
            plan_id=plan_id,
            alert_type="RELEASE_ID_REUSED_WITH_DIFFERENT_CONTENT",
            message=f"release_manifest_{release_id}.json differs from archived content",
            details={"file": manifest_path.name, "archived": dst.name},
        )
        return None

    atomic_copy(manifest_path, dst)
    return obj


def _refresh_latest_release_manifest(ctx: RouterContext, *, plan_id: str) -> None:
    paths = _plan_paths(ctx, plan_id)
    if not paths["releases"].exists():
        return
    # pick newest created_at; fallback to name ordering
    newest: tuple[str | None, Path] | None = None
    for p in paths["releases"].glob("release_manifest_*.json"):
        if not p.is_file():
            continue
        try:
            obj = read_json(p)
        except Exception:
            continue
        created_at = obj.get("created_at")
        key = str(created_at) if isinstance(created_at, str) else None
        if newest is None:
            newest = (key, p)
        else:
            if newest[0] is None and key is not None:
                newest = (key, p)
            elif newest[0] is not None and key is not None and key > newest[0]:
                newest = (key, p)
            elif newest[0] == key and p.name > newest[1].name:
                newest = (key, p)

    if newest is None:
        return

    dst = paths["base"] / "release_manifest.json"
    if dst.exists() and file_sha256(dst) == file_sha256(newest[1]):
        return
    atomic_copy(newest[1], dst)


def _delivery_entry(
    *,
    plan_id: str,
    message_id: str,
    envelope_sha: str,
    from_agent_id: str,
    to_agent_id: str,
    status: str,
    task_id: str | None = None,
    command_id: str | None = None,
    output_name: str | None = None,
    skip_reason: str | None = None,
    superseded: bool | None = None,
    superseded_by: dict | None = None,
    error: dict | None = None,
    payload_files: list[dict] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    entry: dict[str, Any] = {
        "schema_version": "1.0",
        "delivery_id": _delivery_id(now),
        "plan_id": plan_id,
        "message_id": message_id,
        "envelope_sha256": envelope_sha,
        "task_id": task_id,
        "command_id": command_id,
        "output_name": output_name,
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "delivered_at": _iso_z(now),
        "status": status,
        "skip_reason": skip_reason,
        "superseded": superseded,
        "superseded_by_message_id": None if not superseded_by else superseded_by.get("message_id"),
        "superseded_by_command_id": None if not superseded_by else superseded_by.get("command_id"),
        "superseded_by_command_seq": None if not superseded_by else superseded_by.get("command_seq"),
        "payload": {"files": payload_files or []},
        "error": error,
    }
    return entry


def _deliver_human_provided_file(
    ctx: RouterContext,
    *,
    plan_id: str,
    request_id: str,
    human_gateway_outbox_plan: Path,
    target_agent_id: str,
    file_name: str,
    log: DeliveryLog,
    delivered: set[tuple[str, str]],
) -> None:
    rel = _safe_relpath(file_name)
    src = human_gateway_outbox_plan / rel
    if not src.exists():
        raise EnvelopeInvalid(code="MISSING_PAYLOAD", message=f"missing payload file: {rel}")
    if not ctx.agents.agent_root(target_agent_id).exists():
        raise RoutingNoTarget(code="TARGET_AGENT_NOT_FOUND", message=f"target agent not found: {target_agent_id}")

    dst_inbox = ctx.agents.agent_inbox(target_agent_id) / plan_id
    dst_inbox.mkdir(parents=True, exist_ok=True)

    sha = file_sha256(src)
    message_id = f"msg_human_{request_id}_{sha.replace('sha256:', '')[:12]}"
    if any(mid == message_id for mid, _ in delivered):
        return
    envelope_obj: dict[str, Any] = {
        "schema_version": "1.0",
        "message_id": message_id,
        "plan_id": plan_id,
        "producer_agent_id": "agent_human_gateway",
        "type": "artifact",
        "created_at": _iso_z(datetime.now(timezone.utc)),
        "task_id": "human_gateway",
        "output_name": request_id,
        "payload": {"files": [{"path": rel.as_posix(), "sha256": sha}]},
    }

    # Dedup for this generated artifact.
    env_tmp = dst_inbox / f"{message_id}.msg.json.tmp"
    env_path = dst_inbox / f"{message_id}.msg.json"
    atomic_write_json(env_tmp, envelope_obj)
    env_tmp.replace(env_path)
    env_sha = file_sha256(env_path)

    atomic_copy(src, dst_inbox / rel)
    log.append(
        _delivery_entry(
            plan_id=plan_id,
            message_id=message_id,
            envelope_sha=env_sha,
            from_agent_id="agent_human_gateway",
            to_agent_id=target_agent_id,
            status="DELIVERED",
            task_id="human_gateway",
            output_name=request_id,
            payload_files=[{"path": rel.as_posix(), "sha256": sha}],
        )
    )
    delivered.add((message_id, env_sha))


def _archive_command(ctx: RouterContext, plan_id: str, envelope_path: Path, envelope_obj: dict) -> None:
    paths = _plan_paths(ctx, plan_id)
    message_id = str(envelope_obj.get("message_id") or envelope_path.stem)
    dst = paths["commands"] / f"{message_id}__{envelope_path.name}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        atomic_copy(envelope_path, dst)


def _max_command_seq_in_archive(ctx: RouterContext, plan_id: str, *, task_id: str, dag_sha: str) -> tuple[int | None, dict | None]:
    paths = _plan_paths(ctx, plan_id)
    if not paths["commands"].exists():
        return None, None
    max_seq: int | None = None
    max_meta: dict | None = None
    for p in paths["commands"].glob("*.msg.json"):
        try:
            env = read_json(p)
        except Exception:
            continue
        if env.get("type") != "command":
            continue
        cmd = (env.get("payload") or {}).get("command") or {}
        if str(cmd.get("task_id")) != task_id:
            continue
        if str((cmd.get("dag_ref") or {}).get("sha256")) != dag_sha:
            continue
        try:
            seq = int(cmd.get("command_seq"))
        except Exception:
            continue
        if max_seq is None or seq > max_seq:
            max_seq = seq
            max_meta = {
                "message_id": str(env.get("message_id")),
                "command_id": str(cmd.get("command_id")),
                "command_seq": seq,
            }
    return max_seq, max_meta


def _deliver_one(
    ctx: RouterContext,
    *,
    dag: Dag,
    dag_sha: str,
    plan_id: str,
    from_agent_id: str,
    envelope_path: Path,
    delivered: set[tuple[str, str]],
) -> None:
    paths = _plan_paths(ctx, plan_id)
    log = DeliveryLog(paths["deliveries"])
    envelope_sha = file_sha256(envelope_path)
    try:
        env = read_json(envelope_path)
    except Exception as e:
        raise EnvelopeInvalid(code="ENVELOPE_PARSE_ERROR", message=str(e)) from e

    if str(env.get("schema_version") or "") != "1.0":
        raise EnvelopeInvalid(code="SCHEMA_VERSION_UNSUPPORTED", message=str(env.get("schema_version")))

    if ctx.config.schema_validation_enabled:
        try:
            ctx.schemas.validate(env, "message_envelope.schema.json")
            if env.get("type") == "command":
                cmd_obj = (env.get("payload") or {}).get("command") or {}
                if str(cmd_obj.get("schema_version") or "") != "1.0":
                    raise EnvelopeInvalid(code="SCHEMA_VERSION_UNSUPPORTED", message=str(cmd_obj.get("schema_version")))
                ctx.schemas.validate(cmd_obj, "command.schema.json")
        except SchemaInvalid as e:
            raise EnvelopeInvalid(code=e.code, message=str(e)) from e
        except RouterError:
            raise
        except Exception as e:
            raise EnvelopeInvalid(code="SCHEMA_INVALID", message=str(e)) from e

    message_id = str(env["message_id"])
    if (message_id, envelope_sha) in delivered:
        log.append(
            _delivery_entry(
                plan_id=plan_id,
                message_id=message_id,
                envelope_sha=envelope_sha,
                from_agent_id=from_agent_id,
                to_agent_id="*",
                status="SKIPPED_DUPLICATE",
                skip_reason="DUPLICATE_MESSAGE_ID_AND_SHA256",
                task_id=env.get("task_id"),
                command_id=env.get("command_id"),
                output_name=env.get("output_name"),
                payload_files=(env.get("payload") or {}).get("files") or [],
            )
        )
        return
    # message_id reused with different payload is forbidden
    for mid, sha in delivered:
        if mid == message_id and sha != envelope_sha:
            raise EnvelopeInvalid(
                code="MESSAGE_ID_REUSED_WITH_DIFFERENT_PAYLOAD",
                message=f"message_id reused with different envelope sha256: {message_id}",
            )

    if env.get("type") == "command":
        cmd = (env.get("payload") or {}).get("command") or {}
        task_id = str(cmd.get("task_id"))
        cmd_seq = int(cmd.get("command_seq"))
        cmd_id = str(cmd.get("command_id"))
        if str((cmd.get("dag_ref") or {}).get("sha256")) != dag_sha:
            raise EnvelopeInvalid(code="COMMAND_DAG_MISMATCH", message="command dag_ref.sha256 mismatch")
        _archive_command(ctx, plan_id, envelope_path, env)
        max_seq, max_meta = _max_command_seq_in_archive(ctx, plan_id, task_id=task_id, dag_sha=dag_sha)
        if max_seq is not None and cmd_seq < max_seq:
            log.append(
                _delivery_entry(
                    plan_id=plan_id,
                    message_id=message_id,
                    envelope_sha=envelope_sha,
                    from_agent_id=from_agent_id,
                    to_agent_id="*",
                    status="SKIPPED_SUPERSEDED",
                    skip_reason="SUPERSEDED_BY_NEWER_COMMAND",
                    superseded=True,
                    superseded_by=max_meta,
                    task_id=task_id,
                    command_id=cmd_id,
                )
            )
            return
        target = dag.assigned_agent_for_task(task_id)
        if not ctx.agents.agent_root(target).exists():
            raise RoutingNoTarget(code="TARGET_AGENT_NOT_FOUND", message=f"target agent not found: {target}")
        dst_inbox = ctx.agents.agent_inbox(target) / plan_id
        dst_inbox.mkdir(parents=True, exist_ok=True)
        # deliver envelope file only (commands have no payload files)
        atomic_copy(envelope_path, dst_inbox / envelope_path.name)
        log.append(
            _delivery_entry(
                plan_id=plan_id,
                message_id=message_id,
                envelope_sha=envelope_sha,
                from_agent_id=from_agent_id,
                to_agent_id=target,
                status="DELIVERED",
                task_id=task_id,
                command_id=cmd_id,
            )
        )
        delivered.add((message_id, envelope_sha))
        return

    if env.get("type") == "artifact":
        task_id = str(env.get("task_id"))
        output_name = str(env.get("output_name"))
        targets = dag.deliver_to_for_output(task_id, output_name)
        if not targets:
            raise RoutingNoTarget(code="ROUTING_NO_TARGET", message="deliver_to empty")

        payload_files = (env.get("payload") or {}).get("files") or []
        for target in targets:
            if not ctx.agents.agent_root(target).exists():
                raise RoutingNoTarget(code="TARGET_AGENT_NOT_FOUND", message=f"target agent not found: {target}")
            dst_inbox = ctx.agents.agent_inbox(target) / plan_id
            dst_inbox.mkdir(parents=True, exist_ok=True)
            # payload first
            for f in payload_files:
                rel = Path(str(f["path"]))
                src_payload = envelope_path.parent / rel
                if not src_payload.exists():
                    raise EnvelopeInvalid(code="MISSING_PAYLOAD", message=f"missing payload file: {rel}")
                atomic_copy(src_payload, dst_inbox / rel)
            # envelope last
            atomic_copy(envelope_path, dst_inbox / envelope_path.name)
            log.append(
                _delivery_entry(
                    plan_id=plan_id,
                    message_id=message_id,
                    envelope_sha=envelope_sha,
                    from_agent_id=from_agent_id,
                    to_agent_id=target,
                    status="DELIVERED",
                    task_id=task_id,
                    output_name=output_name,
                    payload_files=payload_files,
                )
            )
        delivered.add((message_id, envelope_sha))
        return

    raise EnvelopeInvalid(code="UNSUPPORTED_MESSAGE_TYPE", message=str(env.get("type")))


def tick(ctx: RouterContext) -> None:
    agent_ids = _discover_agents(ctx.agents.agents_root)
    plan_ids: set[str] = set()
    for agent_id in agent_ids:
        outbox = ctx.agents.agent_outbox(agent_id)
        if not outbox.exists():
            continue
        for plan_dir in outbox.iterdir():
            if plan_dir.is_dir() and not plan_dir.name.startswith("."):
                plan_ids.add(plan_dir.name)

    for plan_id in sorted(plan_ids):
        paths = _plan_paths(ctx, plan_id)
        paths["base"].mkdir(parents=True, exist_ok=True)
        log = DeliveryLog(paths["deliveries"])
        delivered = delivered_index(log.read_entries())

        # control-plane: human intervention requests/responses (not routed by DAG)
        paths["human_requests"].mkdir(parents=True, exist_ok=True)
        paths["human_responses"].mkdir(parents=True, exist_ok=True)
        paths["decisions"].mkdir(parents=True, exist_ok=True)
        paths["releases"].mkdir(parents=True, exist_ok=True)

        # Requests: any agent -> agent_human_gateway inbox
        for from_agent_id in agent_ids:
            outbox_plan = ctx.agents.agent_outbox(from_agent_id) / plan_id
            for req_path in _discover_outbox_human_requests(outbox_plan):
                req = _archive_human_request(ctx, plan_id=plan_id, request_path=req_path)
                if not req:
                    continue
                if not ctx.agents.agent_root("agent_human_gateway").exists():
                    _alert(
                        ctx,
                        plan_id=plan_id,
                        alert_type="HUMAN_GATEWAY_AGENT_MISSING",
                        message="agent_human_gateway not found; cannot deliver human requests",
                        details={"file": req_path.name},
                    )
                    continue
                dst = ctx.agents.agent_inbox("agent_human_gateway") / plan_id / req_path.name
                if not dst.exists():
                    atomic_copy(req_path, dst)

        # Responses: agent_human_gateway outbox -> target agent inbox as injected artifact envelopes
        gw_outbox_plan = ctx.agents.agent_outbox("agent_human_gateway") / plan_id
        processed_marker_dir = paths["human_responses"] / ".processed"
        processed_marker_dir.mkdir(parents=True, exist_ok=True)
        for resp_path in _discover_outbox_human_responses(gw_outbox_plan):
            resp = _archive_human_response(ctx, plan_id=plan_id, response_path=resp_path)
            if not resp:
                continue
            request_id = str(resp.get("request_id") or "")
            if not request_id:
                continue
            marker = processed_marker_dir / f"{request_id}.json"
            if marker.exists():
                continue

            decision = str(resp.get("decision") or "")
            provided_files = resp.get("provided_files") or []
            if decision != "PROVIDE" or not isinstance(provided_files, list) or not provided_files:
                atomic_write_json(marker, {"schema_version": "1.0", "plan_id": plan_id, "request_id": request_id, "processed_at": _iso_z(datetime.now(timezone.utc))})
                continue

            ok = True
            for f in provided_files:
                if not isinstance(f, dict):
                    ok = False
                    break
                file_name = str(f.get("name") or "")
                target = str(f.get("deliver_to_agent_id") or "")
                if not file_name or not target:
                    ok = False
                    _deadletter(
                        ctx,
                        plan_id=plan_id,
                        reason_code="HUMAN_RESPONSE_MISSING_DELIVER_TO",
                        reason="provided_files[] must include name and deliver_to_agent_id",
                        original_file=resp_path.name,
                        message_id=None,
                        producer_agent_id="agent_human_gateway",
                    )
                    _alert(
                        ctx,
                        plan_id=plan_id,
                        alert_type="HUMAN_RESPONSE_MISSING_DELIVER_TO",
                        message="provided_files[] must include name and deliver_to_agent_id",
                        details={"file": resp_path.name},
                    )
                    continue
                try:
                    _deliver_human_provided_file(
                        ctx,
                        plan_id=plan_id,
                        request_id=request_id,
                        human_gateway_outbox_plan=gw_outbox_plan,
                        target_agent_id=target,
                        file_name=file_name,
                        log=log,
                        delivered=delivered,
                    )
                except RouterError as e:
                    ok = False
                    _deadletter(
                        ctx,
                        plan_id=plan_id,
                        reason_code=e.code,
                        reason=str(e),
                        original_file=resp_path.name,
                        message_id=None,
                        producer_agent_id="agent_human_gateway",
                    )
                    _alert(ctx, plan_id=plan_id, alert_type=e.code, message=str(e), details={"file": resp_path.name})
                except Exception as e:
                    ok = False
                    _deadletter(
                        ctx,
                        plan_id=plan_id,
                        reason_code="UNHANDLED_EXCEPTION",
                        reason=str(e),
                        original_file=resp_path.name,
                        message_id=None,
                        producer_agent_id="agent_human_gateway",
                    )
                    _alert(
                        ctx,
                        plan_id=plan_id,
                        alert_type="UNHANDLED_EXCEPTION",
                        message=str(e),
                        details={"file": resp_path.name},
                    )

            if ok:
                atomic_write_json(marker, {"schema_version": "1.0", "plan_id": plan_id, "request_id": request_id, "processed_at": _iso_z(datetime.now(timezone.utc))})

        # control-plane: decision records + release manifests (not routed by DAG)
        for from_agent_id in agent_ids:
            outbox_plan = ctx.agents.agent_outbox(from_agent_id) / plan_id
            for decision_path in _discover_outbox_decision_records(outbox_plan):
                _archive_decision_record(ctx, plan_id=plan_id, decision_path=decision_path)
            for manifest_path in _discover_outbox_release_manifests(outbox_plan):
                _archive_release_manifest(ctx, plan_id=plan_id, manifest_path=manifest_path)
        _refresh_latest_release_manifest(ctx, plan_id=plan_id)

        # archive ACKs (control-plane collection; not routed by DAG)
        for from_agent_id in agent_ids:
            outbox_plan = ctx.agents.agent_outbox(from_agent_id) / plan_id
            for ack in _discover_outbox_acks(outbox_plan):
                _archive_ack(ctx, plan_id=plan_id, ack_path=ack)
        try:
            dag, dag_sha = _load_current_dag(ctx, plan_id)
        except RouterError as e:
            _alert(ctx, plan_id=plan_id, alert_type=e.code, message=str(e))
            continue

        # Collect command envelopes for supersede comparisons within this tick (same task_id)
        cmd_candidates: dict[str, tuple[int, Path]] = {}
        cmd_all: list[tuple[str, int, Path]] = []
        for from_agent_id in agent_ids:
            outbox_plan = ctx.agents.agent_outbox(from_agent_id) / plan_id
            for env_path in _discover_outbox_envelopes(outbox_plan):
                try:
                    env = read_json(env_path)
                except Exception:
                    continue
                if env.get("type") != "command":
                    continue
                cmd = (env.get("payload") or {}).get("command") or {}
                if str((cmd.get("dag_ref") or {}).get("sha256")) != dag_sha:
                    continue
                try:
                    task_id = str(cmd.get("task_id"))
                    seq = int(cmd.get("command_seq"))
                except Exception:
                    continue
                cmd_all.append((task_id, seq, env_path))
                cur = cmd_candidates.get(task_id)
                if cur is None or seq > cur[0]:
                    cmd_candidates[task_id] = (seq, env_path)

        for from_agent_id in agent_ids:
            outbox_plan = ctx.agents.agent_outbox(from_agent_id) / plan_id
            for env_path in _discover_outbox_envelopes(outbox_plan):
                try:
                    env_obj = read_json(env_path)
                    if env_obj.get("type") == "command":
                        cmd = (env_obj.get("payload") or {}).get("command") or {}
                        task_id = str(cmd.get("task_id"))
                        seq = int(cmd.get("command_seq"))
                        best = cmd_candidates.get(task_id)
                        if best and best[0] > seq:
                            _archive_command(ctx, plan_id, env_path, env_obj)
                            # skip early: superseded by newer in same tick
                            log.append(
                                _delivery_entry(
                                    plan_id=plan_id,
                                    message_id=str(env_obj.get("message_id")),
                                    envelope_sha=file_sha256(env_path),
                                    from_agent_id=from_agent_id,
                                    to_agent_id="*",
                                    status="SKIPPED_SUPERSEDED",
                                    skip_reason="SUPERSEDED_BY_NEWER_COMMAND",
                                    superseded=True,
                                    superseded_by={
                                        "message_id": str(read_json(best[1]).get("message_id")),
                                        "command_id": str(
                                            ((read_json(best[1]).get("payload") or {}).get("command") or {}).get("command_id")
                                        ),
                                        "command_seq": best[0],
                                    },
                                    task_id=task_id,
                                    command_id=str(cmd.get("command_id")),
                                )
                            )
                            continue
                except Exception:
                    pass

                try:
                    _deliver_one(
                        ctx,
                        dag=dag,
                        dag_sha=dag_sha,
                        plan_id=plan_id,
                        from_agent_id=from_agent_id,
                        envelope_path=env_path,
                        delivered=delivered,
                    )
                except RouterError as e:
                    # Best-effort extraction for deadletter triage.
                    try:
                        env_obj = read_json(env_path)
                        message_id = str(env_obj.get("message_id") or env_path.stem)
                        producer_agent_id = str(env_obj.get("producer_agent_id") or from_agent_id)
                    except Exception:
                        message_id = env_path.stem
                        producer_agent_id = from_agent_id

                    _deadletter(
                        ctx,
                        plan_id=plan_id,
                        reason_code=e.code,
                        reason=str(e),
                        original_file=env_path.name,
                        message_id=message_id,
                        producer_agent_id=producer_agent_id,
                    )
                    _alert(ctx, plan_id=plan_id, alert_type=e.code, message=str(e), details={"file": env_path.name})

                    # Write a delivery log record for traceability even when deadlettered.
                    log.append(
                        _delivery_entry(
                            plan_id=plan_id,
                            message_id=message_id,
                            envelope_sha=file_sha256(env_path),
                            from_agent_id=from_agent_id,
                            to_agent_id="*",
                            status="DEADLETTERED",
                            skip_reason=None,
                            task_id=None,
                            command_id=None,
                            output_name=None,
                            error={"code": e.code, "message": str(e), "file": env_path.name},
                        )
                    )
                except Exception as e:
                    _deadletter(
                        ctx,
                        plan_id=plan_id,
                        reason_code="UNHANDLED_EXCEPTION",
                        reason=str(e),
                        original_file=env_path.name,
                        message_id=env_path.stem,
                        producer_agent_id=from_agent_id,
                    )
                    _alert(
                        ctx,
                        plan_id=plan_id,
                        alert_type="UNHANDLED_EXCEPTION",
                        message=str(e),
                        details={"file": env_path.name},
                    )


def run_once(ctx: RouterContext) -> None:
    tick(ctx)


def run_forever(*, agents_root: Path, system_runtime: Path, schemas_base_dir: Path) -> None:
    ctx = RouterContext(
        agents=AgentsPaths(agents_root=agents_root),
        system=SystemPaths(system_runtime=system_runtime),
        schemas=SchemaRegistry(schemas_base_dir=schemas_base_dir),
        config=RouterConfig(),
    )
    while True:
        tick(ctx)
        time.sleep(ctx.config.poll_interval_seconds)
