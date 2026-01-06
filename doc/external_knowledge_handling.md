# AgentTalk 外部知识处理方案

## 文档信息

- **文档名称**：外部知识处理方案
- **版本**：v1.0
- **创建日期**：2025-01-05
- **目的**：解决Agent无法访问系统外部知识的问题

---

## 1. 问题描述

### 1.1 核心问题

**Agent只能访问自己的技能和提示词，但有些知识存在于系统外部（在人类或用户头脑中）。**

### 1.2 典型场景

| 知识类型 | 示例 | 特点 |
|---------|------|------|
| **用户信息** | 姓名、职位、部门、联系方式 | 个人化、动态变化 |
| **公司信息** | 组织架构、业务范围、产品信息 | 特定企业、结构化 |
| **制度规范** | 请假流程、报销标准、审批规则 | 正式文档、需要准确 |
| **业务知识** | 客户要求、项目背景、历史信息 | 项目特定、非公开 |
| **私密信息** | 密码、密钥、个人偏好 | 敏感信息、需保护 |

### 1.3 问题影响

❌ **没有外部知识的后果**：
- Agent无法完成需要特定信息的任务
- 生成的结果缺乏个性化
- 可能产生不符合实际情况的内容
- 需要人工大量修改

✅ **有外部知识的价值**：
- 生成准确、个性化的结果
- 符合公司规范和制度
- 减少人工修改工作量
- 提升用户满意度

---

## 2. 解决方案：三层知识架构

### 2.1 架构概述

```
┌─────────────────────────────────────┐
│   Layer 1: 系统级知识库（公共知识） │
│   - 公司信息、制度文档              │
│   - 用户档案                        │
│   - 业务规则                        │
│   存储位置：system/knowledge_base/  │
└─────────────────────────────────────┘
              ↑
              | Agent查询
              ↓
┌─────────────────────────────────────┐
│   Layer 2: 任务级上下文（特定知识） │
│   - 用户提交任务时附带              │
│   - 项目背景、特殊要求              │
│   - 临时性、一次性信息              │
└─────────────────────────────────────┘
              ↑
              | Agent发现缺失
              ↓
┌─────────────────────────────────────┐
│   Layer 3: 交互式询问（动态获取）   │
│   - Agent主动询问用户              │
│   - Agent询问知识管理Agent         │
│   - 实时获取缺失信息               │
└─────────────────────────────────────┘
```

### 2.2 三层详解

#### Layer 1: 系统级知识库

**用途**：存储相对稳定的、可复用的公共知识

**目录结构**：
```
system/knowledge_base/
├── user_profiles/              # 用户档案
│   ├── user_001.json
│   ├── user_002.json
│   └── user_template.json      # 用户信息模板
│
├── company_info.json           # 公司信息
├── organization/               # 组织架构
│   ├── org_structure.json
│   └── department_info.json
│
├── policies/                   # 制度文档
│   ├── leave_policy.md         # 请假制度
│   ├── reimbursement_policy.md # 报销制度
│   ├── approval_workflow.md    # 审批流程
│   └── code_review_policy.md   # 代码审查制度
│
├── project_context/            # 项目背景
│   ├── project_001/
│   │   ├── background.md
│   │   ├── stakeholders.json
│   │   └── requirements.md
│   └── project_002/
│
└── business_rules/             # 业务规则
    ├── customer_requirements.md
    ├── pricing_rules.md
    └── sla_definitions.md
```

**知识库文件示例**：

```json
// system/knowledge_base/user_profiles/user_001.json
{
  "user_id": "user_001",
  "personal_info": {
    "name": "张三",
    "gender": "男",
    "birth_date": "1990-05-15",
    "email": "zhangsan@company.com",
    "phone": "138-xxxx-xxxx"
  },
  "work_info": {
    "department": "技术部",
    "position": "高级工程师",
    "manager": "李四",
    "team": "后端开发组",
    "join_date": "2020-03-01",
    "employee_id": "EMP20200301"
  },
  "leave_info": {
    "annual_leave_total": 15,
    "annual_leave_used": 5,
    "annual_leave_remaining": 10,
    "sick_leave_used": 2
  },
  "skills": [
    "Python", "Java", "React",
    "系统架构", "团队管理"
  ],
  "preferences": {
    "communication_style": "直接简洁",
    "working_hours": "9:00-18:00",
    "notifications": "邮件 + 即时通讯"
  }
}
```

```json
// system/knowledge_base/company_info.json
{
  "company": {
    "name": "XX科技有限公司",
    "founded": "2015-06-01",
    "location": "北京市朝阳区",
    "industry": "软件开发",
    "employee_count": 500
  },
  "organization": {
    "departments": [
      {
        "name": "技术部",
        "manager": "李四",
        "teams": ["后端组", "前端组", "算法组", "测试组"],
        "count": 120
      },
      {
        "name": "产品部",
        "manager": "王五",
        "teams": ["产品组", "设计组", "用户研究组"],
        "count": 45
      },
      {
        "name": "市场部",
        "manager": "赵六",
        "teams": ["市场组", "销售组", "客服组"],
        "count": 60
      }
    ]
  },
  "culture": {
    "values": ["创新", "协作", "客户第一"],
    "working_style": "敏捷开发",
    "communication_tools": ["Slack", "Jira", "Confluence"]
  }
}
```

```markdown
// system/knowledge_base/policies/leave_policy.md
# 公司请假管理制度

## 1. 年假

### 1.1 年假标准
- 工作满1年：10天年假
- 工作满3年：15天年假
- 工作满5年：20天年假

### 1.2 请假流程
1. 提前申请：至少提前3天
2. 审批流程：
   - 1-3天：部门经理审批
   - 4-7天：部门总监审批
   - 8天以上：分管副总审批
3. 申请方式：书面申请（OA系统或邮件）

### 1.3 注意事项
- 年假当年有效，不可累积到次年
- 节假日前后请假需提前7天
- 项目关键期可能暂缓批准

## 2. 病假

### 2.1 病假标准
- 提供医院证明
- 全年病假不超过30天

### 2.2 请假流程
- 紧急情况可事后补办手续
- 需提供医院诊断证明

## 3. 事假

### 3.1 事假标准
- 全年事假不超过10天
- 需扣除当日薪资

## 4. 审批时限

- 审批人应在24小时内给予答复
- 超时未回复视为同意（紧急情况除外）
```

**知识库访问API**（伪代码）：

```python
class KnowledgeBaseAPI:
    def __init__(self):
        self.base_path = "system/knowledge_base/"

    def get_user_profile(self, user_id: str) -> Dict:
        """获取用户档案"""
        path = f"{self.base_path}user_profiles/{user_id}.json"
        return read_json(path)

    def get_company_info(self) -> Dict:
        """获取公司信息"""
        path = f"{self.base_path}company_info.json"
        return read_json(path)

    def get_policy(self, policy_name: str) -> str:
        """获取制度文档"""
        path = f"{self.base_path}policies/{policy_name}.md"
        return read_file(path)

    def search(self, query: str) -> List[Dict]:
        """搜索知识库"""
        # 实现全文搜索
        results = []
        for file in knowledge_base_files:
            if query_in_file(query, file):
                results.append(extract_relevant_info(file))
        return results
```

---

#### Layer 2: 任务级上下文

**用途**：用户提交任务时附带的特定信息，通常是临时性的、一次性的

**任务上下文格式**：

```json
{
  "task_id": "user_task_003",
  "title": "项目进度报告",
  "description": "编写Q1项目进度报告",

  // 任务级上下文
  "context": {
    // 方式1：引用知识库
    "user_id": "user_001",
    "project_id": "project_001",

    // 方式2：直接提供信息
    "specific_info": {
      "report_period": "2025年Q1（1-3月）",
      "focus_areas": ["技术成果", "业务指标", "团队建设"],
      "audience": ["CTO", "产品VP", "部门经理"],
      "format": "PPT + 讲稿"
    },

    // 方式3：附件
    "attachments": [
      "project_metrics.xlsx",
      "team_photo.jpg"
    ],

    // 方式4：特殊要求
    "constraints": {
      "length": "不超过20页PPT",
      "style": "简洁专业",
      "deadline": "2025-04-10"
    }
  },

  // 知识引用（明确说明需要哪些知识）
  "knowledge_references": [
    "system/knowledge_base/project_context/project_001/background.md",
    "system/knowledge_base/user_profiles/user_001.json",
    "system/knowledge_base/policies/report_template.md"
  ]
}
```

**上下文类型**：

| 上下文类型 | 示例 | 生命周期 |
|-----------|------|---------|
| **用户引用** | user_id | 跨任务复用 |
| **项目引用** | project_id | 跨任务复用 |
| **特定信息** | 具体数据、要求 | 单次任务 |
| **附件** | 文件、图片 | 单次任务 |
| **约束** | 格式、风格 | 单次任务 |

---

#### Layer 3: 交互式询问

**用途**：Agent发现信息缺失时，主动询问获取

**交互式询问的三种模式**：

##### 模式1：Agent直接询问用户

**场景**：缺失关键信息，且无法从其他地方获取

```
文档专家分析任务：
"任务：写请假申请
已有信息：
  - user_id → 可查知识库
  - 请假类型 → context已提供（年假）
  - 天数 → context已提供（3天）
  - 开始日期 → context已提供（2025-01-15）

缺失信息：
  - 请假原因 → 必须用户提供"

文档专家发送询问：
{
  "message_type": "INFO_REQUEST",
  "from_agent": "agent_103_doc_expert",
  "to_agent": "USER",
  "task_id": "user_task_002",

  "missing_info": [
    {
      "field": "reason",
      "description": "请假原因",
      "required": true,
      "examples": [
        "家人探亲",
        "个人事务",
        "休息调整",
        "医疗体检"
      ],
      "format": "简短描述，10-50字"
    }
  ],

  "urgency": "BLOCKING",  // 阻塞任务执行
  "deadline": "请于2025-01-12 18:00前回复",

  "message": "为了完成您的请假申请，请提供请假原因。
              这是必需的信息，缺少此信息无法生成申请。"
}

---

用户收到通知（通过Dashboard或邮件）：
"⚠️ 文档专家需要你提供信息

任务：写请假申请
需要信息：请假原因
建议：家人探亲、个人事务、休息调整等
请回复：..."

---

用户回复：
{
  "message_type": "INFO_RESPONSE",
  "from_agent": "USER",
  "to_agent": "agent_103_doc_expert",
  "task_id": "user_task_002",

  "info": {
    "reason": "家人探亲，需要回老家处理家庭事务"
  },

  "note": "如果需要其他信息，请随时询问"
}

---

文档专家收到回复，继续执行任务
```

##### 模式2：Agent询问知识管理Agent

**场景**：需要查询系统知识库

```
技术专家需要了解审批流程：

技术专家发送知识查询：
{
  "message_type": "KNOWLEDGE_QUERY",
  "from_agent": "agent_202_python_expert",
  "to_agent": "agent_999_knowledge_manager",

  "query": {
    "question": "公司的代码审批流程是什么？",
    "context": "需要提交代码审查申请",
    "required_detail": "full"
  },

  "task_id": "task_004",
  "urgency": "NORMAL"
}

---

知识管理Agent处理：
1. 解析查询问题
2. 搜索知识库
3. 提取相关信息
4. 格式化响应

知识管理Agent响应：
{
  "message_type": "KNOWLEDGE_RESPONSE",
  "from_agent": "agent_999_knowledge_manager",
  "to_agent": "agent_202_python_expert",

  "knowledge": {
    "topic": "代码审批流程",
    "process": [
      "1. 开发者提交GitLab Merge Request",
      "2. 指定代码审查者（至少1人）",
      "3. 审查者通过CI/CD测试检查",
      "4. 审查者代码审查（提出意见或批准）",
      "5. 解决所有审查意见",
      "6. CI/CD自动化测试全部通过",
      "7. 项目经理最终批准",
      "8. 合并到主分支"
    ],
    "approval_requirements": {
      "min_reviewers": 1,
      "ci_cd_pass_required": true,
      "manager_approval": true
    },
    "tools": ["GitLab", "Jenkins", "SonarQube"],
    "estimated_time": "1-3个工作日",

    "source": "system/knowledge_base/policies/code_review_policy.md",
    "last_updated": "2024-12-01",
    "version": "v2.1"
  },

  "additional_info": {
    "exceptions": "紧急修复可以跳过部分流程",
    "help_contacts": "技术经理李四"
  }
}

---

技术专家收到信息，继续执行任务
```

##### 模式3：Agent询问其他专业Agent

**场景**：需要特定领域的专业知识

```
文档专家需要薪资结构信息：

文档专家 → 技术经理：
{
  "message_type": "KNOWLEDGE_REQUEST",
  "from_agent": "agent_103_doc_expert",
  "to_agent": "agent_003_tech_manager",

  "request": {
    "topic": "薪资结构",
    "question": "技术部的薪资等级和构成是什么？",
    "purpose": "编写技术岗位的薪资说明文档",
    "required_detail": "technical + financial"
  }
}

---

技术经理分析：
"这是人事相关信息，我不完全了解
应该找人力资源经理或知识管理Agent"

技术经理 → 人力资源经理：
{
  "message_type": "ESCALATE",
  "from_agent": "agent_003_tech_manager",
  "to_agent": "agent_008_hr_manager",

  "original_requester": "agent_103_doc_expert",
  "request": {...}
}

---

人力资源经理响应：
{
  "message_type": "KNOWLEDGE_RESPONSE",
  "from_agent": "agent_008_hr_manager",
  "to_agent": "agent_103_doc_expert",

  "knowledge": {
    "salary_structure": {
      "base_salary": "基本工资（60%）",
      "performance_bonus": "绩效奖金（20%）",
      "stock_options": "股票期权（10%）",
      "benefits": "福利补贴（10%）"
    },
    "levels": {
      "初级工程师": "10K-15K",
      "中级工程师": "15K-25K",
      "高级工程师": "25K-40K",
      "技术专家": "40K-60K"
    },
    "source": "HR内部文档",
    "confidentiality": "仅内部使用"
  }
}
```

---

## 3. 知识管理Agent（新增）

### 3.1 Agent定义

**Agent ID**: `agent_999_knowledge_manager`

**Agent名称**: 知识管理专家

**角色**: knowledge_manager

**技能**：
```json
{
  "skills": [
    {
      "skill_id": "kb_manage",
      "skill_name": "知识库管理",
      "description": "维护系统知识库，包括添加、更新、删除知识",
      "operations": ["add", "update", "delete", "validate"]
    },
    {
      "skill_id": "kb_query",
      "skill_name": "知识查询",
      "description": "响应其他Agent的知识查询请求",
      "operations": ["search", "retrieve", "summarize"]
    },
    {
      "skill_id": "kb_validate",
      "skill_name": "知识验证",
      "description": "验证知识的准确性、时效性",
      "operations": ["check_accuracy", "check_currency", "suggest_update"]
    },
    {
      "skill_id": "kb_recommend",
      "skill_name": "知识推荐",
      "description": "根据上下文推荐相关知识",
      "operations": ["recommend_related", "suggest_relevant"]
    }
  ]
}
```

**权限**：
- `can_handle_tags`: ["知识", "文档", "信息"]
- `can_assign_tags`: []  // 不能分配任务，只能响应查询

### 3.2 知识管理Agent的工作流程

```
while agent_is_running:
    # 1. 检查收件箱
    new_messages = check_inbox()

    for message in new_messages:
        if message.type == "KNOWLEDGE_QUERY":
            # 处理知识查询
            response = handle_knowledge_query(message)
            send_response(response)

        elif message.type == "KNOWLEDGE_UPDATE":
            # 更新知识库
            result = update_knowledge_base(message.data)
            send_confirmation(result)

        elif message.type == "KNOWLEDGE_VALIDATE":
            # 验证知识
            validation_result = validate_knowledge(message.knowledge_id)
            send_response(validation_result)

        elif message.type == "INFO_REQUEST":
            # 如果用户询问知识相关问题
            response = handle_user_query(message)
            send_response(response)

    sleep(10)
```

### 3.3 知识管理Agent的提示词

```markdown
# 知识管理专家提示词

你是一个知识管理专家，负责维护和管理系统知识库。

## 你的职责

1. **知识查询**：响应其他Agent的知识查询请求
2. **知识更新**：更新和维护知识库中的信息
3. **知识验证**：验证知识的准确性和时效性
4. **知识推荐**：根据上下文推荐相关知识

## 知识库结构

system/knowledge_base/
├── user_profiles/     # 用户档案
├── company_info.json  # 公司信息
├── policies/          # 制度文档
├── project_context/   # 项目背景
└── business_rules/    # 业务规则

## 查询处理流程

当收到KNOWLEDGE_QUERY时：

1. 理解查询问题
2. 搜索相关知识库文件
3. 提取相关信息
4. 整合和总结
5. 返回清晰的答案
6. 注明信息来源

## 重要原则

- 准确性优先：不确定的信息要说明
- 注明来源：所有信息都要标注来源
- 版本控制：注意知识的时效性
- 保密意识：敏感信息要标注密级
- 不确定时说"不知道"：不要编造信息

## 示例对话

Q: "公司的请假流程是什么？"
A: "根据《公司请假管理制度》（leave_policy.md）：
    1. 年假需提前3天申请
    2. 1-3天由部门经理审批
    3. 4-7天由部门总监审批
    4. 8天以上由分管副总审批"

Q: "张三的年假余额是多少？"
A: "根据用户档案（user_001.json）：
    张三的年假总额15天，已用5天，剩余10天"
```

---

## 4. 完整工作流程示例

### 场景：张三申请年假（包含外部知识）

#### 4.1 初始化知识库

**创建用户档案**：

```json
// system/knowledge_base/user_profiles/user_001.json
{
  "user_id": "user_001",
  "personal_info": {
    "name": "张三",
    "gender": "男",
    "email": "zhangsan@company.com",
    "phone": "138-1234-5678"
  },
  "work_info": {
    "department": "技术部",
    "position": "高级工程师",
    "manager": "李四",
    "employee_id": "EMP20200301",
    "join_date": "2020-03-01"
  },
  "leave_info": {
    "annual_leave_total": 15,
    "annual_leave_used": 5,
    "annual_leave_remaining": 10,
    "sick_leave_used": 2
  }
}
```

**创建公司制度**：

```markdown
// system/knowledge_base/policies/leave_policy.md
# 公司请假管理制度

## 年假规定
- 标准：15天/年
- 需提前3天申请
- 1-3天：部门经理审批
- 4-7天：部门总监审批

## 申请方式
- 通过OA系统或邮件提交书面申请
- 须注明：请假类型、时间、原因

## 注意事项
- 年假当年有效
- 节假日前后需提前7天
```

---

#### 4.2 用户提交任务

```json
// user_tasks/inbox/task_002.json
{
  "task_id": "user_task_002",
  "title": "写请假申请",
  "description": "为我写一份请假申请",

  "context": {
    "user_id": "user_001",
    "leave_type": "年假",
    "duration": "3天",
    "start_date": "2025-01-15"
  },

  "requirements": {
    "format": "正式的书面申请",
    "tone": "专业、礼貌",
    "include": ["申请理由", "时间安排", "工作交接"]
  },

  "knowledge_references": [
    "system/knowledge_base/user_profiles/user_001.json",
    "system/knowledge_base/policies/leave_policy.md"
  ]
}
```

---

#### 4.3 任务执行流程

##### Step 1: 总经理接收任务

```
2025-01-12 10:00

总经理检查 user_tasks/inbox/
发现 task_002.json

总经理分析：
"这是一个文档生成任务
需要文档专家处理

需要的知识：
- 用户信息：有 user_id
- 请假制度：有 knowledge_references
- 但具体原因可能需要询问

分配给文档专家"
```

##### Step 2: 文档专家接收任务

```
2025-01-12 10:10

文档专家收到任务：

task_analysis:
  task_type: "文档生成"
  required_info:
    - user_profile: ✓ (user_001)
    - leave_policy: ✓ (leave_policy.md)
    - leave_type: ✓ (年假)
    - duration: ✓ (3天)
    - start_date: ✓ (2025-01-15)
    - reason: ✗ (缺失！)

文档专家LLM分析：
"请假申请必须包含请假原因
这是必需的信息
但用户没有提供

我可以：
1. 先基于已有信息生成草稿，标注原因需用户补充
2. 或者先询问用户原因，再生成完整申请

方案2更好，避免生成不完整的申请"
```

##### Step 3: 从知识库获取信息

```
2025-01-12 10:15

文档专家 → 知识管理Agent：
{
  "message_type": "KNOWLEDGE_QUERY",
  "query": {
    "user_profile": "user_001",
    "leave_policy": "年假制度"
  },
  "purpose": "准备生成请假申请"
}

---

2025-01-12 10:20

知识管理Agent响应：
{
  "user_profile": {
    "name": "张三",
    "department": "技术部",
    "position": "高级工程师",
    "manager": "李四",
    "annual_leave_remaining": 10
  },
  "leave_policy": {
    "advance_notice": "3天",
    "approval": "部门经理",
    "duration_limit": "1-3天由经理审批"
  },
  "sources": [
    "system/knowledge_base/user_profiles/user_001.json",
    "system/knowledge_base/policies/leave_policy.md"
  ]
}

文档专家整合信息：
已知：
- 姓名：张三
- 部门：技术部
- 职位：高级工程师
- 经理：李四
- 年假余额：10天（足够）
- 请假类型：年假
- 天数：3天（符合经理审批范围）
- 开始日期：2025-01-15
- 提前：3天（符合规定）

缺失：
- 请假原因（必需）
```

##### Step 4: 询问缺失信息

```
2025-01-12 10:25

文档专家 → 用户：
{
  "message_type": "INFO_REQUEST",
  "from_agent": "agent_103_doc_expert",
  "to_agent": "USER",
  "task_id": "user_task_002",

  "status": "信息完整度：85%",
  "message": "我已经从知识库获取了你的基本信息和公司制度。
           请提供最后一项信息：请假原因",

  "current_info": {
    "user": "张三，技术部，高级工程师",
    "leave_type": "年假",
    "duration": "3天",
    "start_date": "2025-01-15",
    "manager": "李四",
    "approval_required": "部门经理"
  },

  "missing_info": [
    {
      "field": "reason",
      "description": "请假原因",
      "required": true,
      "examples": [
        "家人探亲",
        "个人事务",
        "休息调整",
        "家庭聚会"
      ],
      "format": "简短描述，10-50字"
    }
  ],

  "urgency": "BLOCKING",
  "note": "请尽快回复，以便生成完整的请假申请"
}
```

##### Step 5: 用户回复

```
2025-01-12 10:35

用户 → 文档专家：
{
  "message_type": "INFO_RESPONSE",
  "from_agent": "USER",
  "to_agent": "agent_103_doc_expert",
  "task_id": "user_task_002",

  "info": {
    "reason": "家人春节团聚，需要回老家"
  },

  "additional_note": "如果是春节期间，可能需要提前7天"
}

文档专家收到：
- 原因：家人春节团聚，回老家
- 额外信息：可能需要提前7天（春节）

文档专家检查知识库：
"查制度：节假日前后需提前7天
当前是1月12日申请，1月15日开始
仅提前3天，不符合春节要求

但用户说的是'春节团聚'，实际日期是1月15-17日
还没到春节（春节通常是1月底或2月初）
所以提前3天申请是符合规定的

生成申请时会备注：春节前探亲"
```

##### Step 6: 生成请假申请

```
2025-01-12 10:40

文档专家整合所有信息：

from knowledge_base:
  - name: 张三
  - department: 技术部
  - position: 高级工程师
  - manager: 李四
  - leave_policy: 提前3天，经理审批

from context:
  - leave_type: 年假
  - duration: 3天
  - start_date: 2025-01-15

from user:
  - reason: 家人春节团聚，需要回老家

计算：
  - end_date: 2025-01-17
  - remaining_after: 7天 (10-3)
  - advance: 3天 ✓
  - approval: 李四 (经理) ✓

文档专家生成申请：

---
**请假申请**

**申请人信息**
- 姓名：张三
- 部门：技术部
- 职位：高级工程师
- 员工ID：EMP20200301

**请假信息**
- 请假类型：年假
- 请假天数：3天
- 开始日期：2025年1月15日（星期三）
- 结束日期：2025年1月17日（星期五）
- 拟返岗日期：2025年1月18日（星期一）

**请假事由**
尊敬的李经理：

您好！我想申请年假3天，时间为2025年1月15日至1月17日。

原因是：家人春节团聚，需要提前回老家处理家庭事务。

我的年假余额为10天，本次请假使用3天，剩余7天。

根据公司制度，我已提前3天提交申请，符合年假管理规定。

**工作交接安排**
- 日常工作：已委托王五同事代为处理
- 紧急事务：可通过电话联系（138-1234-5678）
- 当前项目：项目进度正常，关键节点已在本周完成

**补充说明**
请假期间如有紧急事务，我会保持通讯畅通，随时配合处理。

请审批。

此致
敬礼！

**申请人**：张三
**申请日期**：2025年1月12日
**联系方式**：zhangsan@company.com / 138-1234-5678

---

**附件**
- 年假余额证明：系统显示剩余10天
- 工作交接清单：work_handover.docx
```

##### Step 7: 产出交付

```
2025-01-12 11:00

文档专家完成

产出：
{
  "outputs": [
    {
      "name": "leave_application.docx",
      "type": "Word文档",
      "content": "正式的请假申请"
    },
    {
      "name": "leave_application.txt",
      "type": "纯文本",
      "content": "可复制到OA系统"
    }
  ],

  "info_used": {
    "from_kb": [
      "user_profiles/user_001.json",
      "policies/leave_policy.md"
    ],
    "from_context": [
      "leave_type",
      "duration",
      "start_date"
    ],
    "from_user": [
      "reason"
    ]
  },

  "notes": [
    "申请符合公司规定",
    "提前3天申请 ✓",
    "年假余额充足 ✓",
    "工作交接已安排 ✓"
  ]
}

文档专家 → 总经理 → 用户
```

---

## 5. 关键机制设计

### 5.1 知识查询协议

**查询消息格式**：

```json
{
  "message_type": "KNOWLEDGE_QUERY",
  "from_agent": "agent_xxx",
  "to_agent": "agent_999_knowledge_manager",

  "query": {
    "question": "具体的问题",
    "context": "查询背景",
    "required_detail": "brief|standard|detailed",
    "scope": "specific|all_relevant"
  },

  "task_id": "task_xxx",
  "urgency": "LOW|MEDIUM|HIGH|BLOCKING",
  "timestamp": "2025-01-12T10:15:00Z"
}
```

**响应消息格式**：

```json
{
  "message_type": "KNOWLEDGE_RESPONSE",
  "from_agent": "agent_999_knowledge_manager",
  "to_agent": "agent_xxx",

  "response": {
    "answer": "答案内容",
    "details": {...},
    "sources": ["文件路径"],
    "confidence": "high|medium|low",
    "last_updated": "时间戳",
    "version": "版本号"
  },

  "metadata": {
    "query_processed": "原始问题",
    "search_results": 5,
    "time_used": "0.5s"
  }
}
```

### 5.2 信息缺失检测

**Agent如何判断信息缺失？**

```
Agent的LLM分析流程：

1. 接收任务和上下文
2. 列出所需信息清单
3. 逐项检查：
   - 已有 → 标记available
   - 可从知识库获取 → 标记kb_query
   - 可推断 → 标记inferred
   - 必须用户提供 → 标记required
   - 可选 → 标记optional

4. 生成信息完整性报告

示例：
{
  "task": "写请假申请",
  "info_completeness": {
    "user_profile": {
      "status": "kb_query",
      "source": "user_001",
      "confidence": "high"
    },
    "leave_policy": {
      "status": "kb_query",
      "source": "leave_policy.md",
      "confidence": "high"
    },
    "leave_type": {
      "status": "available",
      "source": "context",
      "confidence": "high"
    },
    "reason": {
      "status": "required",
      "source": null,
      "confidence": null
    }
  },
  "missing_required": ["reason"],
  "can_proceed": false,
  "action": "ask_user"
}
```

### 5.3 交互式询问的UI/UX

**Dashboard界面**：

```
┌─────────────────────────────────────────┐
│  AgentTalk Dashboard                    │
├─────────────────────────────────────────┤
│                                         │
│  📋 任务：写请假申请                    │
│  状态：等待信息                         │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ ⚠️ 文档专家需要你的信息         │   │
│  │                                 │   │
│  │ 缺失信息：                      │   │
│  │ • 请假原因                      │   │
│  │                                 │   │
│  │ 示例：                          │   │
│  │ • 家人探亲                      │   │
│  │ • 个人事务                      │   │
│  │ • 休息调整                      │   │
│  │                                 │   │
│  │ [输入框]                        │   │
│  │                                 │   │
│  │ [提交] [稍后回复]               │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

**邮件通知**：

```
主题：【AgentTalk】任务需要你的信息

你好，

文档专家正在执行"写请假申请"任务，但需要你提供以下信息：

缺失信息：
• 请假原因（必需）

请访问Dashboard或直接回复此邮件提供信息。

任务ID: user_task_002
紧急程度: 高

谢谢！
AgentTalk系统
```

### 5.4 知识更新机制

**知识过时检测**：

```
知识管理Agent的定期检查：

while true:
    sleep(24_hours)  # 每天检查

    # 检查知识库中的文件
    for knowledge_file in knowledge_base:
        # 检查文件时间戳
        file_age = current_time - file.modified_time

        if file_age > 180_days:  # 超过6个月
            # 标记为可能过时
            mark_as_possibly_outdated(knowledge_file)

            # 通知相关维护者
            send_notification({
                "type": "KNOWLEDGE_REVIEW",
                "file": knowledge_file,
                "reason": "文件超过6个月未更新",
                "action": "请验证是否仍为最新"
            })
```

**知识更新流程**：

```
用户或Agent发起更新：

{
  "message_type": "KNOWLEDGE_UPDATE",
  "from_agent": "USER",
  "to_agent": "agent_999_knowledge_manager",

  "update": {
    "file": "user_profiles/user_001.json",
    "changes": {
      "leave_info": {
        "annual_leave_used": 6,  # 从5更新到6
        "annual_leave_remaining": 9
      }
    },
    "reason": "张三刚休了1天年假",
    "source": "OA系统同步",
    "timestamp": "2025-01-12"
  }
}

知识管理Agent处理：
1. 验证更新请求
2. 更新文件
3. 记录更新日志
4. 确认更新
```

---

## 6. 最佳实践

### 6.1 知识库维护

**定期更新**：
- 用户信息：每月同步一次（从OA/HR系统）
- 公司制度：有变更时立即更新
- 项目信息：项目里程碑更新时

**版本控制**：
```
system/knowledge_base/
├── .git/
├── user_profiles/
│   └── user_001.json
├── policies/
│   └── leave_policy.md
└── CHANGELOG.md  # 知识库变更日志
```

**变更日志示例**：
```markdown
# 知识库变更日志

## 2025-01-12
- 更新 user_001.json：年假已用天数 5→6
- 更新 leave_policy.md：添加春节特殊规定

## 2025-01-05
- 新增 project_001/ 项目背景信息
```

### 6.2 敏感信息处理

**密级标注**：

```json
{
  "user_id": "user_001",
  "personal_info": {
    "name": "张三",
    "salary": {
      "value": "30K",
      "classification": "CONFIDENTIAL",  // 机密
      "access_level": "MANAGER_ONLY"
    }
  }
}
```

**访问控制**：

```python
class KnowledgeAccessControl:
    def can_access(self, agent_id: str, knowledge: Dict) -> bool:
        clearance_level = get_agent_clearance(agent_id)
        knowledge_level = knowledge.get('classification')

        return clearance_level >= knowledge_level

# 示例
# 文档专家（clearance: PUBLIC）不能访问薪资信息
# 人力资源经理（clearance: CONFIDENTIAL）可以访问
```

### 6.3 知识质量保证

**验证机制**：

```
知识管理Agent的质量检查：

1. 准确性验证
   - 检查信息来源
   - 交叉验证多个来源
   - 标注置信度

2. 时效性验证
   - 检查最后更新时间
   - 过期提醒

3. 完整性验证
   - 检查必填字段
   - 检查格式一致性

4. 一致性验证
   - 检查与相关知识的一致性
   - 发现矛盾及时告警
```

---

## 7. 扩展场景

### 7.1 项目背景知识

**场景**：生成项目进度报告

```
system/knowledge_base/project_context/project_001/
├── background.md
├── stakeholders.json
├── requirements.md
├── milestones.json
└── risks.md

使用：
{
  "context": {
    "project_id": "project_001"
  },
  "knowledge_references": [
    "system/knowledge_base/project_context/project_001/"
  ]
}
```

### 7.2 客户知识

**场景**：生成客户提案

```
system/knowledge_base/customers/
├── customer_alibaba/
│   ├── company_info.md
│   ├── contact_persons.json
│   ├── history_cooperation.md
│   └── preferences.json
└── customer_tencent/
    └── ...

使用：
{
  "context": {
    "customer_id": "customer_alibaba"
  }
}
```

### 7.3 动态知识

**场景**：实时数据（股票价格、天气等）

```
知识管理Agent扩展：
- 接入外部API
- 实时获取数据
- 缓存机制

{
  "message_type": "KNOWLEDGE_QUERY",
  "query": "当前天气",
  "location": "北京",
  "source": "external_api"  // 使用外部API
}
```

---

## 8. 总结

### 8.1 三层知识架构的价值

| 层级 | 解决的问题 | 优势 |
|------|-----------|------|
| **Layer 1: 知识库** | 公共知识复用 | 避免重复提供，保持一致性 |
| **Layer 2: 上下文** | 任务特定信息 | 灵活，一次性 |
| **Layer 3: 交互式** | 动态获取信息 | 准确，实时 |

### 8.2 知识管理Agent的角色

- **知识库管理员**：维护和更新
- **知识服务员**：响应查询
- **质量保证者**：验证准确性
- **知识推荐师**：推荐相关信息

### 8.3 关键原则

1. **准确性优先**：不确定就说明，不要编造
2. **来源明确**：所有信息标注来源
3. **版本控制**：跟踪知识变化
4. **访问控制**：保护敏感信息
5. **持续更新**：保持知识新鲜

---

**文档版本**：v1.0
**最后更新**：2025-01-05
