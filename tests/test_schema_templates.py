from __future__ import annotations

import json
from pathlib import Path

import pytest

from agenttalk.heartbeat.schema import SchemaRegistry


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


TEMPLATE_VALIDATIONS: list[tuple[str, str]] = [
    ("doc/rule/templates/ack.json", "ack.schema.json"),
    ("doc/rule/templates/active_dag_ref.json", "active_dag_ref.schema.json"),
    ("doc/rule/templates/alert.json", "alert.schema.json"),
    ("doc/rule/templates/dag_review_result.json", "dag_review_result.schema.json"),
    ("doc/rule/templates/deadletter_entry.json", "deadletter_entry.schema.json"),
    ("doc/rule/templates/decision_record.json", "decision_record.schema.json"),
    ("doc/rule/templates/delivery_log_entry.json", "delivery_log_entry.schema.json"),
    ("doc/rule/templates/heartbeat_config.json", "heartbeat_config.schema.json"),
    ("doc/rule/templates/human_intervention_request.json", "human_intervention_request.schema.json"),
    ("doc/rule/templates/human_intervention_response.json", "human_intervention_response.schema.json"),
    ("doc/rule/templates/input_index.json", "input_index.schema.json"),
    ("doc/rule/templates/message_envelope.msg.json", "message_envelope.schema.json"),
    ("doc/rule/templates/command_envelope.msg.json", "message_envelope.schema.json"),
    ("doc/rule/templates/command.cmd.json", "command.schema.json"),
    ("doc/rule/templates/plan_manifest.json", "plan_manifest.schema.json"),
    ("doc/rule/templates/plan_status.json", "plan_status.schema.json"),
    ("doc/rule/templates/release_manifest.json", "release_manifest.schema.json"),
    ("doc/rule/templates/status_heartbeat.json", "status_heartbeat.schema.json"),
    ("doc/rule/templates/task_dag.json", "task_dag.schema.json"),
    ("doc/rule/templates/task_state.json", "task_state.schema.json"),
]


@pytest.mark.parametrize("template_path,schema_name", TEMPLATE_VALIDATIONS)
def test_templates_match_schemas(template_path: str, schema_name: str):
    schemas = SchemaRegistry(Path("doc/rule/templates/schemas"))
    schemas.validate(_read(template_path), schema_name)

