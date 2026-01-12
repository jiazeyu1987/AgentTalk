from __future__ import annotations

import json
from pathlib import Path

from agenttalk.heartbeat.schema import SchemaRegistry


def test_ack_template_matches_schema():
    schemas = SchemaRegistry(Path("doc/rule/templates/schemas"))
    ack = json.loads(Path("doc/rule/templates/ack.json").read_text(encoding="utf-8"))
    schemas.validate(ack, "ack.schema.json")

