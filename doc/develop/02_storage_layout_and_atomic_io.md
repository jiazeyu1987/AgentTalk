# 02 目录布局与原子 IO 模块

## 目标

实现“文件即消息”可靠落盘协议：
- 写入阶段：`*.tmp`
- 完成阶段：同目录原子 rename
- 消费方只处理非 `.tmp`

并固化 MVP 目录布局：
- `agents/<agent_id>/{inbox,outbox,workspace,logs,...}`
- `system_runtime/{plans,deadletter,alerts,artifacts,agent_status}`（其中 `plans/<plan_id>/` 内含 `deliveries.jsonl/commands/decisions/dag_history` 等，见 PR-024）

## 目录协议（MVP 必须统一）

为避免各模块对“消息是否已处理/是否在处理中”的理解分叉，统一约定每个 Agent 的每个 plan inbox 下存在以下子目录（由 Agent 自己创建与维护）：

- `inbox/<plan_id>/.pending/`：已被本 Agent 原子 claim，等待/正在处理
- `inbox/<plan_id>/.processed/`：已处理完毕归档
- `inbox/<plan_id>/.deadletter/`：消费侧无法处理的消息隔离（消费侧 DLQ）

约束：
- 系统路由程序投递时只写 `inbox/<plan_id>/` 根目录（不写 `.pending/.processed`）。
- Agent 的消费循环只从 `inbox/<plan_id>/` 根目录挑选“可处理文件”，并通过原子 rename/move 进入 `.pending/` 完成 claim。

## 模块边界

- 输入：目标目录、文件名、内容（bytes/str）、是否需要原子写入
- 输出：写入成功 + sha256 + mtime
- 不负责：业务 schema、路由策略

约束（避免实现分叉）：
- `deliveries.jsonl`、`plan_status.json`、`active_dag_ref.json`、`system_runtime/plans/<plan_id>/decisions/*` 等“系统视角文件”由系统程序单写者写入；Agent 不应写入这些路径（见PR-024）。
- Agent inbox 下的 `.pending/.processed/.deadletter` 仅由该 Agent 维护；系统程序投递只写 `inbox/<plan_id>/` 根目录。

## 接口草案

- `atomic_write(path, bytes) -> sha256`
- `atomic_copy(src, dst) -> sha256`
- `list_ready_files(dir) -> list[path]`（过滤 tmp、过滤 staging 目录）

## Pytest

- 单测：写入 tmp→rename 后文件存在且内容一致
- 单测：list_ready_files 不返回 tmp
- 集成：模拟并发写入（两个 tmp）确保消费方不会读到半文件
