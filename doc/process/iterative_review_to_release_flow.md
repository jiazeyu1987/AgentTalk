# 通用流程：方案生成 → 多人评审 → 方案修改（多轮）→ 最终发布

本文给出一个可复用的“方案类产物”通用闭环：从初稿生成，到多轮多人评审与修订，再到最终发布（APPROVE/REJECT）。
适用于：DAG 方案、技术设计方案、架构方案、验收方案、发布方案等。

补充：对于“先生成大DAG再执行”的体系，建议使用固定的 Meta-DAG 来生成并放行业务DAG，见：`doc/process/meta_dag_generate_execution_dag.md`。

核心目标：
- 单职责：每个 Agent 只做一件事（单提示词、可控）
- 可计算：何时进入下一步由规则决定（收齐/超时/阈值）
- 可审计：每轮评审对象、结论、修改都可落盘追溯
- 可阻塞：缺材料/缺标准时不“继续编”，走 Human Gateway

## 0) 角色划分（推荐最小集合）

1) **方案起草员**（Author/Drafter）
- 只负责从输入材料生成“方案初稿”。

2) **评审协调员**（Review Coordinator）
- 只负责发起评审、收集评审结果、按预定义规则给出“通过/返工/终止”判定。
- 不负责写方案内容、不负责写代码。

3) **评审经理/评审专家**（Reviewers，可并行多名）
- 只负责按模板评审并输出结构化评审结果（APPROVE/REVISE/REJECT + score + 建议）。

4) **方案修订员**（Reviser）
- 只负责根据评审意见修改方案（编辑型，强调“按意见改、不扩展范围”）。

5) **发布/门禁协调员**（Release Coordinator，可选但推荐）
- 只负责汇总门禁证据并产出最终发布决策文件（release manifest）。

6) **Human Gateway**
- 人类补齐外部材料/标准/审批/风险接受。

备注：如果希望更简化，也可以把“起草员+修订员”合并为同一 Agent（但会让提示词变复杂）。

---

## 1) 文件与目录约定（遵循 inbox/outbox）

### 1.1 基本约束
- Agent 只写自己的 `outbox/<plan_id>/`，只读自己的 `inbox/<plan_id>/`。
- 跨 Agent 投递由系统路由程序执行并记录投递日志（deliveries.jsonl）。
- 路由统一：跨 Agent 投递一律由**当前阶段的 DAG** 定义（Meta-DAG 或 Business-DAG）。
  - 对业务产物：使用 `nodes[].outputs[].deliver_to`（或 `routing_rules` 兜底）确定接收者集合。
  - 对命令投递（方案B）：使用 DAG 的 `nodes[].assigned_agent_id` 将命令消息 `cmd_*.msg.json`（envelope `type=command`）投递到对应执行者 inbox（链路唯一ID为 `message_id`）。
  - 这样路由只有一套来源（DAG），避免“命令一套、DAG一套”分叉。

### 1.2 关键产物（建议命名）

- 方案文件（被评审对象）：`proposal.json` / `proposal.md`
  - DAG 场景可为 `task_dag.json`
  - 技术设计可为 `design_spec.md`
- 评审请求命令：`review_request.cmd.json`
  - DAG 场景可复用 `dag_review_request.cmd.json`
- 评审结果：`review_result.json`
  - DAG 场景可复用 `dag_review_result.json`
- 修订请求命令：`revise_proposal.cmd.json`
- 放行/发布决策：`release_manifest.json`（或 `proposal_approval.json`，若你们希望把“放行证据”单独命名）
- 人类介入：`human_intervention_request.json` / `human_intervention_response.json`

### 1.3 评分必须按模板（避免自由发挥）

凡是 `score_required=true` 的评审/验收命令，Reviewer 的评分必须使用预先给定的“评分模板/量表”，输出应包含：
- `score`：总分（0-100）
- `score_breakdown`：分项得分（例如 A/B/C… 每项多少分、为何扣分）
- `criteria_version`：所用评分模板版本（便于审计）

评分模板的典型形式：
- 满足 A（必选项）给 X 分；不满足则扣 Y 分并记录 blocking
- 满足 B（推荐项）给 Z 分；不满足可扣分但不阻塞

---

## 2) 轮次与版本锁定（必须）

多人多轮评审的核心是“评审对象不能漂移”。因此每一轮必须锁定一个方案版本。

建议两种方式之一：
- **revision 递增**：在方案里加入 `revision: 1,2,3...`
- **hash 锁定**：评审结果里记录被评审文件的 `sha256`

推荐同时做：revision + sha256（便于人读 + 便于系统校验）。

---

## 3) 标准流程（Round-0 到 Release）

下面所有步骤都可以通过命令消息 `cmd_*.msg.json` 串联（PR-007，message_envelope `type=command`），并由系统路由执行投递（PR-024）。

### Step 1：方案初稿生成（Author）

触发条件：
- Author 的命令 `cmd_create_proposal.json` 的 `required_inputs` 全部满足（例如需求文档、澄清结果包、约束、验收标准）。

Author 输出：
- `proposal.*`（初稿）
-（可选）`proposal_rationale.md`（关键假设/风险/权衡）

投递目标：
- 由本轮 DAG 的 `outputs[].deliver_to` 定义（例如方案文件投递给评审协调员与发布协调员）。

### Step 2：发起多人评审（Review Coordinator）

触发条件：
- Review Coordinator 在 inbox 收到 `proposal.*`（以及需要的上下文）且版本锁定信息齐全。

Review Coordinator 输出：
- 多份 `review_request.cmd.json`（一位评审者一份）
  - 每份命令的投递目标由 DAG 决定：命令文件投递到对应 reviewer 的 inbox；reviewer 的评审结果产物投递给 Review Coordinator 与 Reviser（由 outputs.deliver_to 定义）。
  - 本流程中：被选定参与本轮的 Reviewer 都视为“必需评审者”，不存在“可选评审者”。

### Step 3：并行评审产出（Reviewers）

触发条件：
- Reviewer 的 `review_request.cmd.json` 输入满足。

Reviewer 输出：
- `review_result.json`（结构化：decision、score、score_breakdown、criteria_version、issues、suggestions、ref_sha256/revision）

若缺材料/缺标准：
- Reviewer 必须发 `human_intervention_request.json` 并阻塞等待（不要猜）。

### Step 4：评审汇总判定（Review Coordinator）

触发条件（至少其一）：
- **收齐触发**：所有必需评审结果到齐（required_inputs 满足）
- **超时触发**：到达 `timeout` 仍未收齐（必须给出判定；本流程默认“通过”，但必须显式记录哪些 Reviewer 缺席，并产出告警/后续补评安排）
- **超时触发**：到达 `timeout` 仍未收齐（必须给出判定；默认决策建议为“通过”，但应允许在 `plan_manifest.json.policies.timeouts.dag_review` 中覆盖；无论默认判定为何，都必须显式记录哪些 Reviewer 缺席，并产出告警/后续补评安排）
- **版本不一致触发**：评审结果引用的 revision/hash 不一致（判定为无效并要求重评）

判定职责（避免分叉）：
- “超时到了怎么办”的业务判定只能由 Review Coordinator 做，并必须落盘为结构化结论文件（可审计、可重放）。
- Monitor 只负责发现超时风险并告警/展示 BLOCKED，不得替代协调员产出通过/不通过结论。

判定规则（必须预定义、可审计）：
- 必需评审者规则：本轮被纳入的 Reviewer 全部视为“必需评审者”（由协调员在发起评审时确定名单并落盘）。
- 分数阈值：例如 score >= 80 才算通过
- 轮次上限：例如最多 2~3 轮，超限转 Human Gateway 决策

Review Coordinator 输出（两类）：
- **通过**：产出“本轮通过结论”文件（可以是汇总版 `review_result.json`）
- **不通过**：产出 `revise_proposal.cmd.json` 投递给 Reviser，并附带“必须修哪些问题”的清单引用

建议统一落盘（MVP 强制，便于 Monitor/Dashboard 通用化）：
- 无论通过/不通过/超时判定，Review Coordinator 都必须额外产出一份 `decision_record.json`
  - `decision_type=PROPOSAL_REVIEW`（或 DAG 场景用 `DAG_REVIEW`）
  - `decision=APPROVE|REVISE|REJECT`
  - `missing_participants[]`（若超时缺席）
  - `evidence_files[]`（指向本轮 review_result/dag_review_result 等证据文件）
模板：`doc/rule/templates/decision_record.json`

### Step 5：方案修订（Reviser）

触发条件：
- 收到 `revise_proposal.cmd.json`，且 required_inputs（评审汇总、原方案、缺失材料）齐全。

Reviser 输出：
- 更新后的 `proposal.*`（revision+1，或新 hash）
-（可选）`proposal_change_log.md`（逐条回应评审意见）

然后回到 Step 2 进入下一轮评审，直到通过或超限。

### Step 6：发布门禁与最终发布（Release Coordinator）

触发条件：
- 方案评审已通过（存在放行结论）且“发布门禁证据”满足（例如 build/deploy/test/security 结果文件齐全）。

Release Coordinator 输出：
- `release_manifest.json decision=APPROVE|REJECT`
-（MVP 强制）`decision_record.json decision_type=RELEASE decision=APPROVE|REJECT`（供 Monitor/Dashboard 统一展示）

约束：
- 未 `decision=APPROVE` 不得对外宣称“已发布/可交付”。

---

## 4) 常见问题与推荐策略

### 4.1 “有的命令需要评分，有的不需要”
- 评审命令通常 `score_required=true`，用于量化阈值与分支通知。
- 普通执行命令可 `score_required=false`。
- 无论是否评分，决策都应外置为“协调员的判定”或“控制面规则”，避免把 if/else 塞进业务执行 Agent 的提示词。

### 4.2 如何避免无限循环
- 轮次上限 + 超限转 Human Gateway 做范围取舍（降级/MVP/停止）。
- 每轮必须有明确“必须改的清单”，Reviser 只改清单内内容（减少漂移）。

### 4.3 多人评审如何加速
- 并行评审 + 多目标投递（协调员、修订员、GM 同时收到结果）。
- 严格版本锁定，避免“评审的是旧版本”导致返工浪费。

---

## 5) 与 Mario/DAG 场景的映射（示例）

- `proposal.*` → `task_dag.json`
- `review_request.cmd.json` → `dag_review_request.cmd.json`
- `review_result.json` → `dag_review_result.json`
- Reviser → `agent_dag_reviser`
- Review Coordinator → `agent_dag_review_coordinator`
- Release manifest → `release_manifest.json`
