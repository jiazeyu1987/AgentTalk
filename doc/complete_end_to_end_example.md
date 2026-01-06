# AgentTalk 完整端到端示例：本地知识库展厅机器人

## 文档信息

- **文档名称**：完整端到端流程示例（Complete End-to-End Example）
- **版本**：v1.0
- **创建日期**：2025-01-06
- **示例项目**：带本地知识库的展厅机器人
- **目的**：通过一个完整案例展示系统从任务提交到最终交付的全过程

---

## 目录

1. [项目背景](#1-项目背景)
2. [Day 0: 用户提交任务](#2-day-0-用户提交任务)
3. [Day 0: 总经理接收任务](#3-day-0-总经理接收任务)
4. [Day 0: 召集规划会议](#4-day-0-召集规划会议)
5. [Day 0: 会议讨论与输入识别](#5-day-0-会议讨论与输入识别)
6. [Day 0: 生成输入需求清单](#6-day-0-生成输入需求清单)
7. [Day 0.5: 用户提供第一批输入](#7-day-05-用户提供第一批输入)
8. [Day 0.5: 总经理验证并分发](#8-day-05-总经理验证并分发)
9. [Day 1-2: 专家执行任务](#9-day-1-2-专家执行任务)
10. [Day 3: 用户提供第二批输入](#10-day-3-用户提供第二批输入)
11. [Day 3-5: 完成剩余任务](#11-day-3-5-完成剩余任务)
12. [Day 5: 最终交付](#12-day-5-最终交付)
13. [时间线总结](#13-时间线总结)

---

## 1. 项目背景

### 1.1 用户需求

**用户**：某科技公司的产品经理

**场景**：公司需要在一个科技展厅放置一个机器人，参观者可以向机器人提问，机器人基于公司的产品文档、技术手册等资料回答问题。

**需求描述**：
> "我想做一个带本地知识库的展厅机器人。参观者可以用自然语言提问，机器人基于本地的产品文档、技术手册等资料回答问题。需要有语音交互功能，能识别参观者的问题并语音回答。"

### 1.2 项目信息

- **项目类型**：AI应用开发
- **涉及技术**：自然语言处理、向量数据库、语音识别、语音合成
- **预计工期**：5个工作日
- **团队规模**：5-7个Agent

---

## 2. Day 0: 用户提交任务

### 2.1 创建任务文件

**时间**：2025-01-06 09:00

**操作**：用户在 `user_tasks/inbox/` 目录创建任务文件

**文件路径**：`user_tasks/inbox/task_20250106_090000.json`

**文件内容**：
```json
{
  "task_id": "user_task_001",
  "submitted_at": "2025-01-06T09:00:00Z",
  "submitted_by": "user",

  "title": "开发一个带本地知识库的展厅机器人",

  "description": "我想做一个带本地知识库的展厅机器人。参观者可以用自然语言提问，机器人基于本地的产品文档、技术手册等资料回答问题。需要有语音交互功能，能识别参观者的问题并语音回答。",

  "requirements": {
    "functional_requirements": [
      "用户可以通过语音或文字提问",
      "机器人基于本地知识库回答问题",
      "知识库包含产品文档、技术手册等资料",
      "回答要准确，并注明来源",
      "支持语音交互（语音识别+语音合成）"
    ],
    "non_functional_requirements": [
      "响应时间<3秒",
      "支持并发访问（多个参观者同时使用）",
      "知识库可以方便地更新和扩展"
    ]
  },

  "provided_inputs": {
    "description": "用户目前提供的材料",
    "files": []
  },

  "expected_outputs": {
    "description": "用户期望得到的产出",
    "deliverables": [
      "可运行的展厅机器人系统",
      "知识库构建工具",
      "部署文档",
      "使用手册"
    ]
  },

  "priority": "HIGH",
  "deadline": "2025-01-13T18:00:00Z"
}
```

### 2.2 任务文件结构

```
user_tasks/
└── inbox/
    └── task_20250106_090000.json  ✅ 用户创建
```

---

## 3. Day 0: 总经理接收任务

### 3.1 总经理轮询发现任务

**时间**：2025-01-06 09:00:10

**事件**：总经理Agent的轮询循环检测到新任务

**Agent内部处理**：
```python
# agent_001_general_manager 的执行循环
while True:
    # 1. 检查收件箱
    new_messages = check_inbox("agents/agent_001_general_manager/inbox/")

    # 2. 检查用户任务队列（GM特有）
    new_user_tasks = check_user_tasks("user_tasks/inbox/")

    if new_user_tasks:
        for task in new_user_tasks:
            process_user_task(task)

    sleep(10)
```

**发现任务**：
```json
{
  "detected_at": "2025-01-06T09:00:10Z",
  "task_file": "user_tasks/inbox/task_20250106_090000.json",
  "task_id": "user_task_001"
}
```

### 3.2 总经理分析任务

**时间**：2025-01-06 09:00:15

**总经理的LLM分析**：

```
【任务分析】

任务类型：AI应用开发
涉及领域：
  - 自然语言处理（NLP）
  - 向量数据库
  - 语音识别（ASR）
  - 语音合成（TTS）
  - Web开发（管理界面）

复杂度：中高
  - 需要多个专业领域协作
  - 需要技术方案设计
  - 需要集成多个第三方服务

预估需要的专家：
  1. 产品经理：需求分析
  2. 技术经理：技术架构设计
  3. NLP专家：问答系统实现
  4. 向量数据库专家：知识库实现
  5. 语音集成专家：ASR/TTS集成
  6. Python开发专家：后端开发
  7. 前端专家：管理界面

需要的层级：4层
  总经理 → 项目经理 → 技术经理 → 专家

决策：召集规划会议
```

### 3.3 总经理决定召集会议

**时间**：2025-01-06 09:00:30

**总经理创建会议邀请**：

**文件路径**：`agents/agent_002_project_manager/inbox/meeting_invitation_001.json`

**文件内容**：
```json
{
  "message_id": "msg_20250106_090030",
  "message_type": "MEETING_INVITATION",

  "from_agent": "agent_001_general_manager",
  "to_agent": ["agent_002_project_manager", "agent_003_tech_manager", "agent_004_product_manager"],

  "meeting_subject": "展厅机器人项目 - 规划会议",
  "meeting_agenda": [
    "1. 理解用户需求",
    "2. 识别所需的外部输入",
    "3. 确定技术方案",
    "4. 分解任务和分工",
    "5. 制定时间计划"
  ],

  "user_task_summary": {
    "task_id": "user_task_001",
    "title": "开发一个带本地知识库的展厅机器人",
    "description": "参观者可以用自然语言提问，机器人基于本地知识库回答，支持语音交互"
  },

  "deadline": "2025-01-06T12:00:00Z",
  "priority": "HIGH",

  "timestamp": "2025-01-06T09:00:30Z"
}
```

---

## 4. Day 0: 召集规划会议

### 4.1 会议邀请发送

**时间**：2025-01-06 09:00:30

**消息路由**：
```
总经理
  → 项目经理收件箱：agents/agent_002_project_manager/inbox/
  → 技术经理收件箱：agents/agent_003_tech_manager/inbox/
  → 产品经理收件箱：agents/agent_004_product_manager/inbox/
```

### 4.2 参与者收到邀请

**项目经理**（09:00:40，轮询时发现）：
```python
# agent_002_project_manager 的处理
message = {
  "message_type": "MEETING_INVITATION",
  "meeting_subject": "展厅机器人项目 - 规划会议",
  "from_agent": "agent_001_general_manager"
}

# 决定：接受邀请，准备输入
```

**技术经理**（09:00:45，轮询时发现）：
```python
# 接受邀请
```

**产品经理**（09:00:50，轮询时发现）：
```python
# 接受邀请
```

### 4.3 参与者准备输入

**项目经理准备**（09:01:00）：

**文件路径**：`system/meetings/meeting_001/inputs/pm_input.md`

**文件内容**：
```markdown
# 项目经理的会议输入

## 资源评估
当前可用的技术专家：
- NLP专家：agent_201，可用
- 向量数据库专家：agent_202，可用
- 语音集成专家：agent_203，可用
- Python开发专家：agent_204，可用
- 前端专家：agent_205，可用

## 时间预估
基于类似项目的经验：
- 需求分析：0.5天
- 技术设计：1天
- 开发实现：2-3天
- 测试优化：1天
- 总计：4.5-5.5天

## 风险识别
1. 语音识别的准确率可能影响体验
2. 本地知识库的检索准确度需要验证
3. 需要确认用户是否有现有的文档资料

## 建议
建议先明确用户提供的资料类型和数量，以便评估知识库构建工作量。
```

**技术经理准备**（09:01:10）：

**文件路径**：`system/meetings/meeting_001/inputs/tm_input.md`

**文件内容**：
```markdown
# 技术经理的会议输入

## 技术栈建议

### 1. 知识库方案
**推荐**：向量数据库 + 语义检索
- 向量数据库：ChromaDB或Faiss
- Embedding模型：OpenAI text-embedding-3-small 或 本地模型（all-MiniLM-L6-v2）
- 检索算法：向量相似度 + 重排序

### 2. 问答系统
**推荐**：RAG（Retrieval-Augmented Generation）
- LLM：Claude 3.5 Sonnet 或 GPT-4
- Prompt工程：优化回答质量
- 来源引用：确保答案可追溯

### 3. 语音交互
**推荐**：
- ASR（语音识别）：Whisper (OpenAI)
- TTS（语音合成）：Azure TTS 或 Google TTS
- 或者：使用百度语音、讯飞语音（国内方案）

### 4. 后端框架
**推荐**：Python + FastAPI
- 性能好，易于部署
- 支持异步处理
- API设计清晰

### 5. 前端界面
**推荐**：React + Ant Design
- 管理知识库
- 查看问答历史
- 系统监控

## 【需要用户提供的外部输入】

1. **knowledge_documents**：现有的知识文档
   - 来源：EXTERNAL（用户特定）
   - 紧急度：BLOCKING
   - 原因：需要知道文档的类型、数量、格式，才能设计知识库方案
   - 期望：产品手册、技术文档、FAQ等样本

2. **voice_service_provider**：语音服务提供商选择
   - 来源：EXTERNAL（业务决策）
   - 紧急度：BLOCKING
   - 原因：需要确定使用哪个语音服务（Whisper、百度、讯飞等）
   - 期望：明确使用哪个服务商，或预算限制

3. **deployment_environment**：部署环境信息
   - 来源：EXTERNAL（基础设施）
   - 紧急度：OPTIONAL
   - 原因：影响硬件配置和部署方案
   - 期望：云服务商、本地服务器、硬件配置

除了以上3项，其他技术细节（框架选择、架构设计）我可以用我的内部知识处理。
```

**产品经理准备**（09:01:20）：

**文件路径**：`system/meetings/meeting_001/inputs/product_input.md`

**文件内容**：
```markdown
# 产品经理的会议输入

## 需求理解

### 核心功能
1. **知识问答**
   - 用户：语音或文字提问
   - 系统：基于本地知识库检索相关文档
   - 产出：准确的答案 + 来源引用

2. **知识库管理**
   - 上传文档（PDF、TXT、MD）
   - 文档解析和向量化
   - 知识库更新

3. **管理界面**
   - 查看问答历史
   - 评估回答质量
   - 系统配置

### 用户场景
- **主要用户**：展厅参观者
- **使用场景**：在展厅现场，向机器人提问公司产品相关问题
- **关键指标**：回答准确率、响应速度、用户体验

### 【需要用户提供的外部输入】

1. **user_personas**：目标用户画像
   - 来源：EXTERNAL（业务特定）
   - 紧急度：OPTIONAL
   - 原因：了解参观者的背景，优化问答策略
   - 期望：参观者的专业程度、主要关注点

2. **success_criteria**：成功标准定义
   - 来源：EXTERNAL（业务目标）
   - 紧急度：BLOCKING
   - 原因：需要明确什么样的回答算是"好的回答"
   - 期望：回答准确率目标（如≥90%）、响应时间要求（如<3秒）

3. **use_cases**：典型使用场景
   - 来源：EXTERNAL（业务特定）
   - 紧急度：OPTIONAL
   - 原因：了解常见问题类型
   - 期望：参观者通常会问哪些问题

除了以上3项，我可以基于行业最佳实践设计产品方案。
```

---

## 5. Day 0: 会议讨论与输入识别

### 5.1 会议开始

**时间**：2025-01-06 09:05:00

**会议协调器收集所有输入**：
```
收集到的输入：
  ✅ 项目经理输入（pm_input.md）
  ✅ 技术经理输入（tm_input.md）
  ✅ 产品经理输入（product_input.md）
```

### 5.2 LLM多轮对话

**第1轮 - 总经理**（09:05:10）：
```
各位，收到一个新任务："开发一个带本地知识库的展厅机器人"。

用户需求：
- 参观者可以用自然语言提问
- 机器人基于本地知识库回答
- 支持语音交互（语音识别+语音合成）

请各位从自己的角度分析：
1. 这个任务需要哪些专家？
2. 技术方案有什么建议？
3. **关键：需要用户提供哪些外部输入？**

请开始讨论。
```

**第2轮 - 产品经理**（09:05:30，LLM生成）：
```
从产品角度，我认为：

【核心功能】
1. 知识问答系统
2. 知识库管理工具
3. 管理界面（查看历史、配置系统）

【用户体验】
- 参观者可能不懂技术，提问很随意
- 需要支持模糊问题（如："这个产品怎么样？"）
- 回答要准确，并说明来源（如："根据《产品手册》第3页..."）

【需要用户提供的外部输入】

1. knowledge_documents：现有的知识文档样本
   - 来源：EXTERNAL（项目特定）
   - 紧急度：BLOCKING
   - 期望格式：PDF、TXT或Markdown
   - 验证标准：至少包含5篇文档（产品手册、技术文档等）
   - 原因：需要分析文档类型、内容结构，才能设计问答策略

2. success_criteria：成功标准
   - 来源：EXTERNAL（业务目标）
   - 紧急度：BLOCKING
   - 期望格式：Markdown or Text
   - 验证标准：
     * 包含回答准确率目标（如≥90%）
     * 包含响应时间要求（如<3秒）
   - 原因：需要明确项目目标，才能设计方案

3. typical_questions：典型问题列表
   - 来源：EXTERNAL（业务场景）
   - 紧急度：OPTIONAL
   - 期望格式：List or Markdown
   - 验证标准：至少包含10个常见问题
   - 原因：了解参观者通常会问什么，优化知识库

4. user_profile：参观者背景
   - 来源：EXTERNAL（业务特定）
   - 紧急度：OPTIONAL
   - 期望格式：Text description
   - 验证标准：说明参观者的专业程度
   - 原因：专业观众和普通观众的问题风格不同

除了以上4项，产品需求分析、功能设计我可以用我的内部知识完成。
```

**第3轮 - 技术经理**（09:06:00，LLM生成）：
```
从技术角度，我认为：

【技术方案】
1. **知识库**：向量数据库（ChromaDB）+ Embedding
2. **问答系统**：RAG架构（检索+生成）
3. **语音交互**：
   - ASR：Whisper（OpenAI）或百度语音
   - TTS：Azure TTS或讯飞语音
4. **后端**：Python + FastAPI
5. **前端**：React + Ant Design（管理界面）

【需要的专家】
- NLP专家：RAG系统实现
- 向量数据库专家：知识库构建
- 语音集成专家：ASR/TTS集成
- Python开发专家：后端开发
- 前端专家：管理界面

【需要用户提供的外部输入】

5. knowledge_documents：现有的知识文档
   - 来源：EXTERNAL（项目特定）
   - 紧急度：BLOCKING
   - 期望格式：PDF、TXT、Markdown
   - 验证标准：
     * 至少5篇文档
     * 文档内容清晰、结构化
     * 包含产品相关信息
   - 原因：必须基于真实文档设计知识库，不能虚构

6. voice_service_provider：语音服务选择
   - 来源：EXTERNAL（业务决策）
   - 紧急度：BLOCKING
   - 期望格式：Text or JSON
   - 验证标准：
     * 明确使用哪个服务商（Whisper、百度、讯飞）
     * 或提供预算限制（如："优先免费方案"）
   - 原因：不同服务商的API不同，必须提前确定

7. voice_service_credentials：语音服务凭证（如果需要）
   - 来源：EXTERNAL（第三方凭证）
   - 紧急度：BLOCKING
   - 期望格式：JSON
   - 验证标准：
     * 包含API Key或密钥
     * 包含AppID（如需要）
   - 原因：必须从服务商处获取，无法生成
   - 注意：如果使用本地方案（如本地Whisper），则不需要

8. deployment_environment：部署环境信息
   - 来源：EXTERNAL（基础设施）
   - 紧急度：OPTIONAL
   - 期望格式：Text or JSON
   - 验证标准：
     * 部署位置（云服务器、本地）
     * 硬件配置（CPU、内存、GPU）
   - 原因：影响性能优化和部署方案
   - 如果不提供：使用默认方案（云服务器，4核8G）

9. llm_provider_choice：LLM服务商选择
   - 来源：EXTERNAL（业务决策）
   - 紧急度：BLOCKING
   - 期望格式：Text
   - 验证标准：
     * 明确使用Claude、GPT、或本地模型
     * 或说明预算和性能要求
   - 原因：不同LLM的API和成本不同

除了以上5项，技术架构、代码实现我可以用我的内部知识完成。
```

**第4轮 - 项目经理**（09:06:30，LLM生成）：
```
从项目管理的角度：

【时间规划】
基于各位的方案，预估时间：
- Day 0.5：需求明确 + 技术设计
- Day 1-2：知识库构建 + RAG系统
- Day 3：语音集成
- Day 4：前端管理界面
- Day 5：测试优化 + 部署

总计：5天（符合用户deadline）

【需要的专家确认】
✅ NLP专家：可用
✅ 向量数据库专家：可用
✅ 语音集成专家：可用
✅ Python开发专家：可用
✅ 前端专家：可用

【风险】
⚠️ 知识库质量取决于文档质量，建议用户提供高质量文档
⚠️ 语音识别准确率可能影响体验，建议准备备选方案

【需要用户提供的外部输入】

10. milestone_checkpoints：里程碑检查点
    - 来源：EXTERNAL（项目管理偏好）
    - 紧急度：OPTIONAL
    - 期望格式：Text or List
    - 验证标准：说明希望在哪些节点检查进度
    - 原因：了解用户的沟通偏好

除了以上1项，项目规划、进度管理我可以用我的内部知识完成。
```

**第5轮 - 总经理**（09:07:00，LLM生成）：
```
感谢各位的详细分析！

让我汇总一下大家的意见：

【技术方案共识】
- 知识库：ChromaDB + Embedding
- 问答：RAG架构
- 语音：Whisper（ASR）+ Azure TTS（TTS）
- 后端：Python + FastAPI
- 前端：React + Ant Design

【需要的专家】
1. 产品经理：需求分析和功能设计
2. 技术经理：架构设计和技术方案
3. NLP专家：RAG系统实现
4. 向量数据库专家：知识库构建
5. 语音集成专家：ASR/TTS集成
6. Python开发专家：后端开发
7. 前端专家：管理界面

【需要用户提供的外部输入 - 汇总】

🔴 BLOCKING（必须提供）- 6项：

1. knowledge_documents（知识文档）
   - 需要方：产品经理、技术经理、向量数据库专家
   - 格式：PDF/TXT/MD，至少5篇
   - 原因：必须基于真实文档设计知识库

2. success_criteria（成功标准）
   - 需要方：产品经理
   - 格式：Markdown，包含准确率和响应时间目标
   - 原因：明确项目目标

3. voice_service_provider（语音服务商选择）
   - 需要方：技术经理、语音集成专家
   - 格式：Text，明确使用Whisper、百度或讯飞
   - 原因：决定集成方案

4. voice_service_credentials（语音服务凭证）
   - 需要方：语音集成专家
   - 格式：JSON（API Key、AppID等）
   - 原因：第三方凭证，无法生成

5. llm_provider_choice（LLM服务商选择）
   - 需要方：技术经理、NLP专家
   - 格式：Text，明确使用Claude、GPT或本地模型
   - 原因：决定RAG系统的LLM

🟡 OPTIONAL（可选提供）- 4项：

6. typical_questions（典型问题列表）
   - 需要方：产品经理、NLP专家
   - 格式：List，至少10个问题
   - 原因：优化知识库和问答策略

7. user_profile（参观者背景）
   - 需要方：产品经理
   - 格式：Text
   - 原因：调整问答风格

8. deployment_environment（部署环境）
   - 需要方：技术经理、Python开发专家
   - 格式：Text或JSON
   - 原因：优化部署方案

9. milestone_checkpoints（里程碑检查点）
   - 需要方：项目经理
   - 格式：Text或List
   - 原因：了解沟通偏好

【下一步】
我将生成详细的用户输入需求清单文档，并等待用户准备材料。

各位先准备技术方案，等用户材料到位后立即开始执行。

同意这个方案的请回复。
```

**第6轮 - 参与者确认**（09:07:30）：
```
项目经理：✅ 同意

技术经理：✅ 同意

产品经理：✅ 同意
```

### 5.3 会议结束

**时间**：2025-01-06 09:08:00

**会议协调器生成会议纪要**：

**文件路径**：`system/meetings/meeting_001/meeting_minutes.md`

**文件内容**：
```markdown
# 展厅机器人项目 - 规划会议纪要

**会议时间**：2025-01-06 09:05 - 09:08
**会议ID**：meeting_001
**参会者**：总经理、项目经理、技术经理、产品经理
**会议结果**：✅ APPROVED

---

## 会议结论

### 技术方案
- 知识库：ChromaDB + Embedding
- 问答系统：RAG架构
- 语音交互：Whisper（ASR）+ Azure TTS（TTS）
- 后端：Python + FastAPI
- 前端：React + Ant Design

### 团队组成
1. 产品经理（agent_004）
2. 技术经理（agent_003）
3. NLP专家（agent_201）
4. 向量数据库专家（agent_202）
5. 语音集成专家（agent_203）
6. Python开发专家（agent_204）
7. 前端专家（agent_205）

### 时间计划
- Day 0.5：需求明确 + 技术设计
- Day 1-2：知识库构建 + RAG系统
- Day 3：语音集成
- Day 4：前端管理界面
- Day 5：测试优化 + 部署

### 需要用户提供的输入

🔴 **必须提供**（6项）：
1. knowledge_documents - 知识文档样本
2. success_criteria - 成功标准
3. voice_service_provider - 语音服务商选择
4. voice_service_credentials - 语音服务凭证
5. llm_provider_choice - LLM服务商选择

🟡 **可选提供**（4项）：
6. typical_questions - 典型问题列表
7. user_profile - 参观者背景
8. deployment_environment - 部署环境信息
9. milestone_checkpoints - 里程碑检查点

详细需求见：user_inputs/meeting_001/REQUIRED_INPUTS.md

---

**生成时间**：2025-01-06 09:08:00
```

---

## 6. Day 0: 生成输入需求清单

### 6.1 总经理生成用户需求文档

**时间**：2025-01-06 09:08:30

**文件路径**：`user_inputs/meeting_001/REQUIRED_INPUTS.md`

**文件内容**：
```markdown
# 🤖 展厅机器人项目 - 输入材料需求清单

**会议时间**：2025-01-06 09:05
**会议ID**：meeting_001
**项目名称**：带本地知识库的展厅机器人
**状态**：⏳ 等待您提供材料

**预计准备时间**：30分钟 - 2小时
**预计项目启动时间**：收到必须材料后10分钟内
**预计项目完成时间**：5个工作日

---

## 📋 材料需求清单

### 🔴 必须提供（BLOCKING）- 5项

以下材料是完成任务必需的，请尽快提供：

---

#### 1. knowledge_documents（知识文档样本）

**为什么需要**：
产品经理、技术经理和向量数据库专家需要分析您的文档类型、内容结构和信息密度，才能设计合适的知识库方案和问答策略。

**需要什么**：
- 提供您计划导入知识库的文档样本
- 至少5篇文档（可以是产品手册、技术文档、FAQ等）
- 文档格式：PDF、TXT或Markdown
- 文档内容：包含公司产品或服务的相关信息

**期望格式**：
- 单个PDF文件（多篇文档合并）或
- 多个文件（PDF/TXT/MD）打包成ZIP或
- 放置在单独的文件夹中

**验证标准**：
- ✅ 至少包含5篇文档
- ✅ 文档内容清晰、结构化
- ✅ 包含产品相关信息（功能、参数、使用方法等）
- ✅ 文档语言：中文或英文

**示例文档类型**：
- ✅ 产品手册（产品功能介绍、使用指南）
- ✅ 技术文档（技术规格、API文档）
- ✅ FAQ（常见问题解答）
- ✅ 培训材料（用户培训、操作指南）
- ✅ 营销材料（产品介绍、宣传册）

**如果文档很多**：
- 可以先提供5-10篇代表性文档
- 系统会基于样本设计方案
- 后续可以添加更多文档

**将用于**：
- task_002: 需求分析（产品经理）
- task_003: 技术架构设计（技术经理）
- task_005: 知识库构建（向量数据库专家）

---

#### 2. success_criteria（成功标准）

**为什么需要**：
产品经理需要明确项目的目标和验收标准，才能设计合适的评估方法。

**需要什么**：
明确说明项目的成功标准，包括：
- 回答准确率目标（如：90%的问题能准确回答）
- 响应时间要求（如：3秒内给出答案）
- 并发支持（如：支持5个参观者同时使用）
- 其他关键指标

**期望格式**：
- Markdown文档
- 或JSON格式的指标定义

**验证标准**：
- ✅ 包含回答准确率目标（建议≥85%）
- ✅ 包含响应时间要求（建议<5秒）
- ✅ 明确至少3个关键指标

**示例**：
```markdown
# 成功标准

1. 回答准确率：≥90%
   - 定义：答案能解决用户问题的比例
   - 测试方法：使用100个典型问题测试

2. 响应时间：<3秒
   - 定义：从提问到显示答案的时间
   - 测试方法：测量100次问答的平均响应时间

3. 并发支持：≥5人
   - 定义：同时使用系统的参观者数量
   - 测试方法：模拟5个用户同时提问

4. 来源引用：100%
   - 定义：每个答案都要说明来源文档
   - 测试方法：检查所有答案是否包含引用
```

**如果不确定**：
可以提供行业基准（如："参考同类产品的标准"），系统会使用最佳实践。

**将用于**：
- task_002: 需求分析和成功标准定义（产品经理）

---

#### 3. voice_service_provider（语音服务商选择）

**为什么需要**：
技术经理和语音集成专家需要确定使用哪个语音服务，才能设计集成方案。

**需要什么**：
明确说明您希望使用哪个语音服务商。

**期望格式**：
- 简短文本说明
- 或JSON格式

**验证标准**：
- ✅ 明确选择一个服务商或方案

**可选方案对比**：

| 方案 | ASR（语音识别） | TTS（语音合成） | 成本 | 优点 | 缺点 |
|------|----------------|----------------|------|------|------|
| **OpenAI Whisper** | ✅ | ❌（需另选） | 低 | 准确率高，支持多语言 | 需要API访问（可能有网络问题） |
| **百度语音** | ✅ | ✅ | 低 | 中文识别好，国内稳定 | 需要申请账号 |
| **讯飞语音** | ✅ | ✅ | 中 | 中文语音自然 | 需要申请账号 |
| **Azure TTS** | ❌（需另选） | ✅ | 中 | 语音质量高 | 价格较高 |
| **本地方案** | 本地Whisper | 本地TTS | 0成本 | 无需网络，隐私安全 | 准确率略低，需要GPU |

**推荐方案**：
- **如果预算有限**：本地Whisper + 本地TTS（免费，但需要GPU）
- **如果追求准确率**：OpenAI Whisper + Azure TTS（成本适中）
- **如果需要国内稳定**：百度语音全套（申请简单，价格低）

**示例回答**：
```
文本格式：
"使用百度语音（ASR + TTS全套），因为在国内稳定且价格合理"

或

JSON格式：
{
  "asr_provider": "baidu",
  "tts_provider": "baidu",
  "reason": "国内稳定，价格合理"
}
```

**将用于**：
- task_003: 技术架构设计（技术经理）
- task_007: 语音功能集成（语音集成专家）

---

#### 4. voice_service_credentials（语音服务凭证）

**为什么需要**：
语音集成专家需要真实的API凭证才能集成语音功能。

**需要什么**：
语音服务提供商的应用凭证。

**期望格式**：
- JSON文件

**验证标准**：
- ✅ 包含API Key或密钥
- ✅ 包含AppID（如需要）
- ✅ 包含Secret Key（如需要）

**不同服务商的凭证格式**：

**百度语音**：
```json
{
  "api_key": "您的API Key",
  "secret_key": "您的Secret Key",
  "app_id": "您的AppID"
}
```

**讯飞语音**：
```json
{
  "app_id": "您的AppID",
  "api_key": "您的API Key",
  "api_secret": "您的APISecret"
}
```

**OpenAI Whisper**：
```json
{
  "openai_api_key": "您的OpenAI API Key"
}
```

**本地方案**：
如果选择本地Whisper，**不需要**此凭证文件。请在`voice_service_provider`中明确说明"使用本地方案"。

**如何获取**：
1. 注册对应服务商的开发者账号
2. 创建应用/项目
3. 获取API Key、AppID等凭证
4. 将凭证信息填入JSON文件

**注意事项**：
- ⚠️ 凭证是敏感信息，请妥善保管
- ⚠️ 不要泄露给他人
- ✅ 系统会将凭证文件加密存储

**将用于**：
- task_007: 语音功能集成（语音集成专家）

---

#### 5. llm_provider_choice（LLM服务商选择）

**为什么需要**：
技术经理和NLP专家需要确定使用哪个LLM（大语言模型），才能设计RAG问答系统。

**需要什么**：
明确说明您希望使用哪个LLM服务商。

**期望格式**：
- 简短文本说明
- 或JSON格式

**验证标准**：
- ✅ 明确选择一个LLM服务商

**可选方案对比**：

| 方案 | 成本 | 速度 | 准确率 | 优点 | 缺点 |
|------|------|------|--------|------|------|
| **Claude 3.5 Sonnet** | 中 | 快 | 高 | 准确率高，支持长文本 | 需要API访问 |
| **GPT-4** | 高 | 中 | 高 | 综合能力强 | 成本较高 |
| **GPT-3.5 Turbo** | 低 | 快 | 中 | 速度快，成本低 | 准确率略低 |
| **本地模型（Llama 2）** | 0成本 | 慢 | 中 | 无需网络，隐私安全 | 需要GPU，准确率较低 |

**推荐方案**：
- **如果追求准确率**：Claude 3.5 Sonnet（推荐）
- **如果预算有限**：GPT-3.5 Turbo
- **如果需要离线**：本地Llama 2（需要GPU）

**示例回答**：
```
文本格式：
"使用Claude 3.5 Sonnet，因为准确率高且成本合理"

或

JSON格式：
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "reason": "准确率高，成本合理"
}
```

**如果选择需要API的方案**：
还需要提供LLM API凭证：

```json
{
  "anthropic_api_key": "您的Anthropic API Key"
}
```

**将用于**：
- task_003: 技术架构设计（技术经理）
- task_006: RAG问答系统实现（NLP专家）

---

### 🟡 可选提供（OPTIONAL）- 4项

以下材料是可选的，如果不提供，系统会使用最佳实践或默认方案：

---

#### 6. typical_questions（典型问题列表）

**为什么需要**：
产品经理和NLP专家可以基于常见问题优化知识库和问答策略。

**需要什么**：
列出参观者可能会问的典型问题。

**期望格式**：
- Markdown列表
- 或JSON数组
- 或TXT文件（每行一个问题）

**验证标准**：
- ✅ 至少包含10个问题
- ✅ 问题与产品/服务相关

**示例**：
```markdown
# 典型问题列表

1. 这个产品的主要功能是什么？
2. 这个产品和竞品相比有什么优势？
3. 产品的价格是多少？
4. 如何购买这个产品？
5. 产品有保修吗？保修期多长？
6. 这个产品适合哪些人群？
7. 产品的技术参数是什么？
8. 如何联系技术支持？
9. 有培训课程吗？
10. 产品有移动端版本吗？
```

**如果无法提供**：
系统会基于文档自动生成候选问题。

**将用于**：
- task_002: 需求分析（产品经理）
- task_006: RAG系统优化（NLP专家）

---

#### 7. user_profile（参观者背景）

**为什么需要**：
产品经理可以了解参观者的专业程度，调整问答的风格和复杂度。

**需要什么**：
说明参观者的背景特征。

**期望格式**：
- 简短文本描述

**示例**：
```
"参观者主要是潜在客户，背景多样：
- 50%是技术决策者（CTO、技术总监）
- 30%是业务决策者（CEO、产品经理）
- 20%是普通用户

技术决策者关注技术细节，业务决策者关注商业价值。"
```

**如果无法提供**：
系统会使用通用策略（平衡专业术语和通俗解释）。

**将用于**：
- task_002: 需求分析和用户画像（产品经理）

---

#### 8. deployment_environment（部署环境信息）

**为什么需要**：
技术经理和Python开发专家可以优化部署方案和性能配置。

**需要什么**：
说明系统部署的位置和硬件配置。

**期望格式**：
- 文本描述
- 或JSON格式

**示例**：
```json
{
  "deployment_type": "cloud",
  "provider": "aliyun",
  "server_spec": {
    "cpu": "4核",
    "memory": "8GB",
    "storage": "100GB SSD"
  }
}
```

**如果无法提供**：
系统使用默认方案（云服务器，4核8G内存）。

**将用于**：
- task_003: 技术架构设计（技术经理）
- task_008: 系统部署（Python开发专家）

---

#### 9. milestone_checkpoints（里程碑检查点）

**为什么需要**：
项目经理可以了解您希望在哪些节点检查进度。

**需要什么**：
说明您希望在项目的哪些节点进行检查和确认。

**期望格式**：
- 文本列表
- 或JSON数组

**示例**：
```markdown
# 里程碑检查点

1. Day 1: 知识库原型完成
   - 检查内容：知识库能否正确检索文档
   - 确认后继续

2. Day 3: 问答系统原型完成
   - 检查内容：问答功能是否正常
   - 确认后继续

3. Day 5: 系统上线前
   - 检查内容：整体功能和性能
   - 确认后部署
```

**如果无法提供**：
项目经理会按照标准流程在关键节点向您报告。

**将用于**：
- task_001: 项目规划（项目经理）

---

## 📊 需求汇总

| 类型 | 数量 | 预估准备时间 |
|------|------|-------------|
| 🔴 必须提供 | 5项 | 30分钟 - 2小时 |
| 🟡 可选提供 | 4项 | 10-30分钟 |

**总计准备时间**：30分钟 - 2.5小时

---

## 🚀 下一步操作

### 方案A：一次性提供（推荐）

如果您现在或今天内能准备好所有材料：

1. **创建目录**：
   ```bash
   mkdir -p user_inputs/meeting_001
   ```

2. **放置文件**：
   ```bash
   # 必须材料
   cp knowledge_documents.zip user_inputs/meeting_001/
   cp success_criteria.md user_inputs/meeting_001/
   cp voice_service_provider.txt user_inputs/meeting_001/
   cp voice_service_credentials.json user_inputs/meeting_001/
   cp llm_provider_choice.txt user_inputs/meeting_001/

   # 可选材料（如果有）
   cp typical_questions.md user_inputs/meeting_001/
   cp user_profile.txt user_inputs/meeting_001/
   ```

3. **等待系统验证**（约1分钟）

4. **查看验证报告**：
   ```bash
   cat user_inputs/meeting_001/validation_report.md
   ```

5. **任务启动**：验证通过后10分钟内开始执行

**优势**：任务连续执行，不被打断

---

### 方案B：分批提供

如果您需要时间准备（如：语音服务凭证需要申请）：

**第一批**（现在提供）：
- knowledge_documents（知识文档）✅
- success_criteria（成功标准）✅
- llm_provider_choice（LLM选择）✅

**系统响应**：
- 产品经理：开始需求分析 ✅
- 技术经理：开始架构设计 ✅
- NLP专家：⏳ 等待技术方案

**第二批**（2天后提供）：
- voice_service_provider（语音服务商）✅
- voice_service_credentials（语音凭证）✅

**系统响应**：
- 语音集成专家：开始集成工作 ✅

---

### 方案C：无法提供某些材料

如果某些材料确实无法提供：

1. **告知系统**：
   ```bash
   cat > user_inputs/meeting_001/voice_service_credentials_NOT_AVAILABLE.md <<EOF
   # 语音服务凭证暂时无法提供

   ## 原因
   正在申请百度语音账号，预计3天后获批。

   ## 建议
   是否可以先用本地Whisper进行开发？待账号获批后再切换。
   EOF
   ```

2. **系统响应**：
   - 总经理收到说明
   - 组织专家讨论替代方案
   - 可能决策：使用本地Whisper开发，后期切换

---

## 💬 常见问题

**Q1：我不懂JSON格式，怎么办？**

A：所有文件都支持文本格式。例如：
```
voice_service_provider.txt:
"使用百度语音全套"

success_criteria.md:
```
# 成功标准

1. 回答准确率：≥90%
2. 响应时间：<3秒
3. 并发支持：≥5人
```
```

---

**Q2：我的文档很多，都要提供吗？**

A：不需要全部。先提供5-10篇代表性文档：
- 不同的文档类型（产品手册、技术文档、FAQ）
- 不同的产品线（如果有多个产品）
- 系统会基于样本设计，后续可以添加更多

---

**Q3：我没有语音服务凭证，怎么办？**

A：两个选择：
1. **申请免费账号**：百度语音、讯飞语音都有免费额度
2. **使用本地方案**：选择"本地Whisper"，无需凭证，但需要GPU

---

**Q4：LLM服务商怎么选择？**

A：推荐标准：
- **预算充足**：Claude 3.5 Sonnet（准确率最高）
- **预算有限**：GPT-3.5 Turbo（性价比高）
- **需要离线**：本地Llama 2（免费，但需要GPU）

如果不确定，可以选择："使用Claude 3.5 Sonnet"

---

**Q5：我可以边做边补充吗？**

A：可以！
- 必须材料（BLOCKING）最好先提供，否则任务无法开始
- 可选材料（OPTIONAL）可以随时补充
- 如果任务已经开始，补充材料后会自动更新相关部分

---

## 📞 如何联系我们

如果您对材料需求有任何疑问：

**方式1**：在`user_inputs/meeting_001/`中放置问题文件
```bash
cat > user_inputs/meeting_001/questions.md <<EOF
# 我的问题

1. 我的文档格式是Word，可以吗？
2. success_criteria应该怎么写？
EOF
```

**方式2**：提供部分信息，让专家分析
- 哪怕不完整，也可以先提供
- 专家会分析并给出建议

---

## ⏰ 时间节点

- **现在**：查看此需求清单
- **准备阶段**：30分钟 - 2.5小时
- **提交材料**：准备好后复制到指定目录
- **系统验证**：提交后1分钟内
- **任务启动**：验证通过后10分钟内
- **项目完成**：启动后5个工作日

---

**文档生成时间**：2025-01-06 09:08:30
**文档版本**：v1.0
**状态**：⏳ 等待您的材料
```

### 6.2 创建提交状态文件

**时间**：2025-01-06 09:08:30

**文件路径**：`user_inputs/meeting_001/submission_status.json`

**文件内容**：
```json
{
  "meeting_id": "meeting_001",
  "project_name": "展厅机器人",
  "created_at": "2025-01-06T09:08:30Z",
  "last_updated": "2025-01-06T09:08:30Z",
  "status": "WAITING_FOR_USER",

  "inputs": {
    "knowledge_documents": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    },
    "success_criteria": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    },
    "voice_service_provider": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    },
    "voice_service_credentials": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    },
    "llm_provider_choice": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    },
    "typical_questions": {
      "status": "NOT_RECEIVED",
      "urgency": "OPTIONAL",
      "submitted_at": null,
      "validated": false
    },
    "user_profile": {
      "status": "NOT_RECEIVED",
      "urgency": "OPTIONAL",
      "submitted_at": null,
      "validated": false
    },
    "deployment_environment": {
      "status": "NOT_RECEIVED",
      "urgency": "OPTIONAL",
      "submitted_at": null,
      "validated": false
    },
    "milestone_checkpoints": {
      "status": "NOT_RECEIVED",
      "urgency": "OPTIONAL",
      "submitted_at": null,
      "validated": false
    }
  },

  "summary": {
    "total_inputs": 9,
    "blocking_received": 0,
    "blocking_required": 5,
    "optional_received": 0,
    "optional_required": 4
  },

  "next_actions": [
    "请提供5项BLOCKING级别的输入",
    "或先提供部分输入，系统会启动可以执行的任务",
    "如有疑问，在user_inputs/meeting_001/中放置questions.md"
  ]
}
```

---

## 7. Day 0.5: 用户提供第一批输入

### 7.1 用户准备材料

**时间**：2025-01-06 10:00（会议结束后约1小时）

**用户操作**：

```bash
# 1. 查看需求清单
cat user_inputs/meeting_001/REQUIRED_INPUTS.md

# 2. 准备材料

# 2.1 知识文档样本（用户从公司文档库中找到的）
mkdir -p ~/kb_docs_sample
cp ~/公司文档/产品手册.pdf ~/kb_docs_sample/
cp ~/公司文档/技术规格.pdf ~/kb_docs_sample/
cp ~/公司文档/FAQ.pdf ~/kb_docs_sample/
cp ~/公司文档/安装指南.pdf ~/kb_docs_sample/
cp ~/公司文档/维护手册.pdf ~/kb_docs_sample/

# 打包
cd ~/kb_docs_sample
zip -r knowledge_documents.zip *.pdf

# 2.2 成功标准
cat > ~/success_criteria.md <<EOF
# 展厅机器人项目成功标准

## 核心指标

1. 回答准确率：≥90%
   - 定义：使用100个测试问题，至少90个能准确回答
   - 测试问题类型：产品功能、技术参数、使用方法等

2. 响应时间：<3秒
   - 定义：从用户提问到显示完整答案的时间
   - 测试方法：测量100次问答，计算平均响应时间

3. 并发支持：≥5人
   - 定义：支持5个参观者同时使用，体验不下降
   - 测试方法：模拟5个并发用户提问

4. 来源引用：100%
   - 定义：每个答案都要标注信息来源（如："根据《产品手册》第X页"）
   - 验证方法：检查所有答案是否包含引用

5. 语音识别准确率：≥85%
   - 定义：语音转文字的准确率
   - 测试方法：朗读50个问题，检查识别准确率

## 次要指标

6. 知识库覆盖率：
   - 至少覆盖文档中80%的信息
   - 验证方法：人工检查常见问题能否找到答案

7. 用户体验：
   - 参观者满意度≥4.0/5.0
   - 验证方法：现场调研10位参观者
EOF

# 2.3 LLM选择
cat > ~/llm_provider_choice.txt <<EOF
使用Claude 3.5 Sonnet

原因：
1. 准确率高，适合专业场景
2. 支持长文本，可以处理复杂文档
3. 成本合理（相比GPT-4）
EOF

# 3. 复制到系统目录
cp ~/kb_docs_sample/knowledge_documents.zip user_inputs/meeting_001/
cp ~/success_criteria.md user_inputs/meeting_001/
cp ~/llm_provider_choice.txt user_inputs/meeting_001/

# 4. 查看状态
ls -lh user_inputs/meeting_001/
```

**目录内容**：
```
user_inputs/meeting_001/
├── REQUIRED_INPUTS.md                # 系统生成的需求清单
├── submission_status.json            # 提交状态
├── knowledge_documents.zip           ✅ 新提交
├── success_criteria.md               ✅ 新提交
└── llm_provider_choice.txt           ✅ 新提交
```

---

### 7.2 文件监控系统检测

**时间**：2025-01-06 10:00:10

**事件**：文件监控系统检测到3个新文件

**监控日志**：
```json
{
  "timestamp": "2025-01-06T10:00:10Z",
  "event": "new_files_detected",
  "meeting_id": "meeting_001",
  "files": [
    "knowledge_documents.zip",
    "success_criteria.md",
    "llm_provider_choice.txt"
  ]
}
```

**通知总经理**：
```json
{
  "message_type": "NEW_USER_INPUT",
  "from_agent": "system",
  "to_agent": "agent_001_general_manager",
  "meeting_id": "meeting_001",
  "files": [
    {
      "file_name": "knowledge_documents.zip",
      "file_path": "user_inputs/meeting_001/knowledge_documents.zip"
    },
    {
      "file_name": "success_criteria.md",
      "file_path": "user_inputs/meeting_001/success_criteria.md"
    },
    {
      "file_name": "llm_provider_choice.txt",
      "file_path": "user_inputs/meeting_001/llm_provider_choice.txt"
    }
  ]
}
```

---

## 8. Day 0.5: 总经理验证并分发

### 8.1 总经理验证输入

**时间**：2025-01-06 10:00:20

**总经理的处理流程**：

```python
# 总经理的验证逻辑
class GeneralManager:
    def handle_user_inputs(self, meeting_id, input_files):
        # 1. 加载需求清单
        requirements = self.load_input_requirements(meeting_id)

        # 2. 验证每个文件
        validation_results = []
        for file in input_files:
            req = find_requirement(requirements, file)
            result = self.validate_input(file, req)
            validation_results.append(result)

        # 3. 检查BLOCKING输入
        blocking_received = ["knowledge_documents", "success_criteria", "llm_provider_choice"]
        blocking_required = ["knowledge_documents", "success_criteria", "voice_service_provider", "voice_service_credentials", "llm_provider_choice"]

        missing_blocking = set(blocking_required) - set(blocking_received)
        # = {"voice_service_provider", "voice_service_credentials"}

        # 4. 决策：部分启动
        if missing_blocking:
            return {
                "status": "PARTIAL_INPUTS",
                "missing_blocking": list(missing_blocking),
                "can_start": ["product_manager", "tech_manager"],
                "must_wait": ["voice_integration_expert"]
            }
```

**验证结果**：

```json
{
  "validation_report": {
    "knowledge_documents.zip": {
      "valid": true,
      "checks": {
        "format": "✅ ZIP格式正确",
        "content": "✅ 包含5个PDF文档",
        "documents": [
          "产品手册.pdf",
          "技术规格.pdf",
          "FAQ.pdf",
          "安装指南.pdf",
          "维护手册.pdf"
        ]
      }
    },
    "success_criteria.md": {
      "valid": true,
      "checks": {
        "format": "✅ Markdown格式正确",
        "content": "✅ 包含5个明确的成功标准",
        "criteria": [
          "回答准确率：≥90%",
          "响应时间：<3秒",
          "并发支持：≥5人",
          "来源引用：100%",
          "语音识别准确率：≥85%"
        ]
      }
    },
    "llm_provider_choice.txt": {
      "valid": true,
      "checks": {
        "format": "✅ 文本格式正确",
        "content": "✅ 明确选择Claude 3.5 Sonnet",
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022"
      }
    }
  }
}
```

### 8.2 总经理生成验证报告

**时间**：2025-01-06 10:00:30

**文件路径**：`user_inputs/meeting_001/validation_report.md`

**文件内容**：
```markdown
# 文件验证报告

**生成时间**：2025-01-06 10:00:30

---

## ✅ 验证通过

### 1. knowledge_documents.zip

- **状态**：✅ VALID
- **提交时间**：2025-01-06 10:00:10
- **验证结果**：
  - ✅ ZIP格式正确
  - ✅ 包含5个PDF文档
  - ✅ 文档内容清晰
  - ✅ 涵盖产品功能、技术规格、FAQ等多个方面

**文档列表**：
1. 产品手册.pdf（2.3MB）
2. 技术规格.pdf（1.8MB）
3. FAQ.pdf（0.9MB）
4. 安装指南.pdf（1.2MB）
5. 维护手册.pdf（1.5MB）

**将用于**：
- ✅ 产品经理：需求分析（task_002）
- ✅ 技术经理：架构设计（task_003）
- ✅ 向量数据库专家：知识库构建（task_005）

---

### 2. success_criteria.md

- **状态**：✅ VALID
- **提交时间**：2025-01-06 10:00:10
- **验证结果**：
  - ✅ Markdown格式正确
  - ✅ 包含5个明确的成功标准
  - ✅ 标准可衡量、可验证

**成功标准**：
1. 回答准确率：≥90% ✅
2. 响应时间：<3秒 ✅
3. 并发支持：≥5人 ✅
4. 来源引用：100% ✅
5. 语音识别准确率：≥85% ✅

**将用于**：
- ✅ 产品经理：需求分析和验收标准定义（task_002）

---

### 3. llm_provider_choice.txt

- **状态**：✅ VALID
- **提交时间**：2025-01-06 10:00:10
- **验证结果**：
  - ✅ 格式正确
  - ✅ 明确选择Claude 3.5 Sonnet
  - ✅ 包含选择理由

**LLM配置**：
- 提供商：Anthropic
- 模型：Claude 3.5 Sonnet
- 理由：准确率高，支持长文本

**将用于**：
- ✅ 技术经理：架构设计（task_003）
- ✅ NLP专家：RAG系统实现（task_006）

---

## ⏳ 仍需提供

### 4. voice_service_provider（语音服务商选择）

- **状态**：⏳ NOT_RECEIVED
- **紧急度**：BLOCKING
- **建议**：
  - 推荐方案：百度语音全套（国内稳定）
  - 替代方案：本地Whisper（免费，但需要GPU）

### 5. voice_service_credentials（语音服务凭证）

- **状态**：⏳ NOT_RECEIVED
- **紧急度**：BLOCKING
- **建议**：
  - 如选择百度语音：申请免费账号（5万次/天免费）
  - 如选择本地Whisper：无需凭证

---

## 下一步行动

### 立即启动的任务 ✅

以下任务可以立即开始（基于已提供的材料）：

1. **产品经理**：需求分析（task_002）
   - 输入：knowledge_documents.zip, success_criteria.md
   - 产出：详细需求文档

2. **技术经理**：技术架构设计（task_003）
   - 输入：knowledge_documents.zip, llm_provider_choice.txt
   - 产出：架构设计文档

### 等待材料的任务 ⏳

以下任务需要等待语音相关材料：

3. **语音集成专家**：语音功能集成（task_007）
   - 等待：voice_service_provider, voice_service_credentials
   - 预计：2天后可启动

---

## 项目进度

**已完成**：
- ✅ 会议讨论和方案制定
- ✅ 收集到部分用户输入（3/5项必须材料）

**进行中**：
- 🔄 产品经理：需求分析（启动中）
- 🔄 技术经理：架构设计（启动中）

**待启动**：
- ⏳ 向量数据库专家：等待架构设计
- ⏳ NLP专家：等待架构设计
- ⏳ 语音集成专家：等待语音凭证

---

**验证时间**：2025-01-06 10:00:30
**下次更新**：收到剩余材料时
```

### 8.3 总经理更新提交状态

**时间**：2025-01-06 10:00:35

**文件路径**：`user_inputs/meeting_001/submission_status.json`

**更新后的内容**：
```json
{
  "meeting_id": "meeting_001",
  "project_name": "展厅机器人",
  "last_updated": "2025-01-06T10:00:35Z",
  "status": "PARTIAL_INPUTS",

  "inputs": {
    "knowledge_documents": {
      "status": "RECEIVED_AND_DELIVERED",
      "urgency": "BLOCKING",
      "submitted_at": "2025-01-06T10:00:10Z",
      "validated": true,
      "delivered_to": ["agent_004_product_manager", "agent_003_tech_manager", "agent_202_vector_db_expert"]
    },
    "success_criteria": {
      "status": "RECEIVED_AND_DELIVERED",
      "urgency": "BLOCKING",
      "submitted_at": "2025-01-06T10:00:10Z",
      "validated": true,
      "delivered_to": ["agent_004_product_manager"]
    },
    "llm_provider_choice": {
      "status": "RECEIVED_AND_DELIVERED",
      "urgency": "BLOCKING",
      "submitted_at": "2025-01-06T10:00:10Z",
      "validated": true,
      "delivered_to": ["agent_003_tech_manager", "agent_201_nlp_expert"]
    },
    "voice_service_provider": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    },
    "voice_service_credentials": {
      "status": "NOT_RECEIVED",
      "urgency": "BLOCKING",
      "submitted_at": null,
      "validated": false
    }
  },

  "summary": {
    "total_inputs": 9,
    "blocking_received": 3,
    "blocking_required": 5,
    "optional_received": 0,
    "optional_required": 4
  },

  "next_actions": [
    "✅ 产品经理、技术经理已启动任务",
    "⏳ 等待语音相关材料（voice_service_provider, voice_service_credentials）",
    "⏳ 语音集成任务2天后启动"
  ]
}
```

### 8.4 总经理分发文件给专家

**时间**：2025-01-06 10:00:40

#### 8.4.1 分发给产品经理

**文件路径**：`agents/agent_004_product_manager/inbox/task_assignment_002.json`

**文件内容**：
```json
{
  "message_id": "msg_20250106_100040_001",
  "message_type": "TASK_ASSIGNMENT_WITH_INPUT",

  "from_agent": "agent_001_general_manager",
  "to_agent": "agent_004_product_manager",

  "task": {
    "task_id": "task_002",
    "title": "需求分析",
    "description": "基于提供的知识文档和成功标准，进行详细的需求分析",

    "inputs": {
      "knowledge_documents": "user_inputs/meeting_001/knowledge_documents.zip",
      "success_criteria": "user_inputs/meeting_001/success_criteria.md"
    },

    "outputs": {
      "requirement_doc": "详细需求文档（Markdown格式）"
    },

    "deadline": "2025-01-06T18:00:00Z",
    "estimated_duration": "4-6小时"
  },

  "attached_inputs": [
    {
      "input_id": "knowledge_documents",
      "file_path": "user_inputs/meeting_001/knowledge_documents.zip",
      "provided_by": "user",
      "validated": true
    },
    {
      "input_id": "success_criteria",
      "file_path": "user_inputs/meeting_001/success_criteria.md",
      "provided_by": "user",
      "validated": true
    }
  ]
}
```

#### 8.4.2 分发给技术经理

**文件路径**：`agents/agent_003_tech_manager/inbox/task_assignment_003.json`

**文件内容**：
```json
{
  "message_id": "msg_20250106_100040_002",
  "message_type": "TASK_ASSIGNMENT_WITH_INPUT",

  "from_agent": "agent_001_general_manager",
  "to_agent": "agent_003_tech_manager",

  "task": {
    "task_id": "task_003",
    "title": "技术架构设计",
    "description": "基于知识文档和LLM选择，设计技术架构方案",

    "inputs": {
      "knowledge_documents": "user_inputs/meeting_001/knowledge_documents.zip",
      "llm_provider_choice": "user_inputs/meeting_001/llm_provider_choice.txt"
    },

    "outputs": {
      "architecture_doc": "技术架构设计文档（Markdown格式）"
    },

    "deadline": "2025-01-06T18:00:00Z",
    "estimated_duration": "4-6小时"
  },

  "attached_inputs": [
    {
      "input_id": "knowledge_documents",
      "file_path": "user_inputs/meeting_001/knowledge_documents.zip",
      "provided_by": "user",
      "validated": true
    },
    {
      "input_id": "llm_provider_choice",
      "file_path": "user_inputs/meeting_001/llm_provider_choice.txt",
      "provided_by": "user",
      "validated": true
    }
  ]
}
```

---

## 9. Day 1-2: 专家执行任务

### 9.1 产品经理执行需求分析

**时间**：2025-01-06 10:05 - 16:00

**Agent内部处理**：

```
【任务接收】
产品经理收到任务：task_002（需求分析）
输入：
  - knowledge_documents.zip
  - success_criteria.md

【步骤1：解压并阅读文档】
解压knowledge_documents.zip，阅读5个PDF文档：
  1. 产品手册.pdf
     - 产品：智能会议系统
     - 主要功能：视频会议、屏幕共享、会议录制
     - 目标用户：企业客户

  2. 技术规格.pdf
     - 技术架构：微服务架构
     - 支持平台：Web、Windows、macOS、移动端
     - 并发能力：支持1000人同时在线

  3. FAQ.pdf
     - 常见问题：30个
     - 分类：功能类、技术类、购买类、售后类

  4. 安装指南.pdf
     - 部署方式：云端、本地
     - 系统要求：4核8G，100G存储

  5. 维护手册.pdf
     - 维护周期：每月一次
     - 备份策略：每日备份

【步骤2：分析成功标准】
阅读success_criteria.md：
  - 回答准确率：≥90%
  - 响应时间：<3秒
  - 并发支持：≥5人
  - 来源引用：100%
  - 语音识别准确率：≥85%

【步骤3：需求分析】
基于文档和成功标准，进行需求分析：

功能需求：
1. 知识问答
   - 支持文字和语音提问
   - 基于本地知识库检索
   - 准确率≥90%
   - 响应时间<3秒
   - 标注信息来源

2. 知识库管理
   - 支持PDF、TXT、MD文档上传
   - 自动解析和向量化
   - 支持知识库更新和扩展

3. 语音交互
   - 语音识别准确率≥85%
   - 语音合成自然流畅
   - 支持中英文

4. 管理界面
   - 查看问答历史
   - 评估回答质量
   - 系统配置

非功能需求：
1. 性能：响应时间<3秒
2. 并发：支持5人同时使用
3. 可靠性：7x24小时稳定运行
4. 可维护性：知识库易于更新

【步骤4：生成需求文档】
生成详细需求文档
```

**产出文件**：

**文件路径**：`workspace/artifacts/task_002/requirement_doc.md`

**文件内容**：
```markdown
# 展厅机器人需求文档

**项目名称**：带本地知识库的展厅机器人
**文档版本**：v1.0
**编写日期**：2025-01-06
**编写者**：产品经理（agent_004）

---

## 1. 项目概述

### 1.1 项目背景
某科技公司需要在展厅放置一个智能问答机器人，参观者可以通过语音或文字提问，机器人基于公司的产品文档回答问题。

### 1.2 产品定位
- **目标用户**：展厅参观者（潜在客户、合作伙伴、媒体）
- **核心价值**：提供7x24小时的智能问答服务，提升展厅体验
- **使用场景**：展厅现场，参观者询问公司产品相关问题

---

## 2. 功能需求

### 2.1 知识问答系统

#### 2.1.1 文字提问
**需求描述**：参观者可以通过文字输入问题

**功能点**：
- 输入框支持中英文输入
- 支持最多200字的问题
- 提交后3秒内显示答案

**验收标准**：
- 响应时间<3秒 ✅
- 支持中英文 ✅

#### 2.1.2 语音提问
**需求描述**：参观者可以通过语音提问

**功能点**：
- 点击麦克风按钮开始录音
- 再次点击结束录音
- 自动语音转文字（ASR）
- 如果识别准确，显示问题并回答
- 如果识别不准确，提示"请问您是想问：XXX吗？"

**验收标准**：
- 语音识别准确率≥85% ✅
- 支持中英文 ✅
- 识别时间<2秒 ✅

#### 2.1.3 答案生成
**需求描述**：基于知识库生成准确答案

**功能点**：
- 使用RAG架构（检索+生成）
- 从知识库中检索相关文档片段
- 基于检索结果生成答案
- 答案要准确、完整、易懂

**验收标准**：
- 回答准确率≥90% ✅
- 答案完整度≥85% ✅
- 答案语言通俗易懂 ✅

#### 2.1.4 来源引用
**需求描述**：每个答案都要标注信息来源

**功能点**：
- 显示答案来自哪个文档
- 显示文档的页码或章节
- 提供"查看原文"链接

**验收标准**：
- 100%答案都有来源引用 ✅
- 引用信息准确 ✅

### 2.2 知识库管理

#### 2.2.1 文档上传
**需求描述**：管理员可以上传文档到知识库

**功能点**：
- 支持PDF、TXT、Markdown格式
- 单个文档最大20MB
- 批量上传最多10个文档
- 显示上传进度

**验收标准**：
- 支持3种格式 ✅
- 上传成功率≥99% ✅

#### 2.2.2 文档解析
**需求描述**：自动解析文档内容

**功能点**：
- PDF：提取文本内容，保留段落结构
- TXT：直接读取
- Markdown：解析标题、列表、表格
- 解析后显示文档信息（标题、字数、段落数）

**验收标准**：
- 解析准确率≥95% ✅
- 解析时间<10秒/文档 ✅

#### 2.2.3 向量化
**需求描述**：将文档内容转换为向量表示

**功能点**：
- 使用Embedding模型（OpenAI text-embedding-3-small）
- 按段落切分（每段约500字）
- 每个段落生成向量
- 向量存储到ChromaDB

**验收标准**：
- 向量化时间<30秒/文档 ✅
- 向量质量：检索召回率≥90% ✅

#### 2.2.4 知识库更新
**需求描述**：支持知识库的增量更新

**功能点**：
- 添加新文档
- 删除旧文档
- 重新向量化（文档内容变化时）

**验收标准**：
- 更新时间<1分钟 ✅
- 更新成功率100% ✅

### 2.3 管理界面

#### 2.3.1 问答历史
**需求描述**：查看所有问答记录

**功能点**：
- 显示问答列表（时间、问题、答案、准确度评分）
- 支持搜索和筛选
- 导出CSV

**验收标准**：
- 历史记录完整度100% ✅
- 搜索响应时间<1秒 ✅

#### 2.3.2 质量评估
**需求描述**：评估答案质量

**功能点**：
- 管理员可以给答案打分（1-5分）
- 标注答案是否准确
- 查看低分答案列表（用于优化）

**验收标准**：
- 评估功能可用 ✅
- 低分答案可见 ✅

#### 2.3.3 系统配置
**需求描述**：配置系统参数

**功能点**：
- 配置LLM模型（Claude、GPT等）
- 配置Embedding模型
- 配置语音服务
- 查看系统状态（在线/离线）

**验收标准**：
- 配置即时生效 ✅
- 状态准确 ✅

---

## 3. 非功能需求

### 3.1 性能要求

| 指标 | 要求 | 验证方法 |
|------|------|---------|
| 问答响应时间 | <3秒 | 测量100次问答 |
| 语音识别时间 | <2秒 | 测量50次识别 |
| 文档解析时间 | <10秒/文档 | 测量10个文档 |
| 向量化时间 | <30秒/文档 | 测量10个文档 |

### 3.2 并发要求

| 场景 | 并发数 | 要求 |
|------|--------|------|
| 展厅参观 | 5人 | 体验不下降 |
| 问答准确率 | 5人并发 | ≥90% |
| 响应时间 | 5人并发 | <3秒 |

### 3.3 可靠性要求

- **可用性**：99%（每周停机<1.7小时）
- **数据持久化**：所有问答记录持久化存储
- **备份策略**：知识库每日备份

### 3.4 安全性要求

- **访问控制**：管理界面需要登录
- **数据加密**：敏感数据（API凭证）加密存储
- **日志记录**：所有操作记录日志

---

## 4. 用户界面需求

### 4.1 参观者界面

**设计原则**：简洁、直观、无需学习

**界面元素**：
1. 问题输入框（文字+语音按钮）
2. 答案显示区（包含来源引用）
3. 历史问题列表（最近5个）
4. 帮助提示（引导第一次使用）

### 4.2 管理界面

**设计原则**：功能齐全、易于操作

**界面模块**：
1. 知识库管理（上传、删除、查看）
2. 问答历史（查看、搜索、导出）
3. 质量评估（打分、标注）
4. 系统配置（模型选择、参数调整）

---

## 5. 数据需求

### 5.1 知识文档

**当前状态**：已提供5篇文档
- 产品手册.pdf
- 技术规格.pdf
- FAQ.pdf
- 安装指南.pdf
- 维护手册.pdf

**后续扩展**：
- 支持添加更多文档
- 目标：覆盖所有产品和功能

### 5.2 典型问题

**建议收集**（基于FAQ.pdf分析）：
1. 这个产品的主要功能是什么？
2. 产品的技术架构是什么？
3. 如何部署这个系统？
4. 系统支持多少人同时在线？
5. 产品的价格是多少？
6. 如何购买？
7. 有技术支持吗？
8. 产品的优势是什么？
9. 支持哪些平台？
10. 如何培训用户？

---

## 6. 成功标准

### 6.1 核心指标

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 回答准确率 | ≥90% | 100个测试问题 |
| 响应时间 | <3秒 | 100次测量 |
| 并发支持 | ≥5人 | 模拟并发测试 |
| 来源引用 | 100% | 检查所有答案 |
| 语音识别准确率 | ≥85% | 50个语音问题 |

### 6.2 次要指标

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 知识库覆盖率 | ≥80% | 人工检查 |
| 用户满意度 | ≥4.0/5.0 | 现场调研 |

---

## 7. 约束条件

### 7.1 技术约束

- **LLM选择**：使用Claude 3.5 Sonnet（用户指定）
- **知识库**：使用ChromaDB（技术经理建议）
- **部署环境**：待确认（用户未提供）

### 7.2 业务约束

- **项目周期**：5个工作日
- **团队规模**：7个Agent
- **预算**：未明确

### 7.3 合规约束

- **数据隐私**：不收集参观者个人信息
- **内容合规**：知识库内容符合法律法规

---

## 8. 风险与假设

### 8.1 风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 知识库质量不足 | 准确率不达标 | 持续优化知识库 |
| 语音识别准确率低 | 用户体验差 | 提供文字备选方案 |
| 并发性能不足 | 高峰期卡顿 | 性能优化和测试 |

### 8.2 假设

- 参观者会使用语音或文字提问
- 知识文档质量足够高
- 网络连接稳定
- 语音服务可用（待用户提供凭证）

---

## 9. 后续行动

### 9.1 立即行动

1. ✅ 技术经理：基于需求设计技术架构
2. ✅ 向量数据库专家：开始准备知识库构建

### 9.2 等待材料

3. ⏳ 语音集成专家：等待用户提供语音服务凭证

---

**文档状态**：✅ 完成
**下一步**：技术经理基于此文档进行架构设计
