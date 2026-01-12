# 16 Monitor 独立程序（MVP Quickstart）

本文件说明如何运行 `08_plan_status_aggregation.md` 对应的 Monitor 程序，生成 `plan_status.json`。

## 依赖

- Python `>=3.10`
- 安装（可选但推荐）：`python -m pip install -e .`

## 运行

从仓库根目录运行：

`python agenttalk_monitor.py --agents-root agents --system-runtime system_runtime`

可选参数：
- `--schemas-base-dir doc/rule/templates/schemas`

## 输入

- `system_runtime/plans/<plan_id>/task_dag.json`（必须）
- `system_runtime/plans/<plan_id>/active_dag_ref.json`（推荐；用于统一当前 DAG 口径）
- `system_runtime/plans/<plan_id>/deliveries.jsonl`
- `system_runtime/plans/<plan_id>/acks/ack_<message_id>.json`（优先；若不存在会回退扫描 `agents/*/outbox/<plan_id>/ack_*.json`）
- `system_runtime/plans/<plan_id>/commands/*.msg.json`（用于推断 `wait_for_inputs` 的 `BLOCKED_WAITING_INPUT`）
- `agents/<agent_id>/outbox/<plan_id>/task_state_<task_id>.json`（若存在则优先）

## 输出

- `system_runtime/plans/<plan_id>/plan_status.json`
  - 模板：`doc/rule/templates/plan_status.json`
  - Schema：`doc/rule/templates/schemas/plan_status.schema.json`

- `system_runtime/agent_status/<agent_id>.json`（Dashboard 权威数据源，来自 agent 自报的 `agents/<agent_id>/status_heartbeat.json`）

## 测试

`python -m pytest -k monitor`

## 最小验证

1) 准备最小 plan（至少包含 DAG）：
- `system_runtime/plans/<plan_id>/task_dag.json`
- 推荐同时写：`system_runtime/plans/<plan_id>/active_dag_ref.json`
  - 注意：当开启 schema 校验时，`active_dag_ref.json` 必须包含 `dag_kind` 与合法的 `updated_at`（date-time）。

2) 准备一个 agent 的自报心跳（可由 Heartbeat 自动生成，这里也可手写一份）：
- `agents/<agent_id>/status_heartbeat.json`

3) 运行 Monitor 后应看到：
- `system_runtime/plans/<plan_id>/plan_status.json`
- `system_runtime/agent_status/<agent_id>.json`

4) 可选：验证 Monitor 告警输出（见 `doc/develop/08_plan_status_aggregation.md`）
- 当存在 `ack status=CONSUMED` 且超过 `timeout*2`：Monitor 写 `system_runtime/alerts/<plan_id>/alert_*.json type=COMMAND_ACK_TIMEOUT`
