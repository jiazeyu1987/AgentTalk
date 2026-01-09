# 公用文件夹和状态监控机制

**原则ID**: PR-024
**来源文档**: shared_folder_monitoring.md
**类别**: 核心机制

---

## 原则描述

系统维护一个公用文件夹，用于存储验证后的安全有效文件。有权限的Agent可以向这个文件夹的plan_id子文件夹写入文件。同时，每个Agent通过心跳向该文件夹的agent_status子目录写入状态，实现集中式监控。

## 全局配置

### 配置文件位置

**路径**: `用户文件夹/AgentFolder/config.json`

### 配置文件格式

```json
{
  "shared_folder_path": "/path/to/shared/folder",
  "authorized_agents": [
    "agent_testing_engineer",
    "agent_documentation_controller"
  ],
  "monitoring": {
    "enabled": true,
    "heartbeat_interval": 60
  }
}
```

### 配置字段说明

#### shared_folder_path

公用文件夹的完整路径。

**格式**: 绝对路径字符串

**示例**: `"/home/user/AgentTalk/shared"`

#### authorized_agents

有权限向公用文件夹写入文件的Agent列表。

**格式**: Agent ID数组

**示例**:
```json
[
  "agent_testing_engineer",
  "agent_documentation_controller",
  "agent_quality_assurance"
]
```

**权限定义**: 带验证功能的Agent，从这些Agent出来的文件是安全有效的。

#### monitoring

监控配置。

- **enabled**: 是否启用状态监控
- **heartbeat_interval**: 心跳写入间隔（秒）

## 公用文件夹结构

### 目录组织

```
shared_folder_path/
├── <plan_id>/
│   ├── validated_*.md           # 验证后的文档
│   ├── approved_*.json          # 审批通过的文件
│   ├── tested_*.json            # 测试通过的文件
│   └── ...                     # 其他验证后的文件
└── agent_status/
    ├── agent_001.json           # Agent状态文件
    ├── agent_002.json
    └── ...
```

### plan_id子文件夹

每个plan有独立的子文件夹，防止不同plan的文件互相干扰。

**命名**: `<plan_id>/`

**示例**:
```
shared_folder_path/
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

## 文件写入权限

### 有权限的Agent

只有被授权的Agent可以向公用文件夹写入文件。

**授权标准**:
- 带验证功能的Agent
- 输出经过验证的文件
- 例如：
  - 测试Agent (agent_testing_engineer)
  - 文控Agent (agent_documentation_controller)
  - 质量保证Agent (agent_quality_assurance)

### 权限验证

Agent在写入前验证权限：

```python
def can_write_to_shared_folder(agent_id):
    config = load_global_config()
    return agent_id in config.get('authorized_agents', [])
```

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

## Agent状态监控

### 状态文件格式

每个Agent在每次心跳时写入状态文件。

**文件位置**: `shared_folder_path/agent_status/agent_<agent_id>.json`

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

### 心跳写入

Agent每次心跳时更新状态文件。

**写入流程**:
1. Agent收集当前状态
2. 构造状态JSON
3. 写入到 `shared_folder_path/agent_status/agent_<agent_id>.json`
4. 更新last_heartbeat时间

**写入间隔**: 由全局配置的heartbeat_interval指定，默认60秒

## 状态监控

### 监控方式

监控程序扫描`agent_status/`目录：

```python
def monitor_agents():
    status_folder = os.path.join(shared_folder_path, "agent_status")

    for status_file in glob.glob(f"{status_folder}/agent_*.json"):
        with open(status_file) as f:
            status = json.load(f)
            # 分析状态
            check_agent_status(status)
```

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

## 文件隔离

### Plan级别隔离

通过plan_id子文件夹实现不同plan的文件隔离：

```
shared_folder_path/
├── plan_develop_ecommerce/
│   └── approved_requirements.md
└── plan_develop_mobile_app/
    └── approved_requirements.md
```

**好处**:
- 不同plan的文件互不干扰
- 可以单独清理某个plan的文件
- 便于按plan查找文件

### 文件覆盖策略

如果同一plan中存在同名文件：

**原则**: 后写入覆盖先写入

**示例**:
```
plan_develop_ecommerce/
├── approved_requirements.md  (version 1, 10:00)
└── approved_requirements.md  (version 2, 11:00, 覆盖version 1)
```

**建议**: 在文件名中包含版本或时间戳
```
approved_requirements_v2.md
approved_requirements_20250108_1100.md
```

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

所有写入操作记录到日志：

```json
{
  "event": "FILE_WRITTEN",
  "agent_id": "agent_testing_engineer",
  "file_path": "shared_folder/plan_xxx/tested_code.json",
  "timestamp": "2025-01-08T10:30:00Z",
  "file_hash": "sha256:..."
}
```

## 关键要点

- **全局配置**: 从用户文件夹/AgentFolder/config.json读取配置
- **权限控制**: 只有授权Agent可以写入公用文件夹
- **Plan隔离**: 通过plan_id子文件夹防止互相干扰
- **状态监控**: 所有Agent写入状态到agent_status/
- **心跳机制**: 定期更新状态，便于监控
- **标准化命名**: 使用validated、approved、tested等前缀
- **集中监控**: 监控agent_status/目录实现全局监控

## 与其他原则的配合

### 与PR-001（inbox/outbox文件传递）配合

- inbox/outbox用于Agent间通信
- 公用文件夹用于存储验证后的全局文件

### 与PR-017（日志追踪）配合

- 状态更新记录到日志
- 监控告警记录到日志

### 与PR-022（链式验证机制）配合

- 验证通过的文件写入公用文件夹
- 后续Agent从公用文件夹读取验证后的文件

---

**最后更新**: 2025-01-08
