# 统一的执行命令

**原则ID**: PR-007
**来源文档**: unified_command_system.md
**类别**: 核心机制

---

## 原则描述

AgentTalk系统中只有一种命令: 执行命令。Agent在输入满足时，将输入内容、Agent自身的提示词、命令的提示词提交给LLM，获取返回值和可选的评分，然后决定向哪些Agent发送哪些信息。

## 命令格式

执行命令是一个JSON文件，使用最小化格式:

```json
{
  "command_id": "cmd_001",
  "plan_id": "plan_a3f5b2c8",
  "prompt": "命令的提示词描述，告诉Agent要做什么",
  "required_inputs": ["feedback_agent_a.json", "feedback_agent_b.json"],
  "wait_for_inputs": true,
  "score_required": true,
  "score_criteria": "根据共识度和质量评分，范围0-100",
  "on_complete": {
    "send_to": ["agent_general_manager"],
    "message_template": "评估已完成，结果: {result}, 分数: {score}"
  }
}
```

**字段说明**:
- `command_id`: 命令的唯一标识符
- `plan_id`: 关联的plan标识符
- `prompt`: 命令的提示词，描述要执行的任务
- `required_inputs`: 需要的输入文件列表
- `wait_for_inputs`: 是否等待输入文件齐全(true/false)
- `score_required`: 是否需要评分(true/false)
- `score_criteria`: 评分标准描述(仅当score_required=true时)
- `on_complete.send_to`: 完成后向哪些Agent发送结果
- `on_complete.message_template`: 结果消息模板，可用{result}和{score}变量

## 工作流程

### 1. 命令到达

Agent在自己的inbox中发现 `cmd_*.json` 文件。

### 2. 输入检查

Agent检查 `required_inputs` 列表中的文件是否都在inbox中:

**情况A: 文件齐全 或 wait_for_inputs=false**
- Agent继续执行步骤3

**情况B: 文件不齐全 且 wait_for_inputs=true**
- Agent创建等待状态，不执行命令
- 将命令标记为"等待输入"
- 当新文件到达时，自动重新检查并触发执行

### 3. 组合提示词

Agent将以下内容组合:
- 所有输入文件的内容
- Agent自身的提示词(定义在agent_profile.json中)
- 命令的prompt字段

### 4. 提交给LLM

Agent将组合后的提示词提交给LLM。

### 5. LLM返回

LLM返回:

**不需要评分的命令** (score_required=false):
```json
{
  "result": "执行结果描述"
}
```

**需要评分的命令** (score_required=true):
```json
{
  "result": "执行结果描述",
  "score": 85,
  "score_explanation": "评分理由"
}
```

### 6. 处理结果

Agent根据 `on_complete` 定义:
- 使用 `message_template` 格式化消息
- 将 `{result}` 替换为实际结果
- 将 `{score}` 替换为实际分数(如果有)
- 向 `send_to` 列表中的每个Agent发送消息

## 两种命令类型

### 类型1: 不需要评分的命令

**特点**:
- `score_required=false`
- LLM只返回执行结果
- Agent直接转发结果给目标Agent

**典型应用**:
- 信息汇总: "收集所有反馈并总结"
- 简单任务: "生成一份报告"
- 通知发送: "通知所有Agent会议时间"

### 类型2: 需要评分的命令

**特点**:
- `score_required=true`
- 命令的prompt中定义评分标准
- LLM返回结果和分数
- Agent可以根据分数决定发送给不同的Agent

**评分标准在prompt中定义**:
```
请评估以下反馈是否达成共识，并给出0-100分的评分:
- 90-100分: 所有评分一致或差异很小
- 70-89分: 大部分评分一致，有小分歧
- 50-69分: 评分有明显分歧
- 0-49分: 评分严重不一致
```

**条件分支示例**:
Agent可以在 `on_complete` 中根据score决定发送目标:
```json
{
  "score_required": true,
  "on_complete": {
    "send_to_condition": [
      {"min_score": 70, "send_to": ["agent_general_manager"]},
      {"min_score": 0, "send_to": ["agent_developer_01"]}
    ]
  }
}
```

## 等待机制

Agent可以等待输入文件到达:

**创建等待**:
- Agent检查 `required_inputs`，发现文件不齐全
- 设置 `wait_for_inputs=true`
- Agent将命令标记为"等待输入"
- Agent继续处理其他任务或进入休眠

**自动触发**:
- 当新文件到达inbox
- Agent自动检查所有等待中的命令
- 如果某个命令的 `required_inputs` 都已齐全
- Agent自动执行该命令

**超时处理**:
- 配合PR-010超时保护机制
- 如果等待时间超过配置的超时时间
- Agent将命令标记为"超时"并记录错误

## LLM驱动的灵活性

**关键设计思想**: 所有的命令逻辑都在prompt中定义，而非硬编码。

**优势**:
1. **无需修改代码**: 新的命令行为只需修改prompt
2. **充分利用LLM**: LLM理解prompt并执行复杂任务
3. **高度灵活**: 同一个命令格式可以实现不同的行为
4. **易于扩展**: 新增功能不需要新增命令类型

**示例**: 通过prompt实现不同的命令行为

**命令1: 共识检查**
```json
{
  "prompt": "检查所有Agent的评分是否达成共识，给出0-100分的共识度评分",
  "score_required": true
}
```

**命令2: 质量评估**
```json
{
  "prompt": "评估代码质量，检查是否有bug、性能问题、安全问题，给出0-100分的质量评分",
  "score_required": true
}
```

**命令3: 简单汇总**
```json
{
  "prompt": "将所有反馈汇总成一份简洁的报告",
  "score_required": false
}
```

## 与轮询机制的配合

Agent通过轮询机制(见PR-011)工作:

1. 心跳引擎每10秒扫描inbox
2. 发现新的 `cmd_*.json` 文件
3. 检查输入是否满足
4. 执行或等待
5. 继续下一轮轮询

## 与核心机制的配合

**与PR-001(inbox/outbox文件传递)配合**:
- 命令通过inbox接收
- 结果通过outbox发送
- 所有交互都是文件传递

**与PR-010(超时保护)配合**:
- 长时间等待的命令会被超时机制终止
- 避免Agent永久阻塞

**与PR-011(统一轮询)配合**:
- 轮询机制发现命令文件
- 轮询机制检查输入是否齐全
- 轮询机制触发命令执行

## 关键要点

- **统一性**: 只有1种命令类型，简化系统架构
- **最小化**: 命令格式只包含必需字段，易于理解和使用
- **灵活性**: 通过prompt定义不同的命令行为
- **LLM驱动**: 所有的命令逻辑都在prompt中定义，而非硬编码
- **支持等待**: Agent可以等待输入文件到达，不会永久阻塞
- **支持评分**: 可选的评分机制用于条件分支和决策
- **自动触发**: 输入文件到达后自动触发等待中的命令
- **可追溯**: 所有命令执行都以文件形式记录

## 典型应用

**示例1: 经理等待团队共识**
```json
{
  "command_id": "cmd_review_consensus",
  "plan_id": "plan_project_approval",
  "prompt": "检查所有团队成员的评分是否达成共识，如果共识度低于70分，说明分歧原因",
  "required_inputs": ["feedback_*.json"],
  "wait_for_inputs": true,
  "score_required": true,
  "score_criteria": "共识度评分，0-100分",
  "on_complete": {
    "send_to": ["agent_general_manager"],
    "message_template": "共识检查完成，结果: {result}, 共识度: {score}分"
  }
}
```

**示例2: 测试者等待开发者交付**
```json
{
  "command_id": "cmd_test_delivery",
  "plan_id": "plan_feature_development",
  "prompt": "对开发者交付的代码进行测试，评估通过率，给出0-100分的质量评分",
  "required_inputs": ["delivery_package.zip", "test_spec.json"],
  "wait_for_inputs": true,
  "score_required": true,
  "on_complete": {
    "send_to": ["agent_project_manager"],
    "message_template": "测试完成，通过率: {result}, 质量评分: {score}分"
  }
}
```

**示例3: 简单汇总(不需要评分)**
```json
{
  "command_id": "cmd_summary_report",
  "plan_id": "plan_weekly_report",
  "prompt": "汇总所有Agent的周报，生成一份简洁的团队周报",
  "required_inputs": ["weekly_report_*.json"],
  "wait_for_inputs": true,
  "score_required": false,
  "on_complete": {
    "send_to": ["agent_general_manager"],
    "message_template": "团队周报已生成: {result}"
  }
}
```

---

**最后更新**: 2025-01-08
