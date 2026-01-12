# 文件传递由任务文件规定

**原则ID**: PR-002
**来源文档**: file_transfer_mechanism.md
**类别**: 核心机制

---

## 原则描述

AgentTalk系统没有通用的"反馈"或"回复"机制。所有文件传递都必须在任务文件（DAG方案）中明确规定。

在运行期，跨Agent的文件投递由**系统路由程序**完成：Agent只写自己的outbox，不能直接写其他Agent的inbox（见PR-003）。

## 前置阶段：大DAG尚未生成时怎么办（使用 Meta-DAG）

在一些流程中（例如“一次性需求澄清”“DAG评审”“人类介入请求”），Business-DAG（大DAG）可能尚未生成。

为保持路由机制唯一且可审计，本系统不使用命令中的 `send_to` 作为路由来源，而是要求：

- Plan 从一开始就运行一个固定的 Meta-DAG（小DAG），用于生成并放行 Business-DAG。
- 在 Meta-DAG 阶段，所有控制面产物（澄清问题清单、评审结果、告警/请求等）的投递目标都由 Meta-DAG 的 `outputs[].deliver_to` / `routing_rules` 预先定义。
- 命令文件本身投递给谁，由 DAG 中对应任务的 `assigned_agent_id` 决定（见PR-024）。

模板参考：
- `doc/rule/templates/task_dag.json`
- `doc/rule/templates/message_envelope.msg.json`
- `doc/rule/templates/routing_priority.md`
- `doc/rule/templates/command.cmd.json`

## 规定内容

任务文件中必须明确规定：

1. **输出文件**: Agent需要生成哪些输出文件
2. **接收方**: 每个输出文件应该发送给哪些Agent（可能有多个接收者）
3. **路由依据**: 推荐按“输出类型/文件名模式/标签”定义路由规则，避免依赖运行期临时决策
4. **幂等键**: 推荐为每类输出定义 `idempotency_key` 计算方式或唯一标识，便于去重与审计

## 执行流程

1. Agent从 `inbox/<plan_id>/` 读取任务文件
2. 任务文件明确规定：
   - Agent需要完成什么工作
   - 需要生成哪些输出文件
   - 每个输出文件应该发送给哪个Agent
3. Agent完成任务后，将输出文件保存到自己的 `outbox/<plan_id>/`
4. 系统路由程序根据任务文件中的规定，将文件投递给指定的接收者
5. 接收方从自己的 `inbox/<plan_id>/` 读取文件

## 关键要点

- **接收方由任务文件指定，不是由发送者决定**
- 少数“控制面”消息（例如PR-022的重新执行、PR-010的告警）允许按协议路由，但仍应可追溯、可审计（见PR-017/PR-024）
- 没有自动反馈机制，所有传递都必须预先定义
- 如果Backend Agent完成API开发后需要通知Frontend Agent，这个要求必须在DAG方案中明确规定

## 示例

任务文件规定：Backend Agent需要生成"payment_api.zip"，并发送给Frontend Agent和PM Agent。

Backend Agent完成后：
- 将payment_api.zip放到 `outbox/<plan_id>/`
- 系统自动将文件投递给Frontend Agent和PM Agent的 `inbox/<plan_id>/`

推荐同时生成一个元数据文件（例如 `payment_api.zip.meta.json` 或 `msg_payment_api.json`）包含 `message_id`、`plan_id`、`producer_agent`、`sha256`，用于去重与追溯（见PR-001/PR-017/PR-024）。

---

**最后更新**: 2025-01-08
