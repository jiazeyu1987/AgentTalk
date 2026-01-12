from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agenttalk.heartbeat.app import AppContext, tick_plan
from agenttalk.heartbeat.config import HeartbeatConfig
from agenttalk.heartbeat.handlers import CommandResult
from agenttalk.heartbeat.ids import IdGenerator
from agenttalk.heartbeat.io import AgentPaths, atomic_write_json
from agenttalk.heartbeat.schema import SchemaRegistry
from agenttalk.heartbeat.timeutil import Clock, iso_z


class FixedClock(Clock):
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:  # type: ignore[override]
        return self._now


class Handler:
    def __init__(self):
        self.calls = []

    def handle_command(self, *, envelope: dict, command: dict, context: dict) -> CommandResult:
        self.calls.append((envelope["message_id"], command["command_id"]))
        return CommandResult(ok=True, details={"handled": True})


def write_envelope(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def base_ctx(tmp_path: Path, now: datetime) -> AppContext:
    agent_root = tmp_path / "agents" / "agent_a"
    paths = AgentPaths(agent_root=agent_root)
    cfg = HeartbeatConfig(
        schema_version="1.0",
        agent_id="agent_a",
        poll_interval_seconds=1,
        max_new_messages_per_tick=50,
        max_resume_messages_per_tick=10,
        scan_mode="auto",
        allowlist=None,
        schema_validation_enabled=False,
        schemas_base_dir=tmp_path / "schemas",
    )
    reg = SchemaRegistry(schemas_base_dir=Path("doc/rule/templates/schemas"))
    handler = Handler()
    return AppContext(
        agent_paths=paths,
        config=cfg,
        schema_registry=reg,
        clock=FixedClock(now),
        ids=IdGenerator(),
        handler=handler,
    )


def test_only_claims_envelopes_not_payload(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)

    plan_id = "plan_1"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)
    # payload file arrives before envelope
    (inbox_plan / "requirements.md").write_text("hi", encoding="utf-8")

    env = {
        "schema_version": "1.0",
        "message_id": "msg_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_x",
        "type": "artifact",
        "created_at": iso_z(now),
        "task_id": "task_1",
        "output_name": "requirements",
        "payload": {"files": [{"path": "requirements.md", "sha256": "sha256:dummy"}]},
    }
    write_envelope(inbox_plan / "artifact.msg.json", env)

    tick_plan(ctx, plan_id)

    # payload should have been moved out of inbox root (finalized) or still exist (if move skipped),
    # but it must not be claimed into .pending by mistake.
    assert not (inbox_plan / ".pending" / "requirements.md").exists()


def test_wait_for_inputs_blocks_then_resumes(tmp_path: Path):
    now = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)
    plan_id = "plan_2"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)

    cmd_env = {
        "schema_version": "1.0",
        "message_id": "msg_cmd_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_planner",
        "type": "command",
        "created_at": iso_z(now),
        "task_id": "task_10",
        "command_id": "cmd_task_10_001",
        "payload": {
            "command": {
                "schema_version": "1.0",
                "command_id": "cmd_task_10_001",
                "plan_id": plan_id,
                "task_id": "task_10",
                "command_seq": 1,
                "dag_ref": {"sha256": "sha256:dag"},
                "prompt": "do it",
                "required_inputs": ["requirements.md"],
                "resolved_inputs": None,
                "wait_for_inputs": True,
                "score_required": False,
                "timeout": 60,
            }
        },
    }
    write_envelope(inbox_plan / "cmd.msg.json", cmd_env)

    tick_plan(ctx, plan_id)
    outbox_plan = ctx.agent_paths.outbox / plan_id
    task_state = json.loads((outbox_plan / "task_state_task_10.json").read_text(encoding="utf-8"))
    assert task_state["state"] == "BLOCKED_WAITING_INPUT"

    # now deliver required input as artifact
    (inbox_plan / "requirements.md").write_text("hi", encoding="utf-8")
    art_env = {
        "schema_version": "1.0",
        "message_id": "msg_art_1",
        "plan_id": plan_id,
        "producer_agent_id": "agent_x",
        "type": "artifact",
        "created_at": iso_z(now),
        "task_id": "task_src",
        "output_name": "requirements",
        "payload": {"files": [{"path": "requirements.md", "sha256": "sha256:" + "0" * 64}]},
    }
    # fix sha to actual after write
    import hashlib

    art_env["payload"]["files"][0]["sha256"] = "sha256:" + hashlib.sha256(b"hi").hexdigest()
    write_envelope(inbox_plan / "art.msg.json", art_env)

    tick_plan(ctx, plan_id)
    # tick again to resume pending command
    tick_plan(ctx, plan_id)
    ack = json.loads((outbox_plan / "ack_msg_cmd_1.json").read_text(encoding="utf-8"))
    assert ack["status"] == "SUCCEEDED"


def test_wait_for_inputs_timeout_creates_human_request(tmp_path: Path):
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, start)
    plan_id = "plan_3"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)

    cmd_env = {
        "schema_version": "1.0",
        "message_id": "msg_cmd_t",
        "plan_id": plan_id,
        "producer_agent_id": "agent_planner",
        "type": "command",
        "created_at": iso_z(start),
        "task_id": "task_t",
        "command_id": "cmd_task_t_001",
        "payload": {
            "command": {
                "schema_version": "1.0",
                "command_id": "cmd_task_t_001",
                "plan_id": plan_id,
                "task_id": "task_t",
                "command_seq": 1,
                "dag_ref": {"sha256": "sha256:dag"},
                "prompt": "do it",
                "required_inputs": ["missing.txt"],
                "resolved_inputs": None,
                "wait_for_inputs": True,
                "score_required": False,
                "timeout": 1,
            }
        },
    }
    write_envelope(inbox_plan / "cmd.msg.json", cmd_env)
    tick_plan(ctx, plan_id)

    # advance time beyond timeout and resume
    ctx = ctx.__class__(
        agent_paths=ctx.agent_paths,
        config=ctx.config,
        schema_registry=ctx.schema_registry,
        clock=FixedClock(start + timedelta(seconds=5)),
        ids=ctx.ids,
        handler=ctx.handler,
    )
    tick_plan(ctx, plan_id)

    outbox_plan = ctx.agent_paths.outbox / plan_id
    human_files = list(outbox_plan.glob("human_intervention_request_*.json"))
    assert human_files, "expected a human intervention request"


def test_input_conflict_deadletters_and_alert(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)
    plan_id = "plan_conflict"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)
    outbox_plan = ctx.agent_paths.outbox / plan_id

    # first artifact ingests ok
    (inbox_plan / "a.txt").write_text("A", encoding="utf-8")
    import hashlib

    sha_a = "sha256:" + hashlib.sha256(b"A").hexdigest()
    env1 = {
        "schema_version": "1.0",
        "message_id": "msg_a",
        "plan_id": plan_id,
        "producer_agent_id": "agent_x",
        "type": "artifact",
        "created_at": iso_z(now),
        "task_id": "task_1",
        "output_name": "out",
        "payload": {"files": [{"path": "a.txt", "sha256": sha_a}]},
    }
    write_envelope(inbox_plan / "a.msg.json", env1)
    tick_plan(ctx, plan_id)

    # second artifact claims same destination path but different sha
    (inbox_plan / "a.txt").write_text("B", encoding="utf-8")
    sha_b = "sha256:" + hashlib.sha256(b"B").hexdigest()
    env2 = dict(env1)
    env2["message_id"] = "msg_b"
    env2["payload"] = {"files": [{"path": "a.txt", "sha256": sha_b}]}
    write_envelope(inbox_plan / "b.msg.json", env2)
    tick_plan(ctx, plan_id)

    dead = list((inbox_plan / ".deadletter").glob("*msg_b*"))
    assert dead, "expected artifact envelope to be deadlettered"
    alerts = list(outbox_plan.glob("alert_*.json"))
    assert any(json.loads(p.read_text(encoding="utf-8"))["type"] == "INPUT_CONFLICT" for p in alerts)


def test_payload_finalize_conflict_moves_payload_to_deadletter(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)
    plan_id = "plan_payload_conflict"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)
    outbox_plan = ctx.agent_paths.outbox / plan_id

    import hashlib

    # prepare a conflicting already-finalized payload
    processed_payload = inbox_plan / ".processed" / "_payload" / "msg_x" / "p.txt"
    processed_payload.parent.mkdir(parents=True, exist_ok=True)
    processed_payload.write_text("OLD", encoding="utf-8")

    (inbox_plan / "p.txt").write_text("NEW", encoding="utf-8")
    sha_new = "sha256:" + hashlib.sha256(b"NEW").hexdigest()
    env = {
        "schema_version": "1.0",
        "message_id": "msg_x",
        "plan_id": plan_id,
        "producer_agent_id": "agent_x",
        "type": "artifact",
        "created_at": iso_z(now),
        "task_id": "task_1",
        "output_name": "out",
        "payload": {"files": [{"path": "p.txt", "sha256": sha_new}]},
    }
    write_envelope(inbox_plan / "p.msg.json", env)
    tick_plan(ctx, plan_id)

    conflict_payload = inbox_plan / ".deadletter" / "_payload_conflict" / "msg_x" / "p.txt"
    assert conflict_payload.exists(), "expected payload to be moved into payload conflict deadletter area"
    alerts = list(outbox_plan.glob("alert_*.json"))
    assert any(json.loads(p.read_text(encoding="utf-8"))["type"] == "PAYLOAD_FINALIZE_CONFLICT" for p in alerts)


def test_dedupe_skips_when_terminal_ack_exists(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)
    plan_id = "plan_dedupe"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)
    outbox_plan = ctx.agent_paths.outbox / plan_id

    cmd_env = {
        "schema_version": "1.0",
        "message_id": "msg_cmd",
        "plan_id": plan_id,
        "producer_agent_id": "agent_planner",
        "type": "command",
        "created_at": iso_z(now),
        "task_id": "task_1",
        "command_id": "cmd_task_1_001",
        "payload": {
            "command": {
                "schema_version": "1.0",
                "command_id": "cmd_task_1_001",
                "plan_id": plan_id,
                "task_id": "task_1",
                "command_seq": 1,
                "dag_ref": {"sha256": "sha256:dag"},
                "prompt": "do it",
                "required_inputs": [],
                "resolved_inputs": None,
                "wait_for_inputs": False,
                "score_required": False,
                "timeout": 60,
            }
        },
    }
    write_envelope(inbox_plan / "c1.msg.json", cmd_env)
    tick_plan(ctx, plan_id)
    ack = json.loads((outbox_plan / "ack_msg_cmd.json").read_text(encoding="utf-8"))
    assert ack["status"] == "SUCCEEDED"

    # re-deliver same message_id
    write_envelope(inbox_plan / "c2.msg.json", cmd_env)
    handler = ctx.handler
    before = len(handler.calls)
    tick_plan(ctx, plan_id)
    after = len(handler.calls)
    assert after == before, "expected dedupe to skip handler execution"


def test_resume_consumed_only_ack(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)
    plan_id = "plan_resume"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)
    outbox_plan = ctx.agent_paths.outbox / plan_id
    (inbox_plan / ".pending").mkdir(parents=True, exist_ok=True)
    (inbox_plan / ".processed").mkdir(parents=True, exist_ok=True)
    (inbox_plan / ".deadletter").mkdir(parents=True, exist_ok=True)
    outbox_plan.mkdir(parents=True, exist_ok=True)

    env = {
        "schema_version": "1.0",
        "message_id": "msg_r",
        "plan_id": plan_id,
        "producer_agent_id": "agent_planner",
        "type": "command",
        "created_at": iso_z(now),
        "task_id": "task_r",
        "command_id": "cmd_task_r_001",
        "payload": {
            "command": {
                "schema_version": "1.0",
                "command_id": "cmd_task_r_001",
                "plan_id": plan_id,
                "task_id": "task_r",
                "command_seq": 1,
                "dag_ref": {"sha256": "sha256:dag"},
                "prompt": "do it",
                "required_inputs": [],
                "resolved_inputs": None,
                "wait_for_inputs": False,
                "score_required": False,
                "timeout": 60,
            }
        },
    }
    pending = inbox_plan / ".pending" / "msg_r__cmd.msg.json"
    write_envelope(pending, env)
    # simulate crash after CONSUMED
    atomic_write_json(
        outbox_plan / "ack_msg_r.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_id,
            "message_id": "msg_r",
            "consumer_agent_id": "agent_a",
            "status": "CONSUMED",
            "consumed_at": iso_z(now),
        },
    )
    tick_plan(ctx, plan_id)
    ack = json.loads((outbox_plan / "ack_msg_r.json").read_text(encoding="utf-8"))
    assert ack["status"] in ("SUCCEEDED", "FAILED")


def test_schema_validation_invalid_envelope_deadletters(tmp_path: Path):
    pytest.importorskip("jsonschema")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ctx = base_ctx(tmp_path, now)
    plan_id = "plan_schema"
    inbox_plan = ctx.agent_paths.inbox / plan_id
    inbox_plan.mkdir(parents=True, exist_ok=True)
    outbox_plan = ctx.agent_paths.outbox / plan_id

    ctx = ctx.__class__(
        agent_paths=ctx.agent_paths,
        config=ctx.config.__class__(
            **{**ctx.config.__dict__, "schema_validation_enabled": True}
        ),
        schema_registry=SchemaRegistry(schemas_base_dir=Path("doc/rule/templates/schemas")),
        clock=ctx.clock,
        ids=ctx.ids,
        handler=ctx.handler,
    )
    bad_env = {
        "schema_version": "1.0",
        # missing message_id
        "plan_id": plan_id,
        "producer_agent_id": "agent_x",
        "type": "artifact",
        "created_at": iso_z(now),
        "task_id": "task_1",
        "output_name": "out",
        "payload": {"files": [{"path": "x.txt", "sha256": "sha256:dummy"}]},
    }
    write_envelope(inbox_plan / "bad.msg.json", bad_env)
    tick_plan(ctx, plan_id)
    assert list((inbox_plan / ".deadletter").glob("bad.msg.json")), "expected bad envelope in deadletter"
    alerts = list(outbox_plan.glob("alert_*.json"))
    assert alerts, "expected an alert to be written"
