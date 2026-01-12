from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Envelope:
    raw: dict

    @property
    def schema_version(self) -> str:
        return str(self.raw["schema_version"])

    @property
    def message_id(self) -> str:
        return str(self.raw["message_id"])

    @property
    def plan_id(self) -> str:
        return str(self.raw["plan_id"])

    @property
    def producer_agent_id(self) -> str:
        return str(self.raw["producer_agent_id"])

    @property
    def type(self) -> str:
        return str(self.raw["type"])

    @property
    def created_at(self) -> str:
        return str(self.raw["created_at"])

    @property
    def task_id(self) -> str | None:
        return self.raw.get("task_id")

    @property
    def output_name(self) -> str | None:
        return self.raw.get("output_name")

    @property
    def command_id(self) -> str | None:
        return self.raw.get("command_id")

    @property
    def payload(self) -> dict:
        return self.raw["payload"]

    @property
    def payload_files(self) -> list[dict]:
        files = self.payload.get("files")
        return [] if files is None else list(files)

    @property
    def payload_command(self) -> dict | None:
        cmd = self.payload.get("command")
        return None if cmd is None else dict(cmd)


@dataclass(frozen=True)
class Command:
    raw: dict

    @property
    def plan_id(self) -> str:
        return str(self.raw["plan_id"])

    @property
    def task_id(self) -> str:
        return str(self.raw["task_id"])

    @property
    def command_id(self) -> str:
        return str(self.raw["command_id"])

    @property
    def command_seq(self) -> int:
        return int(self.raw["command_seq"])

    @property
    def wait_for_inputs(self) -> bool:
        return bool(self.raw["wait_for_inputs"])

    @property
    def timeout(self) -> int:
        return int(self.raw["timeout"])

    @property
    def required_inputs(self) -> list[str]:
        return list(self.raw.get("required_inputs", []))

    @property
    def resolved_inputs(self) -> list[dict] | None:
        ri = self.raw.get("resolved_inputs")
        return None if ri is None else list(ri)


def as_envelope(obj: dict) -> Envelope:
    return Envelope(raw=obj)


def as_command(obj: dict) -> Command:
    return Command(raw=obj)


def deep_get(obj: dict, *keys: str, default: Any = None) -> Any:
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

