# 01 CLI 接口（agenttalk_heartbeat.py）

## 入口

- 文件：`agenttalk_heartbeat.py`
- 作用：启动 Heartbeat 常驻进程（daemon）

## 参数

- `--agent-root <path>`（必需）
  - 指向单个 Agent 的根目录：`agents/<agent_id>/`
- `--schemas-base-dir <path>`（可选）
  - 默认：`doc/rule/templates/schemas`
  - 用于加载 JSON Schema（message_envelope/command/ack 等）
- `--config <path>`（可选）
  - 默认：`<agent-root>/heartbeat_config.json`
- `--handler-module <module>`（可选）
  - Python 模块名（需暴露 `handler` 对象，见 `03_handler_plugin.md`）

## 行为

- 每轮：扫描 plan → tick → sleep（见 `05_agent_heartbeat_and_dispatch.md`）
- 输出：`status_heartbeat.json`、`ack_*`、`task_state_*`、`human_intervention_request_*`、可选 `alert_*`

## Pytest

- `tests/test_interfaces.py::test_cli_parses_args_and_invokes_runner`

