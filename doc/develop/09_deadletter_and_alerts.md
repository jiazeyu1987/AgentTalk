# 09 Deadletter 与告警模块

## 目标

统一异常处理：
- schema 解析/校验失败（不可投递）
- 路由找不到目标（DAG 不可满足）
- 超时/重试超限（仅告警，不产出业务结论）

输出：
- `system_runtime/deadletter/<plan_id>/...`
- `system_runtime/alerts/<plan_id>/...`

## 责任边界（必须写死）

- Router（系统投递程序）负责：
  - 对“无法投递的消息/产物”写 `deadletter_entry.json` + `alert.json`
  - 并把该次失败写入 `deliveries.jsonl status=DEADLETTERED`（便于 Dashboard/回放）
- Monitor（系统汇总程序）负责：
  - 对“可观测异常”写 `alert.json`（例如 `ACK=CONSUMED` 超时、命令归档不一致、plan_status 汇总失败）
  - 不写 deadletter（避免把“汇总失败”混入“投递失败”）
- Agent（Heartbeat）负责：
  - 对本地执行/输入冲突写 agent outbox 的 `alert_*.json` 或 inbox `.deadletter/`（本地隔离）
  - 这些文件不走 DAG 路由，由系统程序按需收集（见 PR-024）

## 统一落盘格式（Schema）

- Deadletter：`doc/rule/templates/schemas/deadletter_entry.schema.json`
- Alert：`doc/rule/templates/schemas/alert.schema.json`

Router/Monitor 写出的 JSON 必须与 schema 一致；字段扩展允许（`additionalProperties=true`），但必填字段与语义不得改变。

## 错误码（MVP 最小集合）

用于 `deadletter.reason.code` 与 `alert.type`（统一口径，便于筛选/告警聚合）：

- `ENVELOPE_PARSE_ERROR`：消息文件不是合法 JSON
- `SCHEMA_INVALID`：JSON schema 校验失败
- `SCHEMA_VERSION_UNSUPPORTED`：`schema_version` 不受支持（当前仅支持 `1.0`）
- `UNSUPPORTED_MESSAGE_TYPE`：`envelope.type` 不支持
- `MESSAGE_ID_REUSED_WITH_DIFFERENT_PAYLOAD`：同 `message_id` 不同内容（禁止）
- `ROUTING_NO_TARGET`：DAG deliver_to 为空/无法匹配
- `TARGET_AGENT_NOT_FOUND`：目标 agent 目录不存在
- `MISSING_PAYLOAD`：artifact payload 文件缺失
- `UNHANDLED_EXCEPTION`：实现缺陷（必须尽快修复）
- `HUMAN_REQUEST_SCHEMA_INVALID`：human_intervention_request schema 校验失败
- `HUMAN_RESPONSE_SCHEMA_INVALID`：human_intervention_response schema 校验失败
- `HUMAN_RESPONSE_MISSING_DELIVER_TO`：response.provided_files 缺少 `deliver_to_agent_id`
- `HUMAN_REQUEST_ID_REUSED_WITH_DIFFERENT_CONTENT`：同 request_id 不同内容（禁止）
- `HUMAN_RESPONSE_ID_REUSED_WITH_DIFFERENT_CONTENT`：同 request_id 不同内容（禁止）

Monitor 的典型告警：
- `COMMAND_ACK_TIMEOUT`：ACK=CONSUMED 超过 `timeout*2` 仍无终态 ACK
- `COMMAND_ARCHIVE_INCONSISTENT`：命令归档 envelope 与 payload.command 字段不一致
- `PLAN_STATUS_AGGREGATION_FAILED`：plan_status 汇总失败

## Pytest

- 集成：构造无法匹配 DAG deliver_to 的产物（deliver_to 为空）→ 进入 deadletter + alert，且 deliveries.jsonl 记录 `DEADLETTERED`
- 集成：不支持 schema_version → deadletter + alert（`SCHEMA_VERSION_UNSUPPORTED`）
- 集成：消息 JSON 解析失败 → deadletter + alert（`ENVELOPE_PARSE_ERROR`）
