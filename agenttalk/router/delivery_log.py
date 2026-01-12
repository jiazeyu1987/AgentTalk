from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import atomic_write_bytes


@dataclass(frozen=True)
class DeliveryLog:
    path: Path

    def append(self, entry: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        if not self.path.exists():
            atomic_write_bytes(self.path, line.encode("utf-8"))
            return
        with self.path.open("ab") as f:
            f.write(line.encode("utf-8"))

    def read_entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        entries: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
        return entries


def delivered_index(entries: list[dict]) -> set[tuple[str, str]]:
    idx: set[tuple[str, str]] = set()
    for e in entries:
        if e.get("status") != "DELIVERED":
            continue
        mid = e.get("message_id")
        sha = e.get("envelope_sha256")
        if isinstance(mid, str) and isinstance(sha, str):
            idx.add((mid, sha))
    return idx

