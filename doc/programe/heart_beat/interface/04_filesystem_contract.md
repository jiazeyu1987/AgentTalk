# 04 文件系统接口（inbox/outbox/workspace）

Heartbeat 的“外部接口”本质是它读写的文件与目录（文件即消息）。

## 输入（inbox）

- `agents/<agent_id>/inbox/<plan_id>/` 根目录
  - 只处理 `*.msg.json`
  - payload 文件必须先到、envelope 必须最后到

## 输出（outbox）

- `agents/<agent_id>/outbox/<plan_id>/ack_<message_id>.json`
- `agents/<agent_id>/outbox/<plan_id>/task_state_<task_id>.json`（推荐）
- `agents/<agent_id>/outbox/<plan_id>/human_intervention_request_<request_id>.json`（等待输入超时必需）
- `agents/<agent_id>/outbox/<plan_id>/alert_<alert_id>.json`（可选）

## workspace

- 输入归档：`agents/<agent_id>/workspace/<plan_id>/inputs/<task_id>/<output_name>/...`
- 输入索引：`agents/<agent_id>/workspace/<plan_id>/inputs/input_index.json`

## Pytest

- `tests/test_heartbeat.py` 覆盖：artifact 归档、冲突、payload 收尾、ACK/阻塞恢复等

