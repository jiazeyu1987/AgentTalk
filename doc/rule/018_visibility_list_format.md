# visibility_list文件格式

**原则ID**: PR-018
**来源文档**: agent_capability_declaration.md
**类别**: 核心机制

---

## 原则描述

GM Agent的visibility_list文件夹包含各个Agent的描述文件，使用JSON格式保证结构化和可解析性。

## 文件组织

### visibility_list文件夹

位于GM Agent目录下：

```
agent_general_manager/
└── visibility_list/
    ├── agent_product_manager.json
    ├── agent_database_expert.json
    ├── agent_backend_developer.json
    ├── agent_frontend_developer.json
    └── agent_testing_engineer.json
```

### 文件命名规则

**格式**: `agent_<agent_id>.json`

**示例**:
- agent_product_manager.json
- agent_database_expert.json

## JSON文件格式

### 必需字段

每个Agent描述文件包含以下必需字段：

#### agent_id

Agent的唯一标识符。

**格式**: 字符串

**示例**: `"agent_product_manager"`

#### name

Agent的可读名称。

**格式**: 字符串

**示例**: `"产品经理"`

#### skills

Agent拥有的技能列表。

**格式**: 字符串数组

**示例**:
```json
"skills": [
  "需求分析",
  "产品设计",
  "用户故事编写",
  "验收标准定义"
]
```

#### inputs

Agent完成任务所需的输入类型。

**格式**: 对象数组

**每个输入对象包含**:
- `type`: 输入类型（文件类型、数据类型）
- `description`: 输入描述
- `required`: 是否必需

**示例**:
```json
"inputs": [
  {
    "type": "text/markdown",
    "description": "产品想法或用户需求描述",
    "required": true
  },
  {
    "type": "application/json",
    "description": "市场调研数据",
    "required": false
  }
]
```

#### outputs

Agent完成任务后能够提供的输出类型。

**格式**: 对象数组

**每个输出对象包含**:
- `type`: 输出类型
- `description`: 输出描述
- `format`: 输出格式规范

**示例**:
```json
"outputs": [
  {
    "type": "text/markdown",
    "description": "需求文档",
    "format": "标准的PRD格式"
  },
  {
    "type": "application/json",
    "description": "用户故事列表",
    "format": "包含story、acceptance_criteria字段"
  }
]
```

### 可选字段

#### clarification

用于“需求澄清问题收集”的角色模板与约束（推荐）。该字段的目的不是让 GM 全知全能，而是让 GM 可以根据各角色的声明，向合适的 Agent 发出“澄清问题收集”命令，并汇总一次性向用户/Human Gateway 询问。

**格式**: 对象

**建议字段**:
- `templates`: 该角色可复用的澄清模板引用（文件路径或模板名）
- `scope`: 该角色主要负责澄清的范围（例如玩法、验收、技术约束、风险）
- `max_questions`: 建议该角色一次输出的最大问题数（便于“一次性澄清”）

**示例**:
```json
"clarification": {
  "templates": [
    "templates/clarification_game_design.md",
    "templates/clarification_pm.md"
  ],
  "scope": ["玩法与手感", "关卡与美术", "验收标准"],
  "max_questions": 12
}
```

#### constraints

Agent的约束条件。

**格式**: 对象

**常见约束**:
- `max_complexity`: 最大任务复杂度
- `estimated_time`: 预估完成时间
- `dependencies`: 需要的前置条件

**示例**:
```json
"constraints": {
  "max_complexity": "medium",
  "estimated_time": "2-4 hours",
  "dependencies": ["必须有明确的产品目标"]
}
```

#### capabilities

Agent能力的详细说明。

**格式**: 对象

**示例**:
```json
"capabilities": {
  "can_lead_team": true,
  "can_write_code": false,
  "can_create_designs": true
}
```

#### version

Agent能力描述的版本号。

**格式**: 字符串

**示例**: `"1.0.0"`

## 完整示例

```json
{
  "agent_id": "agent_product_manager",
  "name": "产品经理",
  "version": "1.0.0",
  "skills": [
    "需求分析",
    "产品设计",
    "用户故事编写",
    "验收标准定义",
    "原型设计"
  ],
  "inputs": [
    {
      "type": "text/markdown",
      "description": "产品想法或用户需求描述",
      "required": true
    },
    {
      "type": "application/json",
      "description": "市场调研数据",
      "required": false
    }
  ],
  "outputs": [
    {
      "type": "text/markdown",
      "description": "产品需求文档(PRD)",
      "format": "标准的PRD格式，包含背景、目标、功能列表"
    },
    {
      "type": "application/json",
      "description": "用户故事列表",
      "format": "包含story、acceptance_criteria、priority字段"
    }
  ],
  "constraints": {
    "max_complexity": "medium",
    "estimated_time": "2-4 hours",
    "dependencies": ["必须有明确的产品目标"]
  },
  "capabilities": {
    "can_lead_team": true,
    "can_write_code": false,
    "can_create_designs": true
  }
}
```

## 文件验证

### 必需字段检查

加载visibility_list文件时，必须检查：
1. agent_id是否存在且唯一
2. name是否存在
3. skills是否为非空数组
4. inputs是否为数组
5. outputs是否为非空数组

### 格式验证

1. JSON格式必须有效
2. 所有必需字段必须存在
3. 字段类型必须正确
4. 枚举值必须在允许范围内

### 语义验证

1. agent_id必须与文件名匹配
2. skills中不能有重复项
3. inputs和outputs的type必须是标准MIME类型

## GM使用流程

1. **扫描visibility_list文件夹**
   - 发现所有.json文件
   - 解析每个文件

2. **验证文件格式**
   - 检查必需字段
   - 验证JSON有效性

3. **加载Agent能力**
   - 读取skills、inputs、outputs
   - 存储在内存中供查询

4. **任务分配时查询**
   - 根据任务需求匹配Agent
   - 检查inputs/outputs是否匹配
   - 检查constraints是否满足

## 关键要点

- **JSON格式**: 使用JSON保证结构化和可解析性
- **必需字段**: agent_id、name、skills、inputs、outputs
- **可选字段**: constraints、capabilities、version
- **标准命名**: agent_<agent_id>.json
- **可验证**: 必需字段检查、格式验证、语义验证
- **易扩展**: 可以添加自定义字段

## 与其他原则的配合

### 与PR-009（任务分配机制）配合

- GM读取visibility_list中的Agent描述
- 根据Agent的skills、inputs、outputs进行任务分配

### 与PR-020（Agent能力自评机制）配合

- visibility_list提供Agent的能力声明
- Agent接收命令后自评，验证是否匹配能力声明

### 与PR-001（inbox/outbox文件传递）配合

- inputs定义了Agent需要的输入文件类型
- outputs定义了Agent产生的输出文件类型

---

**最后更新**: 2025-01-08
