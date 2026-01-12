from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io import read_json
from .schema import SchemaRegistry


@dataclass(frozen=True)
class HeartbeatConfig:
    schema_version: str
    agent_id: str
    poll_interval_seconds: int
    max_new_messages_per_tick: int
    max_resume_messages_per_tick: int
    scan_mode: str
    allowlist: list[str] | None
    schema_validation_enabled: bool
    schemas_base_dir: Path


def load_config(config_path: Path, schemas_base_dir: Path) -> HeartbeatConfig:
    raw = read_json(config_path)
    reg = SchemaRegistry(schemas_base_dir=schemas_base_dir)
    reg.validate(raw, "heartbeat_config.schema.json")

    plans = raw.get("plans") or {}
    scan_mode = plans.get("scan_mode") or "auto"
    allowlist = plans.get("allowlist")

    schema_validation = raw.get("schema_validation") or {}
    enabled = schema_validation.get("enabled", True)
    base_dir = schema_validation.get("schemas_base_dir")
    if isinstance(base_dir, str) and base_dir.strip():
        schemas_base_dir = (config_path.parent / base_dir).resolve()

    return HeartbeatConfig(
        schema_version=str(raw["schema_version"]),
        agent_id=str(raw["agent_id"]),
        poll_interval_seconds=int(raw["poll_interval_seconds"]),
        max_new_messages_per_tick=int(raw.get("max_new_messages_per_tick", 50)),
        max_resume_messages_per_tick=int(raw.get("max_resume_messages_per_tick", 10)),
        scan_mode=str(scan_mode),
        allowlist=list(allowlist) if isinstance(allowlist, list) else None,
        schema_validation_enabled=bool(enabled),
        schemas_base_dir=schemas_base_dir,
    )

