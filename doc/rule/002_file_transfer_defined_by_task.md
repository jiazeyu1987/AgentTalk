# 文件传递由任务文件规定

**原则ID**: PR-002
**来源文档**: file_transfer_mechanism.md
**类别**: 核心机制

---

## 原则描述

AgentTalk系统没有通用的"反馈"或"回复"机制。所有文件传递都必须在任务文件（DAG方案）中明确规定。

## 规定内容

任务文件中必须明确规定：

1. **输出文件**: Agent需要生成哪些输出文件
2. **接收方**: 每个输出文件应该发送给哪些Agent（可能有多个接收者）

## 执行流程

1. Agent从 `inbox/<plan_id>/` 读取任务文件
2. 任务文件明确规定：
   - Agent需要完成什么工作
   - 需要生成哪些输出文件
   - 每个输出文件应该发送给哪个Agent
3. Agent完成任务后，将输出文件保存到自己的 `outbox/<plan_id>/`
4. 系统根据任务文件中的规定，将文件投递给指定的接收者
5. 接收方从自己的 `inbox/<plan_id>/` 读取文件

## 关键要点

- **接收方由任务文件指定，不是由发送者决定**
- 没有自动反馈机制，所有传递都必须预先定义
- 如果Backend Agent完成API开发后需要通知Frontend Agent，这个要求必须在DAG方案中明确规定

## 示例

任务文件规定：Backend Agent需要生成"payment_api.zip"，并发送给Frontend Agent和PM Agent。

Backend Agent完成后：
- 将payment_api.zip放到 `outbox/<plan_id>/`
- 系统自动将文件投递给Frontend Agent和PM Agent的 `inbox/<plan_id>/`

---

**最后更新**: 2025-01-08
