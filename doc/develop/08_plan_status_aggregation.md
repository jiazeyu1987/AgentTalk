# 08 plan_status 汇总模块（Monitor）

## 目标

系统监控汇总：
- 读取 DAG/plan_manifest（system_runtime/plans/<plan_id>/）
- 读取 deliveries.jsonl、ACK、task_state（如有）
- 输出 plan_status.json（含 blocked_summary、tasks 状态）

补充：为避免 Meta-DAG / Business-DAG 口径分叉，Monitor 应优先读取 `system_runtime/plans/<plan_id>/active_dag_ref.json` 作为当前阶段DAG指针（见 `doc/rule/templates/active_dag_ref.json`）。

## 判定职责边界（必须写死，避免系统“自作主张”）

Monitor 只负责**汇总与推断状态**，不负责产出业务结论文件：
- Monitor 可以把 task 标记为 `BLOCKED_WAITING_REVIEW/HUMAN/INPUT`，并发出 alert
- Monitor 不应在超时后自动产出“评审通过/发布通过”等结论文件

业务结论文件必须由对应单职责协调员产出：
- 评审结论：Review Coordinator 产出（例如汇总版 `review_result.json` 或 DAG 场景的汇总版 `dag_review_result.json`）
- 发布结论：Release Coordinator 产出 `release_manifest.json decision=APPROVE|REJECT`
- 人类决策：Human Gateway 产出 `human_intervention_response.json`

推荐统一结论落盘（MVP 强制）：
- 协调员必须额外产出 `decision_record.json`（模板：`doc/rule/templates/decision_record.json`），供 Monitor/Dashboard 统一展示与审计。
- 系统程序应汇总归档到 `system_runtime/plans/<plan_id>/decisions/`（见 PR-024），Dashboard/Monitor 以该目录为权威源。

## 状态判定优先级（避免“RUNNING/CONSUMED”分叉）

为支持 Dashboard/告警对“当前正在工作”的一致判定，建议状态来源优先级如下（高→低）：

1) `task_state_<task_id>.json`（Agent 主动写的任务状态，若存在则优先）
2) ACK（`ack_<message_id>.json` 的 CONSUMED/SUCCEEDED/FAILED；优先读取 `system_runtime/plans/<plan_id>/acks/` 的归档）
3) deliveries.jsonl（仅用于推断“已投递但未被消费/处理中”）

推荐推断规则（MVP 最小）：
- `RUNNING`：存在 ACK=CONSUMED 且尚无该消息对应的终态 ACK（SUCCEEDED/FAILED），并且未超过命令 timeout 的合理倍数（超时应触发告警）
- `BLOCKED_WAITING_INPUT`：命令存在且 required_inputs 不满足，且 wait_for_inputs=true（可从 agent 的 task_state 或命令执行记录推断）
- `READY`：依赖满足且输入满足（基于 DAG + deliveries/文件存在判定）

备注（MVP 实现约束）：
- Monitor 目前只在“缺输入且 wait_for_inputs=true”时标记 `BLOCKED_WAITING_INPUT`；`BLOCKED_WAITING_REVIEW/HUMAN` 需要依赖协调员/人类网关的结论文件（如 `decision_record.json`、`human_intervention_response.json`）才能稳定推断，后续再补齐。

投递状态过滤（避免误判）：
- `deliveries.status=SKIPPED_*` 的记录不得被当作“已投递”

### 超时告警（MVP 强制）

- 当 `ACK.status=CONSUMED` 且（`now - consumed_at`）超过 `payload.command.timeout * 2`：
  - Monitor 仍保持任务 `state=RUNNING`
  - 但必须在 `tasks[].blocking` 标记 `reason=TIMEOUT`
  - 同时写入告警文件到 `system_runtime/alerts/<plan_id>/`：
    - `alert.type=COMMAND_ACK_TIMEOUT`

## 方案B：命令链路以 message_id 为唯一ID（必须补齐映射）

当命令使用 message_envelope 投递（`cmd_*.msg.json`，`type=command`）时：
- ACK 只认 `message_id`，所以 Monitor 必须能把 `message_id -> task_id` 映射出来。

MVP 统一做法（推荐优先级）：
1) 优先从 `deliveries.jsonl` 读取 `task_id/command_id`（Router 投递时从 envelope 提取写入，见 `delivery_log_entry.schema.json`）
2) 若历史 delivery 缺字段，则从 `system_runtime/plans/<plan_id>/commands/` 归档的命令消息中解析 `payload.command.task_id`

一致性约束（避免分叉）：
- 若归档命令消息存在 `envelope.task_id/command_id`，必须与 `payload.command.task_id/command_id` 一致；不一致视为数据损坏，应告警并停止依赖该消息做状态推断。
  - 告警写入：`system_runtime/alerts/<plan_id>/alert_*.json`，`alert.type=COMMAND_ARCHIVE_INCONSISTENT`

## Pytest

- 集成：构造 2-task DAG，模拟上游完成文件出现 → 下游 READY
- 集成：缺输入 → BLOCKED_WAITING_INPUT
