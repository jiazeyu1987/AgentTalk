from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import atomic_write_json, read_json
from .timeutil import iso_z


def ack_path(outbox_plan_dir: Path, message_id: str) -> Path:
    return outbox_plan_dir / f"ack_{message_id}.json"


def read_ack_status(outbox_plan_dir: Path, message_id: str) -> str | None:
    p = ack_path(outbox_plan_dir, message_id)
    if not p.exists():
        return None
    try:
        return str(read_json(p).get("status"))
    except Exception:
        return None


def write_ack(
    outbox_plan_dir: Path,
    *,
    schema_version: str = "1.0",
    plan_id: str,
    message_id: str,
    consumer_agent_id: str,
    status: str,
    consumed_at: str,
    task_id: str | None = None,
    command_id: str | None = None,
    command_seq: int | None = None,
    finished_at: str | None = None,
    result: dict | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "plan_id": plan_id,
        "message_id": message_id,
        "task_id": task_id,
        "command_id": command_id,
        "command_seq": command_seq,
        "consumer_agent_id": consumer_agent_id,
        "status": status,
        "consumed_at": consumed_at,
        "finished_at": finished_at,
        "result": result,
    }
    atomic_write_json(ack_path(outbox_plan_dir, message_id), payload)


def task_state_path(outbox_plan_dir: Path, task_id: str) -> Path:
    return outbox_plan_dir / f"task_state_{task_id}.json"


def read_task_state(outbox_plan_dir: Path, task_id: str) -> dict | None:
    p = task_state_path(outbox_plan_dir, task_id)
    if not p.exists():
        return None
    try:
        return read_json(p)
    except Exception:
        return None


def write_task_state(
    outbox_plan_dir: Path,
    *,
    plan_id: str,
    task_id: str,
    agent_id: str,
    state: str,
    updated_at: str,
    message_id: str | None = None,
    command_id: str | None = None,
    command_seq: int | None = None,
    blocking: dict | None = None,
    progress: dict | None = None,
    result: dict | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "task_id": task_id,
        "agent_id": agent_id,
        "state": state,
        "updated_at": updated_at,
        "message_id": message_id,
        "command_id": command_id,
        "command_seq": command_seq,
        "blocking": blocking,
        "progress": progress,
        "result": result,
    }
    atomic_write_json(task_state_path(outbox_plan_dir, task_id), payload)


@dataclass(frozen=True)
class InputIndexEntryFile:
    path: str
    sha256: str
    stored_at: str


def load_input_index(path: Path, *, plan_id: str, agent_id: str, updated_at: str) -> dict:
    if path.exists():
        try:
            return read_json(path)
        except Exception:
            pass
    return {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "agent_id": agent_id,
        "updated_at": updated_at,
        "entries": [],
    }


def update_input_index(
    workspace_plan_inputs_dir: Path,
    *,
    plan_id: str,
    agent_id: str,
    message_id: str,
    task_id: str,
    output_name: str,
    received_at: str,
    files: list[InputIndexEntryFile],
    updated_at: str,
) -> None:
    index_path = workspace_plan_inputs_dir / "input_index.json"
    idx = load_input_index(index_path, plan_id=plan_id, agent_id=agent_id, updated_at=updated_at)
    entries: list[dict] = list(idx.get("entries", []))
    if any(e.get("message_id") == message_id for e in entries):
        idx["updated_at"] = updated_at
        atomic_write_json(index_path, idx)
        return
    entries.append(
        {
            "message_id": message_id,
            "task_id": task_id,
            "output_name": output_name,
            "received_at": received_at,
            "files": [f.__dict__ for f in files],
        }
    )
    idx["entries"] = entries
    idx["updated_at"] = updated_at
    atomic_write_json(index_path, idx)


def build_input_lookup(workspace_plan_inputs_dir: Path) -> dict[str, str]:
    index_path = workspace_plan_inputs_dir / "input_index.json"
    if not index_path.exists():
        return {}
    try:
        idx = read_json(index_path)
        lookup: dict[str, str] = {}
        for e in idx.get("entries", []):
            for f in e.get("files", []) or []:
                p = f.get("path")
                stored_at = f.get("stored_at")
                if isinstance(p, str) and isinstance(stored_at, str):
                    lookup[p] = stored_at
        return lookup
    except Exception:
        return {}

