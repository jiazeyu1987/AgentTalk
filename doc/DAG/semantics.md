# DAG 执行语义（实现级规范）

本文件把 `doc/DAG/roadmap.md` 中列出的关键点（状态机、输入匹配、失败传播、版本幂等、门禁绑定）补齐为“可无歧义实现”的执行语义。

适用范围：
- 规划者（GM/规划角色）：生成 `task_dag.json` 与 `plan_manifest.json`
- 系统路由/监控程序：投递、去重、汇总状态、门禁判定、告警、DLQ、回放、Human Gateway
- 执行Agent：按命令执行、产出输出、写状态与证据

不变约束：
- 每个Agent只读写自己的文件夹
- 所有交互只通过文件传递

---

## 1. DAG 文件版本与向后兼容

本规范定义 DAG 的 `schema_version = 1.1`（在原先 v1.0 的基础上补齐运行期语义字段）。

- v1.0：支持 `nodes[].depends_on/required_inputs/outputs[].deliver_to` 与 `routing_rules`
- v1.1：新增/强化：`state`, `inputs[] selector`, `failure_policy`, `output versioning`, `gates`

未知版本处理建议沿用 `doc/rule/templates/schema_versioning.md`：
- 不支持的MAJOR → DLQ + alert
- 更高MINOR → 尝试解析，校验失败→DLQ + alert

---

## 2. 节点状态机（Task State Machine）

### 2.1 状态枚举（必须支持）

- `PENDING`：等待前置依赖满足
- `READY`：输入满足，可执行
- `RUNNING`：执行中
- `BLOCKED_WAITING_INPUT`：等待输入（例如 `wait_for_inputs=true` 且 inputs未满足）
- `BLOCKED_WAITING_REVIEW`：等待评审/验收/门禁结果（DAG评审、交付物验收、release gate）
- `BLOCKED_WAITING_HUMAN`：等待Human Gateway响应
- `FAILED`：本节点失败（可重试/可返工/终止由策略决定）
- `SKIPPED`：按策略跳过（例如依赖失败后跳过下游）
- `COMPLETED`：完成

### 2.2 状态数据结构（建议统一）

每个任务的当前状态应可被系统汇总（推荐写入计划状态文件 `plan_status.json`，详见 2.4）。

最小字段：
- `task_id`
- `state`
- `updated_at`
- `attempts.reexecute_count`
- `blocking.reason`（可选）
- `blocking.request_id`（若 BLOCKED_WAITING_HUMAN）

### 2.3 状态迁移规则（无歧义）

系统监控对每个task按以下判定更新 `plan_status`：

1. `PENDING` → `READY`：所有 `depends_on` 的状态满足（见 4. 失败传播），且输入可满足（见 3. 输入匹配）
2. `READY` → `RUNNING`：执行Agent开始处理对应 `cmd_*.json`（可由Agent写 `task_state` 或由ACK/日志推断）
3. `RUNNING` → `BLOCKED_WAITING_INPUT`：执行Agent发现输入缺失且 `wait_for_inputs=true`
4. `RUNNING` → `FAILED`：命令执行失败（含超时，见PR-010）
5. `RUNNING` → `COMPLETED`：任务输出按预期产生（至少一个 `outputs[].name` 对应的消息/文件出现且通过完整性校验），并触发投递/归档
6. 任何状态 → `BLOCKED_WAITING_REVIEW`：当该任务声明 `gates.required=true` 且尚无通过的 gate evidence
7. `BLOCKED_WAITING_*` → `READY`：阻塞条件解除（输入到达/评审通过/人类响应到达）

### 2.4 Plan 状态汇总（推荐新增，但本文仅定义语义）

系统监控应生成 `system_runtime/plans/<plan_id>/plan_status.json`，至少包含：
- `plan_id`, `schema_version`
- `tasks[]`（每个task的状态快照，包含2.2字段）
- `blocked_summary`（按原因分类：INPUT/REVIEW/HUMAN）
- `gates_summary`（门禁通过情况）

---

## 3. 输入匹配与选择（Input Selector Semantics）

v1.0 的 `required_inputs`（文件名列表）在大项目里会出现多版本冲突与歧义。v1.1 将输入定义为结构化 `inputs[]`。

### 3.1 inputs[] 结构（必须）

每个task的输入使用：
- `inputs[]`：结构化输入列表（v1.1）
- `required_inputs`：仅作为兼容字段（v1.0）；v1.1 若同时存在，以 `inputs[]` 为准

每个 input 的最小字段：
- `name`：逻辑输入名（如 `requirements`）
- `selector`：匹配规则（见3.2）
- `required`：是否必需
- `pick_policy`：多匹配时的选择策略（见3.3）

### 3.2 selector 支持集合（必须实现/必须约束）

推荐系统与Agent至少支持以下 selector 类型：

1. `by_file_name`：精确文件名
   - 示例：`{"type":"by_file_name","value":"requirements.md"}`
2. `by_glob`：通配匹配（glob语义）
   - 示例：`{"type":"by_glob","value":"feedback_*.json"}`
3. `by_output_name`：按 DAG 输出名匹配（语义上等价于“来自某上游输出”）
   - 示例：`{"type":"by_output_name","value":"database_schema.json"}`
4. `by_message_type`：按消息信封 `type/subtype` 匹配（需要 envelope）
   - 示例：`{"type":"by_message_type","type_value":"artifact","subtype_value":"db_schema"}`

### 3.3 pick_policy（必须）

当 selector 命中多份输入时，必须按 pick_policy 选取唯一输入：

- `latest_by_delivered_at`：选择 delivered_at 最新的
- `first_seen`：选择最先到达的
- `by_sha256`：显式指定 `sha256`（需要 selector 提供 allowed_hashes）

如果无法唯一化（缺 delivered_at、缺 hash、或多份并列），则：
- task 进入 `BLOCKED_WAITING_HUMAN`
- 生成 `human_intervention_request.json` 请求人选择或提供判定标准

### 3.5 delivered_at 的权威来源（必须）

为保证 `latest_by_delivered_at` 可计算，规定 delivered_at 的读取优先级：

1. **优先使用系统投递日志**：`system_runtime/plans/<plan_id>/deliveries.jsonl` 中对应 `message_id` 的 `delivered_at`
2. **兜底使用文件时间**：若delivery日志缺失（异常场景），使用目标 `inbox/<plan_id>/...` 的文件 mtime

不允许仅依赖“文件名排序”推断时间。

### 3.4 输入满足判定（must-have）

task 的输入满足条件：
- 对每个 `required=true` 的 input，都必须能选出唯一文件/消息
- 对 `required=false` 的 input，可缺失

---

## 4. 失败传播与跳过策略（Failure Propagation）

大型项目必须把“上游失败”如何影响下游写成可计算规则。v1.1 引入 `failure_policy`。

### 4.1 failure_policy 字段（必须）

每个 task 节点支持：

- `on_dependency_failed`：`SKIP | BLOCK | REPLAN_REQUEST | FALLBACK`
- `max_reexecute_times`：默认从 `plan_manifest.policies.max_reexecute_times` 继承
- `reexecute_target_agent_id`（可选）：默认是 `assigned_agent_id`
- `fallback_task_id`（当 FALLBACK 时使用，可选）

### 4.2 行为语义（必须）

当某依赖任务进入 `FAILED`：

- `SKIP`：下游任务进入 `SKIPPED`，并记录原因（依赖失败）
- `BLOCK`：下游任务进入 `BLOCKED_WAITING_REVIEW` 或 `BLOCKED_WAITING_HUMAN`（由策略决定），等待人工/规划者介入
- `REPLAN_REQUEST`：系统生成对规划者/GM 的“重规划请求”（可落为 `human_intervention_request` 或专门的 `replan_request`，后续可扩展）
- `REPLAN_REQUEST`：系统生成 `replan_request.json` 并投递给规划者角色；若规划者不可达，则转投 Human Gateway 请求人工决策
- `FALLBACK`：触发 `fallback_task_id` 进入可执行（具体触发方式可由规划者在DAG中提前布线）

---

## 5. 输出版本与幂等（Output Versioning & Idempotency）

### 5.1 output 字段（必须）

每个 `outputs[]` 建议包含：
- `name`：文件名/产物名
- `deliver_to[]`
- `deliverable`：是否最终交付物候选
- `idempotency_key`：幂等键（必须）
- `versioning`：
  - `mode`：`immutable_by_message_id | keep_latest | reject_on_change`
  - `conflict_policy`：`accept_duplicate_if_same_hash | deadletter_on_change`

### 5.2 语义（必须）

系统路由对同一 `idempotency_key` 的重复产物处理：

- 如果内容哈希相同：
  - 允许重复出现但应去重投递（记录 `SKIPPED_DUPLICATE`）
- 如果内容哈希不同：
  - 若 `versioning.mode=keep_latest`：可保留最新，并记录替换（仍需审计）
  - 否则：进入 DLQ + alert（避免“同键不同物”破坏可追溯）

建议默认：`reject_on_change + deadletter_on_change`（更安全，适合大项目）。

---

## 6. 门禁绑定（Review/Test/Release Gates Binding）

门禁分三类：

1. **DAG评审门禁**：`dag_review_result.json decision=APPROVE`
2. **交付物验收门禁**：`artifact_validation_result.json decision=PASS`
3. **发布门禁链**：build/deploy/smoke/e2e/security + `release_manifest.json decision=APPROVE`

### 6.1 gate 声明（推荐 v1.1 字段）

在 task 节点增加：

- `gates.required`：true/false
- `gates.evidence_required[]`：需要的证据文件名列表（例如 `artifact_validation_result.json`）
- `gates.thresholds`：阈值（例如 e2e min_score=80）

系统监控判定：当 `gates.required=true` 且证据未满足 → `BLOCKED_WAITING_REVIEW`。

### 6.2 plan级门禁

plan级门禁由 `plan_manifest.policies.release_gates_required[]` 声明；
最终放行以 `release_manifest.json decision=APPROVE` 为准。

---

## 7. 推荐的“最小实现接口”（实现者检查清单）

如果要实现 DAG 执行器/监控器，至少要实现：

- 能解析 v1.1 DAG + schema 校验
- 能计算 inputs satisfied（含 pick_policy，冲突触发 Human Gateway）
- 能按 failure_policy 推导下游状态
- 能按 gates/evidence 推导 BLOCKED_WAITING_REVIEW
- 能生成/更新 plan_status.json（汇总可观测）

模板参考（实现级）：
- `doc/DAG/templates/plan_status.json`
- `doc/DAG/templates/replan_request.json`

---

## 8. 与 doc/rule 的关系

本文件是“实现级语义”的集中说明；落地到规则体系时，应将 v1.1 字段同步到：
- `doc/rule/templates/task_dag.json` 与其 schema
- `doc/rule/templates/schemas/task_dag.schema.json`
- `doc/rule/templates/dag_review_result.json` 的检查项
- `doc/rule/templates/delivery_state_machine.md` 的完成/门禁判定
