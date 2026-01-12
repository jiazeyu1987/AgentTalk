# 00 架构总览（MVP边界与里程碑）

## MVP 范围（必须）

- 单机文件系统作为消息总线（inbox/outbox + system_runtime）
- 系统程序：投递、去重、投递日志、归档控制面文件、plan_status 汇总、agent_status 快照、DLQ/告警
- Agent 运行时：心跳扫描 inbox、claim、校验、等待输入、执行命令、产出 outbox、写 ACK
- 结构化契约：JSON Schema 校验（命令/DAG/评审/验收/发布）

## 非 MVP（明确不做）

- 分布式集群与强一致队列
- 复杂权限系统（先按目录隔离+系统进程权限）
- 复杂 UI（先提供 CLI/文件落盘）

## 关键约束（来自 doc/rule 与 doc/DAG）

- 交互唯一方式：文件（payload + 可解析 envelope）
- Agent 不跨目录：只读写自身目录；系统进程拥有跨目录权限
- 执行入口（方案B）：命令消息 `cmd_*.msg.json`（message_envelope `type=command`，`payload.command` 为命令对象）；系统路由/回执/投递日志以 `message_id` 为链路唯一ID。
- 执行层路由：以“当前阶段 DAG”（Meta-DAG/Business-DAG）为准；产物按 `outputs[].deliver_to` 投递，命令按 `assigned_agent_id` 投递
- Agent 只消费 message envelope（`*.msg.json`）：系统投递 payload 时必须“payload 先到、envelope 后到”；Agent 只 claim envelope 文件

## 进程与职责（装配图口径，必须写死）

### Agent（每个 agent 一份）

- Heartbeat/Dispatch：`agenttalk_heartbeat.py`
  - 读：`agents/<agent_id>/inbox/<plan_id>/*.msg.json`（只读写自身目录）
  - 写：`agents/<agent_id>/outbox/<plan_id>/`（artifact envelopes + payload、ACK、task_state、human_intervention_request、alert）
  - 约束：ACK/task_state/human_request 等控制面文件不走 DAG 路由，由系统程序收集归档

### System（跨目录单写者）

- Router（投递 + 归档控制面）：`agenttalk_router.py`
  - 投递：按 `system_runtime/plans/<plan_id>/task_dag.json` 投递 message + payload 到目标 `agents/<agent_id>/inbox/<plan_id>/`
  - 记录：`system_runtime/plans/<plan_id>/deliveries.jsonl`（含去重、superseded、deadlettered）
  - 归档（权威源）：
    - ACK：`system_runtime/plans/<plan_id>/acks/`
    - 决策记录：`system_runtime/plans/<plan_id>/decisions/`（收集 `decision_record_*.json`）
    - 人类介入：`system_runtime/plans/<plan_id>/human_requests/`、`system_runtime/plans/<plan_id>/human_responses/`
    - 发布：`system_runtime/plans/<plan_id>/releases/`，并刷新 `system_runtime/plans/<plan_id>/release_manifest.json` 指针
  - Human Gateway 注入：把 `agent_human_gateway` 的 response 附件注入为 artifact envelope 投递给目标 agent（保持“Agent 只消费 envelope”）
  - DLQ/告警：`system_runtime/{deadletter,alerts}/<plan_id>/`

- Monitor（状态汇总 + agent_status 快照）：`agenttalk_monitor.py`
  - 汇总：`system_runtime/plans/<plan_id>/plan_status.json`
  - 采集：`agents/<agent_id>/status_heartbeat.json` → `system_runtime/agent_status/<agent_id>.json`（Dashboard 权威源）

- Dashboard（只读 API）：`agenttalk_dashboard.py`
  - 只读 `system_runtime/`：plans/status/deliveries/decisions/acks/agent_status/release_manifest

### Coordinators（业务判定的写作者）

- Release Coordinator（门禁判定）：（库）`agenttalk/release/app.py`
  - 输入：`system_runtime/plans/<plan_id>/plan_manifest.json` + 自己 workspace inputs 的证据文件
  - 输出：`agents/<release_coordinator_id>/outbox/<plan_id>/release_manifest_<release_id>.json` + `decision_record_<decision_id>.json`
  - 归档：由 Router 收集到 system_runtime（避免 Dashboard/Monitor 分叉）

## 里程碑（与 tests 对齐）

M0：原子 IO + 目录布局 + schema 校验可用  
M1：Router 能按 DAG 投递 + deliveries.jsonl + dedup  
M2：Agent heartbeat 能执行 cmd + 产出 ACK + wait_for_inputs  
M3：plan_status 汇总（READY/BLOCKED/RUNNING/COMPLETED）  
M4：DLQ/alerts + Human Gateway  
M5：发布门禁（release_manifest）+ E2E 用例通过
M6：只读 Dashboard（Plan/Task/Deliveries/Agent 状态可视化）
（补充）M1.5：agent_status 快照可用（供 Dashboard 读取）

## Pytest 验证策略（总）

- 单元测试：纯函数/解析/判定（无需真实目录）
- 集成测试：使用 `tmp_path` 构造 agents_root/system_runtime，验证落盘与投递路径
- E2E 测试：最小 plan（2-3 tasks）跑通投递→执行→状态→发布
