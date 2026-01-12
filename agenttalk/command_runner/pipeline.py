from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from agenttalk.heartbeat.io import atomic_write_bytes, atomic_write_json, safe_relpath

from .types import ProducedArtifact


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_message_id(now: datetime) -> str:
    return f"msg_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


@dataclass(frozen=True)
class ArtifactWriteResult:
    envelope_path: Path
    message_id: str


def write_artifacts_to_outbox(
    *,
    outbox_plan_dir: Path,
    producer_agent_id: str,
    plan_id: str,
    task_id: str,
    command_id: str,
    artifacts: list[ProducedArtifact],
    now: datetime | None = None,
) -> list[ArtifactWriteResult]:
    outbox_plan_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    results: list[ArtifactWriteResult] = []
    for artifact in artifacts:
        message_id = _new_message_id(now)
        payload_files: list[dict] = []
        for f in artifact.files:
            rel = safe_relpath(f.path)
            dst = outbox_plan_dir / rel
            atomic_write_bytes(dst, f.content)
            payload_files.append(
                {
                    "path": str(rel).replace("\\", "/"),
                    "sha256": _sha256_bytes(f.content),
                    "content_type": f.content_type,
                    "size_bytes": len(f.content),
                }
            )
        envelope = {
            "schema_version": "1.0",
            "message_id": message_id,
            "plan_id": plan_id,
            "producer_agent_id": producer_agent_id,
            "type": "artifact",
            "subtype": artifact.subtype,
            "created_at": _iso_z(now),
            "task_id": task_id,
            "output_name": artifact.output_name,
            "command_id": command_id,
            "payload": {"files": payload_files},
            "correlation": {"parent_command_id": command_id},
            "notes": artifact.notes,
        }
        envelope_name = f"artifact_{task_id}_{artifact.output_name}_{message_id}.msg.json"
        envelope_path = outbox_plan_dir / envelope_name
        atomic_write_json(envelope_path, envelope)
        results.append(ArtifactWriteResult(envelope_path=envelope_path, message_id=message_id))
    return results

