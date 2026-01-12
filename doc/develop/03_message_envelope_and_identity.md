# 03 消息信封与身份标识模块

## 目标

统一 envelope（推荐 `*.msg.json`）最小字段，使路由/去重/审计可计算：
- `message_id`、`plan_id`、`producer_agent_id`
- `task_id`、`output_name`（用于从 DAG 精确定位 outputs[]）
- `command_id`（命令必需；产物可选但推荐）
- `idempotency_key`（可选，仅用于审计与可读关联）
- `type/subtype`（可选但推荐）
- `sha256`（payload hash）

（方案B补充）命令也通过 envelope 运输：
- 命令消息：`cmd_*.msg.json`，`type=command`
- 命令对象位于：`payload.command`（按 `command.schema.json` 校验）
- 产物消息：`type=artifact` 时，`task_id + output_name + payload.files[]` 必须齐全（否则无法按 DAG 路由）

## 模块边界

- 输入：payload 路径 + 元信息
- 输出：envelope 文件（JSON）+ 解析后的 Envelope 对象
- 不负责：投递、ACK 状态机

## 字段口径（必须写死，避免分叉）

- 命令消息（`type=command`）必须包含：`plan_id`、`task_id`、`command_id`、`payload.command`（且 `payload.command.*` 与 envelope 顶层字段一致）。
- 产物消息（`type=artifact`）必须包含：`plan_id`、`task_id`、`output_name`、`payload.files[]`（否则无法从 DAG 定位 deliver_to）。
- `idempotency_key` 不参与主去重键；Router 仅以 `message_id + sha256` 去重（`idempotency_key` 仅用于审计与人类可读关联）。

## Pytest

- 单测：envelope round-trip（生成→解析一致）
- 单测：缺关键字段应失败（供 schema 校验）
