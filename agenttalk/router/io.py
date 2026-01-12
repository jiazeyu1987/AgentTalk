from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


def file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, obj: object) -> None:
    atomic_write_bytes(path, json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, tmp)
    tmp.replace(dst)


@dataclass(frozen=True)
class SystemPaths:
    system_runtime: Path

    @property
    def plans(self) -> Path:
        return self.system_runtime / "plans"

    @property
    def deadletter(self) -> Path:
        return self.system_runtime / "deadletter"

    @property
    def alerts(self) -> Path:
        return self.system_runtime / "alerts"


@dataclass(frozen=True)
class AgentsPaths:
    agents_root: Path

    def agent_root(self, agent_id: str) -> Path:
        return self.agents_root / agent_id

    def agent_outbox(self, agent_id: str) -> Path:
        return self.agent_root(agent_id) / "outbox"

    def agent_inbox(self, agent_id: str) -> Path:
        return self.agent_root(agent_id) / "inbox"

