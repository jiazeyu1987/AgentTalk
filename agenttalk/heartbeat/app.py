from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import HeartbeatConfig, load_config
from .errors import EnvelopeParseError, UnsafePath
from .handlers import CommandHandler, DefaultCommandHandler
from .ids import IdGenerator
from .io import (
    AgentPaths,
    atomic_copy,
    atomic_move,
    atomic_rename,
    atomic_write_json,
    file_sha256,
    list_ready_envelopes,
    read_json,
    safe_relpath,
)
from .model import as_command, as_envelope
from .schema import SchemaRegistry
from .state import (
    InputIndexEntryFile,
    build_input_lookup,
    read_ack_status,
    read_task_state,
    task_state_path,
    update_input_index,
    write_ack,
    write_task_state,
)
from .timeutil import Clock, iso_z

from agenttalk.command_runner.pipeline import write_artifacts_to_outbox
from agenttalk.command_runner.types import artifacts_from_details


@dataclass(frozen=True)
class AppContext:
    agent_paths: AgentPaths
    config: HeartbeatConfig
    schema_registry: SchemaRegistry
    clock: Clock
    ids: IdGenerator
    handler: CommandHandler


def load_handler(handler_module: str | None) -> CommandHandler:
    if not handler_module:
        return DefaultCommandHandler()
    mod = importlib.import_module(handler_module)
    handler = getattr(mod, "handler", None)
    if handler is None:
        raise RuntimeError(f"handler module must expose `handler`: {handler_module}")
    return handler


def _write_alert(
    ctx: AppContext,
    *,
    plan_id: str,
    alert_type: str,
    severity: str,
    message: str,
    source: dict | None = None,
    details: dict | None = None,
) -> None:
    now = ctx.clock.now()
    alert_id = ctx.ids.new_alert_id(now)
    outbox_plan = ctx.agent_paths.outbox / plan_id
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "alert_id": alert_id,
        "plan_id": plan_id,
        "severity": severity,
        "type": alert_type,
        "created_at": iso_z(now),
        "source": source,
        "message": message,
        "details": details,
    }
    atomic_write_json(outbox_plan / f"alert_{alert_id}.json", payload)


def _write_human_request(
    ctx: AppContext,
    *,
    plan_id: str,
    task_id: str,
    command_id: str,
    missing_files: list[dict],
    severity: str = "HIGH",
    request_type: str = "MISSING_FILE",
    title: str | None = None,
    blocking: dict | None = None,
    context_refs: list[dict] | None = None,
) -> str:
    now = ctx.clock.now()
    request_id = ctx.ids.new_human_request_id(now)
    outbox_plan = ctx.agent_paths.outbox / plan_id
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "request_id": request_id,
        "plan_id": plan_id,
        "created_at": iso_z(now),
        "created_by": {"agent_id": ctx.config.agent_id, "task_id": task_id, "command_id": command_id},
        "severity": severity,
        "type": request_type,
        "title": title,
        "blocking": blocking,
        "needed": {"files": missing_files},
        "deadline": None,
        "context_refs": context_refs,
    }
    atomic_write_json(outbox_plan / f"human_intervention_request_{request_id}.json", payload)
    return request_id


def _write_status_heartbeat(ctx: AppContext, *, current_plan_ids: list[str]) -> None:
    now = ctx.clock.now()
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "agent_id": ctx.config.agent_id,
        "last_heartbeat": iso_z(now),
        "health": "HEALTHY",
        "status": "RUNNING",
        "uptime_seconds": None,
        "current_plan_ids": current_plan_ids,
        "current_task_ids": None,
        "resource_usage": None,
        "last_error": None,
    }
    atomic_write_json(ctx.agent_paths.status_heartbeat, payload)


def _parse_envelope(path: Path) -> dict:
    try:
        return read_json(path)
    except Exception as e:
        raise EnvelopeParseError(code="ENVELOPE_PARSE_ERROR", message=str(e)) from e


def _finalize_payloads(ctx: AppContext, *, inbox_plan: Path, processed_payload_dir: Path, envelope: dict) -> None:
    message_id = str(envelope["message_id"])
    files = (envelope.get("payload") or {}).get("files") or []
    for f in files:
        rel = safe_relpath(str(f["path"]))
        src = inbox_plan / rel
        if not src.exists():
            continue
        dst = processed_payload_dir / message_id / rel
        expected_sha = str(f.get("sha256") or "")
        if dst.exists():
            if expected_sha and file_sha256(dst) == expected_sha:
                continue
            if expected_sha and file_sha256(dst) == file_sha256(src):
                continue
            _write_alert(
                ctx,
                plan_id=str(envelope["plan_id"]),
                alert_type="PAYLOAD_FINALIZE_CONFLICT",
                severity="HIGH",
                message="payload finalize conflict: same path different sha256",
                source={"message_id": message_id},
                details={"path": str(rel)},
            )
            conflict_dst = inbox_plan / ".deadletter" / "_payload_conflict" / message_id / rel
            conflict_dst.parent.mkdir(parents=True, exist_ok=True)
            atomic_move(src, conflict_dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        atomic_move(src, dst)


def _ingest_artifact(ctx: AppContext, *, plan_id: str, envelope_path: Path, envelope: dict) -> bool:
    outbox_plan = ctx.agent_paths.outbox / plan_id
    inbox_plan = ctx.agent_paths.inbox / plan_id
    workspace_plan = ctx.agent_paths.workspace / plan_id
    workspace_inputs = workspace_plan / "inputs"

    task_id = str(envelope.get("task_id") or "")
    output_name = str(envelope.get("output_name") or "")
    if not task_id or not output_name:
        raise EnvelopeParseError(code="ENVELOPE_INVALID", message="artifact must include task_id/output_name")

    files_meta = (envelope.get("payload") or {}).get("files") or []
    stored_files: list[InputIndexEntryFile] = []
    now = ctx.clock.now()
    for f in files_meta:
        rel = safe_relpath(str(f["path"]))
        expected_sha = str(f["sha256"])
        src = inbox_plan / rel
        if not src.exists():
            raise EnvelopeParseError(code="MISSING_PAYLOAD", message=f"missing payload file: {rel}")
        dst = workspace_inputs / task_id / output_name / rel
        if dst.exists():
            if file_sha256(dst) != expected_sha:
                atomic_move(envelope_path, inbox_plan / ".deadletter" / envelope_path.name)
                _write_alert(
                    ctx,
                    plan_id=plan_id,
                    alert_type="INPUT_CONFLICT",
                    severity="HIGH",
                    message="input conflict: same path different sha256",
                    source={"task_id": task_id, "output_name": output_name, "message_id": envelope["message_id"]},
                    details={"path": str(rel), "expected": expected_sha, "actual": file_sha256(dst)},
                )
                return False
        else:
            atomic_copy(src, dst)
        stored_files.append(
            InputIndexEntryFile(path=str(rel), sha256=expected_sha, stored_at=str(dst.as_posix()))
        )

    update_input_index(
        workspace_inputs,
        plan_id=plan_id,
        agent_id=ctx.config.agent_id,
        message_id=str(envelope["message_id"]),
        task_id=task_id,
        output_name=output_name,
        received_at=iso_z(now),
        files=stored_files,
        updated_at=iso_z(now),
    )
    write_ack(
        outbox_plan,
        plan_id=plan_id,
        message_id=str(envelope["message_id"]),
        consumer_agent_id=ctx.config.agent_id,
        status="SUCCEEDED",
        consumed_at=iso_z(now),
        finished_at=iso_z(now),
        task_id=task_id,
        command_id=None,
        command_seq=None,
        result={"ok": True, "details": {"ingested_files": [f.path for f in stored_files]}},
    )

    processed_payload_dir = inbox_plan / ".processed" / "_payload"
    _finalize_payloads(ctx, inbox_plan=inbox_plan, processed_payload_dir=processed_payload_dir, envelope=envelope)
    return True


def _missing_inputs_for_command(ctx: AppContext, *, plan_id: str, command: dict) -> list[dict]:
    workspace_plan = ctx.agent_paths.workspace / plan_id
    workspace_inputs = workspace_plan / "inputs"
    task_workdir = workspace_plan / "tasks" / str(command.get("task_id"))

    lookup = build_input_lookup(workspace_inputs)

    def exists_path(p: str) -> bool:
        if p in lookup:
            return Path(lookup[p]).exists()
        direct = workspace_inputs / safe_relpath(p)
        if direct.exists():
            return True
        task_local = task_workdir / safe_relpath(p)
        return task_local.exists()

    missing: list[dict] = []
    resolved_inputs = command.get("resolved_inputs")
    if isinstance(resolved_inputs, list):
        for item in resolved_inputs:
            if not isinstance(item, dict):
                continue
            if not item.get("required", False):
                continue
            paths = item.get("paths") or []
            if not isinstance(paths, list) or not paths:
                continue
            if any(exists_path(str(p)) for p in paths):
                continue
            name = str(paths[0])
            desc = item.get("description") or f"Required input: {item.get('input_name')}"
            sens = item.get("sensitivity") or "UNKNOWN"
            missing.append({"name": name, "description": desc, "sensitivity": sens})
        return missing

    required_inputs = command.get("required_inputs") or []
    if isinstance(required_inputs, list):
        for p in required_inputs:
            if not exists_path(str(p)):
                missing.append({"name": str(p), "description": "Required input file", "sensitivity": "UNKNOWN"})
    return missing


def _execute_command(ctx: AppContext, *, plan_id: str, envelope_path: Path, envelope: dict) -> None:
    outbox_plan = ctx.agent_paths.outbox / plan_id
    now = ctx.clock.now()
    cmd_raw = envelope.get("payload", {}).get("command")
    if not isinstance(cmd_raw, dict):
        raise EnvelopeParseError(code="ENVELOPE_INVALID", message="command envelope missing payload.command")
    command = cmd_raw

    task_id = str(command.get("task_id"))
    command_id = str(command.get("command_id"))
    command_seq = int(command.get("command_seq"))

    missing_files = _missing_inputs_for_command(ctx, plan_id=plan_id, command=command)
    if missing_files and bool(command.get("wait_for_inputs", False)):
        existing_task_state_path = task_state_path(outbox_plan, task_id)
        existing = read_task_state(outbox_plan, task_id)
        if existing and existing.get("state") == "BLOCKED_WAITING_HUMAN":
            return
        started_at: str | None = None
        if isinstance(existing, dict):
            started_at = (existing.get("blocking") or {}).get("started_at")

        if not started_at:
            fallback_started_at = envelope.get("created_at") or iso_z(now)
            started_at = str(fallback_started_at)
            if existing_task_state_path.exists() and existing is None:
                _write_alert(
                    ctx,
                    plan_id=plan_id,
                    alert_type="TASK_STATE_CORRUPT_FALLBACK",
                    severity="HIGH",
                    message="task_state is missing or corrupted; falling back to envelope.created_at for started_at",
                    source={"task_id": task_id, "command_id": command_id, "message_id": envelope.get("message_id")},
                )

        write_task_state(
            outbox_plan,
            plan_id=plan_id,
            task_id=task_id,
            agent_id=ctx.config.agent_id,
            state="BLOCKED_WAITING_INPUT",
            updated_at=iso_z(now),
            message_id=str(envelope["message_id"]),
            command_id=command_id,
            command_seq=command_seq,
            blocking={"reason": "MISSING_INPUTS", "missing": missing_files, "started_at": started_at},
        )

        state = read_task_state(outbox_plan, task_id)
        started_at = (state.get("blocking") or {}).get("started_at") if isinstance(state, dict) else started_at
        try:
            started_dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            waited = (now - started_dt).total_seconds()
        except Exception:
            waited = 0

        if waited >= int(command.get("timeout", 0)):
            request_id = _write_human_request(
                ctx,
                plan_id=plan_id,
                task_id=task_id,
                command_id=command_id,
                missing_files=missing_files,
                blocking={"status": "BLOCKED_WAITING_HUMAN", "reason": "WAIT_FOR_INPUTS_TIMEOUT"},
            )
            write_task_state(
                outbox_plan,
                plan_id=plan_id,
                task_id=task_id,
                agent_id=ctx.config.agent_id,
                state="BLOCKED_WAITING_HUMAN",
                updated_at=iso_z(now),
                message_id=str(envelope["message_id"]),
                command_id=command_id,
                command_seq=command_seq,
                blocking={"reason": "WAIT_FOR_INPUTS_TIMEOUT", "request_id": request_id, "missing": missing_files},
            )
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type="WAIT_FOR_INPUTS_TIMEOUT",
                severity="HIGH",
                message="wait_for_inputs timeout",
                source={"task_id": task_id, "command_id": command_id, "message_id": envelope["message_id"]},
                details={"missing": missing_files},
            )
        return

    # start execution
    write_ack(
        outbox_plan,
        plan_id=plan_id,
        message_id=str(envelope["message_id"]),
        consumer_agent_id=ctx.config.agent_id,
        status="CONSUMED",
        consumed_at=iso_z(now),
        task_id=task_id,
        command_id=command_id,
        command_seq=command_seq,
        result=None,
    )
    write_task_state(
        outbox_plan,
        plan_id=plan_id,
        task_id=task_id,
        agent_id=ctx.config.agent_id,
        state="RUNNING",
        updated_at=iso_z(now),
        message_id=str(envelope["message_id"]),
        command_id=command_id,
        command_seq=command_seq,
    )

    result = ctx.handler.handle_command(envelope=envelope, command=command, context={"agent_id": ctx.config.agent_id})
    finished = ctx.clock.now()
    if result.ok:
        produced_artifacts = artifacts_from_details(result.details)
        if produced_artifacts:
            write_artifacts_to_outbox(
                outbox_plan_dir=outbox_plan,
                producer_agent_id=ctx.config.agent_id,
                plan_id=plan_id,
                task_id=task_id,
                command_id=command_id,
                artifacts=produced_artifacts,
                now=finished,
            )
            safe_details = dict(result.details or {})
            safe_details["artifacts"] = [
                {
                    "output_name": a.output_name,
                    "files": [{"path": f.path, "content_type": f.content_type} for f in a.files],
                }
                for a in produced_artifacts
            ]
        else:
            safe_details = result.details
        write_ack(
            outbox_plan,
            plan_id=plan_id,
            message_id=str(envelope["message_id"]),
            consumer_agent_id=ctx.config.agent_id,
            status="SUCCEEDED",
            consumed_at=iso_z(now),
            finished_at=iso_z(finished),
            task_id=task_id,
            command_id=command_id,
            command_seq=command_seq,
            result={"ok": True, "details": safe_details},
        )
        write_task_state(
            outbox_plan,
            plan_id=plan_id,
            task_id=task_id,
            agent_id=ctx.config.agent_id,
            state="COMPLETED",
            updated_at=iso_z(finished),
            message_id=str(envelope["message_id"]),
            command_id=command_id,
            command_seq=command_seq,
            result={"ok": True, "details": safe_details},
        )
    else:
        write_ack(
            outbox_plan,
            plan_id=plan_id,
            message_id=str(envelope["message_id"]),
            consumer_agent_id=ctx.config.agent_id,
            status="FAILED",
            consumed_at=iso_z(now),
            finished_at=iso_z(finished),
            task_id=task_id,
            command_id=command_id,
            command_seq=command_seq,
            result={"ok": False, "details": result.details},
        )
        write_task_state(
            outbox_plan,
            plan_id=plan_id,
            task_id=task_id,
            agent_id=ctx.config.agent_id,
            state="FAILED",
            updated_at=iso_z(finished),
            message_id=str(envelope["message_id"]),
            command_id=command_id,
            command_seq=command_seq,
            result={"ok": False, "details": result.details},
        )


def _move_to_processed(inbox_plan: Path, pending_path: Path) -> None:
    processed = inbox_plan / ".processed" / pending_path.name
    atomic_move(pending_path, processed)


def _process_one_envelope(ctx: AppContext, *, plan_id: str, src_path: Path) -> None:
    inbox_plan = ctx.agent_paths.inbox / plan_id
    pending_dir = inbox_plan / ".pending"
    outbox_plan = ctx.agent_paths.outbox / plan_id

    claimed = pending_dir / src_path.name
    atomic_move(src_path, claimed)
    try:
        env = _parse_envelope(claimed)
        if ctx.config.schema_validation_enabled:
            ctx.schema_registry.validate(env, "message_envelope.schema.json")
            if env.get("type") == "command":
                ctx.schema_registry.validate(env["payload"]["command"], "command.schema.json")
    except Exception as e:
        atomic_move(claimed, inbox_plan / ".deadletter" / claimed.name)
        _write_alert(
            ctx,
            plan_id=plan_id,
            alert_type=getattr(e, "code", "SCHEMA_INVALID"),
            severity="HIGH",
            message=str(e),
            source={"file": src_path.name},
        )
        return

    envelope = as_envelope(env)
    renamed = pending_dir / f"{envelope.message_id}__{claimed.name}"
    if renamed.exists():
        status = read_ack_status(outbox_plan, envelope.message_id)
        if status in ("SUCCEEDED", "FAILED"):
            _move_to_processed(inbox_plan, claimed)
            return
        suffix = 1
        while True:
            candidate = pending_dir / f"{envelope.message_id}__{claimed.name}__dup_{suffix}"
            if not candidate.exists():
                renamed = candidate
                break
            suffix += 1
    atomic_rename(claimed, renamed)

    ack_status = read_ack_status(outbox_plan, envelope.message_id)
    if ack_status in ("SUCCEEDED", "FAILED"):
        _move_to_processed(inbox_plan, renamed)
        return

    if envelope.type == "artifact":
        try:
            ok = _ingest_artifact(ctx, plan_id=plan_id, envelope_path=renamed, envelope=envelope.raw)
        except (EnvelopeParseError, UnsafePath) as e:
            atomic_move(renamed, inbox_plan / ".deadletter" / renamed.name)
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type=getattr(e, "code", "ERROR"),
                severity="HIGH",
                message=str(e),
                source={"file": renamed.name},
            )
            return
        if ok:
            _move_to_processed(inbox_plan, renamed)
        return

    if envelope.type == "command":
        try:
            _execute_command(ctx, plan_id=plan_id, envelope_path=renamed, envelope=envelope.raw)
        except (EnvelopeParseError, UnsafePath) as e:
            atomic_move(renamed, inbox_plan / ".deadletter" / renamed.name)
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type=getattr(e, "code", "ERROR"),
                severity="HIGH",
                message=str(e),
                source={"file": renamed.name},
            )
            return
        # only move when terminal ack exists
        ack_status2 = read_ack_status(outbox_plan, envelope.message_id)
        if ack_status2 in ("SUCCEEDED", "FAILED"):
            _move_to_processed(inbox_plan, renamed)
        return

    # unknown
    atomic_move(renamed, inbox_plan / ".deadletter" / renamed.name)
    _write_alert(
        ctx,
        plan_id=plan_id,
        alert_type="UNKNOWN_MESSAGE_TYPE",
        severity="MEDIUM",
        message="unknown envelope type",
        source={"message_id": envelope.message_id},
        details={"type": envelope.type},
    )


def _resume_pending(ctx: AppContext, *, plan_id: str) -> None:
    inbox_plan = ctx.agent_paths.inbox / plan_id
    pending_dir = inbox_plan / ".pending"
    outbox_plan = ctx.agent_paths.outbox / plan_id
    if not pending_dir.exists():
        return
    count = 0
    for p in sorted(pending_dir.iterdir(), key=lambda x: x.name):
        if count >= ctx.config.max_resume_messages_per_tick:
            break
        if not p.is_file() or not p.name.endswith(".msg.json"):
            continue
        env = _parse_envelope(p)
        message_id = str(env.get("message_id") or "")
        if not message_id:
            continue
        ack_status = read_ack_status(outbox_plan, message_id)
        if ack_status in ("SUCCEEDED", "FAILED"):
            _move_to_processed(inbox_plan, p)
            continue
        if str(env.get("type")) == "command":
            _execute_command(ctx, plan_id=plan_id, envelope_path=p, envelope=env)
            ack_status2 = read_ack_status(outbox_plan, message_id)
            if ack_status2 in ("SUCCEEDED", "FAILED"):
                _move_to_processed(inbox_plan, p)
        count += 1


def tick_plan(ctx: AppContext, plan_id: str) -> None:
    inbox_plan = ctx.agent_paths.inbox / plan_id
    outbox_plan = ctx.agent_paths.outbox / plan_id
    outbox_plan.mkdir(parents=True, exist_ok=True)
    (inbox_plan / ".pending").mkdir(parents=True, exist_ok=True)
    (inbox_plan / ".processed").mkdir(parents=True, exist_ok=True)
    (inbox_plan / ".deadletter").mkdir(parents=True, exist_ok=True)

    processed = 0
    for env_path in list_ready_envelopes(inbox_plan):
        if processed >= ctx.config.max_new_messages_per_tick:
            break
        try:
            _process_one_envelope(ctx, plan_id=plan_id, src_path=env_path)
        except (EnvelopeParseError, UnsafePath) as e:
            atomic_move(env_path, inbox_plan / ".deadletter" / env_path.name)
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type=getattr(e, "code", "ERROR"),
                severity="HIGH",
                message=str(e),
                source={"file": env_path.name},
            )
        processed += 1

    _resume_pending(ctx, plan_id=plan_id)


def discover_plans(ctx: AppContext) -> list[str]:
    inbox = ctx.agent_paths.inbox
    if ctx.config.scan_mode == "allowlist_only":
        return list(ctx.config.allowlist or [])
    if not inbox.exists():
        return []
    plans = [p.name for p in inbox.iterdir() if p.is_dir() and not p.name.startswith(".")]
    return sorted(plans)


def run_once(ctx: AppContext) -> list[str]:
    plans = discover_plans(ctx)
    _write_status_heartbeat(ctx, current_plan_ids=plans)
    for plan_id in plans:
        tick_plan(ctx, plan_id)
    return plans


def run_forever(
    *,
    agent_root: Path,
    schemas_base_dir: Path,
    handler_module: str | None = None,
    config_path: Path | None = None,
) -> None:
    agent_paths = AgentPaths(agent_root=agent_root)
    if config_path is None:
        config_path = agent_paths.heartbeat_config
    cfg = load_config(config_path, schemas_base_dir=schemas_base_dir)
    ctx = AppContext(
        agent_paths=agent_paths,
        config=cfg,
        schema_registry=SchemaRegistry(schemas_base_dir=cfg.schemas_base_dir),
        clock=Clock(),
        ids=IdGenerator(),
        handler=load_handler(handler_module),
    )
    while True:
        run_once(ctx)
        time.sleep(cfg.poll_interval_seconds)
