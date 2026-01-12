# 14 前端查看工具（Web Dashboard Viewer）

目标：提供一个本地前端工具，用于查看：
- 当前所有节点（tasks/agents）的状态
- 文件流转历史（deliveries.jsonl + ACK）
- 当前正在工作的节点（RUNNING/CONSUMED 未完成）

## MVP 范围

**只读**仪表盘（不做任何写入/控制操作）：
- Plan 列表与详情（按 `system_runtime/plans/<plan_id>/`）
- Task 状态列表（来自 `plan_status.json`）
- Agent 状态列表（来自 `system_runtime/agent_status/<agent_id>.json`，由系统监控生成的权威快照）
- 投递历史时间线（来自 `deliveries.jsonl`，可按 message_id/task_id/filter）
- 当前阶段DAG信息（来自 `active_dag_ref.json`，用于显示 meta/business 阶段）
- 结论时间线（来自 `decision_record.json`，用于展示“谁在何时做了什么业务判定”）
- ACK 时间线（来自 `system_runtime/plans/<plan_id>/acks/` 的归档；用于判断 CONSUMED/SUCCEEDED/FAILED）
- 当前进行中工作：
  - task state = RUNNING
  - 或 deliveries=DELIVERED 但无 ACK SUCCEEDED/FAILED（推断处理中）

说明：Dashboard 的“投递历史”展示不依赖命令的 `send_to` 字段；投递目标由 Router 按 DAG 的 `deliver_to/routing_rules` 计算并记录到 deliveries.jsonl。

## 数据来源与接口

后端建议提供只读 API（Python）：
- `GET /api/plans`：列出 plan_id + updated_at + 简要统计
- `GET /api/plans/{plan_id}/status`：返回 `plan_status.json`
- `GET /api/plans/{plan_id}/deliveries`：分页返回 deliveries.jsonl
- `GET /api/plans/{plan_id}/decisions`：分页返回 `system_runtime/plans/<plan_id>/decisions/` 下的 decision_record
- `GET /api/plans/{plan_id}/acks`：分页返回 `system_runtime/plans/<plan_id>/acks/` 下的 `ack_<message_id>.json`
- `GET /api/plans/{plan_id}/release_manifest`：返回 `system_runtime/plans/<plan_id>/release_manifest.json`
- `GET /api/agents`：返回 agent_status 列表
- `GET /api/agents/{agent_id}`：返回单 agent 状态快照

MVP 允许直接读取本地文件系统（服务端读 system_runtime），不要求 DB。

## 前端页面（最小）

1) Plan 列表页
- 显示：plan_id、更新时间、完成/阻塞/运行任务数量

2) Plan 详情页
- Tasks 表格：task_id、assigned_agent、state、updated_at、blocking reason
- Deliveries 时间线：delivery_id、message_id、task_id、command_id、output_name、from/to、status、delivered_at、payload files
  - 过滤：默认隐藏 `status=SKIPPED_*`（可勾选显示审计信息，例如 SKIPPED_SUPERSEDED）
- Decisions 时间线：decision_id、decision_type、decision、decided_by、created_at、subject(ref_sha256/revision)、missing_participants、evidence_files

3) Agent 列表页
- agent_id、status、last_heartbeat、current_tasks、health

## 模块边界

- Dashboard 只负责“读取与展示”，不负责推进状态、不负责路由投递
- 所有数据以 system_runtime 为准，避免直接读各 Agent 私有 workspace（符合隔离原则）

## “当前正在工作”的判定口径（与 monitor 对齐）

Dashboard 对“正在工作”的展示必须优先使用 `plan_status.json.tasks[].state`：
- `RUNNING`：直接展示为“工作中”
- 若 `plan_status` 不含 RUNNING（MVP 早期），可用 deliveries+ACK 做推断，但必须与 `doc/develop/08_plan_status_aggregation.md` 的优先级一致，避免前后端口径不一致。

## Pytest（后端）

为 Dashboard 后端提供可验证的 pytest：
- 单测：API 序列化（plan_status/deliveries/agent_status）字段完整且类型正确
- 集成：在 `tmp_path` 构造 `system_runtime/` 目录树与示例 jsonl/json，启动测试 client：
  - `/api/plans` 返回包含 plan_id
  - `/api/plans/{plan_id}/status` 返回 tasks 数组
  - `/api/plans/{plan_id}/deliveries` 支持分页与过滤
  - `/api/plans/{plan_id}/decisions` 返回 decision_record 列表（按 created_at/decision_id 排序）
  - `/api/agents` 返回 agent 列表

前端建议也做最小 e2e（可选）：
- 使用 mock API 或静态 fixture 验证页面渲染不崩

## 安全与性能（MVP）

- 只读接口，默认绑定 localhost
- deliveries.jsonl 可能很大：必须分页/limit，避免一次性加载全量
- 支持按 plan_id/message_id/task_id 过滤

## 与 release_manifest 的展示口径（必须写死）

- “是否已发布/可交付”的权威判据：`release_manifest.json decision=APPROVE`
- `decision_record.json decision_type=RELEASE` 用于审计与时间线展示；若与 `release_manifest.json` 不一致，应在 UI 中标红告警（数据异常/流程违规）
