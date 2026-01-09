# 日志追踪机制

**原则ID**: PR-017
**来源文档**: logging_traceability.md
**类别**: 核心机制

---

## 原则描述

AgentTalk系统通过多层日志追踪机制确保所有Agent活动可追溯、可恢复、可查询。日志采用事务性写入、自动轮转、统一ID关联，保证数据完整性、查询性能和磁盘空间可控。

## 六层日志结构

### 1. Activity（活动日志）

**文件**: `logs/activity.jsonl`

**用途**: 记录Agent做了什么

**内容**:
- 任务开始/结束
- 文件发送/接收
- 状态变更
- 重要事件

**格式**:
```json
{
  "trace_id": "uuid-1234567890",
  "plan_id": "plan_001",
  "task_id": "task_001",
  "command_id": "cmd_001",
  "agent_id": "agent_general_manager",
  "timestamp": "2025-01-08T10:30:00Z",
  "level": "INFO",
  "event": "TASK_STARTED",
  "data": {
    "task_name": "需求分析",
    "assigned_to": "agent_product_manager"
  }
}
```

### 2. Decision（决策日志）

**文件**: `logs/decision_log.jsonl`

**用途**: 记录Agent为什么做出决策

**内容**:
- Agent选择某个Agent的原因
- 任务分解的依据
- 评分判断的依据
- 冲突解决的理由

**格式**:
```json
{
  "trace_id": "uuid-1234567890",
  "plan_id": "plan_001",
  "task_id": "task_001",
  "agent_id": "agent_general_manager",
  "timestamp": "2025-01-08T10:30:05Z",
  "level": "INFO",
  "decision": "AGENT_SELECTION",
  "reason": "Product manager has required skills for requirement analysis",
  "alternatives": [
    {"agent": "agent_tech_lead", "reason": "More suitable for technical tasks"},
    {"agent": "agent_project_manager", "reason": "More suitable for coordination"}
  ]
}
```

### 3. Execution（执行日志）

**文件**: `workspace/task_xxx/trace/execution_trace.jsonl`

**用途**: 记录任务如何执行的详细步骤

**内容**:
- 执行的每个步骤
- 中间结果
- 子操作
- 性能指标

### 4. Input（输入日志）

**文件**: `workspace/task_xxx/trace/input_trace.json`

**用途**: 记录任务使用的输入文件

**内容**:
- 输入文件列表
- 文件元数据（大小、修改时间、哈希值）
- 输入来源（哪个Agent发送的）

### 5. Output（输出日志）

**文件**: `workspace/task_xxx/trace/output_trace.json`

**用途**: 记录任务产生的输出文件

**内容**:
- 输出文件列表
- 文件元数据
- 输出目标（发送给哪个Agent）

### 6. Error（错误日志）

**文件**: `logs/error_chains.jsonl`

**用途**: 记录完整的错误链

**内容**:
- 错误类型和消息
- 错误传播链
- 上下文信息
- 根本原因分析

## 核心机制

### 1. 事务性写入（Write-Ahead Log）

**问题**: Agent崩溃时日志不完整

**解决方案**: 先写临时文件，再原子性重命名

**写入流程**:
1. 日志先写入 `activity.jsonl.tmp`
2. 写入完成后，原子性重命名为 `activity.jsonl`
3. 如果崩溃，.tmp文件会被清理，不影响正式日志

**好处**:
- 原子性：要么全部写入，要么完全不写
- 一致性：不会出现写到一半的日志
- 可恢复：崩溃后可以从最后一个完整的日志恢复

### 2. 检查点机制

**问题**: 无法区分"任务进行中"和"任务卡死"

**解决方案**: 定期更新任务状态

**任务状态** (task_state.json):
- PENDING: 待执行
- RUNNING: 执行中（带最后更新时间戳）
- COMPLETED: 已完成
- FAILED: 失败
- BLOCKED: 阻塞等待输入

**Agent恢复流程**:
1. 扫描所有 task_state.json
2. 如果状态是RUNNING且最后更新时间 > 超时阈值 → 标记为FAILED
3. 如果状态是PENDING → 重新执行
4. 如果状态是BLOCKED → 检查输入是否到达，决定是否恢复

**好处**:
- 明确知道每个任务的状态
- Agent重启后可以恢复未完成的任务
- 自动检测僵尸任务

### 3. 日志轮转机制

**问题**: 日志文件过大，查询困难

**解决方案**: 按时间和大小轮转

**轮转策略**:
1. 按时间：每天一个新文件
   - `activity_2025-01-08.jsonl`
   - `activity_2025-01-09.jsonl`
2. 按大小：单文件超过10MB创建新文件
   - `activity_2025-01-08_001.jsonl`
   - `activity_2025-01-08_002.jsonl`
3. 自动压缩：7天前的日志自动压缩为.gz
4. 自动删除：30天前的压缩日志自动删除

**好处**:
- 文件大小可控
- 查询性能好
- 磁盘空间可控

### 4. 统一ID和关联

**问题**: 多个日志文件难以关联

**解决方案**: 每条日志包含统一的全局ID

**统一ID字段**:
- trace_id: 全局唯一的追踪ID（UUID）
- plan_id: Plan标识符
- task_id: 任务标识符
- command_id: 命令标识符
- agent_id: Agent标识符
- message_id: 消息/投递单元的唯一ID（用于文件投递去重与端到端关联，见PR-001）
- timestamp: ISO 8601时间戳
- level: 日志级别（DEBUG/INFO/WARN/ERROR）

**关联方式**:
- 用trace_id关联所有日志
- 用plan_id查询整个任务的完整流程
- 用task_id查询单个任务的所有日志

**好处**:
- 可以追踪一个请求的完整生命周期
- 可以快速定位问题
- 可以做端到端的性能分析

## 文件级可追溯性（推荐）

为保证“只用文件传递”的可靠性，推荐在输入/输出日志中记录以下元数据：

- `sha256`: 文件内容哈希（用于完整性校验与去重）
- `idempotency_key`: 幂等键（用于“重复消息不重复执行”）
- `schema_version`: 命令/消息schema版本（用于解析兼容与死信处理）
- `delivery`: 投递信息（from_agent、to_agent、delivered_at、delivery_id）

这些字段可以来自 `*.msg.json`/`*.meta.json` 信封文件，或由系统路由程序在投递日志中统一记录（见PR-024）。

### 5. 索引文件

**问题**: 查询慢，需要扫描整个文件

**解决方案**: 自动生成索引

**索引文件**: `logs/activity_index.json`

**索引内容**:
```json
{
  "2025-01-08": {
    "file": "activity_2025-01-08.jsonl",
    "plans": ["plan_001", "plan_002"],
    "tasks": ["task_001", "task_002"],
    "errors": 5,
    "size_bytes": 1024000,
    "first_entry": "2025-01-08T00:00:00Z",
    "last_entry": "2025-01-08T23:59:59Z"
  },
  "2025-01-09": {
    "file": "activity_2025-01-09.jsonl",
    "plans": ["plan_003"],
    "tasks": ["task_003"],
    "errors": 2,
    "size_bytes": 512000,
    "first_entry": "2025-01-09T00:00:00Z",
    "last_entry": "2025-01-09T15:30:00Z"
  }
}
```

**查询流程**:
1. 先查索引，定位到具体文件
2. 只读取相关的日志文件
3. 避免扫描所有文件

**好处**:
- 快速查询
- 可以做聚合统计
- 可以快速定位问题时间段

### 6. 异步写入队列

**问题**: 频繁写日志影响性能

**解决方案**: 内存队列 + 批量写入

**写入流程**:
1. 日志先写入内存队列（非阻塞）
2. 后台线程每秒批量写入磁盘
3. 队列大小限制：最大1000条
4. 超过后阻塞主线程，强制写入

**配置**:
- 批量大小：每次最多写100条
- 刷新间隔：每秒刷新一次
- 队列上限：1000条，超过后阻塞

**好处**:
- 不阻塞主流程
- 批量写入减少I/O次数
- 性能好

**权衡**:
- Agent崩溃时，内存队列未落盘的日志会丢失
- 可以通过检查点机制恢复

### 7. 压缩和归档

**问题**: 历史日志占用磁盘

**解决方案**: 自动归档

**归档策略**:
1. 7天前的日志 → 压缩为.gz
2. 30天前的压缩日志 → 移动到archive目录
3. 90天前的归档日志 → 删除（可配置）

**归档目录结构**:
```
archive/
  2025/
    01/
      activity_2025-01-08.jsonl.gz
      decision_log_2025-01-08.jsonl.gz
      error_chains_2025-01-08.jsonl.gz
    02/
      activity_2025-02-01.jsonl.gz
```

**好处**:
- 自动清理，不占满磁盘
- 历史数据仍可访问
- 压缩节省空间（约10倍）

### 8. 错误链追踪

**问题**: 错误难以定位根本原因

**解决方案**: 结构化错误链

**错误日志格式**:
```json
{
  "error_id": "err_001",
  "trace_id": "uuid-1234567890",
  "plan_id": "plan_001",
  "task_id": "task_002",
  "error_type": "FILE_NOT_FOUND",
  "error_message": "Required input file missing: requirements.md",
  "timestamp": "2025-01-08T10:30:00Z",
  "stack_trace": "...",
  "context": {
    "expected_files": ["requirements.md"],
    "actual_files": ["user_input.txt"],
    "inbox_path": "/inbox/plan_001/"
  },
  "caused_by": null,
  "resolved": false,
  "resolution": null
}
```

**错误传播**:
- caused_by: 指向上游错误ID
- 形成错误链：err_003 → err_002 → err_001
- 可以追踪到根本原因

**好处**:
- 可以追踪错误的传播链
- 可以找到根本原因
- 可以统计错误类型

## 日志级别

**DEBUG**: 调试信息，默认不记录
**INFO**: 一般信息，正常流程
**WARN**: 警告信息，不影响运行但需要注意
**ERROR**: 错误信息，需要处理
**FATAL**: 致命错误，导致Agent无法继续

## 性能考虑

### I/O优化

- 使用异步队列，减少阻塞
- 批量写入，减少I/O次数
- 内存映射文件，提高读取速度

### 空间优化

- 自动轮转，文件大小可控
- 自动压缩，节省空间
- 自动清理，避免占满磁盘

### 查询优化

- 索引文件，快速定位
- 按时间分片，减少扫描范围
- 压缩归档，历史数据不影响查询性能

## 关键要点

- **事务性写入**: WAL机制保证日志不损坏
- **检查点恢复**: 定期更新任务状态，支持崩溃恢复
- **自动轮转**: 按时间和大小轮转，文件可控
- **统一ID**: trace_id关联所有日志，可完整追踪
- **索引加速**: 索引文件支持快速查询
- **异步写入**: 队列缓冲，不影响主流程性能
- **自动归档**: 压缩和清理，磁盘空间可控
- **错误链**: 结构化错误追踪，定位根本原因

## 与其他原则的配合

### 与PR-001（inbox/outbox文件传递）配合

- 文件发送/接收都记录到activity.jsonl
- 文件元数据记录到input_trace/output_trace

### 与PR-007（统一的执行命令）配合

- 命令开始/结束记录到activity.jsonl
- 命令执行的决策记录到decision_log.jsonl
- 命令执行的详细步骤记录到execution_trace.jsonl

### 与PR-009（任务分配机制）配合

- 任务分配决策记录到decision_log.jsonl
- DAG图生成记录到activity.jsonl
- 每个子任务的状态记录到各自的task_state.json

---

**最后更新**: 2025-01-08
