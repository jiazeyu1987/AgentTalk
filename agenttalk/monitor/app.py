from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agenttalk.heartbeat.schema import SchemaRegistry as _SchemaRegistry

from .io import atomic_write_json, file_sha256, read_json, read_jsonl


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_z(s: str) -> datetime | None:
    try:
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _write_alert(ctx: MonitorContext, *, plan_id: str, alert_type: str, message: str, details: dict | None = None) -> None:
    now = datetime.now(timezone.utc)
    alert_id = f"alert_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "alert_id": alert_id,
        "plan_id": plan_id,
        "severity": "HIGH",
        "type": alert_type,
        "created_at": _iso_z(now),
        "source": {"agent_id": "agent_system_monitor"},
        "message": message,
        "details": details,
    }
    atomic_write_json(ctx.system_runtime / "alerts" / plan_id / f"{alert_id}.json", payload)

def _list_agents(agents_root: Path) -> list[str]:
    if not agents_root.exists():
        return []
    return sorted([p.name for p in agents_root.iterdir() if p.is_dir() and not p.name.startswith(".")])


def collect_agent_statuses(ctx: MonitorContext) -> list[str]:
    """
    Collects agent self-reported status_heartbeat.json into system_runtime/agent_status/<agent_id>.json.
    This is the Dashboard's authoritative source (12/14).
    """
    out_dir = ctx.system_runtime / "agent_status"
    out_dir.mkdir(parents=True, exist_ok=True)
    collected: list[str] = []
    for agent_id in _list_agents(ctx.agents_root):
        src = ctx.agents_root / agent_id / "status_heartbeat.json"
        if not src.exists():
            continue
        try:
            obj = read_json(src)
            if ctx.config.schema_validation_enabled:
                ctx.schemas.validate(obj, "status_heartbeat.schema.json")
            if str(obj.get("agent_id") or "") and str(obj.get("agent_id")) != agent_id:
                continue
            obj = dict(obj)
            obj["collected_at"] = _iso_z(datetime.now(timezone.utc))
            atomic_write_json(out_dir / f"{agent_id}.json", obj)
            collected.append(agent_id)
        except Exception:
            continue
    return collected


@dataclass(frozen=True)
class MonitorConfig:
    poll_interval_seconds: int = 2
    schema_validation_enabled: bool = True


@dataclass(frozen=True)
class MonitorContext:
    agents_root: Path
    system_runtime: Path
    schemas: _SchemaRegistry
    config: MonitorConfig


def _list_plans(system_runtime: Path) -> list[str]:
    plans_dir = system_runtime / "plans"
    if not plans_dir.exists():
        return []
    return sorted([p.name for p in plans_dir.iterdir() if p.is_dir() and not p.name.startswith(".")])


def _load_current_dag(ctx: MonitorContext, plan_id: str) -> tuple[dict, str]:
    plan_dir = ctx.system_runtime / "plans" / plan_id
    dag_path = plan_dir / "task_dag.json"
    ref_path = plan_dir / "active_dag_ref.json"
    dag = read_json(dag_path)
    if ctx.config.schema_validation_enabled:
        ctx.schemas.validate(dag, "task_dag.schema.json")
    dag_sha = file_sha256(dag_path)
    if ref_path.exists():
        ref = read_json(ref_path)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(ref, "active_dag_ref.schema.json")
        if str(ref.get("task_dag_sha256")) != dag_sha:
            raise ValueError(f"active_dag_ref mismatch: {ref.get('task_dag_sha256')} != {dag_sha}")
    return dag, dag_sha


def _agent_outbox_task_state(ctx: MonitorContext, plan_id: str, agent_id: str, task_id: str) -> dict | None:
    p = ctx.agents_root / agent_id / "outbox" / plan_id / f"task_state_{task_id}.json"
    if not p.exists():
        return None
    try:
        obj = read_json(p)
        if ctx.config.schema_validation_enabled:
            ctx.schemas.validate(obj, "task_state.schema.json")
        return obj
    except Exception:
        return None


def _load_acks(ctx: MonitorContext, plan_id: str) -> dict[str, dict]:
    plan_dir = ctx.system_runtime / "plans" / plan_id
    acks_dir = plan_dir / "acks"
    acks: dict[str, dict] = {}
    if acks_dir.exists():
        for p in acks_dir.glob("ack_*.json"):
            try:
                obj = read_json(p)
                if ctx.config.schema_validation_enabled:
                    ctx.schemas.validate(obj, "ack.schema.json")
                acks[str(obj.get("message_id"))] = obj
            except Exception:
                continue
        return acks

    # fallback: scan agent outboxes
    if not ctx.agents_root.exists():
        return {}
    for agent_dir in ctx.agents_root.iterdir():
        if not agent_dir.is_dir():
            continue
        outbox_plan = agent_dir / "outbox" / plan_id
        if not outbox_plan.exists():
            continue
        for p in outbox_plan.glob("ack_*.json"):
            try:
                obj = read_json(p)
                if ctx.config.schema_validation_enabled:
                    ctx.schemas.validate(obj, "ack.schema.json")
                acks[str(obj.get("message_id"))] = obj
            except Exception:
                continue
    return acks


def _load_latest_commands(ctx: MonitorContext, plan_id: str, dag_sha: str) -> dict[str, dict]:
    plan_dir = ctx.system_runtime / "plans" / plan_id
    cmds_dir = plan_dir / "commands"
    latest: dict[str, dict] = {}
    if not cmds_dir.exists():
        return latest
    for p in cmds_dir.glob("*.msg.json"):
        try:
            env = read_json(p)
        except Exception:
            continue
        if env.get("type") != "command":
            continue
        cmd = (env.get("payload") or {}).get("command") or {}
        if str((cmd.get("dag_ref") or {}).get("sha256")) != dag_sha:
            continue
        task_id = str(cmd.get("task_id") or "")
        if not task_id:
            continue
        try:
            seq = int(cmd.get("command_seq"))
        except Exception:
            continue
        cur = latest.get(task_id)
        if cur is None or int(cur.get("command_seq", -1)) < seq:
            latest[task_id] = cmd
    return latest


def _map_messages_from_command_archive(
    ctx: MonitorContext,
    *,
    plan_id: str,
    dag_sha: str,
) -> tuple[dict[str, str], dict[str, dict]]:
    """
    Returns:
      - message_id -> task_id
      - message_id -> payload.command (for timeout, etc.)

    Consistency rule (08): envelope.task_id/command_id must match payload.command.task_id/command_id.
    If inconsistent, ignore that envelope for mapping and write an alert.
    """
    plan_dir = ctx.system_runtime / "plans" / plan_id
    cmds_dir = plan_dir / "commands"
    msg_to_task: dict[str, str] = {}
    msg_to_cmd: dict[str, dict] = {}
    if not cmds_dir.exists():
        return msg_to_task, msg_to_cmd

    for p in cmds_dir.glob("*.msg.json"):
        try:
            env = read_json(p)
        except Exception:
            continue
        if env.get("type") != "command":
            continue
        cmd = (env.get("payload") or {}).get("command") or {}
        if str((cmd.get("dag_ref") or {}).get("sha256")) != dag_sha:
            continue

        message_id = str(env.get("message_id") or "")
        env_task_id = str(env.get("task_id") or "")
        env_command_id = str(env.get("command_id") or "")
        cmd_task_id = str(cmd.get("task_id") or "")
        cmd_command_id = str(cmd.get("command_id") or "")
        if not message_id or not cmd_task_id:
            continue

        # If envelope has task/command ids, they must match payload.command.
        if env_task_id and env_task_id != cmd_task_id:
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type="COMMAND_ARCHIVE_INCONSISTENT",
                message="command envelope.task_id != payload.command.task_id",
                details={"file": p.name, "message_id": message_id, "envelope_task_id": env_task_id, "command_task_id": cmd_task_id},
            )
            continue
        if env_command_id and cmd_command_id and env_command_id != cmd_command_id:
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type="COMMAND_ARCHIVE_INCONSISTENT",
                message="command envelope.command_id != payload.command.command_id",
                details={
                    "file": p.name,
                    "message_id": message_id,
                    "envelope_command_id": env_command_id,
                    "command_command_id": cmd_command_id,
                },
            )
            continue

        msg_to_task[message_id] = cmd_task_id
        msg_to_cmd[message_id] = cmd

    return msg_to_task, msg_to_cmd


def _delivered_artifacts(deliveries: list[dict]) -> tuple[set[tuple[str, str]], list[dict]]:
    outputs: set[tuple[str, str]] = set()
    delivered_files: list[dict] = []
    for d in deliveries:
        if d.get("status") != "DELIVERED":
            continue
        task_id = d.get("task_id")
        output_name = d.get("output_name")
        if isinstance(task_id, str) and isinstance(output_name, str):
            outputs.add((task_id, output_name))
        payload = d.get("payload") or {}
        files = payload.get("files") or []
        for f in files:
            if isinstance(f, dict) and isinstance(f.get("path"), str):
                delivered_files.append(f)
    return outputs, delivered_files


def _inputs_satisfied(
    dag_node: dict,
    *,
    delivered_outputs: set[tuple[str, str]],
    delivered_files: list[dict],
) -> bool:
    inputs = dag_node.get("inputs")
    if isinstance(inputs, list) and inputs:
        for inp in inputs:
            if not isinstance(inp, dict):
                continue
            if not inp.get("required", False):
                continue
            selector = inp.get("selector") or {}
            stype = selector.get("type")
            if stype == "by_output_name":
                value = selector.get("value")
                if not any(o == value for _, o in delivered_outputs):
                    return False
            elif stype == "by_file_name":
                value = selector.get("value")
                if not any(f.get("path") == value for f in delivered_files):
                    return False
            elif stype == "by_glob":
                pat = selector.get("value")
                if not any(fnmatch.fnmatch(str(f.get("path")), str(pat)) for f in delivered_files):
                    return False
            else:
                return False
        return True

    required_inputs = dag_node.get("required_inputs")
    if isinstance(required_inputs, list) and required_inputs:
        for name in required_inputs:
            if not any(f.get("path") == name for f in delivered_files):
                return False
        return True
    return True


def _command_inputs_missing(cmd: dict, delivered_files: list[dict]) -> list[str]:
    def exists_path(p: str) -> bool:
        return any(f.get("path") == p for f in delivered_files)

    resolved = cmd.get("resolved_inputs")
    if isinstance(resolved, list):
        missing: list[str] = []
        for item in resolved:
            if not isinstance(item, dict) or not item.get("required", False):
                continue
            paths = item.get("paths") or []
            if not isinstance(paths, list) or not paths:
                continue
            if any(exists_path(str(p)) for p in paths):
                continue
            missing.append(str(paths[0]))
        return missing

    required_inputs = cmd.get("required_inputs") or []
    if isinstance(required_inputs, list):
        return [str(p) for p in required_inputs if not exists_path(str(p))]
    return []


def aggregate_plan_status(ctx: MonitorContext, plan_id: str) -> dict:
    plan_dir = ctx.system_runtime / "plans" / plan_id
    dag, dag_sha = _load_current_dag(ctx, plan_id)
    deliveries = read_jsonl(plan_dir / "deliveries.jsonl")
    acks = _load_acks(ctx, plan_id)
    commands = _load_latest_commands(ctx, plan_id, dag_sha)
    delivered_outputs, delivered_files = _delivered_artifacts(deliveries)

    # Map message_id -> task_id for commands using deliveries (preferred)
    msg_to_task: dict[str, str] = {}
    msg_to_cmd: dict[str, str] = {}
    for d in deliveries:
        if d.get("status") == "DELIVERED" and isinstance(d.get("message_id"), str) and isinstance(d.get("task_id"), str):
            msg_to_task[str(d["message_id"])] = str(d["task_id"])
            if isinstance(d.get("command_id"), str):
                msg_to_cmd[str(d["message_id"])] = str(d["command_id"])

    # Fallback mapping: command archive (only fill gaps)
    cmd_msg_to_task, cmd_msg_to_cmd = _map_messages_from_command_archive(ctx, plan_id=plan_id, dag_sha=dag_sha)
    for mid, tid in cmd_msg_to_task.items():
        msg_to_task.setdefault(mid, tid)

    tasks_out: list[dict] = []
    task_state_by_id: dict[str, str] = {}
    for node in dag.get("nodes", []):
        task_id = str(node.get("task_id"))
        assigned = str(node.get("assigned_agent_id"))

        # priority 1: task_state file
        ts = _agent_outbox_task_state(ctx, plan_id, assigned, task_id)
        if ts and isinstance(ts.get("state"), str):
            state = str(ts["state"])
            tasks_out.append(
                {
                    "task_id": task_id,
                    "assigned_agent_id": assigned,
                    "state": state,
                    "updated_at": ts.get("updated_at"),
                    "blocking": ts.get("blocking"),
                }
            )
            task_state_by_id[task_id] = state
            continue

        # priority 2: ACKs (command messages)
        # pick any ack mapped to this task_id; prefer terminal over consumed
        ack_for_task = None
        for mid, tid in msg_to_task.items():
            if tid != task_id:
                continue
            a = acks.get(mid)
            if not a:
                continue
            if ack_for_task is None:
                ack_for_task = a
            else:
                # prefer terminal
                if ack_for_task.get("status") == "CONSUMED" and a.get("status") in ("SUCCEEDED", "FAILED"):
                    ack_for_task = a
        if ack_for_task:
            s = str(ack_for_task.get("status"))
            if s == "SUCCEEDED":
                state = "COMPLETED"
            elif s == "FAILED":
                state = "FAILED"
            else:
                state = "RUNNING"
            blocking: dict | None = None
            if state == "RUNNING":
                consumed_at = ack_for_task.get("consumed_at")
                if isinstance(consumed_at, str):
                    consumed_dt = _parse_iso_z(consumed_at)
                else:
                    consumed_dt = None
                timeout_seconds = None
                # Try to find timeout from command archive for this message_id.
                for mid, tid in msg_to_task.items():
                    if tid != task_id:
                        continue
                    a = acks.get(mid)
                    if not a:
                        continue
                    if a is ack_for_task:
                        cmd_obj = cmd_msg_to_cmd.get(mid)
                        if cmd_obj and isinstance(cmd_obj.get("timeout"), int):
                            timeout_seconds = int(cmd_obj["timeout"])
                        break
                if consumed_dt and timeout_seconds is not None:
                    if datetime.now(timezone.utc) - consumed_dt > timedelta(seconds=timeout_seconds * 2):
                        blocking = {
                            "reason": "TIMEOUT",
                            "timeout_seconds": timeout_seconds,
                            "multiplier": 2,
                            "consumed_at": consumed_at,
                        }
                        _write_alert(
                            ctx,
                            plan_id=plan_id,
                            alert_type="COMMAND_ACK_TIMEOUT",
                            message="ack is CONSUMED for too long without terminal ack",
                            details={"task_id": task_id, "timeout_seconds": timeout_seconds, "consumed_at": consumed_at},
                        )
            tasks_out.append(
                {
                    "task_id": task_id,
                    "assigned_agent_id": assigned,
                    "state": state,
                    "updated_at": ack_for_task.get("finished_at") or ack_for_task.get("consumed_at"),
                    "blocking": blocking,
                }
            )
            task_state_by_id[task_id] = state
            continue

        # derive based on dag deps and inputs
        deps = [str(x) for x in (node.get("depends_on") or [])]
        deps_ok = all(task_state_by_id.get(d) == "COMPLETED" for d in deps)
        inputs_ok = _inputs_satisfied(node, delivered_outputs=delivered_outputs, delivered_files=delivered_files)

        # If a latest command exists and waits for inputs, we can mark blocked
        latest_cmd = commands.get(task_id)
        if latest_cmd and bool(latest_cmd.get("wait_for_inputs", False)):
            missing = _command_inputs_missing(latest_cmd, delivered_files)
            if missing:
                state = "BLOCKED_WAITING_INPUT"
                tasks_out.append(
                    {
                        "task_id": task_id,
                        "assigned_agent_id": assigned,
                        "state": state,
                        "updated_at": None,
                        "blocking": {"reason": "MISSING_INPUTS", "missing": missing},
                    }
                )
                task_state_by_id[task_id] = state
                continue

        if deps_ok and inputs_ok:
            state = "READY"
        else:
            state = "PENDING"
        tasks_out.append(
            {
                "task_id": task_id,
                "assigned_agent_id": assigned,
                "state": state,
                "updated_at": None,
                "blocking": None,
            }
        )
        task_state_by_id[task_id] = state

    blocked_summary: dict[str, int] = {"INPUT": 0, "REVIEW": 0, "HUMAN": 0}
    for t in tasks_out:
        s = t.get("state")
        if s == "BLOCKED_WAITING_INPUT":
            blocked_summary["INPUT"] += 1
        if s == "BLOCKED_WAITING_REVIEW":
            blocked_summary["REVIEW"] += 1
        if s == "BLOCKED_WAITING_HUMAN":
            blocked_summary["HUMAN"] += 1

    now = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "active_task_dag_sha256": dag_sha,
        "updated_at": _iso_z(now),
        "blocked_summary": blocked_summary,
        "tasks": tasks_out,
    }


def run_once(ctx: MonitorContext) -> list[str]:
    collect_agent_statuses(ctx)
    plans = _list_plans(ctx.system_runtime)
    for plan_id in plans:
        try:
            status = aggregate_plan_status(ctx, plan_id)
            if ctx.config.schema_validation_enabled:
                ctx.schemas.validate(status, "plan_status.schema.json")
            plan_dir = ctx.system_runtime / "plans" / plan_id
            atomic_write_json(plan_dir / "plan_status.json", status)
        except Exception as e:
            _write_alert(
                ctx,
                plan_id=plan_id,
                alert_type="PLAN_STATUS_AGGREGATION_FAILED",
                message=str(e),
                details=None,
            )
    return plans


def run_forever(*, agents_root: Path, system_runtime: Path, schemas_base_dir: Path) -> None:
    ctx = MonitorContext(
        agents_root=agents_root,
        system_runtime=system_runtime,
        schemas=_SchemaRegistry(schemas_base_dir=schemas_base_dir),
        config=MonitorConfig(),
    )
    while True:
        run_once(ctx)
        time.sleep(ctx.config.poll_interval_seconds)
