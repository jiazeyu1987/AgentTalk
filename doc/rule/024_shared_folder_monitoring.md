# 系统路由与状态监控机制

**原则ID**: PR-024
**来源文档**: shared_folder_monitoring.md
**类别**: 核心机制

---

## 原则描述

系统运行一个具备跨目录权限的**系统路由与监控程序**（下称“系统程序”），负责：

1. **文件路由投递**：根据任务文件（DAG方案/路由表）将各Agent `outbox/<plan_id>/` 中的文件投递到目标Agent `inbox/<plan_id>/`（见PR-001/PR-002/PR-003）。
2. **集中式状态与进度**：采集各Agent状态与任务进度，形成全局可观测视图，支持告警、归档与审计（见PR-010/PR-017/PR-025）。
3. **产物收集与归档**：收集“验证后的产物/最终交付物”，统一落盘到系统归档区，避免引入可被多个Agent直接读写的共享目录。
4. **结论收集与归档**：收集协调员产出的 `decision_record.json`，统一落盘到 `system_runtime/plans/<plan_id>/decisions/`，作为 Dashboard/Monitor 的权威业务结论源。
5. **回执收集与归档**：收集执行方产出的 `ack_<message_id>.json`，统一落盘到 `system_runtime/plans/<plan_id>/acks/`，作为 Monitor/Dashboard 的权威处理状态源。

同时系统程序应实现“文件即消息”的可靠性增强：
- **原子投递**：复制到目标目录时先写临时文件再原子重命名，避免下游读到半写入文件（见PR-001）。
- **去重与幂等**：以 `message_id + sha256` 为主去重键；`idempotency_key` 仅用于审计与人类可读关联，防止“双口径去重”导致行为分叉。
- **投递日志**：记录每次投递的delivery_id、来源/目标、时间、哈希，便于审计与重放（见PR-017）。
- **回执汇总**：收集并归档 `ack_<message_id>.json`（到 `system_runtime/plans/<plan_id>/acks/`），形成端到端“已投递/已处理”视图（见PR-001/PR-025）。
- **死信隔离**：将不可解析/不符合schema的消息隔离到deadletter并告警（见PR-010）。

## 全局配置（示例）

### 配置文件位置

**路径**: `用户文件夹/AgentFolder/system_config.json`

### 配置文件格式

```json
{
  "agents_root": "/path/to/agents/root",
  "system_runtime_path": "/path/to/agenttalk/system_runtime",
  "router": {
    "enabled": true,
    "poll_interval_seconds": 2
  },
  "monitoring": {
    "enabled": true,
    "heartbeat_interval_seconds": 60,
    "stale_heartbeat_multiplier": 2
  },
  "artifact_collection": {
    "enabled": true,
    "trusted_validators": ["agent_testing_engineer", "agent_documentation_controller"]
  }
}
```

### 配置字段说明（要点）

#### agents_root

所有Agent根目录（系统程序用于扫描每个Agent的inbox/outbox与状态文件）。

#### system_runtime_path

系统程序的运行目录（全局状态、投递记录、归档产物等都写在这里；Agent无需读写）。

#### artifact_collection.trusted_validators

被信任的“验证者Agent”列表。系统程序只会将这些Agent产出的“已验证产物”归档为最终交付物（配合PR-022/PR-017）。

## 系统运行目录结构（示例）

### 目录组织

```
system_runtime/
├── plans/
│   └── <plan_id>/
│       ├── active_dag_ref.json      # 当前阶段DAG指针（系统生成/更新，供路由/监控/看板统一口径）
│       ├── task_dag.json            # DAG/路由表（来自规划者，如GM）
│       ├── plan_manifest.json       # 本plan涉及的Agent/任务清单（可选）
│       ├── plan_status.json         # 汇总进度（系统生成）
│       ├── deliveries.jsonl         # 投递日志（每行一条；见 delivery_log_entry.json）
│       ├── commands/                # 命令归档区（系统生成，用于审计/重放）
│       │   └── cmd_*.msg.json       # 从规划者 outbox 收到并校验通过的“命令消息”（envelope type=command）
│       ├── decisions/               # 结论归档区（系统生成，用于Dashboard/审计）
│       │   └── decision_record_*.json
│       └── dag_history/             # DAG 历史归档（系统生成，用于审计/回溯）
│           └── task_dag.<ts>.<sha>.json
├── deadletter/
│   └── <plan_id>/                   # 无法投递/无法解析/超限重试的消息（系统生成）
├── alerts/
│   └── <plan_id>/                   # 告警文件（系统生成，可供Human Gateway处理）
├── agent_status/
│   ├── <agent_id>.json              # 最新状态快照（系统生成）
│   └── ...
└── artifacts/
    └── <plan_id>/
        └── ...                      # 归档产物（系统生成）

模板参考：
- `doc/rule/templates/alert.json`
- `doc/rule/templates/deadletter_entry.json`
- `doc/rule/templates/delivery_state_machine.md`
- `doc/rule/templates/schema_versioning.md`
- `doc/rule/templates/delivery_log_entry.json`
- `doc/rule/templates/command_envelope.msg.json`
- `doc/rule/templates/active_dag_ref.json`
- `doc/rule/templates/decision_record.json`
- `doc/rule/templates/routing_priority.md`
- `doc/rule/templates/replay_procedure.md`
- `doc/rule/templates/dag_review_result.json`
- `doc/rule/templates/artifact_validation_result.json`
- `doc/rule/templates/build_validation_result.json`
- `doc/rule/templates/deploy_validation_result.json`
- `doc/rule/templates/smoke_test_result.json`
- `doc/rule/templates/e2e_test_result.json`
- `doc/rule/templates/security_scan_result.json`
- `doc/rule/templates/release_manifest.json`

## 命令归档区（commands/）

为支持“同一 Agent 同时参与多个 plan”且不混线、可重放、可审计，系统程序应把所有通过校验的“命令消息”（`cmd_*.msg.json`，envelope `type=command`）归档到：
- `system_runtime/plans/<plan_id>/commands/`

约束（MVP 强制）：
- 命令投递目标不由命令文件决定；系统程序以“当前阶段 DAG”的 `nodes[].assigned_agent_id` 为唯一来源进行命令投递。
- 命令消息必须包含 `message_id`（链路唯一ID）以及可绑定字段（`plan_id/task_id/command_id`）；系统程序据此把命令绑定到 DAG 节点并执行投递与去重。

## 当前阶段DAG指针（active_dag_ref.json，必须原子更新）

为避免 Router/Monitor/Dashboard 在“Meta-DAG vs Business-DAG”口径上分叉，系统程序应维护：
- `system_runtime/plans/<plan_id>/active_dag_ref.json`

硬规则（MVP 必须写死）：
- `active_dag_ref.task_dag_sha256` 必须与 `system_runtime/plans/<plan_id>/task_dag.json` 内容一致；不一致视为系统异常，暂停该 plan 的投递并告警。
- 在 meta→business 切换时：必须先归档旧 DAG 到 `dag_history/`，再原子更新 `task_dag.json`，最后原子更新 `active_dag_ref.json`（active 指针必须最后更新）。

## 结论归档区（decisions/，必须统一数据源）

为让 Monitor/Dashboard 不再“识别一堆不同结论文件”，系统程序应把协调员产出的 `decision_record.json` 汇总归档到：
- `system_runtime/plans/<plan_id>/decisions/`

硬规则（MVP 必须写死）：
- `decision_record.json` 必须通过 schema 校验（`decision_record.schema.json`），否则进入 DLQ + alert。
- 归档采用原子写入（tmp→rename），避免 Dashboard/Monitor 读到半文件。
- Dashboard/Monitor 对“业务结论”的统一数据源是 `decisions/`，而不是散落在各 Agent outbox 的零散文件。

### 文件命名与去重（必须写死）

- 文件名：`decision_record_<decision_id>.json`
- `decision_id` 必须全局唯一（至少在同一 plan 内唯一）
- 系统程序的去重键口径：
  - 主键：`decision_id + sha256(文件内容)`
  - 若同 `decision_id` 且 sha256 相同：可视为重复写入，归档时记录 `SKIPPED_DUPLICATE`
  - 若同 `decision_id` 但 sha256 不同：视为“决策ID被重用/篡改/bug”，进入 DLQ + alert（DECISION_ID_REUSED_WITH_DIFFERENT_CONTENT）

### 与 release_manifest 的权威关系（必须写死）

- `release_manifest.json` 是“是否可交付/是否已发布”的权威放行判据。
- `decision_record.json` 用于统一审计/时间线展示与业务判定落盘；在 release 场景下应与 `release_manifest.json.decision` 保持一致（不一致视为告警信号）。

### 读写一致性窗口（必须说明）

系统运行期允许“最终一致”：
- 先出现 `decision_record.json`，后补齐证据文件（或反之）是允许的；Dashboard/Monitor 应标注“证据暂缺/稍后一致”而不是误判。
- 系统程序写入顺序建议：先归档被引用的证据文件（若系统会收集），再原子写入 `decision_record_*`；避免“决策已出现但证据长期缺失”。

### plan_id子文件夹

每个plan有独立的子文件夹，防止不同plan的文件互相干扰。

**命名**: `<plan_id>/`

**示例**:
```
system_runtime/artifacts/
├── plan_develop_ecommerce/
│   ├── approved_requirements.md
│   └── tested_backend_code.json
└── plan_develop_mobile_app/
    ├── approved_requirements.md
    └── tested_ui_code.json
```

### agent_status子文件夹

存储所有Agent的状态文件。

**命名**: `agent_status/`

**用途**: 集中式监控所有Agent的状态

## 权限与隔离

### 有权限的Agent

系统程序具备跨目录读写权限；普通Agent只读写自己的目录（见PR-003）。因此：

- Agent之间不需要也不允许直接共享目录
- 任何跨Agent的文件投递与集中式状态汇总，均由系统程序完成

### 文件命名规范

验证后的文件使用标准化的前缀：

- `validated_`: 验证通过的文件
- `approved_`: 审批通过的文件
- `tested_`: 测试通过的文件
- `reviewed_`: 评审完成的文件

**示例**:
```
validated_requirements.md
approved_design_doc.json
tested_backend_code.json
reviewed_user_stories.json
```

## Agent状态与进度采集

### 状态文件格式

系统程序以“只读”方式采集Agent状态，数据来源推荐二选一或同时使用：

1. （建议写死）读取Agent自写的心跳快照：`agents/<agent_id>/status_heartbeat.json`（见 `doc/develop/05_agent_heartbeat_and_dispatch.md`）
2. （可选）读取Agent在 `outbox/<plan_id>/` 输出的计划级状态/回执文件（例如 `ack_<message_id>.json`、`task_state*.json`），用于端到端视图与审计
3. （兼容）若历史实现仍使用 `agent_state.json`（见PR-008），系统程序可继续采集，但应逐步迁移到上述“写死路径”的心跳快照口径

**文件内容**:
```json
{
  "agent_id": "agent_001_general_manager",
  "agent_name": "总经理",
  "status": "RUNNING",
  "last_heartbeat": "2025-01-08T10:30:00Z",
  "uptime_seconds": 3600,
  "current_tasks": [
    {
      "task_id": "task_001",
      "plan_id": "plan_develop_ecommerce",
      "status": "IN_PROGRESS",
      "progress": 60
    }
  ],
  "resource_usage": {
    "cpu_percent": 15.5,
    "memory_mb": 512,
    "disk_mb": 2048
  },
  "health": "HEALTHY",
  "last_error": null
}
```

### 状态字段说明

#### agent_id

Agent的唯一标识符。

#### agent_name

Agent的可读名称。

#### status

Agent的当前状态。

**可选值**:
- `STOPPED`: 已停止
- `STARTING`: 启动中
- `RUNNING`: 运行中
- `IDLE`: 空闲
- `DORMANT`: 休眠
- `BLOCKED_WAITING_INPUT`: 等待输入
- `ERROR`: 错误

#### last_heartbeat

最后心跳时间。

**格式**: ISO 8601时间戳

#### uptime_seconds

Agent运行时长（秒）。

#### current_tasks

当前正在处理的任务列表。

**每个任务包含**:
- task_id: 任务ID
- plan_id: Plan ID
- status: 任务状态
- progress: 进度百分比（0-100）

#### resource_usage

资源使用情况。

- **cpu_percent**: CPU使用率
- **memory_mb**: 内存使用（MB）
- **disk_mb**: 磁盘使用（MB）

#### health

健康状态。

**可选值**:
- `HEALTHY`: 健康
- `WARNING`: 警告
- `CRITICAL`: 严重

#### last_error

最后的错误信息（如果有）。

系统程序将采集到的状态汇总为 `system_runtime/agent_status/<agent_id>.json`，并可进一步汇总成 `system_runtime/plans/<plan_id>/plan_status.json`。

## 监控与告警（要点）

### 监控方式

系统程序根据心跳超时、任务长期无进展、资源超限等条件触发告警；告警可以落盘到 `system_runtime/alerts/` 或转发到人工介入通道（见PR-010/PR-025）。

### 监控检查项

1. **心跳检查**
   - last_heartbeat是否过时
   - 过时阈值：heartbeat_interval * 2
   - 过时判定：Agent可能异常或崩溃

2. **健康检查**
   - health字段是否为HEALTHY
   - 非HEALTHY时告警

3. **资源检查**
   - CPU、内存、磁盘使用率
   - 超过阈值时告警

4. **任务检查**
   - current_tasks是否过多
   - 任务进度是否长时间不变
   - 任务是否卡住

5. **错误检查**
   - last_error是否有新错误
   - 错误频率是否过高

### 告警机制

当监控发现异常时：

```json
{
  "alert_type": "HEARTBEAT_TIMEOUT",
  "agent_id": "agent_001",
  "severity": "HIGH",
  "message": "Agent心跳超时",
  "timestamp": "2025-01-08T10:35:00Z",
  "details": {
    "last_heartbeat": "2025-01-08T10:30:00Z",
    "timeout_seconds": 300
  }
}
```

## 产物收集与归档（要点）

### Plan级别隔离

系统程序按plan归档最终产物到 `system_runtime/artifacts/<plan_id>/`。是否视为“最终产物”可通过以下方式定义：

- 由任务文件（DAG方案）明确指定某些输出为“deliverable”
- 或由受信任验证者Agent产出并加上标准化前缀/元数据（例如 `validated_`/`tested_`）

## 安全考虑

### 权限控制

- 只有授权Agent可以写入
- 所有Agent都可以读取
- 防止未授权Agent写入验证文件

### 文件完整性

验证后的文件应包含验证信息：

```json
{
  "file_type": "validated_requirement",
  "validated_by": "agent_documentation_controller",
  "validated_at": "2025-01-08T10:30:00Z",
  "validation_score": 95,
  "content": "...",
  "signature": "..."
}
```

### 审计追踪

系统程序的关键写入/投递操作记录到日志：

```json
{
  "event": "FILE_WRITTEN",
  "agent_id": "agent_testing_engineer",
  "file_path": "system_runtime/artifacts/plan_xxx/tested_code.json",
  "timestamp": "2025-01-08T10:30:00Z",
  "file_hash": "sha256:..."
}
```

## 关键要点

- **系统中介**: 文件投递/状态汇总由系统程序完成（Agent不跨目录）
- **路由可计算**: 任务文件（DAG方案）同时定义依赖与投递规则
- **无共享目录**: 不引入可被多个Agent直接读写的共享文件夹
- **集中可观测**: 系统生成全局状态与投递日志，支持告警与审计

## 与其他原则的配合

### 与PR-001（inbox/outbox文件传递）配合

- inbox/outbox用于Agent间通信
- 系统程序负责跨Agent投递与集中归档

### 与PR-017（日志追踪）配合

- 状态更新记录到日志
- 监控告警记录到日志

### 与PR-022（链式验证机制）配合

- 验证通过的文件由系统程序归档为最终产物
- 后续Agent继续通过inbox/outbox接收验证者的输出文件

---

**最后更新**: 2025-01-08
