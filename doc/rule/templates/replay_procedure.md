# Replay Procedure（死信回放/重放流程）

本文件定义“死信（DLQ）如何回放”的最小流程，保证可审计、可幂等、可控。

约束：
- Agent之间不跨目录读写（PR-003）
- 交互仅通过文件（PR-001）
- 系统路由程序负责跨目录投递（PR-024）

## 1. 什么时候需要回放

典型场景：
- schema_version不兼容 → 升级后需要回放
- 投递目标缺失（ROUTING_NO_TARGET）→ 修正DAG/路由规则后回放
- 消费方临时故障/未启动 → 恢复后回放（如果已进入DLQ）

## 2. 回放原则（必须）

- **不改变message_id**：回放仍使用原 `message_id`，保证端到端可追溯。
- **幂等优先**：系统路由以 `message_id + sha256` 为主去重键；回放必须是“显式动作”，且只用于把“此前未成功投递/未成功消费”的同一内容重新投递（回放不应导致重复执行）。
- **可审计**：每次回放都要写入投递日志（delivery_id不同）与回放记录。

补充（避免语义分叉）：
- 如果你希望“同一任务重新执行一次”（而不是重试投递/重试消费），应生成**新的** `message_id`（并按需要生成新的 `command_id/command_seq`），而不是复用旧 `message_id`。

## 3. 回放步骤（系统侧）

1. 人工/自动化工具选定 `system_runtime/deadletter/<plan_id>/` 中的条目
2. 修复原因：
   - 更新对应Schema/代码
   - 或修正 `task_dag.json`（路由）
   - 或补齐缺失字段/文件
3. 生成一条回放请求记录（推荐文件）：`system_runtime/plans/<plan_id>/replay_requests.jsonl`
   - 包含 deadletter_id、message_id、原因、操作者、时间
4. 系统路由程序执行回放：
   - 重新计算投递目标（见 `routing_priority.md`）
   - 按原子投递协议复制到目标 `inbox/<plan_id>/`
   - 写入delivery日志（新delivery_id，引用原message_id）
5. 监控等待ACK（可选但推荐）

## 4. 回放步骤（Agent侧）

Agent侧不直接操作系统DLQ。若Agent自己的 `inbox/<plan_id>/.deadletter/` 有条目：

- 推荐由系统程序收集并统一搬运到 `system_runtime/deadletter/<plan_id>/` 再走系统回放流程

## 5. 回放的停止条件

- 同一 message_id 回放次数超过阈值（默认3）→ 只告警不再自动回放
- 若回放后仍持续FAILED/无ACK → 升级为人工介入

