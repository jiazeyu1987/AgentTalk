# 命令完整性保证机制

**原则ID**: PR-020
**来源文档**: command_integrity_guarantee.md
**类别**: 核心机制

---

## 原则描述

通过skill保证生成的命令是完整的、符合格式的JSON文件。Agent使用skill生成命令，确保命令包含所有必需字段且格式正确。

## 核心思想

**命令生成 = Skill调用**

Agent不手动构造JSON命令，而是通过调用专门的skill来生成命令。Skill负责：
1. 验证所有必需字段
2. 确保JSON格式正确
3. 添加默认值
4. 验证字段类型
5. 返回完整的命令对象

## 命令生成流程

### 1. Agent准备命令参数

Agent收集命令所需的信息：
- command_id
- plan_id
- task_id
- command_seq（推荐，用于“同一task多条命令”的可计算排序）
- prompt
- required_inputs
- 其他参数

### 2. 调用命令生成skill

Agent调用专门的skill，例如"generate_command"：

**调用示例**:
```
请生成一个执行命令，包含以下参数：
- command_id: cmd_task_001
- plan_id: plan_develop_ecommerce
- task_id: task_001
- command_seq: 1
- prompt: 分析需求文档并生成用户故事
- required_inputs: ["requirements.md"]
- wait_for_inputs: true
- score_required: true
```

### 3. Skill生成完整命令

Skill根据参数生成完整的命令JSON：

**生成的命令**:
```json
{
  "schema_version": "1.0",
  "command_id": "cmd_task_001",
  "plan_id": "plan_develop_ecommerce",
  "task_id": "task_001",
  "command_seq": 1,
  "idempotency_key": "plan_develop_ecommerce:task_001:cmd_task_001",
  "prompt": "分析需求文档并生成用户故事",
  "required_inputs": ["requirements.md"],
  "wait_for_inputs": true,
  "score_required": true,
  "score_criteria": "根据用户故事的完整性、清晰度、可测试性评分0-100",
  "on_complete": {
    "message_template": "用户故事生成完成: {result}, 评分: {score}"
  },
  "on_failure": {
    "message_template": "用户故事生成失败: {error}"
  },
  "timeout": 3600
}
```

### 4. 验证命令完整性

Skill自动验证生成的命令：

**检查项**:
1. ✅ command_id存在且唯一
2. ✅ plan_id存在
3. ✅ task_id存在且非空（用于绑定DAG节点并投递给assigned_agent_id）
4. ✅ command_seq存在且可排序（MVP 必须；并且必须等于 command_id 末尾序号）
5. ✅ prompt存在且非空
6. ✅ required_inputs是数组
7. ✅ wait_for_inputs是布尔值
8. ✅ score_required是布尔值
9. ✅ on_complete存在（可选，仅用于本地通知/日志）
10. ✅ on_failure存在（可选，仅用于本地通知/日志）
11. ✅ timeout是正整数

### 5. 返回完整命令

Skill返回验证通过的命令：
- 验证通过：返回完整命令JSON
- 验证失败：返回错误信息

## 命令格式标准

### 必需字段

所有命令必须包含以下字段：

#### command_id

命令的唯一标识符。

**格式**: 字符串

**生成规则**: `cmd_<task_id>_<sequence>`

**示例**: `"cmd_task_001_001"`

补充（MVP 必须写死）：
- `command_id` 必须符合：`cmd_<task_id>_<NNN...>`（末尾序号至少3位数字）
- `command_seq` 必须等于 `command_id` 最末尾序号（从右侧最后一个 `_` 之后解析为整数）；若不一致视为命令不合法
- `command_id` 中的 `<task_id>` 必须等于字段 `task_id`（不允许“命令ID写的是别的task”）

#### plan_id

关联的plan标识符。

**格式**: 字符串

**示例**: `"plan_develop_ecommerce"`

#### task_id（MVP 强制）

命令绑定到 DAG 节点的关键字段。系统路由程序以 `task_id` 在“当前阶段 DAG”中定位 `nodes[]`，并使用该节点的 `assigned_agent_id` 作为唯一投递目标。

**格式**: 字符串，非空

**示例**: `"task_001"`

#### prompt

命令的提示词描述。

**格式**: 字符串，非空

**示例**: `"分析需求文档并生成用户故事"`

#### required_inputs

需要的输入文件列表。

**格式**: 字符串数组

**示例**: `["requirements.md", "user_stories.json"]`

#### wait_for_inputs

是否等待输入文件齐全。

**格式**: 布尔值

**示例**: `true`

#### score_required

是否需要评分。

**格式**: 布尔值

**示例**: `true`

#### on_complete

完成后的操作。

**格式**: 对象，包含message_template（用于本地通知/日志；不作为跨Agent投递路由来源）

**示例**:
```json
{
  "message_template": "任务完成: {result}"
}
```

#### on_failure

失败时的操作。

**格式**: 对象，包含message_template（用于本地通知/日志；不作为跨Agent投递路由来源）

**示例**:
```json
{
  "message_template": "任务失败: {error}"
}
```

#### timeout

超时时间（秒）。

**格式**: 正整数

**示例**: `3600`

### 可选字段

#### score_criteria

评分标准描述。

**格式**: 字符串

**示例**: `"根据完整性、清晰度、可测试性评分0-100"`

#### retry_times

重试次数。

**格式**: 非负整数

**默认值**: `0`

#### schema_version（推荐）

命令schema版本，用于解析兼容与死信处理。

**格式**: 字符串

**示例**: `"1.0"`

#### idempotency_key（推荐）

用于“重复命令不重复执行”的幂等键。可由规划者按规则生成，也可由skill补全默认值（例如用command_id）。

**格式**: 字符串

**示例**: `"plan_001:task_002:cmd_task_002_001"`

#### dag_ref（MVP 必须）

用于防止“旧命令跑在新DAG上”。命令生成时必须把当前 `task_dag.json` 的 `sha256`（以及可选 revision）写入命令，Router 在投递前校验一致性。

**示例**:
```json
{
  "dag_ref": { "sha256": "..." }
}
```

#### payload_hash（推荐）

命令内容哈希（或关键字段哈希），用于完整性校验与审计。

**格式**: 字符串（如sha256）

## Skill实现

### skill定义

**文件**: `skills/generate_command/skill.md`

**内容**:
```markdown
---
skill_name: generate_command
skill_version: 1.0.0
description: 生成完整的、符合格式的执行命令
inputs:
  - name: command_params
    type: object
    description: 命令参数对象
outputs:
  - name: command
    type: object
    description: 完整的命令JSON
---

# 命令生成技能

根据提供的参数生成完整的执行命令JSON，确保所有必需字段都存在且格式正确。
```

### 验证逻辑

Skill包含验证逻辑：

1. **字段存在性检查**
   - 检查所有必需字段是否存在
   - 缺失字段添加默认值

2. **字段类型检查**
   - 检查字段类型是否正确
   - 类型不匹配时尝试转换

3. **字段值验证**
   - 检查字段值是否在有效范围内
   - 无效值使用默认值

4. **一致性检查**
   - 检查字段之间的一致性
   - 例如：score_required=true时，score_criteria必须存在

## 关键要点

- **Skill生成**: 通过skill生成命令，不手动构造
- **完整性保证**: Skill验证所有必需字段
- **格式正确**: Skill确保JSON格式正确
- **默认值**: Skill为可选字段提供合理默认值
- **验证返回**: Skill返回验证结果
- **可扩展**: 可以添加新的必需或可选字段

## 与其他原则的配合

### 与PR-007（统一的执行命令）配合

- 确保生成的命令符合统一的执行命令格式
- 保证所有Agent都能解析和执行

### 与PR-019（Claude Code调用机制）配合

- 通过Claude Code调用命令生成skill
- 利用LLM的能力生成合理的命令参数

### 与PR-017（日志追踪）配合

- 记录命令生成过程
- 记录验证结果

---

**最后更新**: 2025-01-08
