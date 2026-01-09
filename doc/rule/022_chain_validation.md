# 链式验证机制

**原则ID**: PR-022
**来源文档**: chain_validation_mechanism.md
**类别**: 核心机制

---

## 原则描述

Agent的任务完成结果不需要自己验证，由后续的Agent验证。如果验证不通过，后续Agent通过inbox/outbox机制触发前序任务重新执行。

## 核心思想

**简化职责，链式保证**:
- Agent A完成任务，不自己验证结果
- Agent B使用Agent A的输出，验证时发现问题
- Agent B发起[重新执行]命令（写入自己的outbox，由系统路由程序投递到Agent A的inbox）
- Agent A重新执行任务

## 验证流程

### 正常流程

```
Agent A → 产生输出 → Agent B → 验证通过 → 继续执行
```

### 异常流程

```
Agent A → 产生输出 → Agent B → 验证失败 → 发送[重新执行]命令 → Agent A → 重新执行
```

## 重新执行命令

### 命令格式

**文件名**: `cmd_reexecute_<task_id>.json`（仍然是执行命令文件，只是语义为“重新执行”）

**命令内容**:
```json
{
  "schema_version": "1.0",
  "command_id": "cmd_reexecute_001",
  "plan_id": "plan_develop_ecommerce",
  "idempotency_key": "plan_develop_ecommerce:task_001:reexecute",
  "original_task_id": "task_001",
  "original_agent": "agent_product_manager",
  "validation_result": {
    "validator": "agent_backend_developer",
    "score": 30,
    "reason": "需求文档不完整，缺少API接口定义",
    "issues": [
      "用户认证接口未定义",
      "商品查询接口参数不明确",
      "缺少错误处理规范"
    ]
  },
  "prompt": "请补充完善需求文档，特别是API接口定义部分。结合validation_result中的问题列表逐条修复，并重新生成输出。",
  "required_inputs": ["previous_output.json", "validation_feedback.json"],
  "wait_for_inputs": true,
  "score_required": false,
  "timeout": 3600
}
```

### 字段说明

#### original_task_id

原始任务的ID。

#### original_agent

原始任务执行者的Agent ID。

#### validation_result

验证结果，包含：
- validator: 验证者的Agent ID
- score: 验证评分（0-100）
- reason: 验证失败的原因
- issues: 具体问题列表

#### prompt

重新执行的提示词，指导Agent如何改进。

#### required_inputs

重新执行需要的输入文件，通常包括：
- previous_output.json: 上次的输出
- validation_feedback.json: 验证反馈

## 验证触发

### 何时验证

Agent在使用前一个Agent的输出时，自动触发验证：

1. **读取输出文件**
   Agent B从inbox读取Agent A的输出文件

2. **分析输出内容**
   Agent B分析输出文件的内容、格式、完整性

3. **发现问题**
   如果发现输出不符合要求，触发验证失败

4. **发送重新执行命令**
   Agent B将[重新执行]命令文件写入自己的 `outbox/<plan_id>/`，由系统路由程序投递到Agent A的 `inbox/<plan_id>/`

### 验证标准

验证者Agent根据自己的需求定义验证标准：

**示例**：
```json
{
  "validation_criteria": {
    "format": "JSON",
    "required_fields": ["api_endpoints", "request_params", "response_format"],
    "quality_threshold": 80,
    "completeness": "all_apis_defined"
  }
}
```

## 重新执行处理

### Agent A接收重新执行命令

1. **读取命令**
   Agent A从inbox收到`cmd_reexecute_*.json`

2. **分析验证反馈**
   Agent A读取validation_feedback.json
   了解具体问题和改进建议

3. **重新执行任务**
   Agent A根据prompt和验证反馈重新执行

4. **标记为重新执行**
   在输出的元数据中标记这是重新执行的结果
   记录重新执行的次数

### 重新执行次数限制

为了避免无限循环，设置重新执行次数限制：

**默认限制**: 3次

**超过限制后**:
- Agent A停止重新执行
- Agent A输出失败状态/错误到outbox
- 监控系统告警并请求人工介入（见PR-010/PR-024/PR-025）

## 验证反馈格式

### validation_feedback.json

**格式**:
```json
{
  "validator": "agent_backend_developer",
  "original_agent": "agent_product_manager",
  "original_task_id": "task_001",
  "validation_time": "2025-01-08T10:30:00Z",
  "score": 30,
  "decision": "REJECT",
  "reason": "需求文档不完整，无法用于后端开发",
  "issues": [
    {
      "severity": "HIGH",
      "category": "COMPLETENESS",
      "description": "用户认证API未定义",
      "location": "requirements.md#section3",
      "suggestion": "需要定义登录、注册、密码重置等API"
    },
    {
      "severity": "MEDIUM",
      "category": "CLARITY",
      "description": "商品查询参数不明确",
      "location": "requirements.md#section5",
      "suggestion": "需要明确查询参数：分页、排序、筛选条件"
    }
  ],
  "expectations": {
    "additions": [
      "用户认证相关API定义",
      "明确的API参数规范"
    ],
    "modifications": [
      "补充错误处理规范"
    ]
  }
}
```

## 典型场景

### 场景1: 需求文档不完整

```
PM Agent → 需求文档 → Backend Dev Agent
                              ↓
                        验证失败：缺少API定义
                              ↓
发送[重新执行]命令 → PM Agent
                              ↓
PM Agent补充完善需求文档
```

### 场景2: 代码质量不合格

```
Backend Dev → 代码 → Testing Agent
                          ↓
                    验证失败：测试通过率<80%
                          ↓
发送[重新执行]命令 → Backend Dev
                          ↓
Backend Dev修复bug，提高代码质量
```

> 推荐将“测试验收结果”落为结构化文件（包含score/decision/issues），并作为交付物是否可归档的依据（见PR-024与模板 `artifact_validation_result.json`）。

对于“需要高置信可运行”的交付，建议将验收扩展为多门禁证据链（构建/部署/冒烟/E2E/安全），并由发布角色汇总为 `release_manifest.json`（见PR-024与templates）。

### 场景3: 设计图不规范

```
Frontend Dev → 设计图 → UI Designer
                            ↓
                      验证失败：缺少响应式设计
                            ↓
发送[重新执行]命令 → Frontend Dev
                            ↓
Frontend Dev补充响应式设计
```

## 关键要点

- **不自己验证**: Agent完成任务后不验证，交给后续Agent验证
- **链式保证**: 每个Agent验证前一个Agent的输出
- **明确反馈**: 验证失败时提供详细的问题描述和改进建议
- **重新执行**: 发送[重新执行]命令触发前一个Agent重新执行
- **次数限制**: 最多重新执行3次，避免无限循环
- **记录历史**: 记录验证和重新执行的历史

## 与其他原则的配合

### 与PR-007（统一的执行命令）配合

- [重新执行]命令也是一种执行命令
- 遵循统一的命令格式
- 通过文件名/字段语义区分“重新执行”场景

### 与PR-017（日志追踪）配合

- 记录验证结果
- 记录重新执行命令
- 记录重新执行的次数和结果

### 与PR-009（任务分配机制）配合

- 验证失败触发重新执行
- 超过重新执行次数限制时，监控系统告警并请求人工介入（可选：由专门的规划者Agent重规划）

模板参考：
- `doc/rule/templates/artifact_validation_result.json`

---

**最后更新**: 2025-01-08
