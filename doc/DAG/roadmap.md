# DAG（实现级）详细规划

目标：把当前 `doc/rule` 中的 DAG 从“依赖+路由描述”补齐到“可无歧义实现执行器/路由器/监控器”的程度，并与现有模板、JSON Schema、发布门禁、Human Gateway 自洽。

## 0. 当前基础（已有）

- 规则层（当前运行约定）：`doc/rule/`
- DAG实现级语义：`doc/DAG/semantics.md`
- DAG v1.1 Schema：`doc/DAG/schemas/task_dag.v1.1.schema.json`
- DAG v1.1 示例：`doc/DAG/examples/task_dag.v1.1.example.json`

不足：DAG v1.1 的实现级语义已在 `doc/DAG/` 明确，但仍缺少“系统汇总状态（plan_status）”、“重规划请求（replan_request）”、“delivered_at 取值来源”等实现级配套模板与schema；同时还需要将 v1.1 回灌到 `doc/rule` 以避免实现分叉。

## 1. 规划原则（不变约束）

- 每个Agent只读写自己的文件夹（PR-003）
- 交互仅通过文件（PR-001）
- 跨Agent投递由系统程序完成（PR-024）
- 通过模板+JSON Schema 强制结构一致
- 可追溯：每个关键动作都能在 `deliveries.jsonl`/ACK/alerts/DLQ 中找到证据

## 2. 需要补齐的“实现级语义”

### 2.1 DAG节点状态机（必须）

为每个 `task_id` 定义最小状态机与状态落盘位置：

- `PENDING`：等待前置任务/输入
- `READY`：输入已满足，可执行
- `RUNNING`：执行中
- `BLOCKED_WAITING_INPUT`：等待输入文件到达（wait_for_inputs=true）
- `BLOCKED_WAITING_REVIEW`：等待评审/验收门禁（DAG评审、交付物验收、release gate）
- `FAILED`：失败（可重试/可返工/可终止）
- `SKIPPED`：按策略跳过（例如上游失败后下游skip）
- `COMPLETED`：完成（产出已生成并投递/归档）

状态来源与写入职责：
- Agent负责写自身任务的执行状态（建议写入 `outbox/<plan_id>/task_state_<task_id>.json` 或其workspace trace）
- 系统程序负责汇总到 `system_runtime/plans/<plan_id>/plan_status.json`

补齐动作（在 doc/DAG 下落盘为可复用模板）：
- `doc/DAG/templates/plan_status.json`
- `doc/DAG/schemas/plan_status.schema.json`

### 2.2 输入匹配与选择规则（必须）

目前 `required_inputs` 只是文件名列表，会出现同名多版本歧义。需要把“如何匹配/如何选取”写成硬规则：

建议增加 `inputs[]` 结构，支持：
- `name`：逻辑输入名（如 requirements）
- `selector`：
  - `by_file_name`：精确文件名
  - `by_glob`：通配（如 `feedback_*.json`）
  - `by_message_type`：按 message envelope 的 `type/subtype`
  - `by_artifact_name`：按输出名（如 `database_schema.json`）
- `pick_policy`：
  - `latest_by_delivered_at`
  - `first_seen`
  - `highest_score`（若存在验收/评分文件）
  - `by_sha256`（显式指定哈希）
- `required`：true/false

并规定：当 selector 命中多份时，必须按 `pick_policy` 确定唯一输入；无法唯一化则进入 `BLOCKED_WAITING_HUMAN`。

补齐动作（明确 delivered_at 来源与优先级）：
- `deliveries.jsonl` 的 `delivered_at` 作为权威来源（见 `delivery_log_entry`）
- 若缺失 delivered_at（异常场景），再使用 inbox 文件的 mtime 作为兜底

### 2.3 失败传播与跳过策略（必须）

为 DAG 增加可计算的 failure policy，避免“实现各自理解”：

建议每个节点支持：
- `on_dependency_failed`：`SKIP | BLOCK | FALLBACK | REPLAN_REQUEST`
- `max_reexecute_times`：默认继承 `plan_manifest.policies.max_reexecute_times`
- `reexecute_target`：默认是原assigned_agent_id，也可指定替代角色

系统程序在汇总状态时，必须能判定下游是否应自动SKIP/阻塞/触发Human Gateway/触发规划者重规划。

补齐动作（将 REPLAN_REQUEST 落盘为文件/路由）：
- `doc/DAG/templates/replan_request.json`
- `doc/DAG/schemas/replan_request.schema.json`

### 2.4 输出版本与幂等（必须）

输出字段需明确“重复产出”的处理语义：

建议在 `outputs[]` 增加：
- `idempotency_key`（已存在于模板，需强制）
- `versioning`：
  - `mode`：`immutable_by_message_id | overwrite_by_name | semver_tagged`
  - `conflict_policy`：`reject_duplicate | accept_duplicate_if_same_hash | keep_latest`
- `deliverable`：是否为最终交付物候选
- `acceptance`：验收要求（可引用门禁证据）

并规定：同一 `idempotency_key` 重复出现时，系统路由必须去重并记录 `SKIPPED_DUPLICATE`；若内容不同则进入DLQ并告警（避免“同键不同物”破坏可追溯）。

### 2.5 DAG评审关口（已引入，需强制化规则）

明确：在大任务/高风险任务中，DAG必须先 `APPROVE` 才允许投递执行命令或放开执行。

需要补齐：
- `plan_manifest` 中增加 `gates.dag_review.required=true` 与阈值
- `task_dag` 中标记 `review_gate=true`
- 系统程序将“未通过评审”归为 `BLOCKED_WAITING_REVIEW`

### 2.6 门禁证据链与Release（已引入，需与DAG挂钩）

现有 release gate 证据（build/deploy/smoke/e2e/security/release_manifest）需要与 DAG 的最终交付物绑定：

- `task_dag.outputs[].acceptance.evidence_required`：声明该输出需要哪些证据文件为PASS
- `plan_manifest.policies.release_gates_required`：项目级放行门禁
- 最终 “可交付版本” 以 `release_manifest.json decision=APPROVE` 为准

### 2.7 Human Gateway（已引入，需触发条件写死）

明确哪些情形必须触发 `human_intervention_request.json`：
- 输入无法唯一选择（多版本冲突）
- 缺少验收阈值/标准（criteria为空）
- 需要风险接受（security REJECT，但希望继续）
- 需要外部环境文件/凭据

## 3. 需要新增/修改的文件（文档与模板层）

建议新增/扩展：
- 在 `doc/DAG/` 下新增实现级模板+schema：
  - `doc/DAG/templates/plan_status.json` + `doc/DAG/schemas/plan_status.schema.json`
  - `doc/DAG/templates/replan_request.json` + `doc/DAG/schemas/replan_request.schema.json`
- 同步回灌到规则层（避免实现分叉）：
  - 将 v1.1 结构同步到 `doc/rule/templates/task_dag.json` 与 schema

## 4. 执行器/路由器应遵循的最小算法（实现约束）

### 4.1 路由器（系统程序）

对每个 outbox 新消息：
1. 校验 envelope/schema
2. 计算投递目标（先 outputs[].deliver_to，空则按 routing_rules first-match）
3. 去重：按 `message_id/idempotency_key + sha256`
4. 原子投递到目标 inbox
5. 写 `deliveries.jsonl`（delivery_log_entry）

### 4.2 执行器（Agent）

对每个 cmd：
1. 校验schema_version
2. 按 inputs/required_inputs 检查是否满足
3. 若满足→执行→写输出与message envelope到outbox
4. 若不满足且wait_for_inputs→BLOCKED_WAITING_INPUT
5. 若输入冲突/缺标准→触发Human Gateway请求

## 5. 分阶段落地步骤（可执行里程碑）

1. **定义状态机字段**：补 `plan_status.json` 模板+schema，明确状态写入职责与字段
2. **定义inputs selector**：扩展 `task_dag.json` 与 schema，确定 pick_policy 与冲突策略
3. **定义失败传播**：增加 `on_dependency_failed` 与 reexecute/skip/replan 规则
4. **定义输出版本/幂等**：强制 idempotency_key 与 duplicate policy
5. **更新评审模板**：DAG评审结果必须覆盖“输入闭合/路由完整/失败策略/门禁绑定”
6. **更新示例**：补齐成功/失败/冲突/人类介入的端到端目录快照
7. **一致性校验**：确保 `doc/DAG` 与 `doc/rule` 引用一致、schema覆盖、规则不冲突

## 6. 完成标准（Definition of Done）

- `task_dag.json` 在“依赖、输入匹配、路由、失败策略、版本策略、门禁绑定”六方面可计算、无歧义
- 存在 `plan_status.json` 且能表达每个task的状态与阻塞原因
- 存在对应 JSON Schema 并能自动校验
- examples 包含至少：成功、路由缺失DLQ、重复去重、多版本冲突触发Human Gateway
