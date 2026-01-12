# 统一的执行命令

**原则ID**: PR-007
**来源文档**: unified_command_system.md
**类别**: 核心机制

---

## 原则描述

AgentTalk系统中只有一种命令: 执行命令。Agent在输入满足时，将输入内容、Agent自身的提示词、命令的提示词提交给LLM，获取返回值和可选的评分，然后按任务文件/命令中**预先定义**的投递规则产出文件到outbox。

注意：Agent不直接写其他Agent的inbox（见PR-003）。跨Agent投递由系统路由程序按任务文件（DAG路由表）执行（见PR-002/PR-024）。

## 路由归属：命令不定义投递目标（由 DAG/Meta-DAG 统一定义）

为保持路由机制唯一且可审计，`cmd_*.msg.json`（命令消息）不作为“投递目标”的来源：
- 命令文件投递给哪个执行者：由 DAG 中任务的 `assigned_agent_id` 决定。
- 命令执行产物投递给谁：由 DAG/Meta-DAG 的 `outputs[].deliver_to`（或 `routing_rules` 兜底）决定。

补充：在 DAG/Meta-DAG 驱动投递的口径下，命令必须能绑定到某个 DAG 节点；因此 `payload.command.task_id` 在 MVP 中视为必填字段（见 `doc/DAG/semantics.md` 9）。

涉及评分的 if/else 也不在命令里做“分支投递”，而是通过：
- DAG 门禁（gates/thresholds）与评审协调员/发布协调员的判定任务
- 或在 DAG 中显式建模不同后续任务（例如 REVISE/REJECT 分支各自的返工任务）

## 命令格式

（方案B）执行命令通过 message_envelope 投递：命令消息文件 `cmd_*.msg.json`（envelope `type=command`），具体命令对象位于 `payload.command`。
系统投递日志/回执以 `message_id` 为链路唯一ID。

命令对象本身使用最小化格式（见 `doc/rule/templates/command.cmd.json`），作为 `payload.command` 的内容：

```json
{
  "command_id": "cmd_001",
  "plan_id": "plan_a3f5b2c8",
  "task_id": "task_001",
  "command_seq": 1,
  "schema_version": "1.0",
  "idempotency_key": "plan_a3f5b2c8:task_001:cmd_001",
  "prompt": "命令的提示词描述，告诉Agent要做什么",
  "required_inputs": ["feedback_agent_a.json", "feedback_agent_b.json"],
  "wait_for_inputs": true,
  "score_required": true,
  "score_criteria": "根据共识度和质量评分，范围0-100",
  "timeout": 3600,
  "on_complete": {
    "message_template": "评估已完成，结果: {result}, 分数: {score}"
  },
  "on_failure": {
    "message_template": "评估失败，错误: {error}"
  }
}
```

模板参考：
- `doc/rule/templates/command.cmd.json`
- `doc/rule/templates/command_envelope.msg.json`

**字段说明**:
- `command_id`: 命令的唯一标识符
- `plan_id`: 关联的plan标识符
- `task_id`: 绑定到 DAG 节点的任务ID（MVP 必填）
- `command_seq`: 命令序号（推荐；用于 Router 侧丢弃旧命令，避免同一 task 多条命令并发）
- `schema_version`: 命令schema版本，用于兼容性与解析校验
- `idempotency_key`: 幂等键，用于“重复命令不重复执行”（推荐）
- `prompt`: 命令的提示词，描述要执行的任务
- `required_inputs`: 兼容字段；需要的输入文件列表（MVP 仍要求存在，但当 `resolved_inputs` 存在时可为空数组）
- `resolved_inputs`: 权威输入清单（推荐）；由控制面把 DAG v1.1 的 selector/pick_policy 解析/编译后的“可执行输入列表”
- `wait_for_inputs`: 是否等待输入文件齐全(true/false)
- `score_required`: 是否需要评分(true/false)
- `score_criteria`: 评分标准描述(仅当score_required=true时)
- `timeout`: 超时时间（秒），用于避免无限等待（见PR-010）
- `on_complete.message_template`: 结果消息模板，可用{result}和{score}变量
- `on_failure.message_template`: 失败消息模板，可用{error}变量

## 工作流程

### 1. 命令到达

Agent 在自己的 inbox 中发现命令消息 `cmd_*.msg.json`（envelope `type=command`）。

### 2. 输入检查

Agent检查 `required_inputs` 列表中的文件是否都已“可用”：
- 输入文件应由 Heartbeat 的 `type=artifact` 输入归档机制落盘到 `workspace/<plan_id>/inputs/`（见 `doc/develop/05_agent_heartbeat_and_dispatch.md`）
- 命令执行时默认只在 `workspace/<plan_id>/inputs/` 与当前任务工作目录下匹配（不再把 inbox 根目录当作长期输入仓库，避免文件被移动/清理导致“输入忽然消失”）

补充（避免双口径）：
- 若命令包含 `resolved_inputs`：执行侧必须以其为准；`required_inputs` 仅保留兼容。
- `resolved_inputs` 是把 DAG v1.1 的 `inputs[] selector/pick_policy` 编译为可执行清单的结果，执行侧不直接读取 DAG。

**情况A: 文件齐全 或 wait_for_inputs=false**
- Agent继续执行步骤3

**情况B: 文件不齐全 且 wait_for_inputs=true**
- Agent创建等待状态，不执行命令
- 将命令标记为"等待输入"
- 当新文件到达时，自动重新检查并触发执行
- 若等待超过 `timeout`：应产出 `human_intervention_request.json` 请求人类补齐（见PR-025；实现口径见 `doc/develop/05_agent_heartbeat_and_dispatch.md`）

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
- 将结果文件写入自己的 `outbox/<plan_id>/`，由系统路由程序根据“当前阶段 DAG”（Meta-DAG/Business-DAG）的 `outputs[].deliver_to`/`routing_rules` 投递到目标Agent的 `inbox/<plan_id>/`

为提升可靠性，推荐：
- 结果文件随附元数据（message_id、sha256、type、idempotency_key），便于系统路由去重与审计（见PR-001/PR-017/PR-024）
- 采用原子写入（先写`.tmp`再重命名），避免下游读到半写入文件（见PR-001）

## 两种命令类型

### 类型1: 不需要评分的命令

**特点**:
- `score_required=false`
- LLM只返回执行结果
- Agent产出结果文件到outbox，由系统路由投递到目标Agent

**典型应用**:
- 信息汇总: "收集所有反馈并总结"
- 简单任务: "生成一份报告"
- 通知发送: "通知所有Agent会议时间"

### 类型2: 需要评分的命令

**特点**:
- `score_required=true`
- 命令的prompt中定义评分标准
- LLM返回结果和分数
- Agent可以根据分数决定走哪条预先定义的输出分支（例如生成不同的输出文件），投递仍由系统路由程序完成

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
    "notes": "Score branching is modeled in DAG (gates/thresholds + coordinator tasks), not by command routing."
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
2. 发现新的 `cmd_*.msg.json` 文件
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
  "task_id": "task_review_consensus",
  "command_seq": 1,
  "schema_version": "1.0",
  "timeout": 3600,
  "prompt": "检查所有团队成员的评分是否达成共识，如果共识度低于70分，说明分歧原因",
  "required_inputs": ["feedback_*.json"],
  "wait_for_inputs": true,
  "score_required": true,
  "score_criteria": "共识度评分，0-100分",
  "on_complete": {
    "message_template": "共识检查完成，结果: {result}, 共识度: {score}分"
  },
  "on_failure": {
    "message_template": "共识检查失败，错误: {error}"
  }
}
```

**示例2: 测试者等待开发者交付**
```json
{
  "command_id": "cmd_test_delivery",
  "plan_id": "plan_feature_development",
  "task_id": "task_test_delivery",
  "command_seq": 1,
  "schema_version": "1.0",
  "timeout": 3600,
  "prompt": "对开发者交付的代码进行测试，评估通过率，给出0-100分的质量评分",
  "required_inputs": ["delivery_package.zip", "test_spec.json"],
  "wait_for_inputs": true,
  "score_required": true,
  "score_criteria": "质量评分，0-100分",
  "on_complete": {
    "message_template": "测试完成，通过率: {result}, 质量评分: {score}分"
  },
  "on_failure": {
    "message_template": "测试失败，错误: {error}"
  }
}
```

**示例4: 专家评审DAG**

将DAG评审作为一个标准执行命令投递给“专家评审角色”，输出结构化打分与修改建议：
- 评审命令模板：`doc/rule/templates/dag_review_request.cmd.json`
- 评审结果模板：`doc/rule/templates/dag_review_result.json`

**示例3: 简单汇总(不需要评分)**
```json
{
  "command_id": "cmd_summary_report",
  "plan_id": "plan_weekly_report",
  "task_id": "task_summary_report",
  "command_seq": 1,
  "schema_version": "1.0",
  "timeout": 1800,
  "prompt": "汇总所有Agent的周报，生成一份简洁的团队周报",
  "required_inputs": ["weekly_report_*.json"],
  "wait_for_inputs": true,
  "score_required": false,
  "on_complete": {
    "message_template": "团队周报已生成: {result}"
  },
  "on_failure": {
    "message_template": "周报汇总失败，错误: {error}"
  }
}
```

---

**最后更新**: 2025-01-08
