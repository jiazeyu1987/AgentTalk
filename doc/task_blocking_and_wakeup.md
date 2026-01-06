# AgentTalk 任务阻塞与唤醒机制

## 文档信息

- **文档名称**：任务阻塞与唤醒机制
- **版本**：v1.0
- **创建日期**：2025-01-05
- **目的**：处理"资料随任务补充，Agent等待唤醒"的场景

---

## 1. 场景描述

### 1.1 典型场景

**用户的困境**：
> "我想做一个项目，但现在资料还不齐。比如产品需求文档还在写，技术方案还没确定。但是我想先启动项目，随着资料逐步补充，系统能自动推进。"

**具体例子**：

| 场景 | 已有资料 | 缺失资料 | 需要等待 |
|------|---------|---------|---------|
| **网站开发** | 项目名称、大致功能 | 详细需求、UI设计图 | 等产品经理 |
| **数据分析** | 数据字段说明 | 实际数据文件 | 等客户 |
| **文档翻译** | 源文档 | 专业术语表 | 等业务专家 |
| **系统集成** | 接口规范 | 第三方API密钥 | 等供应商 |

### 1.2 问题分析

**传统方式的问题**：
❌ 任务卡住无法推进
❌ 需要人工干预和协调
❌ 资料一到就要手动重启
❌ 容易遗漏和混乱

**AgentTalk的解决方案**：
✅ Agent自动识别缺失的输入
✅ 进入阻塞等待状态
✅ 通知用户需要什么资料
✅ 资料提供后自动唤醒
✅ 继续执行任务

---

## 2. 核心概念

### 2.1 任务输入依赖

**每个任务可以声明"输入依赖"**：

```json
{
  "task_id": "task_003",
  "title": "开发用户注册功能",

  "input_requirements": [
    {
      "input_id": "product_requirements",
      "description": "产品需求文档",
      "type": "document",
      "format": "PDF or Markdown",
      "provided_by": "product_manager",
      "location": "workspace/inputs/requirements.pdf",
      "status": "PENDING",  // PENDING | PROVIDED | APPROVED
      "urgency": "BLOCKING"   // BLOCKING | OPTIONAL
    },
    {
      "input_id": "ui_designs",
      "description": "UI设计稿",
      "type": "images",
      "format": "Figma or PNG",
      "provided_by": "USER",
      "location": "workspace/inputs/ui_designs/",
      "status": "PENDING",
      "urgency": "BLOCKING"
    },
    {
      "input_id": "technical_specs",
      "description": "技术规范",
      "type": "document",
      "format": "Markdown",
      "provided_by": "tech_manager",
      "location": "workspace/inputs/tech_specs.md",
      "status": "OPTIONAL",
      "urgency": "OPTIONAL"
    }
  ]
}
```

### 2.2 Agent状态扩展

**现有任务状态**：
- PENDING（等待执行）
- READY（准备执行）
- EXECUTING（执行中）
- READY_TO_CHECK（待审查）
- DONE（完成）
- FAILED（失败）

**新增状态**：
- **BLOCKED_WAITING_INPUT**（等待输入）：阻塞，等待用户或其他Agent提供资料
- **INPUT_PROVIDED**（输入已提供）：资料已提供，等待验证

### 2.3 输入提供位置

**统一的输入文件存储**：

```
workspace/
├── inputs/                    # 全局输入（跨项目）
│   ├── requirements.pdf
│   └── company_policies.pdf
│
└── projects/                  # 项目级输入
    └── project_001/
        └── inputs/
            ├── user_stories.json
            ├── ui_designs/
            │   ├── page1.png
            │   └── page2.png
            └── api_specs.yaml
```

---

## 3. 工作流程

### 3.1 完整流程图

```
┌─────────────────────────────────────────┐
│  Step 1: 用户提交任务（资料不完整）    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Step 2: Agent接收任务                 │
│  - 检查input_requirements              │
│  - 发现缺失的输入                       │
│  - 区分BLOCKING vs OPTIONAL            │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Step 3: Agent进入等待状态            │
│  - 状态改为BLOCKED_WAITING_INPUT       │
│  - 生成"缺失资料清单"                  │
│  - 记录等待时间                       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Step 4: 通知用户                      │
│  - Dashboard通知                       │
│  - 邮件通知                           │
│  - 说明需要什么资料、放到哪里          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Step 5: 用户补充资料                 │
│  - 将资料放到指定位置                  │
│  - 系统检测到新文件                    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Step 6: 自动唤醒Agent                │
│  - 验证输入完整性                      │
│  - 状态改为READY                       │
│  - Agent继续执行任务                   │
└─────────────────────────────────────────┘
```

### 3.2 详细步骤说明

#### Step 1: 用户提交任务

```json
// user_tasks/inbox/task_003.json
{
  "task_id": "user_task_003",
  "title": "开发用户注册功能",
  "description": "实现用户注册、登录、密码找回功能",

  "note": "产品需求文档还在编写中，预计本周五完成。
         UI设计图预计下周完成。
         希望先启动任务，资料就位后自动推进。",

  "context": {
    "project_id": "project_001",
    "team": ["frontend_expert", "backend_expert"]
  },

  "input_requirements": [
    {
      "input_id": "requirements_doc",
      "description": "产品需求文档",
      "type": "document",
      "expected_format": "PDF or Markdown",
      "required_fields": ["功能列表", "用户故事", "验收标准"],
      "provide_method": "上传到 workspace/projects/project_001/inputs/",
      "expected_by": "2025-01-10",
      "urgency": "BLOCKING"  // 阻塞任务
    },
    {
      "input_id": "ui_designs",
      "description": "UI设计稿（注册页、登录页）",
      "type": "images",
      "expected_format": "PNG or Figma export",
      "required_files": ["register.png", "login.png"],
      "provide_method": "上传到 workspace/projects/project_001/inputs/ui_designs/",
      "expected_by": "2025-01-15",
      "urgency": "BLOCKING"
    }
  ],

  "execution_plan": "等待所有BLOCKING输入就绪后自动开始"
}
```

#### Step 2: Agent接收任务

```
Python专家接收任务：

任务分析：
{
  "task_id": "user_task_003",
  "title": "开发用户注册功能",
  "inputs": [
    {
      "input_id": "requirements_doc",
      "status": "PENDING",
      "urgency": "BLOCKING"
    },
    {
      "input_id": "ui_designs",
      "status": "PENDING",
      "urgency": "BLOCKING"
    }
  ]
}

Python专家检查输入：
check_inputs(input_requirements):

结果：
{
  "requirements_doc": {
    "exists": false,
    "location": "workspace/projects/project_001/inputs/requirements.pdf",
    "status": "MISSING",
    "urgency": "BLOCKING"
  },
  "ui_designs": {
    "exists": false,
    "location": "workspace/projects/project_001/inputs/ui_designs/",
    "status": "MISSING",
    "urgency": "BLOCKING"
  }
}

判断：有两个BLOCKING输入缺失 → 无法开始执行
操作：进入等待状态
```

#### Step 3: Agent进入等待状态

```
Python专家更新状态：

{
  "task_id": "user_task_003",
  "agent_id": "agent_202_python_expert",
  "status": "BLOCKED_WAITING_INPUT",
  "blocked_since": "2025-01-05T10:00:00Z",

  "missing_inputs": [
    {
      "input_id": "requirements_doc",
      "description": "产品需求文档",
      "expected_location": "workspace/projects/project_001/inputs/requirements.pdf",
      "expected_by": "2025-01-10",
      "urgency": "BLOCKING"
    },
    {
      "input_id": "ui_designs",
      "description": "UI设计稿",
      "expected_location": "workspace/projects/project_001/inputs/ui_designs/",
      "expected_by": "2025-01-15",
      "urgency": "BLOCKING"
    }
  ],

  "agent_note": "我将等待这些资料就位。
                 资料提供后我会自动开始工作。
                 请确保文件格式符合要求。"
}

记录到 state/current_status.json
```

#### Step 4: 通知用户

**方式1：Dashboard通知**

```
┌─────────────────────────────────────────┐
│  AgentTalk Dashboard                    │
├─────────────────────────────────────────┤
│                                         │
│  📋 任务：开发用户注册功能              │
│  状态：⏸️ 等待资料                      │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ ⏸️ Python专家正在等待          │   │
│  │                                 │   │
│  │ 需要的资料：                    │   │
│  │                                 │   │
│  │ 1. 产品需求文档                 │   │
│  │    格式：PDF或Markdown         │   │
│  │    位置：workspace/projects/    │   │
│  │          project_001/inputs/    │   │
│  │          requirements.pdf       │   │
│  │    截止时间：2025-01-10         │   │
│  │                                 │   │
│  │ 2. UI设计稿（2个页面）          │   │
│  │    格式：PNG                   │   │
│  │    位置：workspace/projects/    │   │
│  │          project_001/inputs/    │   │
│  │          ui_designs/           │   │
│  │    文件：register.png          │   │
│  │          login.png             │   │
│  │    截止时间：2025-01-15         │   │
│  │                                 │   │
│  │ [上传资料]                      │   │
│  └─────────────────────────────────┘   │
│                                         │
│  📌 提示：                            │
│  - 请确保文件名符合要求              │
│  - 上传后会自动通知Python专家         │
│  - 可以分批上传（先传需求，再传UI）  │
│                                         │
└─────────────────────────────────────────┘
```

**方式2：邮件通知**

```
主题：【AgentTalk】任务需要资料 - 开发用户注册功能

你好，

Python专家正在执行"开发用户注册功能"任务，但需要你提供以下资料：

【必需资料】（阻塞任务）

1. 产品需求文档
   - 格式：PDF或Markdown
   - 必需字段：功能列表、用户故事、验收标准
   - 上传位置：workspace/projects/project_001/inputs/requirements.pdf
   - 截止时间：2025-01-10

2. UI设计稿（注册页、登录页）
   - 格式：PNG图片
   - 必需文件：
     * register.png
     * login.png
   - 上传位置：workspace/projects/project_001/inputs/ui_designs/
   - 截止时间：2025-01-15

【上传方式】
方式1：通过Dashboard上传按钮
方式2：直接复制文件到指定目录
方式3：使用命令：cp local_file.pdf workspace/projects/project_001/inputs/

【重要提示】
- 资料上传后会自动唤醒Python专家
- 可以分批上传（例如：先上传需求文档）
- 如果有任何问题，请回复此邮件

任务ID: user_task_003
Agent: Python专家（agent_202_python_expert）
开始等待时间: 2025-01-05 10:00

谢谢！
AgentTalk系统
```

#### Step 5: 用户补充资料

**方式1：通过Dashboard上传**

```
用户操作：
1. 点击"上传资料"按钮
2. 选择文件：requirements.pdf
3. 系统上传到：workspace/projects/project_001/inputs/requirements.pdf

系统处理：
{
  "upload_event": {
    "file": "requirements.pdf",
    "location": "workspace/projects/project_001/inputs/requirements.pdf",
    "uploaded_at": "2025-01-08T14:30:00Z",
    "uploaded_by": "USER",
    "task_id": "user_task_003"
  }
}
```

**方式2：直接复制文件**

```bash
# 用户在命令行执行
$ cp ~/Downloads/requirements.pdf workspace/projects/project_001/inputs/
$ cp ~/Downloads/register.png workspace/projects/project_001/inputs/ui_designs/
$ cp ~/Downloads/login.png workspace/projects/project_001/inputs/ui_designs/

# 文件监控系统检测到新文件
```

**方式3：通过邮件附件**

```
用户回复邮件：
"附件是需求文档，请查收"

系统处理：
1. 保存附件到 workspace/projects/project_001/inputs/requirements.pdf
2. 触发文件监控事件
```

#### Step 6: 自动唤醒Agent

**文件监控系统**：

```python
# 系统文件监控服务
class FileMonitoringService:
    def __init__(self):
        self.watched_directories = []
        self.waiting_agents = {}  # task_id -> agent_id

    def watch_directory(self, directory: str):
        """监控指定目录"""
        self.watched_directories.append(directory)

    def check_new_files(self):
        """检查新文件"""
        for directory in self.watched_directories:
            new_files = scan_directory(directory)

            for file in new_files:
                self.on_file_added(file)

    def on_file_added(self, file_path: str):
        """文件添加时的处理"""
        # 查找等待此文件的Agent
        for task_id, agent_info in self.waiting_agents.items():
            if self.file_matches_requirement(file_path, agent_info.required_inputs):
                # 唤醒Agent
                self.wakeup_agent(task_id, agent_info.agent_id, file_path)

    def wakeup_agent(self, task_id: str, agent_id: str, file_path: str):
        """唤醒等待的Agent"""
        # 发送WAKEUP消息
        send_message(
            to_agent=agent_id,
            message={
                "message_type": "WAKEUP",
                "trigger": "INPUT_PROVIDED",
                "file": file_path,
                "task_id": task_id,
                "action": "请检查输入是否完整，如果完整则开始执行任务"
            }
        )
```

**Agent接收WAKEUP消息**：

```
Python专家收到WAKEUP消息：

{
  "message_type": "WAKEUP",
  "trigger": "INPUT_PROVIDED",
  "file": "workspace/projects/project_001/inputs/requirements.pdf",
  "task_id": "user_task_003"
}

Python专家处理：

1. 检查输入状态
   check_input_status():

   结果：
   {
     "requirements_doc": {
       "exists": true,
       "status": "PROVIDED",
       "location": "workspace/projects/project_001/inputs/requirements.pdf"
     },
     "ui_designs": {
       "exists": false,
       "status": "PENDING",
       "location": "workspace/projects/project_001/inputs/ui_designs/"
     }
   }

2. 判断是否所有BLOCKING输入就绪
   if all_blocking_inputs_ready():
       → 可以开始执行
   else:
       → 继续等待其他输入

3. 本例中：ui_designs仍缺失
   决定：继续等待，但更新状态

   状态更新：
   {
     "status": "BLOCKED_WAITING_INPUT",
     "missing_inputs": ["ui_designs"],
     "received_inputs": ["requirements_doc"],
     "message": "需求文档已收到，继续等待UI设计稿"
   }

4. 通知用户进度
   send_notification("需求文档已收到，等待UI设计稿...")
```

**所有输入就绪后**：

```
用户上传UI设计稿：
- register.png
- login.png

文件监控系统检测到新文件
→ 唤醒Python专家

Python专家检查：
{
  "requirements_doc": "PROVIDED" ✓
  "ui_designs": "PROVIDED" ✓
}

判断：所有BLOCKING输入就绪
操作：开始执行任务

状态更新：
{
  "status": "READY",
  "message": "所有必需资料已就位，开始执行任务"
}

Python专家开始工作：
1. 读取需求文档
2. 查看UI设计图
3. 开发用户注册功能
...
```

---

## 4. 关键机制设计

### 4.1 输入依赖声明

**在任务分配时声明输入需求**：

```json
{
  "message_type": "TASK_ASSIGNMENT",
  "from_agent": "agent_003_tech_manager",
  "to_agent": "agent_202_python_expert",

  "task": {
    "task_id": "task_003",
    "title": "开发用户注册功能",
    "description": "基于需求文档和UI设计开发功能",

    "input_requirements": [
      {
        "input_id": "requirements_doc",
        "description": "产品需求文档",
        "type": "document",
        "expected_format": "PDF or Markdown",
        "required_fields": ["功能列表", "用户故事", "验收标准"],
        "validation": {
          "check_fields": true,
          "min_size": "1KB",
          "max_size": "10MB"
        },
        "provide_method": "上传到 workspace/projects/project_001/inputs/",
        "expected_by": "2025-01-10",
        "urgency": "BLOCKING",
        "on_missing": "WAIT"  // WAIT | FAIL | ASK_USER
      },

      {
        "input_id": "ui_designs",
        "description": "UI设计稿",
        "type": "images",
        "expected_format": "PNG",
        "required_files": ["register.png", "login.png"],
        "provide_method": "上传到 workspace/projects/project_001/inputs/ui_designs/",
        "expected_by": "2025-01-15",
        "urgency": "BLOCKING",
        "on_missing": "WAIT"
      },

      {
        "input_id": "tech_specs",
        "description": "技术规范（可选）",
        "type": "document",
        "expected_format": "Markdown",
        "urgency": "OPTIONAL",
        "on_missing": "SKIP"
      }
    ]
  },

  "execution": {
    "wait_for_inputs": true,
    "auto_start_on_complete": true,
    "partial_execution": false
  }
}
```

### 4.2 输入验证

**Agent接收到输入后的验证**：

```python
def validate_input(input_requirement: Dict, file_path: str) -> Dict:
    """验证输入是否符合要求"""

    result = {
        "valid": False,
        "errors": [],
        "warnings": []
    }

    # 检查文件是否存在
    if not file_exists(file_path):
        result["errors"].append("文件不存在")
        return result

    # 检查文件格式
    file_format = get_file_format(file_path)
    expected_format = input_requirement["expected_format"]

    if file_format not in expected_format:
        result["errors"].append(f"格式错误：期望{expected_format}，实际{file_format}")

    # 检查必需字段
    if "required_fields" in input_requirement:
        content = read_file(file_path)
        for field in input_requirement["required_fields"]:
            if field not in content:
                result["errors"].append(f"缺少必需字段：{field}")

    # 检查文件大小
    file_size = get_file_size(file_path)
    if "validation" in input_requirement:
        validation = input_requirement["validation"]
        if "min_size" in validation and file_size < validation["min_size"]:
            result["warnings"].append(f"文件过小：{file_size} < {validation['min_size']}")
        if "max_size" in validation and file_size > validation["max_size"]:
            result["errors"].append(f"文件过大：{file_size} > {validation['max_size']}")

    # 如果有错误，验证失败
    if result["errors"]:
        result["valid"] = False
    else:
        result["valid"] = True

    return result
```

### 4.3 状态转换图

```
┌──────────┐
│  READY   │
└─────┬────┘
      │ 检查输入
      │
      v
┌──────────────────┐
│  检查输入依赖     │
└─────┬────────────┘
      │
      ├─→ 所有输入就绪 ─→ EXECUTING
      │
      └─→ 有缺失输入 ─→ BLOCKED_WAITING_INPUT
                           │
                           └─→ 监控文件系统
                               │
                               ├─→ 输入提供 ─→ 验证
                               │               │
                               │               ├─→ 有效 ─→ READY
                               │               │
                               │               └─→ 无效 ─→ 通知用户
                               │
                               └─→ 超时 ─→ FAILED 或 ESCCALATE
```

### 4.4 超时处理

**超时配置**：

```json
{
  "task_id": "task_003",
  "timeout_settings": {
    "input_wait_timeout": "7 days",  // 等待输入的最长时间
    "individual_input_timeout": {
      "requirements_doc": "5 days",
      "ui_designs": "10 days"
    },
    "on_timeout": {
      "action": "ESCALATE",  // REMIND | ESCALATE | FAIL
      "escalate_to": "project_manager",
      "message": "等待超时，请协助解决"
    }
  }
}
```

**超时处理流程**：

```
if waiting_time > input_wait_timeout:
    if on_timeout.action == "REMIND":
        # 再次提醒用户
        send_notification({
            "type": "REMINDER",
            "message": "任务仍在等待资料，请尽快提供",
            "missing_inputs": [...],
            "waiting_time": "7天"
        })

    elif on_timeout.action == "ESCALATE":
        # 上报给经理
        escalate_to_manager({
            "task": task_id,
            "issue": "等待输入超时",
            "missing_inputs": [...],
            "suggestion": "请协助催促资料提供"
        })

    elif on_timeout.action == "FAIL":
        # 标记任务失败
        update_task_status({
            "task_id": task_id,
            "status": "FAILED",
            "reason": "等待输入超时"
        })
```

---

## 5. 部分执行与分批输入

### 5.1 部分执行（Partial Execution）

**场景**：某些任务可以部分执行，不需要所有输入

```json
{
  "task_id": "task_003",
  "title": "开发用户注册功能",

  "input_requirements": [
    {
      "input_id": "requirements_doc",
      "urgency": "BLOCKING",
      "phase": "phase1"  // 可以执行Phase 1
    },
    {
      "input_id": "ui_designs",
      "urgency": "BLOCKING",
      "phase": "phase2"  // 可以执行Phase 2
    },
    {
      "input_id": "api_specs",
      "urgency": "OPTIONAL",
      "phase": "phase3"
    }
  ],

  "execution_plan": {
    "partial_execution": true,
    "phases": [
      {
        "phase_id": "phase1",
        "description": "数据模型和API设计",
        "required_inputs": ["requirements_doc"],
        "can_start": true
      },
      {
        "phase_id": "phase2",
        "description": "前端页面开发",
        "required_inputs": ["requirements_doc", "ui_designs"],
        "can_start": false  // 需要ui_designs
      }
    ]
  }
}
```

**执行流程**：

```
Python专家分析任务：
"可以部分执行：
Phase 1: 数据模型和API设计 - 只需要requirements_doc
Phase 2: 前端页面开发 - 需要requirements_doc + ui_designs

策略：先执行Phase 1，Phase 2等待UI设计"

执行Phase 1：
- 读取requirements_doc
- 设计数据模型
- 设计API接口
- 产出：database_schema.sql, api_specs.yaml

状态更新：
{
  "phase1": "COMPLETED",
  "phase2": "BLOCKED_WAITING_INPUT",
  "message": "Phase 1已完成，等待UI设计稿以开始Phase 2"
}

通知用户：
"✅ Phase 1已完成（数据模型和API设计）
⏸️ Phase 2等待UI设计稿"

用户上传UI设计后：
自动执行Phase 2
```

### 5.2 分批输入（Batch Input）

**场景**：用户分批提供资料

```
第一批（2025-01-08）：
用户上传：requirements.pdf

系统处理：
- 检测到新文件
- 唤醒Python专家
- Python专家验证：✅ 有效的
- 更新状态：1/2 输入就绪
- 通知用户："需求文档已收到，等待UI设计稿"

第二批（2025-01-12）：
用户上传：register.png

系统处理：
- 检测到新文件
- 唤醒Python专家
- Python专家验证：⚠️ 不完整（还需要login.png）
- 更新状态：1.5/2 输入就绪
- 通知用户："register.png已收到，还缺少login.png"

第三批（2025-01-13）：
用户上传：login.png

系统处理：
- 检测到新文件
- 唤醒Python专家
- Python专家验证：✅ 所有输入就绪
- 更新状态：2/2 输入就绪
- 自动开始执行任务
```

### 5.3 输入依赖关系

**复杂的输入依赖**：

```json
{
  "task_id": "task_004",
  "title": "集成第三方支付功能",

  "input_requirements": [
    {
      "input_id": "payment_api_doc",
      "description": "支付API文档",
      "urgency": "BLOCKING",
      "depends_on": []  // 无依赖
    },
    {
      "input_id": "api_key",
      "description": "API密钥（测试环境）",
      "urgency": "BLOCKING",
      "depends_on": ["payment_api_doc"]  // 需要先看文档才知道如何获取密钥
    },
    {
      "input_id": "production_credentials",
      "description": "生产环境凭证",
      "urgency": "BLOCKING",
      "depends_on": ["payment_api_doc", "api_key"],
      "phase": "production"  // 生产阶段才需要
    }
  ],

  "execution_plan": {
    "sequential_inputs": true,
    "auto_detect_dependencies": true
  }
}
```

**依赖解析**：

```
Python专家分析依赖：

依赖图：
payment_api_doc (无依赖)
    ↓
api_key (依赖 payment_api_doc)
    ↓
production_credentials (依赖 payment_api_doc, api_key)

执行策略：
1. 等待 payment_api_doc
2. 有了文档后，检查是否包含api_key获取方式
3. 如果文档说明需要申请，询问用户是否已有api_key
4. 如果没有，引导用户申请
5. 收集齐测试环境输入后，先开发测试版本
6. 生产凭证可以后续提供，部署时使用
```

---

## 6. 用户交互设计

### 6.1 Dashboard界面

**等待状态的Dashboard**：

```
┌─────────────────────────────────────────┐
│  AgentTalk Dashboard                    │
├─────────────────────────────────────────┤
│                                         │
│  📋 任务：开发用户注册功能              │
│  状态：⏸️ 等待资料（1/2 已就绪）        │
│  进度：██░░░░░░░░░░░░░░░░░ 10%          │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ 📊 输入状态                     │   │
│  │                                 │   │
│  │ ✅ requirements.pdf             │   │
│  │    状态：已接收                 │   │
│  │    时间：2025-01-08 14:30       │   │
│  │    验证：通过                   │   │
│  │                                 │   │
│  │ ⏸️ ui_designs/                 │   │
│  │    状态：等待中                 │   │
│  │    需求：register.png, login.png │   │
│  │    期望：2025-01-15             │   │
│  │                                 │   │
│  │ [上传文件] [查看详情]           │   │
│  └─────────────────────────────────┘   │
│                                         │
│  📝 Agent消息：                        │
│  "需求文档已收到，内容很详细。         │
│   我会先基于需求文档设计数据模型和    │
│   API接口，等UI设计稿就位后再开发    │
│   前端页面。"                         │
│                                         │
│  📌 提示：                            │
│  - 可以分批上传（如：先上传register.png）│
│  - 上传后会自动通知Python专家         │
│  - 如果对需求有疑问，可以随时询问    │
│                                         │
└─────────────────────────────────────────┘
```

### 6.2 进度通知

**邮件通知（分批输入）**：

```
主题：【AgentTalk】任务进度更新 - 开发用户注册功能

你好！

任务"开发用户注册功能"有新进展：

✅ 输入已就绪（1/2）：
  - 产品需求文档（requirements.pdf）
    已于 2025-01-08 14:30 收到
    验证通过，格式正确

⏸️ 仍在等待（1/2）：
  - UI设计稿（register.png, login.png）
    期望时间：2025-01-15

📊 当前进度：
  Python专家已开始Phase 1工作：
  - 设计数据模型
  - 设计API接口
  - 预计完成：2025-01-09

📌 下一步：
  Phase 2（前端开发）将在UI设计稿就位后开始

如有问题，请回复此邮件。

任务ID: user_task_003
Agent: Python专家
```

---

## 7. Agent协作场景

### 7.1 多个Agent等待不同输入

**场景**：需要多个Agent协作，每个Agent等待不同的输入

```
任务：开发完整的用户注册功能

分工：
- 数据库专家：等待数据库设计文档
- Python专家：等待需求文档 + UI设计
- 前端专家：等待UI设计 + Python API

时间线：

Day 1 (1月5日):
- 总经理分配任务
- 所有Agent进入等待状态

Day 3 (1月7日):
- 用户上传：database_design.pdf
- 唤醒数据库专家
- 数据库专家开始工作
- 其他Agent继续等待

Day 5 (1月9日):
- 用户上传：requirements.pdf
- 唤醒Python专家
- Python专家开始Phase 1（数据模型和API）
- 前端专家继续等待

Day 8 (1月12日):
- Python专家完成Phase 1
- 数据库专家完成数据库设计
- 通知用户：可以上传UI设计了

Day 10 (1月15日):
- 用户上传：register.png, login.png
- 唤醒Python专家和前端专家
- Python专家开始Phase 2（前端开发）
- 前端专家也开始工作

Day 13 (1月18日):
- 所有Agent完成任务
- 系统集成测试
- 交付给用户
```

### 7.2 Agent之间的等待依赖

**场景**：Python专家需要等待数据库专家完成

```
任务输入依赖：

Python专家的输入：
- requirements_doc（用户提供）
- database_schema（数据库专家产出）

数据库专家的任务：
- 输入：database_design.pdf（用户提供）
- 产出：database_schema.sql

执行流程：

Step 1: 数据库专家等待database_design.pdf

Step 2: 用户上传database_design.pdf
→ 唤醒数据库专家

Step 3: 数据库专家完成database_schema.sql
→ 输出：workspace/outputs/database_schema.sql

Step 4: 文件监控系统检测到database_schema.sql
→ 通知Python专家："数据库schema已就绪"

Step 5: Python专家收到通知
→ 检查输入状态：
  - requirements_doc: ✓ (已提供)
  - database_schema: ✓ (数据库专家已产出)
→ 所有输入就绪，开始执行
```

**Agent-to-Agent的等待声明**：

```json
{
  "task_id": "task_003",
  "assigned_to": "agent_202_python_expert",

  "input_requirements": [
    {
      "input_id": "database_schema",
      "description": "数据库schema",
      "type": "document",
      "provided_by": "agent_401_database_expert",  // Agent提供
      "expected_location": "workspace/outputs/database_schema.sql",
      "depends_on_task": "task_002",  // 依赖任务
      "urgency": "BLOCKING",
      "auto_notify_when_ready": true
    }
  ]
}
```

---

## 8. 完整示例

### 场景：开发电商网站

#### 8.1 任务分解

```
总经理召集会议，产生任务分配：

Phase 1: 基础准备（1周）
- 产品经理：编写需求文档（用户提供初稿，经理完善）
- 架构师：设计技术架构（等待需求文档）

Phase 2: 后端开发（2周）
- 数据库专家：设计数据库（等待架构文档）
- Python专家：开发API（等待数据库schema + 需求）

Phase 3: 前端开发（2周）
- 前端专家：开发Web界面（等待UI设计 + API）

Phase 4: 集成测试（1周）
- 测试专家：测试（等待所有模块完成）
```

#### 8.2 执行时间线

```
Week 1, Day 1 (1月5日):
├─ 用户提交任务："开发电商网站"
├─ 总经理分配任务
└─ 所有Agent进入等待状态

Week 1, Day 3 (1月7日):
├─ 用户上传：产品需求初稿.md
├─ 唤醒产品经理
└─ 产品经理开始完善需求文档

Week 1, Day 5 (1月9日):
├─ 产品经理完成：PRD.md
├─ 输出：workspace/outputs/PRD.md
└─ 唤醒架构师

Week 2, Day 1 (1月12日):
├─ 架构师完成：architecture.md
├─ 输出：workspace/outputs/architecture.md
└─ 唤醒数据库专家

Week 2, Day 3 (1月14日):
├─ 数据库专家完成：database_schema.sql
├─ 输出：workspace/outputs/database_schema.sql
└─ 通知Python专家："数据库schema已就绪，还需需求文档"

Week 2, Day 5 (1月16日):
├─ 用户上传：UI设计稿（所有页面）
├─ 唤醒前端专家
└─ 前端专家开始工作

Week 3, Day 1 (1月19日):
├─ Python专家检查输入：
│  - requirements.doc: ✅ (PRD.md已就绪)
│  - database_schema: ✅ (已提供)
│  - api_specs: ✅ (从架构文档提取)
├─ 所有输入就绪
└─ Python专家开始开发API

Week 4 (1月26日):
├─ Python专家完成API
├─ 前端专家完成界面
└─ 唤醒测试专家

Week 5 (2月2日):
├─ 测试完成
├─ 系统集成
└─ 交付给用户
```

#### 8.3 通知示例

**通知1：唤醒产品经理**

```
主题：【AgentTalk】新任务 - 编写需求文档

你好！

你有一个新任务需要处理：

任务：编写电商网站需求文档
截止时间：2025-01-09

输入要求：
- 用户初稿：user_draft.md
- 已提供位置：workspace/projects/ecommerce/inputs/user_draft.md

你的任务：
1. 阅读用户初稿
2. 完善需求文档
3. 产出：PRD.md

输入资料已就位，可以开始工作。

任务ID: task_001
Agent: 产品经理（agent_004_product_manager）
```

**通知2：通知架构师（产品经理完成后）**

```
主题：【AgentTalk】输入已就绪 - 设计技术架构

你好！

你需要的输入资料已准备就绪：

输入：产品需求文档
位置：workspace/outputs/PRD.md
提供者：产品经理（agent_004_product_manager）

你的任务：
- 基于PRD设计技术架构
- 产出：architecture.md

所有输入就绪，可以开始工作。

任务ID: task_002
Agent: 架构师（agent_006_architect）
```

**通知3：通知Python专家（数据库专家完成后）**

```
主题：【AgentTalk】部分输入已就绪 - 开发后端API

你好！

你的任务"开发后端API"有新进展：

✅ 已就绪的输入（1/2）：
  - 数据库schema
    位置：workspace/outputs/database_schema.sql
    提供者：数据库专家（agent_401_database_expert）
    时间：2025-01-14 16:00

⏸️ 仍在等待（1/2）：
  - 产品需求文档
    状态：等待产品经理
    期望：2025-01-19

📊 当前进度：
  建议先做准备工作：
  - 搭建开发环境
  - 设计API接口规范
  - 生成OpenAPI文档

  正式开发将在需求文档就位后开始

任务ID: task_003
Agent: Python专家（agent_202_python_expert）
```

---

## 9. 技术实现要点

### 9.1 文件监控服务

```python
class InputFileWatcher:
    """监控输入文件的变化"""

    def __init__(self):
        self.watching_directories = {}
        self.waiting_agents = {}  # task_id -> list of agent_ids

    def watch_for_task(self, task_id: str, input_requirements: List[Dict]):
        """为任务监控输入文件"""
        watched_files = []

        for req in input_requirements:
            if req["urgency"] == "BLOCKING":
                location = req["expected_location"]
                self.watching_directories[location] = task_id

                # 检查文件是否已存在
                if file_exists(location):
                    self.on_file_detected(location, task_id)
                else:
                    watched_files.append(location)

        return watched_files

    def check_directories(self):
        """定期检查目录（每10秒）"""
        for directory, task_id in self.watching_directories.items():
            new_files = scan_directory(directory)

            for file in new_files:
                self.on_file_detected(file, task_id)

    def on_file_detected(self, file_path: str, task_id: str):
        """检测到新文件时的处理"""
        # 查找等待此文件的Agent
        agents = self.waiting_agents.get(task_id, [])

        for agent_id in agents:
            send_wakeup_message(agent_id, {
                "message_type": "INPUT_DETECTED",
                "file": file_path,
                "task_id": task_id
            })
```

### 9.2 Agent的等待逻辑

```python
def wait_for_inputs(self, input_requirements: List[Dict]):
    """等待输入"""

    # 检查当前状态
    missing_inputs = get_missing_inputs(input_requirements)

    if not missing_inputs:
        # 所有输入已就绪
        return {
            "can_start": True,
            "message": "所有输入已就位"
        }

    # 有缺失输入
    blocking_inputs = [inp for inp in missing_inputs if inp["urgency"] == "BLOCKING"]

    if blocking_inputs:
        # 进入等待状态
        update_status("BLOCKED_WAITING_INPUT")

        # 生成缺失资料清单
        missing_list = generate_missing_inputs_list(blocking_inputs)

        # 通知用户
        send_user_notification({
            "type": "WAITING_FOR_INPUT",
            "task_id": self.current_task,
            "agent_id": self.agent_id,
            "missing_inputs": blocking_inputs,
            "message": f"等待{len(blocking_inputs)}项必需资料"
        })

        # 等待被唤醒
        return {
            "can_start": False,
            "action": "WAIT",
            "missing_inputs": blocking_inputs
        }
```

### 9.3 唤醒后的处理

```python
def on_wakeup(self, wakeup_message: Dict):
    """被唤醒后的处理"""

    trigger = wakeup_message["trigger"]
    file = wakeup_message.get("file")

    if trigger == "INPUT_DETECTED":
        # 新文件检测到
        validate_and_add_input(file)

    elif trigger == "INPUT_PROVIDED":
        # 用户明确告知输入已提供
        input_id = wakeup_message.get("input_id")
        validate_input(input_id)

    # 检查是否所有BLOCKING输入就绪
    missing_inputs = get_missing_inputs(self.input_requirements)
    blocking_inputs = [inp for inp in missing_inputs if inp["urgency"] == "BLOCKING"]

    if not blocking_inputs:
        # 所有输入就绪
        update_status("READY")
        start_execution()
    else:
        # 仍有缺失输入
        update_status("BLOCKED_WAITING_INPUT")
        send_progress_notification(f"已收到{len(missing_inputs) - len(blocking_inputs)}项资料，仍需要{len(blocking_inputs)}项")
```

---

## 10. 最佳实践

### 10.1 输入声明建议

✅ **DO（应该做的）**：
- 明确指定输入格式（PDF、PNG、JSON等）
- 说明必需字段
- 提供示例或模板
- 设置合理的期望时间
- 区分BLOCKING和OPTIONAL
- 说明如何提供资料（上传路径）

❌ **DON'T（不应该做的）**：
- 模糊的描述（如"相关资料"）
- 不说明格式要求
- 不设置截止时间
- 所有输入都设为BLOCKING
- 不提供提供方式的指导

### 10.2 等待时间的设置

**建议的等待时间**：

| 任务类型 | 合理等待时间 | 理由 |
|---------|-------------|------|
| 用户提供 | 3-7天 | 用户可能需要协调 |
| 内部Agent提供 | 1-3天 | Agent执行需要时间 |
| 外部供应商提供 | 7-14天 | 依赖外部，不可控 |
| 简单文档 | 1-2天 | 编写快速 |
| 复杂设计 | 7-14天 | 设计迭代 |

### 10.3 用户沟通建议

**等待时的通知频率**：

```
Day 0 (进入等待): "任务已启动，等待XX资料"
Day 3 (中期): "任务仍在等待，预计XX时间完成"
Day 5 (中期): "任务仍在等待，如需帮助请回复"
Day 7 (即将超时): "任务等待即将超时，请尽快提供资料"
Day 8 (超时): "任务已超时，已上报给项目经理"
```

---

## 11. 与现有机制的整合

### 11.1 与任务状态机的整合

**扩展现有状态机**：

```
现有状态：
PENDING → READY → EXECUTING → READY_TO_CHECK → DONE
              ↓
            FAILED

新增状态：
PENDING → READY → BLOCKED_WAITING_INPUT → READY → EXECUTING → ...
              ↓
            FAILED

BLOCKED_WAITING_INPUT的转换：
- 输入全部就绪 → READY
- 超时 → FAILED
- 用户提供无效输入 → BLOCKED_WAITING_INPUT（继续等待）
```

### 11.2 与求助机制的整合

```
场景：Agent等待输入，但不知道具体需要什么

Agent的处理：
1. 检查输入要求
2. 发现描述模糊（"相关设计稿"）
3. 发送HELP_REQUEST给经理
4. 经理明确需求（"需要Figma导出的PNG，至少800x600"）
5. Agent更新输入要求
6. 重新通知用户

好处：
- 输入要求更清晰
- 避免用户提供错误的资料
- 提升一次性成功率
```

### 11.3 与外部知识处理的整合

```
知识库 + 输入等待：

场景：等待用户提供公司信息

知识库中有：
- 公司基本信息
- 部分架构信息

但仍需要用户提供：
- 具体的项目需求
- 团队成员信息

整合流程：
1. Agent先查知识库，获取已有信息
2. 发现仍缺失关键信息
3. 进入BLOCKED_WAITING_INPUT状态
4. 明确告知用户：
   "已从知识库获取公司基本信息（✓）
   但仍需提供项目需求文档（✗）
   请上传到：..."
```

---

## 12. 故障处理

### 12.1 常见问题

**问题1：用户上传了错误的文件**

```
用户上传：requirements.txt（纯文本）
期望格式：PDF或Markdown

Agent检测：
{
  "validation": {
    "valid": false,
    "errors": ["格式错误：期望PDF或Markdown，实际TXT"]
  }
}

处理：
1. 标记输入为INVALID
2. 通知用户：
   "文件格式错误。请上传PDF或Markdown格式
    当前文件：requirements.txt
    期望格式：PDF/MD"
3. 继续等待正确的文件
4. 删除错误文件（避免混淆）
```

**问题2：用户上传了不完整的文件**

```
用户上传：register.png（只有1个页面）
期望：register.png + login.png（2个页面）

Agent检测：
{
  "validation": {
    "valid": false,
    "errors": ["文件不完整：需要register.png和login.png，目前只有1个"]
  },
  "partial": true,
  "received": ["register.png"],
  "missing": ["login.png"]
}

处理：
1. 标记为PARTIAL
2. 通知用户：
   "已收到register.png ✓
   还缺少login.png
   请继续上传"
3. 继续等待剩余文件
4. 所有文件到齐后统一验证
```

**问题3：用户一直不提供资料**

```
等待时间：7天
超时策略：ESCALATE（上报给项目经理）

处理流程：
1. 第3天：第一次提醒
2. 第5天：第二次提醒
3. 第7天：超时上报

上报给项目经理：
{
  "message_type": "ESCALATE",
  "from_agent": "agent_202_python_expert",
  "to_agent": "agent_002_project_manager",
  "issue": "等待输入超时",
  "task": "task_003",
  "waiting_duration": "7天",
  "missing_inputs": [...],
  "suggestion": "请协助催促用户或替代方案"
}

项目经理处理：
1. 联系用户了解情况
2. 看是否可以使用替代资料
3. 或调整任务范围
4. 或申请延长时间
```

### 12.2 输入验证失败的处理

```
Agent收到文件，验证失败：

{
  "file": "requirements.pdf",
  "validation": {
    "valid": false,
    "errors": [
      "文件大小超过限制（10MB）",
      "缺少必需字段：验收标准"
    ]
  }
}

处理步骤：
1. 通知用户验证失败原因
2. 提供详细的错误说明
3. 给出修正建议
4. 保留无效文件（供用户参考）
5. 等待用户上传正确文件

通知示例：
{
  "type": "VALIDATION_FAILED",
  "file": "requirements.pdf",
  "errors": [
    "文件大小超过限制：15MB > 10MB",
    "缺少必需字段：验收标准"
  ],
  "suggestions": [
    "压缩文件或移除不必要内容",
    "在文档中添加'验收标准'章节"
  ],
  "action_required": "请上传修正后的文件"
}
```

---

## 13. 用户体验优化

### 13.1 输入指导

**为用户提供清晰的指导**：

```
Dashboard显示：

┌─────────────────────────────────────────┐
│  📤 上传资料指南                      │
├─────────────────────────────────────────┤
│                                         │
│  需求文档（requirements.doc）         │
│  ┌─────────────────────────────────┐   │
│  │ 要求：                           │   │
│  │ • 格式：PDF或Markdown          │   │
│  │ • 必需章节：                   │   │
│  │   - 功能列表                   │   │
│  │   - 用户故事                   │   │
│  │   - 验收标准                   │   │
│  │ • 文件大小：<10MB              │   │
│  │                                 │   │
│  │ 📎 模板下载：                   │   │
│  │ [下载requirements_template.md]│   │
│  │                                 │   │
│  │ 📖 示例参考：                   │   │
│  │ [查看requirements_example.pdf]│   │
│  └─────────────────────────────────┘   │
│                                         │
│  [选择文件] 或拖放到此处              │
│                                         │
└─────────────────────────────────────────┘
```

### 13.2 进度可视化

**清晰的进度指示**：

```
任务进度总览：

开发用户注册功能
└─ 整体进度：███░░░░░░░░░░░░░░ 30%

   ├─ Phase 1: 数据模型和API (Python专家)
   │  ├─ 状态：✅ 已完成
   │  └─ 进度：██████████ 100%
   │
   ├─ Phase 2: 前端开发 (前端专家)
   │  ├─ 状态：⏸️ 等待UI设计
   │  └─ 进度：██░░░░░░░░░░ 20%
   │     └─ 等待：ui_designs (1/2 已就绪)
   │
   └─ Phase 3: 集成测试 (测试专家)
      ├─ 状态：⏳ 等待中
      └─ 进度：░░░░░░░░░░░░ 0%
```

### 13.3 智能提醒

**根据情况智能提醒**：

```
场景1：用户部分完成输入
系统通知：
"✅ register.png已收到
⏸️ 还需要login.png才能继续
💡 提示：可以一次上传所有文件"

场景2：即将超时
系统通知：
"⚠️ ui_designs的期望时间是2025-01-15（还有3天）
⏰ 如果需要延期，请回复说明原因"

场景3：输入格式错误
系统通知：
"❌ requirements.pdf验证失败
📝 错误：缺少验收标准章节
💡 建议：参考requirements_example.pdf

[查看错误详情] [重新上传]"

场景4：所有输入就绪
系统通知：
"🎉 所有资料已就位！
✅ requirements.pdf
✅ ui_designs (2个文件)

Python专家将立即开始工作..."
```

---

## 14. 总结

### 14.1 核心机制

| 机制 | 说明 |
|------|------|
| **输入依赖声明** | 任务声明需要的输入及要求 |
| **阻塞等待状态** | BLOCKED_WAITING_INPUT |
| **文件监控** | 实时检测新文件 |
| **自动唤醒** | 检测到文件后唤醒Agent |
| **输入验证** | 验证文件格式和内容 |
| **超时处理** | 超时后提醒或上报 |
| **部分执行** | 可以部分执行时先开始 |

### 14.2 用户操作流程

```
1. 提交任务（资料不完整）
   ↓
2. 系统通知需要什么资料
   ↓
3. 用户上传资料（随时、分批）
   ↓
4. 系统自动验证
   ↓
5. Agent自动唤醒并执行
   ↓
6. 任务完成
```

### 14.3 关键优势

✅ **灵活性**：资料可以逐步补充
✅ **自动化**：资料到位后自动推进
✅ **可视化**：清晰的等待和进度信息
✅ **容错性**：支持错误修正和重新上传
✅ **协作性**：多Agent可以分别等待不同输入

---

## 15. 与其他机制的配合

### 15.1 与"外部知识处理"配合

```
场景：需要公司制度文档

处理流程：
1. 先查知识库
2. 如果知识库有 → 直接使用
3. 如果知识库没有 → 等待用户提供
4. 用户上传后 → 加入知识库 → 后续复用
```

### 15.2 与"求助机制"配合

```
场景：Agent不确定需要什么输入

处理流程：
1. Agent发现需求描述模糊
2. 发送HELP_REQUEST给经理
3. 经理明确输入要求
4. Agent更新input_requirements
5. 重新通知用户
```

### 15.3 与"会议机制"配合

```
场景：等待关键决策输入

处理流程：
1. Agent等待决策文档
2. 用户上传会议纪要
3. Agent发现纪要中有冲突
4. 建议召开会议澄清
5. 会议达成一致
6. Agent继续执行
```

---

**文档版本**：v1.0
**最后更新**：2025-01-05
