# 12 可观测与追溯模块

## 目标

最小追溯闭环：
- router：deliveries.jsonl
- agent：status_heartbeat.json（自报）→ system_runtime/agent_status（系统汇总）
- task：workspace trace（inputs/input_index.json + outbox 产物 + task_state/ACK）
- 结论：decision_record（system_runtime/plans/<plan_id>/decisions/）与 release_manifest（system_runtime/plans/<plan_id>/release_manifest.json）
- 异常：alerts/deadletter（system_runtime/{alerts,deadletter}/<plan_id>/）

## Dashboard 的权威数据源（MVP 约束）

为符合隔离原则并避免 Dashboard 直接读取各 Agent 私有目录，规定：
- Dashboard/外部可视化只读取 `system_runtime/` 下的汇总文件。
- 系统监控程序负责生成 `system_runtime/agent_status/<agent_id>.json` 作为 Agent 状态快照的权威来源。
  - 实现约定（MVP）：Monitor 每次 run_once 扫描 `agents/<agent_id>/status_heartbeat.json`，校验后写入 `system_runtime/agent_status/<agent_id>.json`，并附加 `collected_at` 字段。

## Pytest

- 集成：Monitor 生成 `system_runtime/agent_status/<agent_id>.json`（来自 agent 的 status_heartbeat）
- 集成：E2E 跑完后，断言关键追溯文件存在且包含 `plan_id/message_id`（deliveries/acks/decisions/releases/alerts/deadletter）
