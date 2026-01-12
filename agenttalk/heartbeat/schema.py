from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import SchemaInvalid
from .io import read_json


@dataclass(frozen=True)
class SchemaRegistry:
    schemas_base_dir: Path

    def validate(self, document: dict, schema_filename: str) -> None:
        schema_path = self.schemas_base_dir / schema_filename
        schema = read_json(schema_path)
        try:
            import jsonschema  # type: ignore
            from jsonschema.validators import Draft202012Validator  # type: ignore

            store: dict[str, Any] = {}
            try:
                for p in self.schemas_base_dir.glob("*.schema.json"):
                    try:
                        s = read_json(p)
                        sid = s.get("$id")
                        if isinstance(sid, str) and sid:
                            store[sid] = s
                    except Exception:
                        continue
            except Exception:
                store = {}

            resolver = jsonschema.RefResolver.from_schema(schema, store=store)  # type: ignore[attr-defined]
            Draft202012Validator(schema, resolver=resolver).validate(document)
        except ImportError:
            required = schema.get("required", [])
            missing = [k for k in required if k not in document]
            if missing:
                raise SchemaInvalid(
                    code="SCHEMA_INVALID",
                    message=f"missing required keys: {missing} (jsonschema not installed)",
                )
        except Exception as e:
            raise SchemaInvalid(code="SCHEMA_INVALID", message=str(e)) from e


def infer_schema_filename(envelope: dict) -> str:
    t = envelope.get("type")
    if t == "command" or t == "artifact":
        return "message_envelope.schema.json"
    return "message_envelope.schema.json"


def get_or_none(obj: dict, key: str) -> Any:
    return obj.get(key, None)
