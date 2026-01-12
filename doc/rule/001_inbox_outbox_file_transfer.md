# 唯一的交互方式：inbox/outbox文件传递

**原则ID**: PR-001
**来源文档**: file_transfer_mechanism.md
**类别**: 核心机制

---

## 原则描述

AgentTalk系统中Agent之间只有一种交互方式：向对方的inbox文件夹发送文件。

所有的沟通、通知、请求、响应都是通过文件传递来实现的。系统中不存在"通知"、"命令"、"调用"等抽象概念。

为保证可靠性与可追溯性，文件传递应遵循以下约定：

- **消息信封（Envelope）**：每次投递都应有一个可解析的元数据文件（推荐 `*.msg.json` 或 `*.meta.json`），携带消息ID、类型、关联任务等字段。
- **原子落盘**：写入文件时先写临时文件（如 `*.tmp`），完成后原子重命名；消费方只处理“已完成写入”的文件。
- **幂等与去重**：系统路由以 `message_id + sha256` 为主去重键；`idempotency_key` 仅用于审计与人类可读关联，避免“双口径去重”导致行为分叉。
- **回执（ACK）**：消费方处理完成后产出 `ack_<message_id>.json`，用于确认已处理（可选，但推荐）。
- **死信（Deadletter）**：无法解析/不符合Schema/多次失败的消息进入 `inbox/<plan_id>/.deadletter/`，避免阻塞主流程（见PR-010/PR-024）。

模板参考：
- `doc/rule/templates/message_envelope.msg.json`
- `doc/rule/templates/ack.json`
- `doc/rule/templates/deadletter_entry.json`
- `doc/rule/templates/delivery_state_machine.md`
- `doc/rule/templates/schema_versioning.md`

## 交互流程

1. **发送方**: Agent A将文件放到自己的 `outbox/<plan_id>/`
2. **系统**: 系统自动投递到Agent B的 `inbox/<plan_id>/`
3. **接收方**: Agent B从自己的 `inbox/<plan_id>/` 读取文件

所有的沟通都是通过这个机制实现的。

## 关键要点

- **统一性**: 所有Agent间的交互都使用同一套文件传递机制
- **简单性**: 没有复杂的RPC、消息队列等抽象，只有文件传递
- **可追溯**: 所有交互都以文件形式记录，便于追溯和调试
- **解耦**: 发送方和接收方通过文件解耦，无需直接交互
- **可靠投递**: 通过消息ID、原子写入、去重、回执与死信机制降低“重复/丢失/半写入”风险

## 适用范围

所有Agent之间的交互，包括但不限于：
- 任务分配
- 结果反馈
- 资源共享
- 状态通知
- 协作请求

---

**最后更新**: 2025-01-08
