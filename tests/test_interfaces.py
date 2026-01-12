from __future__ import annotations

import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

import agenttalk_heartbeat
import agenttalk_router
import agenttalk_dashboard
from agenttalk.heartbeat.app import AppContext, load_handler, run_once
from agenttalk.heartbeat.config import load_config
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


def test_cli_parses_args_and_invokes_runner(tmp_path: Path):
    called = {}

    def runner(**kwargs):
        called.update(kwargs)

    agent_root = tmp_path / "agents" / "agent_a"
    agenttalk_heartbeat.main(
        ["--agent-root", str(agent_root), "--schemas-base-dir", "doc/rule/templates/schemas"],
        runner=runner,
    )
    assert called["agent_root"] == agent_root
    assert Path(called["schemas_base_dir"]).as_posix().endswith("doc/rule/templates/schemas")


def test_router_cli_parses_args_and_invokes_runner(tmp_path: Path):
    called = {}

    def runner(**kwargs):
        called.update(kwargs)

    agents_root = tmp_path / "agents"
    system_runtime = tmp_path / "system_runtime"
    agenttalk_router.main(
        ["--agents-root", str(agents_root), "--system-runtime", str(system_runtime)],
        runner=runner,
    )
    assert called["agents_root"] == agents_root
    assert called["system_runtime"] == system_runtime


def test_dashboard_app_factory(tmp_path: Path):
    pytest.importorskip("fastapi")
    from agenttalk.dashboard.app import create_app

    app = create_app(system_runtime=tmp_path / "system_runtime")
    assert app.title


def test_load_config_validates_and_resolves_schema_dir(tmp_path: Path):
    cfg_path = tmp_path / "heartbeat_config.json"
    atomic_write_json(
        cfg_path,
        {
            "schema_version": "1.0",
            "agent_id": "agent_a",
            "poll_interval_seconds": 2,
            "max_new_messages_per_tick": 5,
            "max_resume_messages_per_tick": 2,
            "plans": {"scan_mode": "allowlist_only", "allowlist": ["p1"]},
            "schema_validation": {"enabled": True, "schemas_base_dir": "doc/rule/templates/schemas"},
        },
    )
    cfg = load_config(cfg_path, schemas_base_dir=Path("doc/rule/templates/schemas"))
    assert cfg.agent_id == "agent_a"
    assert cfg.scan_mode == "allowlist_only"
    assert cfg.allowlist == ["p1"]
    assert cfg.schemas_base_dir.name == "schemas"


def test_load_handler_requires_handler_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = types.ModuleType("dummy_handler_module")
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", mod)
    with pytest.raises(RuntimeError):
        load_handler("dummy_handler_module")

    class H:
        def handle_command(self, *, envelope: dict, command: dict, context: dict) -> CommandResult:
            return CommandResult(ok=True)

    mod.handler = H()
    assert load_handler("dummy_handler_module") is mod.handler


def test_run_once_writes_status_heartbeat(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    agent_root = tmp_path / "agents" / "agent_a"
    paths = AgentPaths(agent_root=agent_root)
    (paths.inbox / "plan_1").mkdir(parents=True, exist_ok=True)
    (paths.outbox / "plan_1").mkdir(parents=True, exist_ok=True)

    cfg = types.SimpleNamespace(
        agent_id="agent_a",
        scan_mode="auto",
        allowlist=None,
        poll_interval_seconds=1,
        max_new_messages_per_tick=1,
        max_resume_messages_per_tick=1,
        schema_validation_enabled=False,
        schemas_base_dir=Path("doc/rule/templates/schemas"),
    )

    ctx = AppContext(
        agent_paths=paths,
        config=cfg,  # type: ignore[arg-type]
        schema_registry=SchemaRegistry(schemas_base_dir=Path("doc/rule/templates/schemas")),
        clock=FixedClock(now),
        ids=IdGenerator(),
        handler=load_handler(None),
    )
    plans = run_once(ctx)
    assert plans == ["plan_1"]
    heartbeat = __import__("json").loads(paths.status_heartbeat.read_text(encoding="utf-8"))
    assert heartbeat["agent_id"] == "agent_a"
    assert heartbeat["last_heartbeat"] == iso_z(now)
