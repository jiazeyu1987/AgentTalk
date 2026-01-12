# 固定小DAG（Meta-DAG）：用于生成“大DAG”的流程

本文把我们讨论的“在大DAG产生之前，先跑一个固定的小DAG来生成大DAG”固化为可复用的文档约定。

目标：
- 用一个结构稳定、可审计、可阻塞的 **Meta-DAG** 处理“澄清→需求成稿→生成大DAG→多人多轮评审→放行”。
- 大DAG（业务DAG）只在 Meta-DAG 放行后才允许进入执行与发布门禁链。

---

## 1. 概念定义

### 1.1 Meta-DAG（固定小DAG）

Meta-DAG 是一个固定流程（可复用模板），用于把“用户一句话”变成“可执行的大DAG”：
- 澄清收集（各角色输出澄清问题清单）
- Human Gateway 回填外部材料/决策
- 需求成稿（PM/策划输出 requirements/acceptance）
- 生成大DAG（DAG起草员）
- 多人多轮评审与修订（评审协调员 + reviewers + 修订员）
- 产出放行证据（通过才允许投递执行命令/进入发布门禁）

### 1.2 Business-DAG（大DAG）

Business-DAG 是项目特定的执行计划（开发/测试/发布等任务的 DAG），由 Meta-DAG 产出并放行：
- 文件示例：`task_dag.json`（v1.1）
- 只在“DAG评审放行证据”存在时才可投递执行命令

---

## 2. 固定角色（推荐）

Meta-DAG 建议固定使用以下单职责角色（每个 Agent 一份提示词）：

- `agent_general_manager`：编排入口（接收用户请求、触发Meta-DAG启动）
- `agent_dag_review_coordinator`：评审协调员（发起评审轮次、收集结果、判定通过/返工/终止）
- `agent_dag_drafter`：DAG起草员（只生成大DAG初稿）
- `agent_dag_reviser`：DAG修订员（只根据评审意见改大DAG）
- Reviewer 角色（并行、多名、都视为必需评审者）：
  - `agent_engineering_manager`（工程/架构）
  - `agent_game_design_manager`（玩法/范围）
  - `agent_qa_manager`（测试/验收）
  - `agent_security_manager`（安全/合规）
- 需求制定角色（产出 requirements/acceptance）：
  - `agent_product_manager` / `agent_game_designer`
- `agent_human_gateway`：人类网关（外部材料/标准/审批/风险接受）

说明：
- Reviewer 一旦在本轮被纳入即为“必需评审者”。
- 超时未收齐默认可以“通过”（策略选择），但必须记录缺席者并告警/补评。

---

## 3. 路由与投递规则（统一）

### 3.1 总原则

- 所有跨 Agent 投递都通过系统路由程序完成（PR-024）。
- “发给谁”必须可审计、可追溯：系统路由程序在执行层面只依赖**当前阶段的 DAG** 进行投递。
  - Meta-DAG 阶段：使用 Meta-DAG 的 `outputs[].deliver_to` / `routing_rules` 路由澄清文件、评审结果、放行证据等控制面产物。
  - Business-DAG 阶段：使用 Business-DAG 的 `outputs[].deliver_to` / `routing_rules` 路由业务产物。
  - 命令投递本身也由 DAG 驱动（方案B）：将每个 task 的命令消息 `cmd_*.msg.json`（envelope `type=command`）投递到 `assigned_agent_id` 对应的 agent inbox（链路ID为 `message_id`）。

补充（推荐写死）：为避免 Meta-DAG/Business-DAG 的“当前阶段”口径在 Router/Monitor/Dashboard 之间分叉，系统程序应维护：
- `system_runtime/plans/<plan_id>/active_dag_ref.json`（`dag_kind=meta|business` + `task_dag_sha256/revision`）
并在切换阶段（meta→business）时先归档旧 DAG 到 `dag_history/`，再原子更新 `task_dag.json` 与 `active_dag_ref.json`。

### 3.2 关键点：避免跨项目混线

当同一个 Agent 同时处理多个项目时，必须依赖：
- `plan_id` 隔离目录（`inbox/<plan_id>/`、`outbox/<plan_id>/`）
- message/envelope 中携带 `plan_id`、`task_id`、`command_id`/`idempotency_key`、`sha256`
以保证系统路由能把产物投递到正确的目标集合。

---

## 4. Meta-DAG 的最小步骤（阶段化）

下面按“阶段”描述 Meta-DAG 的固定闭环。每个阶段都应有明确的输入文件、输出文件、阻塞条件与责任角色。

### Phase A：一次性澄清（Clarify）

1) GM 下发澄清收集命令（`cmd_collect_clarification_*`）给各角色（策划/PM/架构/QA/安全等）
- 输入：`user_request.*`（以及可选上下文）
- 输出：`clarification_questions_<role>.*`
- 投递：由 Meta-DAG 输出的 `deliver_to` 定义（例如投递给评审协调员/GM/需求制定角色）

2) 汇总后发起 Human Gateway 澄清请求
- 输出：`human_intervention_request.json type=CLARIFY`
- 回填：`human_intervention_response.json` + 附件

### Phase B：需求成稿（Requirements）

由需求制定角色生成：
- `requirements.md`（或 `.json`）
- `acceptance_criteria.md`
并投递给 DAG 起草员与评审协调员（可多目标）。

### Phase C：生成大DAG初稿（Draft Business-DAG）

由 `agent_dag_drafter` 生成：
- `task_dag.json`（v1.1）
- `plan_manifest.json`

### Phase D：多人多轮评审与修订（Review & Revise, Round-N）

1) 评审协调员发起本轮评审命令（每个 reviewer 一份）
- required_inputs：`task_dag.json`、`plan_manifest.json`、`requirements.*` 等
- 评审结果的 deliver_to：评审协调员 + DAG修订员 + GM

2) reviewer 产出 `dag_review_result.json`
- 必须引用被评审的 DAG 版本（revision + sha256）
- 评分必须按模板（包含 criteria_version 与 score_breakdown），避免自由发挥

3) 评审协调员汇总判定
- 触发条件：收齐 / 超时 / 版本不一致
- 通过：产出“放行结论（汇总版 dag_review_result.json）”
- 不通过：产出 `cmd_revise_dag.json` 给 DAG 修订员，并进入下一轮
- 轮次上限：超限必须走 Human Gateway 做范围取舍（downscope/stop）
 - 评分要求：reviewer 必须按评分模板产出 `criteria_version` 与分项得分（见下文模板约定），避免自由发挥

### Phase E：DAG 放行（Approve）

Meta-DAG 的最终输出是“大DAG放行证据”：
- 建议：评审协调员产出“汇总版 `dag_review_result.json`（decision=APPROVE）”
- 后续执行命令的投递必须以该放行证据为前提条件

---

## 5. 关键约束（必须遵守）

- 未通过 DAG 评审不得投递执行命令（这是强制门禁）。
- 缺材料/缺标准不得编造：应阻塞并发起 Human Gateway 请求（PR-025）。
- 多轮评审必须版本锁定（revision + sha256），否则评审结果不可合并。
- 评分必须按模板量表（criteria_version + score_breakdown），否则分数不可用于阈值/分支。

---

## 6. 与已有文档的关系

- 通用“生成→评审→修订→发布”流程：`doc/process/iterative_review_to_release_flow.md`
- Mario 案例（大DAG评审与发布）：`doc/case/mario/dag_review_and_release_flow.md`
- DAG v1.1 语义：`doc/DAG/semantics.md`
