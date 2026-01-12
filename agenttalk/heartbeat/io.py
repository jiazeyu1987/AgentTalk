from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .errors import UnsafePath


def is_tmp(path: Path) -> bool:
    return path.name.endswith(".tmp")


def safe_relpath(rel: str) -> Path:
    rel_path = Path(rel)
    if rel_path.is_absolute():
        raise UnsafePath(code="UNSAFE_PATH", message=f"absolute path is not allowed: {rel}")
    if any(part in ("..",) for part in rel_path.parts):
        raise UnsafePath(code="UNSAFE_PATH", message=f"path traversal is not allowed: {rel}")
    return rel_path


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
    atomic_write_bytes(path, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dst)


def atomic_rename(src: Path, dst: Path) -> None:
    atomic_move(src, dst)


def atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, tmp)
    tmp.replace(dst)


def list_ready_envelopes(inbox_plan_dir: Path) -> list[Path]:
    if not inbox_plan_dir.exists():
        return []
    candidates: list[Path] = []
    for child in inbox_plan_dir.iterdir():
        if child.is_dir():
            continue
        if is_tmp(child):
            continue
        if not child.name.endswith(".msg.json"):
            continue
        candidates.append(child)
    return sorted(candidates, key=lambda p: p.name)


@dataclass(frozen=True)
class AgentPaths:
    agent_root: Path

    @property
    def inbox(self) -> Path:
        return self.agent_root / "inbox"

    @property
    def outbox(self) -> Path:
        return self.agent_root / "outbox"

    @property
    def workspace(self) -> Path:
        return self.agent_root / "workspace"

    @property
    def heartbeat_config(self) -> Path:
        return self.agent_root / "heartbeat_config.json"

    @property
    def status_heartbeat(self) -> Path:
        return self.agent_root / "status_heartbeat.json"

