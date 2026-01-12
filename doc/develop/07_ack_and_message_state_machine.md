# 07 ACK 与消息状态机模块

## 目标

实现消息/命令处理状态（参考 delivery_state_machine.md）：
- CONSUMED / SUCCEEDED / FAILED（ACK 文件）
- 与 deliveries.jsonl 关联（message_id）

## 口径（必须写死）

- ACK 文件名固定：`ack_<message_id>.json`
- 写入位置固定：`agents/<agent_id>/outbox/<plan_id>/`
- ACK 允许“两阶段”：先写 `CONSUMED`，结束后覆盖写成 `SUCCEEDED/FAILED`（覆盖必须 tmp→rename）
- 一旦进入终态（`SUCCEEDED/FAILED`）不得回退

## 采集与权威源（避免 Monitor/Dashboard 分叉）

- 系统程序（PR-024）应跨目录采集各 Agent 的 ACK，并归档到：
  - `system_runtime/plans/<plan_id>/acks/ack_<message_id>.json`
- Monitor/Dashboard 以该归档目录为首选权威源；若不存在（兼容期）再回退扫描 agent outbox。
- 在 MVP 实现里：由 Router 程序负责采集并归档 ACK（同一进程即可，避免再引入一个“ACK 收集器”分叉）。

## Schema / 模板

- Schema：`doc/rule/templates/schemas/ack.schema.json`
- 模板示例：`doc/rule/templates/ack.json`

## 归档冲突策略（必须写死）

- 同一个 `message_id` 的 ACK 若内容完全一致：允许重复归档（幂等）
- 同一个 `message_id` 的 ACK 若内容不同：视为异常（`ACK_ID_REUSED_WITH_DIFFERENT_CONTENT`）
  - 系统程序必须写入 deadletter + alert（不覆盖已归档版本）

## Pytest

- 单测：ACK schema 校验通过
- 集成：router 投递后，agent 写 ACK，监控可读到终态
- 集成：系统程序可把 `agents/*/outbox/<plan_id>/ack_*.json` 归档到 `system_runtime/plans/<plan_id>/acks/`（含冲突告警）
