# 04 系统路由投递与去重模块（Router）

## 目标

系统进程扫描所有 agent outbox，执行：
- 发现新消息（payload + envelope）
- 校验 schema（必要时）
- 计算投递目标：以“当前阶段 DAG”（Meta-DAG/Business-DAG）为唯一执行路由来源
- 原子投递到目标 inbox
- 去重：`message_id` + `sha256`（`idempotency_key` 仅用于审计与可读关联）
- 记录 `deliveries.jsonl`

## “payload + envelope”的投递原子性（必须写死）

任意一条消息如果包含 payload 文件（例如 envelope 的 `payload.files[]` 指向的文件），Router 投递必须遵循：
- **先投递 payload 文件**（逐个 tmp→rename）
- **最后投递 envelope 文件**（tmp→rename）

原因：消费方只 claim/解析 `*.msg.json`，因此只要保证 envelope 最后出现，就不会出现“读到 envelope 但 payload 文件尚未到齐”的半写入状态。

约束（避免分叉）：
- 消费方不得把 inbox 根目录当作“长期输入仓库”；payload 文件仅作为“随 envelope 同步到达的附件”，应尽快归档到 workspace（见 `doc/develop/05_agent_heartbeat_and_dispatch.md`）。

## 模块边界

- 输入：agents_root、system_runtime 路径、投递策略（poll interval）
- 输出：inbox 文件、deliveries.jsonl 追加、DLQ/alert（异常）

## 关键判定

- 无法从 DAG 计算投递目标（deliver_to 为空且 routing_rules 未命中）：DLQ + alert（ROUTING_NO_TARGET）
- schema_version 不支持：DLQ + alert
- 目标 agent 不存在：DLQ + alert
- 命令消息字段不一致（envelope 顶层与 payload.command 冲突）：DLQ + alert（COMMAND_ENVELOPE_MISMATCH）
- 命令被更高版本覆盖（同 plan_id+task_id 存在更大 command_seq）：不投递，deliveries.jsonl 记录 `SKIPPED_SUPERSEDED`
- message_id 重用但内容不同（同 message_id 不同 sha256）：DLQ + alert（MESSAGE_ID_REUSED_WITH_DIFFERENT_PAYLOAD）
- 命令序号缺失或无法校验（缺 command_seq / command_id 不符合格式 / command_seq 与 command_id 不一致）：DLQ + alert（COMMAND_SEQ_MISSING / COMMAND_SEQ_INVALID_FORMAT / COMMAND_SEQ_MISMATCH）
- 命令引用的 DAG 版本不一致（dag_ref.sha256 != active_dag_ref.task_dag_sha256）：DLQ + alert（COMMAND_DAG_MISMATCH）
- 命令ID与task不匹配（command_id 的 task 段 != payload.command.task_id）：DLQ + alert（COMMAND_TASK_MISMATCH）

## 去重键口径（必须写死）

- 主去重键：`message_id + sha256`
- 同 `message_id` 但 `sha256` 不同：一律视为重放/篡改/bug，进入 DLQ + alert（MESSAGE_ID_REUSED_WITH_DIFFERENT_PAYLOAD）
- `idempotency_key`：仅作为审计与可读关联（不参与主去重键），避免“双口径去重”导致行为分叉

补充：`created_at` 仅用于审计/展示，不作为去重/排序/兜底依据（避免时间源不一致引入非确定性）。

实现口径补充（MVP 写死）：
- 这里的 `sha256` 指 **envelope 文件本体** 的内容哈希（建议写入 `deliveries.jsonl.envelope_sha256`，模板/Schema：`doc/rule/templates/delivery_log_entry.json`）。
- payload 文件各自的 sha256 仍记录在 `payload.files[].sha256`，用于完整性校验与输入归档冲突判定。

## 与回放（DLQ replay）的关系（必须写死）

为避免“主去重键”阻断必要的 DLQ 回放，Router 的去重判定必须区分：
- **重复投递（应跳过）**：同一 `(message_id + sha256)` 已出现过 `status=DELIVERED`（或已写入目标 inbox 的可证据状态）→ `SKIPPED_DUPLICATE`。
- **失败/死信后的回放（允许重试）**：此前仅出现过 `status=FAILED/DEADLETTERED` 的记录 → 允许再次尝试投递（delivery_id 必须变化），并写入新的一行 deliveries 记录。

“重新执行一次任务”不是回放：应生成新的 `message_id`（并按需要生成新的 `command_id/command_seq`），见 `doc/rule/templates/replay_procedure.md`。

## ACK / task_state 的处理（避免路由分叉）

- `ack_<message_id>.json`、`task_state_<task_id>.json` 不参与 DAG 路由投递（它们不是业务产物 deliver_to）。
- 系统程序可按 PR-024 以“跨目录采集”的方式收集它们，用于 Monitor/Dashboard 端到端视图（无需把 ACK 当成一条需要路由的消息）。

同类控制面文件（不走 DAG 路由）还包括：
- `alert.json`：系统程序收集并归档到 `system_runtime/alerts/<plan_id>/`（见 PR-024 模板）。
- `human_intervention_request.json`：系统程序收集并投递到 `agent_human_gateway`（见 PR-025；由 Human Gateway 产出 `human_intervention_response.json` 回流到系统）。

## DAG 驱动投递（命令与产物）

- 命令投递（方案B）：以“当前阶段 DAG”为准，把“命令消息”`cmd_*.msg.json`（envelope `type=command`）投递到 `nodes[].assigned_agent_id` 对应的 `inbox/<plan_id>/`。
- 产物投递：根据产物的 envelope 中的 `task_id` + `output_name` 定位到 DAG 的 `nodes[].outputs[]`，取 `deliver_to[]` 为目标；若缺失则按 `routing_rules` 兜底。

## “当前阶段 DAG”的权威口径（避免 Meta/Business 分叉）

Router/Monitor/Dashboard 必须共享同一口径的“当前阶段 DAG”：
- 优先读取：`system_runtime/plans/<plan_id>/active_dag_ref.json`（模板：`doc/rule/templates/active_dag_ref.json`）
- 指针中的 `task_dag_sha256` 必须与 `system_runtime/plans/<plan_id>/task_dag.json` 内容一致（不一致视为系统异常，告警并暂停投递该 plan）
- 若指针不存在（兼容早期/迁移期）：默认 `task_dag.json` 为当前 DAG，但应记录审计警告

切换阶段（meta→business）时的原子性要求（MVP 必须写死）：
- 先写入 `dag_history/`（归档旧 DAG）
- 再原子更新 `task_dag.json`（tmp→rename）
- 最后原子更新 `active_dag_ref.json`（tmp→rename），确保“指针指向的 DAG 一定可读且一致”

约束：
- envelope 的 `routing.intended_recipients` 不参与路由（仅调试/审计提示）；路由唯一来源是 DAG 的 `deliver_to/routing_rules`。
- 产物必须可被定位到“哪个 task 的哪个 output”（否则无法从 DAG 计算 deliver_to → DLQ + alert）。

## 命令绑定与来源（避免“找不到对应 cmd”的缺口）

为避免出现“DAG 说要投递命令，但系统不知道 cmd_*.msg.json 在哪里”的实现分叉，MVP 统一如下：

- 命令使用 message_envelope 运输：`cmd_*.msg.json`（`type=command`，`payload.command` 为具体命令对象）。
- `cmd_*.msg.json` 的生成者是规划者/控制面角色（例如：Meta-DAG 中的规划任务、评审协调任务）。
- 生成者把 `cmd_*.msg.json` 写入自己的 `outbox/<plan_id>/`（和其它控制面产物一致）。
- Router 在扫描 outbox 时识别 `cmd_*.msg.json`：
  - 解析 `message_id/plan_id` 并校验 envelope schema
  - 从 `payload.command` 解析 `task_id/command_id`（必须具备）
  - 强制一致性校验（MVP 必须写死）：
    - `envelope.plan_id == payload.command.plan_id`
    - `envelope.task_id == payload.command.task_id`
    - `envelope.command_id == payload.command.command_id`
    - 不一致 → 不投递，进入 DLQ + alert（COMMAND_ENVELOPE_MISMATCH）
  - 强制 command_seq 校验（MVP 必须写死）：
    - 命令必须包含 `payload.command.command_seq`
    - `payload.command.command_id` 必须匹配 `^cmd_.+_[0-9]{3,}$`
    - `payload.command.command_seq` 必须等于 `command_id` 最末尾的数字序号（从右侧最后一个 `_` 之后解析为整数）
    - 不满足 → DLQ + alert（COMMAND_SEQ_MISSING / COMMAND_SEQ_INVALID_FORMAT / COMMAND_SEQ_MISMATCH）
  - 强制 command_id↔task_id 校验（MVP 必须写死）：
    - `payload.command.command_id` 必须形如 `cmd_<task_id>_<seq>`
    - 解析出的 `<task_id>` 必须等于 `payload.command.task_id`
    - 不满足 → DLQ + alert（COMMAND_TASK_MISMATCH）
  - 用 `task_id` 在“当前阶段 DAG”中定位节点，取 `assigned_agent_id` 作为唯一投递目标
  - 旧命令丢弃（MVP 必须写死，Router 侧处理）：
    - supersede 只在同一 DAG 版本内成立：仅当 `payload.command.dag_ref.sha256 == active_dag_ref.task_dag_sha256` 时才参与覆盖比较；不一致 → DLQ + alert（COMMAND_DAG_MISMATCH）
    - 跨轮一致性（避免“旧命令先进入 inbox”）：投递前应以 `system_runtime/plans/<plan_id>/commands/` 归档区为准，查找该 `task_id` 的最大 `command_seq`；若当前命令不是最大，则直接 `SKIPPED_SUPERSEDED`（不投递）
    - 对同一个 `(plan_id, task_id)`，若本轮扫描到多条命令消息，则只投递 `command_seq` 最大的一条
    - 被丢弃的旧命令：不投递到 inbox；仍要写 `deliveries.jsonl status=SKIPPED_SUPERSEDED skip_reason=SUPERSEDED_BY_NEWER_COMMAND`，并补齐：
      - `superseded=true`
      - `superseded_by_message_id`
      - `superseded_by_command_id`
      - `superseded_by_command_seq`
  - 通过去重后投递到目标 `inbox/<plan_id>/`
  - 同时把命令原件归档到 `system_runtime/plans/<plan_id>/commands/`（见 PR-024），便于审计/重放

可选但推荐：
- 命令内携带 `dag_ref.sha256`（MVP 现已要求），Router 在投递前校验与当前 `active_dag_ref.task_dag_sha256` 一致；不一致则进入 DLQ + alert（避免“旧命令跑在新DAG上”）。

## 投递日志字段（Dashboard/Monitor 依赖）

为支持 Dashboard 按 `task_id/command_id/output_name` 过滤，Router 写入 `deliveries.jsonl` 时应尽量补齐：
- `task_id`：来自 envelope 顶层或可从 `payload.command.task_id` 推导
- `command_id`：对命令消息来自 `payload.command.command_id`；对产物消息来自 envelope 顶层 `command_id`（若有）
- `output_name`：对产物来自 envelope `output_name`

## Pytest

- 集成：tmp 目录下创建 agentA/outbox 写入消息，router 投递到 agentB/inbox
- 集成：重复消息（同 message_id+sha256）只投递一次，deliveries.jsonl 记录 SKIPPED_DUPLICATE
- 集成：同一 plan_id+task_id 的旧命令消息不投递，deliveries.jsonl 记录 SKIPPED_SUPERSEDED
- 集成：deliver_to 多目标投递到多个 inbox
