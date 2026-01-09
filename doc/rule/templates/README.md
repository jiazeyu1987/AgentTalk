# Templates（消息/命令/编排规范）

本目录提供可复用的**模板文件**，用于把 `doc/rule` 中的“概念性约定”落成可执行的结构化契约。

核心原则不变：
- 每个Agent只读写自己的文件夹（见PR-003）
- 所有交互只通过文件传递（见PR-001）

## 文件列表

- `message_envelope.msg.json`：通用消息信封（推荐所有投递都带）
- `command.cmd.json`：统一执行命令模板（PR-007）
- `task_dag.json`：任务DAG + 路由表模板（PR-002/PR-009）
- `plan_manifest.json`：Plan清单 + 交付物定义模板（PR-004/PR-025）
- `ack.json`：回执模板（PR-001）
- `alert.json`：告警模板（PR-010/PR-024/PR-025）
- `deadletter_entry.json`：死信条目模板（PR-001/PR-010/PR-024）
- `delivery_log_entry.json`：投递日志条目模板（PR-024）
- `dag_review_request.cmd.json`：DAG评审命令模板（专家评审角色）
- `dag_review_result.json`：DAG评审结果/打分模板（APPROVE/REVISE/REJECT）
- `artifact_validation_result.json`：交付物测试/验收结果模板（PASS/REJECT）
- `build_validation_result.json`：构建可复现性/制品生成验证（PASS/REJECT）
- `deploy_validation_result.json`：干净环境部署验证（PASS/REJECT）
- `smoke_test_result.json`：关键路径冒烟测试（PASS/REJECT）
- `e2e_test_result.json`：端到端测试（PASS/REJECT，可带score）
- `security_scan_result.json`：安全扫描结果（PASS/REJECT）
- `release_manifest.json`：发布清单与放行决策（APPROVE/REJECT）
- `human_intervention_request.json`：请求人类介入（缺文件/缺标准/审批/外部环境等）
- `human_intervention_response.json`：人类介入响应（提供文件/决策/补充标准）
- `schema_versioning.md`：schema版本与兼容策略（所有结构化文件）
- `delivery_state_machine.md`：投递/回执/重试/死信/完成判定状态机（PR-001/PR-010/PR-024/PR-025）
- `routing_priority.md`：路由优先级与未命中处理（PR-002/PR-024）
- `replay_procedure.md`：死信回放流程（PR-024/PR-010）

## 约定

- **schema_version**：所有模板都包含 `schema_version`，升级时应保持向后兼容或明确不兼容策略。
- **message_id**：端到端唯一；用于去重、关联与审计（见PR-017）。
- **idempotency_key**：用于“重复消息不重复执行”；建议由规划者按规则生成（如 `<plan_id>:<task_id>:<kind>`）。
- **sha256**：对payload文件做内容哈希，保证完整性与去重基础。

## JSON Schema

`doc/rule/templates/schemas/` 提供对应模板的JSON Schema，可用于自动校验。

## Release门禁（推荐）

当Plan需要“高置信可运行”的交付时，建议使用 `plan_manifest.json.policies.release_gates_required` 声明发布门禁，并产出 `release_manifest.json` 作为最终放行记录。
