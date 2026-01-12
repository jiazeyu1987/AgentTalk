from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agenttalk.command_runner.pipeline import write_artifacts_to_outbox
from agenttalk.command_runner.types import ProducedArtifact, ProducedFile
from agenttalk.heartbeat.schema import SchemaRegistry


def test_write_artifacts_to_outbox_writes_files_and_envelope(tmp_path: Path):
    outbox_plan = tmp_path / "outbox" / "plan_1"
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    artifacts = [
        ProducedArtifact(
            output_name="o",
            files=[ProducedFile(path="a.txt", content=b"hello", content_type="text/plain")],
        )
    ]
    results = write_artifacts_to_outbox(
        outbox_plan_dir=outbox_plan,
        producer_agent_id="agent_a",
        plan_id="plan_1",
        task_id="task_1",
        command_id="cmd_task_1_001",
        artifacts=artifacts,
        now=now,
    )
    assert (outbox_plan / "a.txt").exists()
    assert results and results[0].envelope_path.exists()

    env = json.loads(results[0].envelope_path.read_text(encoding="utf-8"))
    reg = SchemaRegistry(Path("doc/rule/templates/schemas"))
    reg.validate(env, "message_envelope.schema.json")
    assert env["type"] == "artifact"
    assert env["output_name"] == "o"

