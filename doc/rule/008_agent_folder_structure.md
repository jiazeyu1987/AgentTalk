# Agent文件夹结构

**原则ID**: PR-008
**来源文档**: agent_architecture_v2.md, CLAUDE.md
**类别**: 核心机制

---

## 原则描述

每个Agent都有标准化的文件夹结构，这个结构支持核心程序与技能分离、inbox/outbox文件传递、plan级组织、六层可追溯性等核心机制。

## 完整文件夹结构

```
agent_xxx_name/
├── core/                           # 核心Python程序（100%稳定）
│   ├── main.py                     # Agent入口点，初始化并启动所有组件
│   ├── heartbeat_engine.py         # 心跳引擎，定期扫描inbox
│   ├── trace_logger.py             # 记录所有活动、决策、错误
│   ├── state_manager.py            # 管理agent_state.json
│   ├── skill_dispatcher.py         # 路由消息到适当的技能
│   ├── wakeup_listener.py          # 休眠时监听唤醒信号
│   └── wakeup_sender.py            # 通过outbox发出唤醒信号（由系统路由程序投递）
│
├── agent_profile.json              # Agent配置（lifecycle、heartbeat、visibility等）
├── agent_state.json                # 运行状态（自动生成，status、health等）
│
├── skills/                         # 业务逻辑技能（LLM驱动，可能失败）
│   └── skill_xxx/
│       ├── skill.md                # 技能定义、描述、参数、返回值
│       ├── references/             # 参考文档和资源
│       └── scripts/                # 可选：稳定的Python处理器
│           └── handler.py
│
├── templates/                      # 消息、文档、提示词模板
├── configs/                        # 配置文件
├── cache/                          # 缓存数据
│
├── inbox/                          # ⭐ 接收消息（唯一的交互入口）
│   └── <plan_id>/                  # 按plan组织
│       ├── *.msg.json              # 任务消息
│       ├── cmd_*.json              # 执行命令
│       └── <资源文件>              # 任意扩展名的资源文件
│
├── outbox/                         # ⭐ 发送消息（唯一的交互出口）
│   └── <plan_id>/                  # 按plan组织
│       └── <发送给其他Agent的文件>
│
├── workspace/                      # 任务工作空间
│   └── task_xxx/
│       ├── trace/                  # 执行跟踪
│       │   ├── execution_trace.jsonl
│       │   ├── input_trace.json
│       │   └── output_trace.json
│       ├── inputs/                 # 任务输入
│       ├── outputs/                # 任务输出
│       ├── work/                   # 临时工作文件
│       └── task_state.json         # 任务状态
│
├── resources/                      # 静态资源文件
│
├── logs/                           # ⭐ 六层可追溯性日志
│   ├── activity.jsonl              # 活动：Agent做了什么
│   ├── decision_log.jsonl          # 决策：Agent为什么这样做
│   ├── error_chains.jsonl          # 错误：完整的错误链
│   └── llm_calls.jsonl             # LLM调用记录
│
└── .runtime/                       # 运行时文件（不提交到git）
    ├── heartbeat.pid               # 心跳进程ID
    └── heartbeat.lock              # 心跳锁文件
```

## 目录说明

### 1. core/ - 核心程序

**用途**: 100%稳定的Python程序，处理Agent的基础设施和关键功能。

**文件说明**:
- `main.py`: Agent入口点，初始化所有组件并启动Agent
- `heartbeat_engine.py`: 定期扫描inbox，发现新文件并分发
- `trace_logger.py`: 记录所有活动、决策、错误到日志文件
- `state_manager.py`: 管理agent_state.json，更新Agent状态
- `skill_dispatcher.py`: 路由消息到适当的技能处理
- `wakeup_listener.py`: Agent休眠时监听唤醒信号
- `wakeup_sender.py`: 通过outbox向其他Agent发送唤醒信号（实际投递由系统路由程序完成）

**关键特性**:
- 必须保证100%稳定性
- 直接Python执行，不依赖外部LLM调用
- 处理关键的基础设施功能

### 2. agent_profile.json - Agent配置

**用途**: Agent的配置文件，定义Agent的基本属性和行为。

**典型内容**:
```json
{
  "agent_id": "agent_xxx_name",
  "agent_name": "Human-readable name",
  "lifecycle": {
    "idle_timeout_seconds": 1800,
    "enable_dormant": true,
    "wakeup_check_interval": 10,
    "auto_wakeup_on_message": true
  },
  "heartbeat": {
    "interval_seconds": 10
  },
  "visibility_list": {
    "can_see": ["agent_general_manager"],
    "can_be_seen_by": ["agent_general_manager"]
  }
}
```

### 3. agent_state.json - 运行状态

**用途**: 自动生成的Agent运行状态，由state_manager.py维护。

**典型内容**:
```json
{
  "status": "RUNNING",
  "health": {
    "last_heartbeat": "2025-01-08T10:30:00Z",
    "idle_seconds": 120
  },
  "current_tasks": []
}
```

**状态值**: STOPPED, STARTING, RUNNING, IDLE, DORMANT, BLOCKED_WAITING_INPUT

### 4. skills/ - 技能目录

**用途**: 业务逻辑模块，定义Agent的专业能力。

**每个技能包含**:
- `skill.md`: 技能定义（技能名称、版本、类型、描述、输入、输出）
- `references/`: 参考文档和资源
- `scripts/handler.py`: 可选的稳定Python处理器

**关键特性**:
- LLM驱动，使用skill.md作为提示词
- 可以失败，不像core程序必须100%稳定
- 可以有可选的scripts/handler.py处理稳定逻辑

### 5. inbox/ - 接收消息

**用途**: 接收来自其他Agent的文件，唯一的交互入口。

**文件类型**:
- `*.msg.json`: 任务消息
- `cmd_*.json`: 执行命令
- 任意扩展名: 资源文件（文档、数据、配置等）

**组织方式**: 按`plan_id`组织到子目录

**关键特性**:
- Agent只能读取自己的inbox
- 其他Agent通过outbox发送文件到此
- 心跳引擎定期扫描新文件

### 6. outbox/ - 发送消息

**用途**: 向其他Agent发送文件，唯一的交互出口。

**文件类型**: 任意，取决于要发送的内容

**组织方式**: 按`plan_id`组织到子目录

**工作流程**:
1. Agent将文件放到outbox/<plan_id>/
2. 系统自动投递到目标Agent的inbox/<plan_id>/
3. Agent从inbox读取文件

### 7. workspace/ - 工作空间

**用途**: Agent处理任务的临时工作空间。

**每个任务包含**:
- `trace/`: 执行跟踪（execution_trace, input_trace, output_trace）
- `inputs/`: 任务输入文件
- `outputs/`: 任务输出文件
- `work/`: 临时工作文件
- `task_state.json`: 任务状态

**组织方式**: 按task_id组织到子目录

### 8. logs/ - 日志目录

**用途**: 实现六层可追溯性。

**日志文件**:
- `activity.jsonl`: Agent做了什么
- `decision_log.jsonl`: Agent为什么做出决策
- `error_chains.jsonl`: 完整的错误链
- `llm_calls.jsonl`: LLM调用记录

**格式**: JSONL（每行一个JSON对象）

### 9. .runtime/ - 运行时文件

**用途**: 存储运行时状态和锁文件。

**文件**:
- `heartbeat.pid`: 心跳进程ID
- `heartbeat.lock`: 心跳锁文件

**特性**: 不提交到git，只在Agent运行时存在

## 文件夹结构的核心原则

### 1. 核心与技能分离

- `core/`: 稳定的Python程序，处理基础设施
- `skills/`: 灵活的业务逻辑，LLM驱动

### 2. inbox/outbox唯一交互

- 所有Agent间交互都通过文件传递
- inbox是唯一的接收入口
- outbox是唯一的发送出口

### 3. plan级组织

- inbox/outbox按plan_id组织到子目录
- 相关的文件在同一个plan目录下
- 便于批量处理和清理

### 4. 六层可追溯性

- logs/记录所有活动
- workspace/trace/记录执行细节
- 完整的决策、输入、输出、错误追踪

### 5. Agent隔离

- 每个Agent只能访问自己的文件夹
- 通过系统投递在inbox和outbox之间传递文件
- 保证了安全和隔离

## 创建新Agent的步骤

1. 复制模板: `cp -r template/agent_template/ system/agents/agent_xxx_name/`
2. 配置agent_profile.json
3. 添加技能到skills/目录
4. 启动Agent: `cd system/agents/agent_xxx_name/ && python core/main.py`

## 关键要点

- **标准化**: 所有Agent使用相同的文件夹结构
- **职责分离**: core/稳定，skills/灵活
- **可追溯**: logs/和workspace/trace/记录所有活动
- **隔离性**: 每个Agent只能访问自己的文件夹
- **组织性**: 按plan和task组织，便于管理
- **可扩展**: skills/目录可以添加新技能

---

**最后更新**: 2025-01-08
