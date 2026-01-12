# 案例：超级马里奥项目（GM 也作为节点）

目标：用户提出“做一个超级马里奥的游戏”，GM 既是规划者也是一个执行节点。
下面按 1~5 推演系统各层做了什么。

## 1) 需求接收与立项（GM 节点）

这一阶段的目标不是“GM凭空想清楚玩法”，而是把用户的一句话变成：
1) 一份可落盘、可投递、可追溯的“澄清请求/澄清答案”；2) 一份最小可执行的需求输入（后续会变成 DAG 的 inputs）。

### 1.1 用户请求如何进入 GM（inbox + message envelope）

- 用户请求应以“payload + 可解析信封”的形式进入 GM 的 `inbox/<plan_id>/`（PR-001）。
  - payload 示例：`user_request.md`
  - envelope 示例：`msg_user_request.msg.json`（参考 `doc/rule/templates/message_envelope.msg.json`）
- 系统程序负责跨目录投递：外部入口/人类网关/其他Agent → GM 的 inbox（PR-024），GM 不直接读写他人目录（PR-003）。

### 1.2 GM 的心跳/事件循环在这里做什么（heart_beat）

- GM 的心跳程序（轮询机制）扫描 `inbox/<plan_id>/`，发现“新消息/新命令”（PR-011/PR-007）。
- GM 对“用户请求消息”做的事是：生成规划与澄清相关的命令消息 `cmd_*.msg.json`（envelope `type=command`），并产出可投递的请求文件到 `outbox/<plan_id>/`。
- 如果所需材料不全，**任何Agent**都不会“继续编”。所需材料必须在命令里显式声明（`required_inputs` + `wait_for_inputs=true`）；输入不满足则进入等待/阻塞；若缺的是外部材料或需要人类决策，则通过 Human Gateway 发起补齐请求（PR-007/PR-025，见下文 1.4）。

### 1.3 一次性澄清怎么走（agentlist/visibility_list → cmd → outbox）

- GM 不假设自己具备“游戏策划/领域全知”能力，而是按 PR-009/PR-018 从 `visibility_list` 选择相关角色 Agent：
  - 游戏策划：玩法/关卡/手感/内容范围（模板见 `doc/case/mario/templates/clarification_game_design.md`）
  - 产品经理：范围锁定/验收口径/交付形式/合规（模板见 `doc/case/mario/templates/clarification_pm.md`）
  -（可选）引擎与架构/测试验收/构建发布：补充技术约束与门禁证据需求
- GM 为每个角色生成一个“澄清问题收集”的命令消息 `cmd_*.msg.json`（PR-007，envelope `type=command`），写入 GM 的 `outbox/<plan_id>/`：
  - `cmd_collect_clarification_game_design.json`
  - `cmd_collect_clarification_pm.json`
- 这些澄清命令**必须在命令里预先指定投递目标**（可多目标），例如：
-  在“Meta-DAG → 生成并放行 Business-DAG”的统一路由口径下，澄清命令不再通过 `send_to` 指定路由；
  这些澄清产物的投递目标由 Meta-DAG 的 `outputs[].deliver_to` 预先定义（例如投递给 DAG 专员与 GM）。
- 系统程序将这些命令投递到对应角色 Agent 的 `inbox/<plan_id>/`（PR-024）。
- 角色 Agent 的心跳程序执行命令，产出“问题清单”到自己的 `outbox/<plan_id>/`，系统再投递回 GM 的 `inbox/<plan_id>/`：
  - 示例输出：`clarification_questions_game_design.md`、`clarification_questions_pm.md`
- GM 汇总去重后，产出一次性澄清请求（面向用户/Human Gateway）：
  - 推荐落为 `human_intervention_request.json`，并使用 `type=CLARIFY`（模板参考 `doc/rule/templates/human_intervention_request.json`）

### 1.4 Human Gateway 如何回填（input 的补齐来源）

- 人类在 `agent_human_gateway/outbox/<plan_id>/` 提供 `human_intervention_response.json` 并附带材料文件（PR-025）。
- 系统程序将这些材料投递到 GM 的 `inbox/<plan_id>/`（PR-024），GM 才能继续推进。
- 这一步的“inputs”产物通常包括：
  - 平台/引擎选择（如 Web/Unity/Godot）
  - MVP 范围与验收标准（例如“1个关卡、支持跑跳、2种敌人、60fps、键盘操控”）
  - 素材来源与版权约束（是否允许占位符/开源素材）

### 1.5 GM 输出什么（outbox → 为 DAG 做 inputs）

在“一个 Agent 只做一件事/只有一份提示词”的约束下，GM 的职责应尽量收敛为**协调与编排**，而不是亲自撰写领域产物（例如完整 PRD/玩法细节文档）。

- 当一次性澄清完成后，GM 主要产出两类东西并写入自己的 `outbox/<plan_id>/`：
  1) **澄清结果包（输入材料的汇总与索引）**
     - 例如：`clarification_answers.md`（或 `.json`），包含用户/Human Gateway 的回答、提供的素材文件列表与约束。
  2) **把“需求成稿”委托给需求制定角色的执行命令**
     - 向 `agent_product_manager`/`agent_game_designer` 投递 `cmd_write_requirements.json`：
       - required_inputs 指向 `user_request.md` + `clarification_answers.*` + 人类提供的附件
       - 产出目标是 `requirements.md`、`acceptance_criteria.md` 等
- 随后由“需求制定 Agent”在自己的心跳循环里执行命令，产出 `requirements.md` 到其 `outbox/<plan_id>/`，再由系统程序投递到需要它的下游节点（PR-002/PR-024）。

### 1.6 与 DAG 的关系（为什么这一阶段必须落盘）

- DAG v1.1 的 `inputs[] selector` 需要可被匹配的“真实文件/消息”作为输入来源（见 `doc/DAG/semantics.md`）。
- 因此第1步的落盘产物会成为后续任务的输入来源：
  - GM 落盘的澄清答案/附件索引会被“需求制定 Agent”的命令引用（required_inputs）。
  - “需求制定 Agent”产出的 `requirements.md` 会成为后续任务的上游输出/输入。
  - 在 DAG 中可用 `by_output_name` 或 `by_file_name` 来引用。
- 约束：澄清只做一轮；后续若执行期发现缺失材料，只允许在任务阻塞时按需澄清（见第4步）。

## 2) 规划与 DAG 生成（GM 节点）

- GM 根据需求生成 `task_dag.json`（v1.1）与 `plan_manifest.json`。
- 明确任务依赖、inputs 选择规则、outputs 投递目标、失败策略与门禁。
- DAG 评审是强制环节：按“统一执行命令”投递 `dag_review_request.cmd.json` 给多名经理/负责人角色，等待评审结果满足放行判据（至少包含 `dag_review_result.json decision=APPROVE`）。
- GM（或系统程序）基于 DAG 为每个 task 生成对应的命令消息 `cmd_*.msg.json`（命令是唯一可执行入口），并投递到各自的 `inbox/<plan_id>/`。

## 3) 系统路由与任务派发（系统程序）

- 系统路由器依据 DAG（路由表）将各 Agent `outbox/<plan_id>/` 的产出投递到目标 `inbox/<plan_id>/`（Agent 不能跨目录写入）。
- 对命令与消息都执行：原子投递（tmp→rename）、主去重键（message_id+sha256）、投递日志落盘（idempotency_key 仅用于审计与可读关联）。
- 记录投递日志 `deliveries.jsonl`，并做幂等去重。
- 监控程序生成/更新 `system_runtime/plans/<plan_id>/plan_status.json`，按依赖、inputs、门禁证据判定各 task 的 PENDING/READY/BLOCKED/… 状态。

## 4) 执行与产出（各 Agent + GM 节点）

- 各 Agent 心跳发现命令消息 `cmd_*.msg.json` 与输入消息，按 v1.1 inputs selector + pick_policy 判断输入是否满足/是否冲突。
- 输入不满足：进入 `BLOCKED_WAITING_INPUT`。
- 输入冲突且无法唯一化：触发 Human Gateway 并进入 `BLOCKED_WAITING_HUMAN`。
- 发现“需求/验收标准/外部素材”等缺失材料：允许按需再次发起 `human_intervention_request.json type=CLARIFY`，但仅在对应任务阻塞时触发。
- 产出：代码、素材、关卡数据、构建脚本、测试报告等。
- GM 作为节点可承担“整合/架构/里程碑验收”任务。
- 每次执行写 ACK（CONSUMED/SUCCEEDED/FAILED 等）、task_state/trace，并将产出写入 `outbox/<plan_id>/` 以供系统投递。

## 5) 验证、门禁与交付（系统 + 验证角色）

- 依据 DAG/plan_manifest 门禁：构建、部署、smoke、e2e、安全等。
- 生成 `artifact_validation_result.json` 与 `release_manifest.json`。
- 系统监控汇总 `plan_status.json`，满足交付条件后标记完成。
- 产物归档到 `system_runtime/artifacts/<plan_id>/`（如启用）。
