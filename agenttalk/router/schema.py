from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agenttalk.heartbeat.schema import SchemaRegistry as _SchemaRegistry


@dataclass(frozen=True)
class SchemaRegistry:
    schemas_base_dir: Path

    def validate(self, document: dict, schema_filename: str) -> None:
        _SchemaRegistry(self.schemas_base_dir).validate(document, schema_filename)

