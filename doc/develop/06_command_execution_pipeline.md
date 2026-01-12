# 06 命令执行流水线模块（Command Runner）

## 目标

实现“命令消息”执行规范（方案B）：
- schema 校验
- 输入检查（复用 Heartbeat 已实现的 `required_inputs/resolved_inputs` 判定）
- 执行器（可插拔）只负责“产出内容”，流水线负责“落盘为 artifact + envelope”
- 输出产物落盘到 outbox + envelope（Router 可投递）

## MVP 执行方式

- 先不接真实 LLM：用可插拔 handler/executor
  - `agenttalk.command_runner.dummy_handler`（测试用，按 `command.produces[]` 生成固定输出）
  - 后续再接 LLM provider

## 输出契约（必须写死）

- handler 返回 `CommandResult.details.artifacts[]`（内存结构）
- 流水线把 artifacts 写入 `outbox/<plan_id>/`：
  - payload 文件：按 `ProducedFile.path` 写入
  - envelope 文件：`artifact_<task_id>_<output_name>_<message_id>.msg.json`（`type=artifact`，并写入 `payload.files[]`）

## command.produces（推荐）

为避免执行侧“猜测应该产出哪个 output_name”，建议命令包含：
- `produces[] { output_name, files[] { path, content_type } }`

## Pytest

- 单测：`write_artifacts_to_outbox` 写入 payload + envelope，且符合 `message_envelope` schema
- 集成：Heartbeat 消费 `cmd_*.msg.json`（handler=DummyArtifactHandler）产出 artifact 到 outbox，Router 可投递
