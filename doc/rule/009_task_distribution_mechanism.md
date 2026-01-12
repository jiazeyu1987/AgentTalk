# 任务分配机制

**原则ID**: PR-009
**来源文档**: agent_task_distribution.md
**类别**: 核心机制

---

## 原则描述

GM（总经理）Agent通过LLM驱动将复杂任务分配给合适的Agent，每个Agent负责独立的一块工作，任务之间不重叠，不递归分配。

说明：本原则中涉及的“生成→多人评审→修订→再评审→放行→发布”的闭环，以通用流程文档为准：
- `doc/process/iterative_review_to_release_flow.md`

## visibility_list文件夹

GM Agent有一个visibility_list文件夹，里面包含各个Agent的描述文件。

### 文件夹结构

visibility_list文件夹位于GM Agent目录下，包含若干个描述文件。

### 描述文件内容

每个文件描述一个Agent，包含以下信息：
- Agent ID：Agent的唯一标识符
- 名字：Agent的可读名称
- 拥有的技能：Agent能够处理的工作类型
- 需要的输入：Agent完成任务所需的输入类型
- 可以的输出：Agent完成任务后能够提供的输出类型

## 任务分配流程

### 0. 一次性需求澄清（推荐）

GM 不应假设自己具备领域全知知识（例如游戏玩法/关卡节奏/美术风格/手感指标）。在生成可执行的 DAG 与命令前，推荐进行**一次性需求澄清**：

1. **基于 visibility_list 选择“需求制定/评审”相关 Agent**
   - 例如：产品经理、游戏策划、引擎/架构、测试/验收、构建发布等角色。
2. **向这些 Agent 投递“澄清问题收集”执行命令**
   - 每个角色根据自己的模板输出：还缺哪些外部信息/文件/验收标准才能开工与验收。
   - 输出必须结构化（问题、原因、优先级、关联任务/交付物、默认假设与风险）。
3. **GM 汇总去重并一次性反馈给用户/Human Gateway**
   - 只做合并、排序与格式化，不替领域角色编造答案。
4. **澄清只做一轮**
   - 第一轮用于锁定不可逆前提（平台/引擎/范围/MVP/验收口径/素材来源与版权）。
   - 后续只允许在运行期出现阻塞时“按需澄清”（见下文“运行期按需澄清”），避免无限前置循环。

### 运行期按需澄清（必须支持）

即使做过一次性澄清，运行中仍可能发现缺少材料或标准。此时应：
- 将相关任务标记为 `BLOCKED_WAITING_INPUT` 或 `BLOCKED_WAITING_HUMAN`
- 产出 `human_intervention_request.json`（或等价请求文件）请求补齐缺失材料/决策
- 在输入到达后继续推进，而不是让 GM 持续在线手动调度

### 1. 读取visibility_list

GM读取visibility_list文件夹中所有Agent的描述文件，了解每个Agent的能力范围、输入和输出要求。

### 2. 分析原始任务

GM使用LLM分析用户提交的原始任务，理解任务的目标、范围和要求。

### 3. 任务分解

GM通过LLM将原始任务分解为多个子任务，分解时遵循以下原则：
- 不重叠：每个子任务负责独立的一块工作，子任务之间没有职责重叠
- 可分配：每个子任务都可以分配给visibility_list中的一个Agent
- 明确边界：每个子任务有清晰的输入和输出定义

### 4. Agent选择

为每个子任务选择最合适的Agent：
- 根据Agent的技能匹配度
- 检查Agent的输入要求是否满足
- 确认Agent的输出符合后续任务的需求

### 5. 不递归分配

任务分配只有一层：
- GM将任务分配给各个Agent
- 被分配的Agent直接执行任务，不继续向下分配
- 保持架构简单，避免多层嵌套的复杂性

## 输出格式

任务分配完成后，GM生成两类文件，放到outbox等待分配给其他Agent。

### DAG图

DAG（有向无环图）描述子任务之间的依赖关系：
- 节点：每个子任务
- 边：子任务之间的依赖关系
- 通过DAG图可以清晰地看到哪些任务可以并行执行，哪些任务必须串行执行

在运行期，DAG图同时充当**路由表/依赖契约**：系统路由程序根据DAG中定义的"某输出文件应投递给哪些Agent"规则执行跨Agent投递（见PR-002/PR-024）。

为支持大任务的质量控制，**必须**在“命令投递到执行Agent之前”增加一个**DAG评审关口**：
- 规划者（如GM）先产出DAG与plan清单（plan_manifest）
- 将DAG提交给专家评审Agent进行打分与建议
- 评审通过后再一次性投递各执行命令（或放开执行Agent）
- 评审不通过则由规划者依据建议重新规划并重新提交评审

这样规划者可以在“DAG评审通过并完成首批投递”后退出运行期；若后续出现返工/重规划需求，可由规划者角色再次介入（见PR-022/PR-025）。

模板参考：
- `doc/rule/templates/task_dag.json`
- `doc/rule/templates/dag_review_request.cmd.json`
- `doc/rule/templates/dag_review_result.json`

### 命令文件

为每个Agent生成执行命令，包含：
- 任务描述
- 输入文件列表
- 输出文件要求
- 完成条件和标准

推荐做法：在Plan开始阶段一次性投递所有“命令消息”`cmd_*.msg.json`（envelope `type=command`）。依赖任务通过“等待输入 + 预定义输入”实现自动串联：

- 在 DAG v1.1 中使用 `inputs[] selector + pick_policy` 定义“逻辑输入如何选择/去歧义”（见 `doc/DAG/semantics.md`）。
- 在命令对象层（`payload.command`）中，仍可落为“具体的 required_inputs 文件清单”并设置 `wait_for_inputs=true`：
  - 若 GM/系统在投递命令时无法将 DAG 的 `inputs[]` 唯一解析为具体文件（例如多版本冲突、缺少 delivered_at/score），应触发 Human Gateway，**不要盲目投递执行命令**。
  - 输入到达后由 Agent 自动触发执行，无需 GM 持续调度。

由于DAG评审关口是强制环节：建议先仅投递“评审命令”给评审角色，待通过后再投递执行命令，避免错误DAG触发大量无效执行。

#### 命令与 DAG 的绑定（方案B，MVP 必须写死，避免分叉）

为了让“命令投递也由 DAG 驱动”可无歧义实现，统一以下绑定协议：

- 命令使用 message_envelope 运输：`cmd_*.msg.json`（`type=command`，`payload.command` 为具体命令对象）。
- `cmd_*.msg.json` 必须包含：`message_id`（链路唯一ID）以及可绑定字段（`plan_id`、`task_id`、`command_id`，以及推荐的 `idempotency_key`）。
- `payload.command.command_seq`（MVP 必须）：用于 Router 侧“旧命令丢弃”（SKIPPED_SUPERSEDED）；并且必须等于 `command_id` 最末尾序号（从右侧最后一个 `_` 之后解析）。
- `payload.command.dag_ref.sha256`（MVP 必须）：必须等于 `active_dag_ref.task_dag_sha256`，以保证 supersede/投递只在同一 DAG 版本内计算。
- 系统路由程序在投递命令时：
  1) 用命令消息的 `plan_id` 选择“当前阶段 DAG”（Meta-DAG 或 Business-DAG）
  2) 用 `payload.command.task_id` 定位到 DAG 的 `nodes[]`
  3) 以该节点的 `assigned_agent_id` 作为唯一投递目标，将命令消息投递到 `inbox/<plan_id>/`
- 命令消息不携带、也不允许携带“投递目标字段”；投递目标只能来自 DAG。
- 推荐命令携带 `dag_ref.sha256`（以及可选 `dag_ref.revision`）：
  - Router 投递前校验与当前 `task_dag.json` 一致，不一致则 DLQ + alert，避免“旧命令跑在新DAG上”。

## 关键特性

### LLM驱动

整个任务分配过程由LLM驱动：
- 理解任务意图
- 分析任务复杂度
- 进行合理分解
- 选择合适的Agent

### 任务独立性

每个子任务独立：
- 不同Agent负责不同的任务
- 避免任务重叠导致的冲突
- 减少Agent之间的协调成本

### 一层分配

只有一层任务分配：
- GM直接分配给执行Agent
- 不存在中间管理层
- 简化系统架构

### 依赖关系清晰

通过DAG图明确表达：
- 哪些任务可以并行
- 哪些任务有先后顺序
- 如何协调多个Agent的工作

## 工作示例

GM收到任务"开发一个电商网站"后：

1. 读取visibility_list，发现有产品经理、数据库专家、后端开发者、前端开发者等Agent
2. 通过LLM分析任务，分解为：需求分析、数据库设计、后端开发、前端开发
3. 为每个子任务分配合适的Agent：
   - 需求分析 → 产品经理
   - 数据库设计 → 数据库专家
   - 后端开发 → 后端开发者
   - 前端开发 → 前端开发者
4. 生成DAG图，表达依赖关系（如：后端开发依赖需求分析和数据库设计）
5. 生成命令文件（可一次性包含全部任务），放到outbox等待分配给各Agent；后续由系统路由程序按DAG路由表投递文件并触发依赖链

## 与其他原则的配合

### 与PR-001（inbox/outbox文件传递）配合

- 任务分配结果通过outbox发送
- 各Agent通过inbox接收分配的任务

### 与PR-007（统一的执行命令）配合

- 生成的命令文件遵循统一的执行命令格式
- 各Agent使用相同的命令处理机制

### 与PR-008（Agent文件夹结构）配合

- visibility_list文件夹是Agent文件夹结构的一部分
- 遵循统一的文件夹组织原则

## 关键要点

- **LLM驱动**: 通过LLM理解任务并智能分配
- **visibility_list**: 明确GM可以看到和分配的Agent
- **不重叠**: 每个子任务独立，避免冲突
- **一层分配**: 不递归，保持架构简单
- **DAG图**: 清晰表达任务依赖关系
- **可扩展**: 可以通过添加新的Agent描述文件来扩展系统

---

**最后更新**: 2025-01-08
