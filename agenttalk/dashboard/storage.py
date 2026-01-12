from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def safe_listdir(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return [p for p in dir_path.iterdir() if p.exists()]


def sort_by_created_at_then_name(items: Iterable[Path]) -> list[Path]:
    def key(p: Path) -> tuple[str, str]:
        try:
            obj = read_json(p)
            created_at = obj.get("created_at") or obj.get("updated_at") or ""
            return (str(created_at), p.name)
        except Exception:
            return ("", p.name)

    return sorted(list(items), key=key)


def paginate(items: list[Any], *, offset: int, limit: int) -> dict:
    total = len(items)
    offset = max(0, offset)
    limit = max(1, min(limit, 500))
    sliced = items[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "items": sliced}


@dataclass(frozen=True)
class RuntimePaths:
    system_runtime: Path

    @property
    def plans(self) -> Path:
        return self.system_runtime / "plans"

    @property
    def agent_status(self) -> Path:
        return self.system_runtime / "agent_status"

