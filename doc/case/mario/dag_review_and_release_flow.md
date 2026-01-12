# 超级马里奥案例：DAG 多人评审到最终发布流程（强制）

本文描述：当 `task_dag.json`（v1.1）生成后，如何进行**多轮、多角色并行评审**，并在评审与发布门禁全部满足后最终发布（release）。

结论先写在前面：在本案例中，**DAG 评审不是可选项**。未通过 DAG 评审不得投递执行命令，不得进入发布门禁链。

适用的核心原则/规范（参考）：
- PR-001：inbox/outbox 文件传递
- PR-002：文件投递目标必须预先定义（DAG 或 cmd）
- PR-007：统一执行命令（方案B：命令消息 `cmd_*.msg.json`，envelope `type=command`）
- PR-024：系统路由与状态监控（deliveries.jsonl / plan_status.json）
- PR-025：生命周期与 Human Gateway（阻塞时请求人类介入）
- `doc/DAG/semantics.md`：DAG v1.1 语义（gates、failure_policy、inputs selector 等）

---

## 0) 角色与产物约定

### 角色（示例）

- `agent_general_manager`：GM（编排/协调）
- `agent_dag_planner`：DAG 专员（只负责生成/更新 DAG 与 plan_manifest）
- `agent_dag_review_coordinator`：评审协调员（只负责发起评审轮次、收集结果、判断是否通过/是否进入下一轮；不写DAG、不写代码）
- 评审经理（可多名，可并行）：
  - `agent_engineering_manager`：工程/架构审查
  - `agent_game_design_manager`：玩法/范围审查
  - `agent_qa_manager`：测试/验收审查
  - `agent_security_manager`：安全/合规审查
- 验证与发布（可按团队拆分）：
  - `agent_build_validator`、`agent_deploy_validator`、`agent_testing_engineer`、`agent_release_manager`
- `agent_human_gateway`：人类网关

### 关键文件（模板参考）

- DAG：`doc/rule/templates/task_dag.json`（已升级到 v1.1）
- 评审命令：`doc/rule/templates/dag_review_request.cmd.json`
- 评审结果：`doc/rule/templates/dag_review_result.json`
- 验收/门禁：`doc/rule/templates/*_validation_result.json`
- 最终发布清单：`doc/rule/templates/release_manifest.json`
- Human Gateway：`doc/rule/templates/human_intervention_request.json` / `human_intervention_response.json`
- Mario评分模板（用于score_required=true命令）：`doc/case/mario/templates/scoring/README.md`

---

## 1) DAG 生成（DAG 专员）

1. `agent_dag_planner` 在自己的 `outbox/<plan_id>/` 写出：
   - `task_dag.json`（v1.1）
   - `plan_manifest.json`（包含 `deliverables[]` 与 `policies.release_gates_required[]` 等）
2. 系统程序将上述控制面文件汇总到：
   - `system_runtime/plans/<plan_id>/task_dag.json`
   - `system_runtime/plans/<plan_id>/plan_manifest.json`
3. 监控程序初始化/更新 `system_runtime/plans/<plan_id>/plan_status.json`：
   - 如果 DAG 声明了 `gates.required=true` 且尚无评审证据，则相关 task 进入 `BLOCKED_WAITING_REVIEW`（见 `doc/DAG/semantics.md`）。

备注：此阶段不得投递执行命令到开发/测试等执行 Agent，避免“未经审查的 DAG”触发大规模无效执行。

---

## 2) 发起第 1 轮 DAG 评审（强制）

1. 由 `agent_dag_review_coordinator`（或 GM）生成多份 `dag_review_request.cmd.json`（一位评审者一份）：
   - 命令投递目标由 Meta-DAG/Business-DAG 中对应评审任务的 `assigned_agent_id` 决定（投递到 reviewer inbox）。
   - reviewer 产出的 `dag_review_result.json` 的接收者由 DAG 中评审结果 output 的 `deliver_to` 决定（通常投递给评审协调员、DAG修订员、GM）。
2. 系统程序按 DAG 规则将这些命令消息 `cmd_*.msg.json` 投递到各评审经理的 `inbox/<plan_id>/`（PR-024）。

建议命令输入（required_inputs）：
- `task_dag.json`
- `plan_manifest.json`
-（可选）澄清结果包/需求文档（如 `requirements.md`、`clarification_answers.*`）

---

## 3) 评审经理产出评审结果（并行）

1. 每个评审经理的心跳程序发现 `dag_review_request.cmd.json`，按命令执行并产出：
   - `dag_review_result.json`（decision=APPROVE/REVISE/REJECT，含 score 与建议）
2. 评审结果写入评审经理的 `outbox/<plan_id>/`，系统程序按 DAG 中该输出的 `deliver_to` 投递给：
   - `agent_dag_review_coordinator`（汇总判定）
   - `agent_dag_planner`/`agent_dag_reviser`（用于修改 DAG）
   - `agent_general_manager`（归档与可见性）

如果评审发现“缺材料/缺标准”，评审经理应：
- 不要编造；发起 `human_intervention_request.json type=CLARIFY` 或 `MISSING_FILE`
- 进入 `BLOCKED_WAITING_HUMAN`，等待 Human Gateway 回填（PR-025）

### 评分相关的分支处理（通过 DAG 显式建模）

涉及评分的 if/else 不通过“命令分支投递”实现，而是通过 DAG 显式建模：
- 评审结果产出后，由评审协调员任务读取评分与模板分项，决定进入“返工任务”或“放行任务”
- 路由始终由 DAG 的 deliver_to/routing_rules 决定，避免命令层分叉

---

## 4) 评审汇总判定与多轮返工（强制，且必须有上限）

1. `agent_dag_review_coordinator` 汇总各 `dag_review_result.json`，并给出本轮判定：
   - 任一 `REJECT`：必须进入返工（或触发“范围降级/终止”的人工决策）
   - 存在 `REVISE`：必须进入返工
   - 全部 `APPROVE` 且分数/阈值满足：进入“DAG 放行”状态
2. 多轮评审（Round-N）规则建议写死并可审计（避免“人治”）：
   - **版本固定**：每轮评审针对一个明确的 DAG 版本（例如 `dag_revision=3` 或用内容哈希标识），防止评审对象漂移
   - **通过条件**：本轮被纳入的评审经理全部视为必需评审者；通过条件建议为“所有评审者 APPROVE 且 score>=阈值”（阈值由评分模板定义）
   - **上限**：例如最多 2~3 轮；超限必须走 Human Gateway 让人做取舍（范围降级/MVP/停止）
3. 返工执行：
   - `agent_dag_planner` 按评审建议更新 `task_dag.json` / `plan_manifest.json`
   - 评审协调员发起下一轮评审（回到第 2 步）

补充（MVP 强制统一结论格式，便于 Monitor/Dashboard 通用化）：
- 每一轮汇总判定后，评审协调员必须额外产出 `decision_record.json`：
  - `decision_type=DAG_REVIEW`
  - `subject.kind=task_dag` + `ref_sha256/ref_revision`（锁定评审对象）
  - `decision=APPROVE|REVISE|REJECT`
  - `missing_participants[]`（若超时缺席）
  - `evidence_files[]`（本轮所有 reviewer 的 `dag_review_result.json`）
模板：`doc/rule/templates/decision_record.json`

---

## 5) DAG 放行（通过评审后才允许）

当 DAG 评审通过后（证据满足，且有明确的“放行判据”落盘）：
1. GM 或系统程序开始将执行命令消息 `cmd_*.msg.json` 投递到各执行 Agent 的 `inbox/<plan_id>/`。
2. 执行 Agent 只按命令执行：
   - `required_inputs` 不满足则等待/阻塞（`wait_for_inputs=true`）
   - 输入冲突/无法唯一化则走 Human Gateway
3. 执行产物写入各自 `outbox/<plan_id>/`，系统程序按 DAG 路由表投递到下游 inbox（PR-002/PR-024）。

---

## 6) 验证门禁与最终发布（release）

1. 验证角色按 `plan_manifest.json.policies.release_gates_required` 产出门禁证据：
   - `build_validation_result.json`（PASS/REJECT）
   - `deploy_validation_result.json`（PASS/REJECT）
   - `smoke_test_result.json`（PASS/REJECT）
   - `e2e_test_result.json`（PASS/REJECT，可带score）
   - `security_scan_result.json`（PASS/REJECT）
2. 系统监控汇总 `plan_status.json`：
   - 缺证据 → `BLOCKED_WAITING_REVIEW`
   - 证据为 REJECT → 触发返工/告警/人工决策
3. 最终由发布负责人产出 `release_manifest.json`：
   - `decision=APPROVE`：作为“可交付版本”的唯一放行判据
   - `decision=REJECT`：阻塞并要求返工/降级

---

## 7) 关键检查点（避免跑偏）

- 评审与门禁证据必须落盘为结构化文件（可审计、可重放）。
- 在 DAG 尚未评审通过前，执行命令不得被投递到执行 Agent。
- 任何“缺材料/缺标准”的情况都应通过命令声明的输入与 Human Gateway 来解决，而不是靠 Agent 自行补全。
- 允许多目标投递：评审结果/澄清文件可同时投递给 GM 与 DAG 专员，减少串行等待。
