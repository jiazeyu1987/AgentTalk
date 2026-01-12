# 01 JSON Schema 校验模块

## 目标

提供统一的 schema 校验能力，覆盖：
- 命令消息：`cmd_*.msg.json`（message_envelope `type=command`，其 `payload.command` 校验 `command.schema.json`）
- `task_dag.json`（v1.1）
- `active_dag_ref.json`（当前阶段 DAG 指针）
- `plan_manifest.json`（plan 清单/门禁策略）
- `dag_review_result.json`
- `human_intervention_request/response.json`
- `release_manifest.json`
- `decision_record.json`（统一结论记录）
- `task_state_<task_id>.json`（任务状态快照）
- `status_heartbeat.json`（Agent 心跳快照）
- `heartbeat_config.json`（Agent 心跳程序配置）
- `input_index.json`（输入索引）
- `plan_status.json`（Plan 状态汇总）
- 其它 validation_result 类文件（后续扩展）

## 模块边界

- 输入：JSON 文本/对象 + schema 名称（或路径）
- 输出：校验通过/失败（结构化错误列表：path、message）
- 不负责：路由、投递、读写目录

## 接口草案

- `validate(document: dict, schema_id: str) -> ValidationResult`
- `load_schemas(base_dir) -> SchemaRegistry`

## Schema 来源（MVP 建议写死）

- `doc/rule/templates/schemas/*.schema.json`：消息/命令/门禁/日志/结论等通用契约（本仓库的唯一权威 schema 目录）

约束：
- 校验以 schema **文件名**作为调用方的稳定入口（例如 `message_envelope.schema.json`、`task_dag.schema.json`）；schema 的 `$id` 仅用于描述与定位，不作为运行时选择依据（避免多版本/多路径引入分叉）。
- 不支持的 `schema_version` → 必须返回可机器识别的错误码（供 Router 进入 DLQ + alert）。

## 强校验口径（schema_validation_enabled=true）

- Heartbeat：
  - 读取 `heartbeat_config.json` 时强制校验 `heartbeat_config.schema.json`
  - 处理 inbox 的 `*.msg.json` 时校验 `message_envelope.schema.json`（命令类再额外校验 `command.schema.json`）
  - schema 校验失败：消息文件移动到 `agents/<agent_id>/inbox/<plan_id>/.deadletter/`，并写 `agents/<agent_id>/outbox/<plan_id>/alert_*.json`

- Router：
  - `task_dag.json` / `active_dag_ref.json` 校验失败：写 `system_runtime/alerts/<plan_id>/`，并跳过该 plan 的投递（避免错误 DAG 继续路由）
  - message_envelope 校验失败：写 `system_runtime/deadletter/<plan_id>/` + `system_runtime/alerts/<plan_id>/`，并追加一条 `deliveries.jsonl status=DEADLETTERED`

- Monitor：
  - 读取 `task_dag.json` / `active_dag_ref.json` / `acks/*` / `task_state_*` 时按需校验（失败则忽略该条数据，不中断整个进程）
  - 生成 `plan_status.json` 时可开启 schema 校验；失败会写 `system_runtime/alerts/<plan_id>/alert_*.json type=PLAN_STATUS_AGGREGATION_FAILED`

## 错误码（与 09 对齐）

- `SCHEMA_INVALID`：schema 校验失败
- `SCHEMA_VERSION_UNSUPPORTED`：`schema_version` 不受支持（当前大多数对象仅支持 `1.0`；DAG schema_version 为 `1.1`）

## $ref 解析（必须离线）

- schema 之间允许通过 `$ref` 引用（例如 message_envelope 引用 command.schema.json）。
- 校验实现必须在本地通过 `$id -> schemas_base_dir/*.schema.json` 建立映射来解析 `$ref`，不得依赖网络请求（否则在离线/内网环境会失败）。

## Pytest

- 单测：对每个模板文件（`doc/rule/templates/*.json`）做“应通过”校验
- 单测：构造缺字段/错枚举的样例做“应失败”校验（断言错误 path）
- 兼容：schema_version 不支持时返回可识别错误码（供 DLQ 使用）
