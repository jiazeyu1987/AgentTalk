# Delivery & ACK State Machine（投递/回执/重试/死信）

本文件把“文件传递”落成一个可执行的状态机，保证在以下约束下仍能可靠运行：
- Agent只读写自己的文件夹（PR-003）
- 所有交互只通过文件（PR-001）
- 投递由系统路由程序跨目录执行（PR-024）

## 1. 术语

- **消息（Message）**：一次投递单元；由payload文件 + 可解析信封(`*.msg.json`/`*.meta.json`)组成。
- **投递（Delivery）**：系统路由把消息从生产者outbox复制到目标inbox的过程。
- **消费（Consume）**：目标Agent读入消息并执行处理（可能触发命令执行/产出新消息）。
- **回执（ACK）**：消费方对消息的状态确认文件（见 `ack.json` 模板）。
- **死信（DLQ）**：无法处理的消息隔离区（Agent侧 `inbox/<plan_id>/.deadletter/` 或系统侧 `system_runtime/deadletter/<plan_id>/`）。

## 2. 文件级原子性协议（必须）

为避免读到半写入文件，生产方与系统路由必须使用一致的原子协议：

1. 写入阶段：先写 `*.tmp`
2. 完成阶段：原子重命名为目标文件名（同目录rename）

消费方只处理：
- 不以 `.tmp` 结尾的文件
- 并且其信封文件存在且可解析（推荐）

## 3. 消息生命周期状态

系统路由与监控以消息为粒度维护状态：

1. `CREATED`：生产方已在 outbox/<plan_id>/ 写入 payload 与 envelope
2. `DELIVERED`：系统路由已复制到目标 inbox/<plan_id>/
3. `CONSUMED`：目标Agent已读取并接受处理（ACK: `CONSUMED`）
4. `SUCCEEDED`：目标Agent处理成功（ACK: `SUCCEEDED`）
5. `FAILED`：目标Agent处理失败但可重试/可返工（ACK: `FAILED` + reason）
6. `DEADLETTERED`：进入DLQ（系统或Agent侧）

说明：
- `CONSUMED` 用于“已开始处理但还未完成”，便于区分“已投递未处理”与“处理中卡住”。
- `SUCCEEDED/FAILED` 表示本次处理终态；是否重试由策略决定。

## 4. ACK语义（推荐最小集合）

ACK文件名：
- 推荐：`ack_<message_id>.json`（也可用 `ack_<message_id>_<seq>.json` 支持多次处理）

ACK字段最小集合（见模板 `ack.json`）：
- `schema_version`
- `plan_id`
- `message_id`
- `consumer_agent_id`
- `status`: `CONSUMED|SUCCEEDED|FAILED`
- `consumed_at` / `finished_at`（可选）
- `result.ok` 与 `result.details`（可选）

## 5. 重试与退避（建议由系统程序执行）

适用场景：
- `DELIVERED` 后长期无 `CONSUMED`（目标Agent可能未启动/卡死）
- `FAILED` 且 `retriable=true`

建议策略：
- 最大重试次数：`N`（默认3）
- 退避：指数退避（如 30s, 60s, 120s）
- 重试不改变 `message_id`，但应增加 `delivery_id`，并在投递日志中记录

达到上限后：
- 写入死信条目（见 `deadletter_entry.json`）
- 生成告警（见 `alert.json`）

## 6. Deadletter处理（必须定义去向）

进入DLQ的典型原因：
- JSON解析失败
- `schema_version` 不支持（见 `schema_versioning.md`）
- 缺少必需字段（Schema校验失败）
- 超过最大重试次数
- 安全策略拒绝（例如不可信来源伪装成validated产物）

DLQ落盘：
- Agent侧：`agents/<agent_id>/inbox/<plan_id>/.deadletter/`
- 系统侧：`system_runtime/deadletter/<plan_id>/`

DLQ条目建议包含：
- 原文件名/路径
- 原message_id（如果可读）
- reason.code + reason.message
- suggested_next（alert/manual_replay/drop）

## 7. Plan完成判定（最小可计算规则）

Plan是否完成由系统监控依据 `plan_manifest.json` 判定（当引入发布门禁时也适用）：

1. `deliverables[]` 中每个条目必须被“满足”：
   - 对应文件已出现并被归档（`system_runtime/artifacts/<plan_id>/...`）
   - 若 `accept_if.validated_by_trusted_validator=true`，必须来自受信任验证者（见PR-024）
   - 若 `accept_if.evidence_required` 存在，则这些证据文件必须存在且为PASS/APPROVE（见templates与各自schema）
2. 所有 `required=true` 的Agent在Plan窗口期内至少有一次有效心跳（或由管理员显式豁免）
3. 不存在处于 `FAILED` 且无处理策略的关键任务（可选：由policies定义）

发布门禁（可选但推荐）：
- 若 `policies.release_gates_required` 存在，则这些门禁证据必须存在且为PASS/APPROVE
- 最终应产生一个 `release_manifest.json`（decision=APPROVE/REJECT），作为“可交付版本”的明确判据

## 9. Human Gateway（人类介入）

当系统检测到“缺文件/缺标准/需要审批/需要外部环境权限”等无法自动推进的阻塞时，推荐走Human Gateway机制：

1. 系统或责任Agent写出 `human_intervention_request.json`（到自己的outbox/<plan_id>/）
2. 系统路由投递到 `agents/agent_human_gateway/inbox/<plan_id>/`
3. 人在 `agents/agent_human_gateway/outbox/<plan_id>/` 写 `human_intervention_response.json` 并附带所需文件
4. 系统路由按response中的 `deliver_to_agent_id` 将文件投递到目标Agent inbox，并解除阻塞

模板参考：
- `doc/rule/templates/human_intervention_request.json`
- `doc/rule/templates/human_intervention_response.json`

## 8. 与DAG/路由表的关系

- DAG负责声明“哪些输出投递给哪些Agent”以及“哪些输出是deliverable”
- 系统路由负责执行投递并记录delivery日志
- Agent负责执行命令与产出输出（写outbox）
