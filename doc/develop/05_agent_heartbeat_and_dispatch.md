# 05 Agent 心跳与分发模块（Heartbeat）

## 目标

每个 agent 进程实现：
- 周期扫描 inbox
- 原子 claim（同 plan 目录内 rename/move 到 `inbox/<plan_id>/.pending/`）
- 去重检查（本地已处理记录）
- 解析消息信封（`*.msg.json`），完成“命令执行”与“输入就绪”两类最小能力：
  - 命令消息：`type=command` → 投递给本 Agent 的执行 handler
  - 产物消息：`type=artifact` → **不执行业务**，但必须被“落盘归档+可被输入匹配命中”，否则 `wait_for_inputs` 机制无法工作
- 写心跳与健康快照（供系统监控采集）

## 模块边界

- 输入：agent_root、poll interval、可见性列表（可后置）
- 输出：ACK、task_state、trace、outbox 产物、心跳快照

约束（与 Router/Monitor 对齐）：
- Agent 不负责“旧命令丢弃”（由 Router 侧 `SKIPPED_SUPERSEDED` 处理）；Agent 收到的命令消息应当默认就是“当前可执行的一条”。
- Agent 侧的“去重检查”仅用于防止本地重复消费（例如进程重启/目录重复扫描）；建议以 `message_id`（可选再加 `sha256`）做本地已处理索引键，不引入额外路由/覆盖语义。

## 作为独立模块的可复用边界（建议写死）

本模块可以作为独立库/组件复用到所有 Agent 进程中，前提是：
- 不直接依赖 Router/Monitor 的实现（只依赖文件契约与目录协议）
- 通过“接口注入”对接原子IO、schema校验、业务 handler，避免耦合导致实现分叉

为让你们可以直接按本文实现一个**独立可运行程序**（CLI/daemon），下文补齐“还差什么”：
- 进程入口与配置加载（读 `heartbeat_config.json`）
- 多 plan 扫描策略与公平性（跨 plan 不饿死）
- 错误码与落盘约定（`.deadletter/`、`alert_*.json`、`human_intervention_request_*.json`）
- 输入索引（`input_index.json`）的结构与更新规则（避免每个实现发明一套）

### 配置输入（最小）

- `agent_root`: 当前 Agent 的根目录（只读写该目录）
- `poll_interval_seconds`
- `max_new_messages_per_tick`（默认 50）
- `max_resume_messages_per_tick`（默认 10）

（建议写死）配置文件：
- 路径：`agents/<agent_id>/heartbeat_config.json`
- 模板/Schema：
  - `doc/rule/templates/heartbeat_config.json`
  - `doc/rule/templates/schemas/heartbeat_config.schema.json`

### 依赖接口（必须注入）

- **Atomic IO**
  - `list_ready_envelopes(inbox_plan_dir) -> list[path]`（仅返回 `*.msg.json`，排除 `.tmp` 与 staging 目录）
  - `atomic_move(src, dst)` / `atomic_rename(src, dst)`
  - `atomic_write_json(path, obj)`
  - `atomic_copy(src, dst)`（用于输入归档）
- **Schema 校验/解析**
  - `validate(envelope_or_payload, schema_id) -> ok/errors`
  - `parse_envelope(path) -> Envelope`（至少解析 `message_id/type/task_id/output_name/command_id/payload`）
- **Handlers（单职责业务实现）**
  - `handle_command(envelope, command, context) -> ExecutionResult`
  - `handle_artifact(envelope, context) -> ArtifactIngestResult`（默认可使用本文定义的“输入归档”逻辑）

### 输出契约（模块必须产出）

- `agents/<agent_id>/outbox/<plan_id>/ack_<message_id>.json`
- （可选但推荐）`agents/<agent_id>/outbox/<plan_id>/task_state_<task_id>.json`
- `agents/<agent_id>/status_heartbeat.json`
- （阻塞超时必需）`agents/<agent_id>/outbox/<plan_id>/human_intervention_request_<request_id>.json`
- （可选）`agents/<agent_id>/outbox/<plan_id>/alert_<alert_id>.json`

### 非职责边界（必须排除）

- 不读取/不解析 `system_runtime/plans/<plan_id>/task_dag.json`（避免跨目录依赖与版本不一致）
- 不负责“旧命令丢弃/覆盖”（由 Router 侧 `SKIPPED_SUPERSEDED` 完成）
- 不负责业务结论文件（review/release decision），只负责执行/输入落盘/回执

## 作为独立程序的运行模型（必须写死）

### 进程入口（建议）

独立程序（heartbeat daemon）启动后循环：
1) 加载并 schema 校验 `heartbeat_config.json`（失败则直接退出并写 `alert` 到 outbox 根目录）
2) 按配置确定要扫描的 plan 列表（见下文）
3) 按顺序对每个 plan 执行一次 `tick(plan_id)`
4) sleep `poll_interval_seconds`

### 多 plan 扫描策略（必须写死）

为避免单一 plan 堵塞导致其它 plan 饿死，写死如下规则：
- plan 列表来源：
  - `scan_mode=auto`：扫描 `inbox/` 下的所有 `<plan_id>` 子目录（按目录名升序）
  - `scan_mode=allowlist_only`：仅扫描 `allowlist[]` 中的 plan（按列表顺序）
- 每轮对每个 plan 分配固定预算：
  - 新消息预算：`max_new_messages_per_tick`
  - 恢复预算：`max_resume_messages_per_tick`

## 输入索引 input_index.json（MVP 必须写死）

目的：
- 让 `wait_for_inputs` 的输入匹配可实现且可审计
- 避免业务 handler 自己扫 `workspace/inputs` 发明一套索引

文件位置（写死）：
- `agents/<agent_id>/workspace/<plan_id>/inputs/input_index.json`

模板/Schema：
- `doc/rule/templates/input_index.json`
- `doc/rule/templates/schemas/input_index.schema.json`

更新规则（必须写死）：
- 输入归档成功后，必须把该条 artifact 的信息追加/合并到 input_index：
  - 去重键：`message_id`（同 message_id 重复出现且内容一致可忽略）
  - 同一 `(task_id, output_name)` 可存在多条 entry（由 message_id 区分），不覆盖旧记录
- input_index 必须采用“读-改-写 + tmp→rename”原子覆盖（避免并发写坏 JSON）

## 错误码与失败处理（必须写死）

### 解析/校验失败（消费侧 DLQ）

- envelope JSON 解析失败 / schema 校验失败：
  - move：`inbox/<plan_id>/.pending/...` → `inbox/<plan_id>/.deadletter/...`
  - 写：`agents/<agent_id>/outbox/<plan_id>/alert_<alert_id>.json type=SCHEMA_INVALID`

### handler 失败（命令执行失败）

- handler 抛异常或返回失败：
  - ACK：写终态 `FAILED`
  - 可选：写 `task_state=FAILED`（含错误摘要）
  - move：消息 envelope → `.processed/`（不再阻塞 inbox）

### 输入冲突/收尾冲突（必须告警）

- `INPUT_CONFLICT`：输入归档同路径不同 sha256（见上文）
- `PAYLOAD_FINALIZE_CONFLICT`：payload 收尾目标存在但 sha256 不同（见上文）

## 与 Router/Monitor 的最小对齐点（独立程序必须遵守）

- Router 投递遵循“payload 先到、envelope 后到”；Heartbeat 只 claim `*.msg.json`
- ACK 与 task_state 不走 DAG 路由；由系统程序跨目录收集归档（见 `doc/develop/07_ack_and_message_state_machine.md` 与 PR-024）
- Human request 不走 DAG 路由；由系统程序投递给 `agent_human_gateway`（见 PR-025）

## Inbox 消费协议（必须写死，避免分叉）

对 `agents/<agent_id>/inbox/<plan_id>/` 下任意“已完成写入的**消息信封**文件”（`*.msg.json` 且非 `.tmp`）：

1. **发现**：只扫描 `inbox/<plan_id>/` 根目录（不扫描 `.pending/.processed/.deadletter`），并且只挑选 `*.msg.json`。
2. **claim**：对候选 envelope 执行原子 move 到 `inbox/<plan_id>/.pending/<original_name>`。
3. **解析**：读取并校验 message_envelope（见 `doc/develop/03_message_envelope_and_identity.md`），得到 `message_id/type/...`。
4. **命名**：把 `.pending/<original_name>` 原子 rename 为 `.pending/<message_id>__<original_name>`（见下文“命名与冲突处理”）。
5. **去重**：
   - 若本地已经存在 `ack_<message_id>.json` 且其 `status` 为 `SUCCEEDED` 或 `FAILED`：视为已处理，直接把消息文件移动到 `.processed/`（不再执行业务）。
   - 若仅存在 `CONSUMED`：视为“曾经开始处理但未完成”，允许恢复处理（避免进程崩溃后永远卡住）。
6. **分发**：
   - `type=command`：进入命令 handler（见下文）。
   - `type=artifact`：进入“输入归档 handler”（见下文）。
   - 其它 `type`：移动到 `.deadletter/`（消费侧 DLQ）并写告警（可选）。

### claim 文件命名与冲突处理（必须写死）

为避免“同名文件覆盖/并发 claim 冲突”的实现分叉，claim 后必须把文件名与 `message_id` 绑定：
- `.pending/<message_id>__<original_name>`

若重命名目标文件已存在：
- 若已存在终态 ACK（`SUCCEEDED/FAILED`）：把当前消息文件直接移入 `.processed/`（视为重复投递）
- 否则：在文件名末尾追加 `__dup_<n>` 后再写入 `.pending/`，并写告警（可选）

## 输入归档（type=artifact，MVP 必须）

目的：让任务的 `wait_for_inputs` 可被稳定实现，不要求业务代码“自己扫 inbox 发明输入缓存”。

最小行为：
- 把 `type=artifact` 的 `payload.files[]` 中列出的文件（或同名伴随文件）原子复制/移动到：
  - `agents/<agent_id>/workspace/<plan_id>/inputs/<task_id>/<output_name>/`
  - 文件来源必须以 envelope 的 `payload.files[].path` 为准：payload 文件应由 Router 与 envelope 一并投递到本 Agent 的 `inbox/<plan_id>/` 根目录（同相对路径/同文件名）。
- 产出/更新本地输入索引（推荐文件）：
  - `agents/<agent_id>/workspace/<plan_id>/inputs/input_index.json`
  - 最小字段：`plan_id`、`entries[] {message_id, task_id, output_name, files[], received_at}`

说明：
- 这里的“task_id/output_name”来自 envelope 顶层字段；这是与 DAG outputs 对齐的唯一稳定键。
- 输入归档成功后，应写 `ack_<message_id>.json status=SUCCEEDED`（表示本 Agent 已“消费并落盘”该输入消息）。
- 约束（与 Router 的“投递顺序”对齐）：payload 文件与 envelope 必须被 Router 一起投递，且 envelope 必须最后出现（见 `doc/develop/04_router_delivery_and_dedup.md`）。

### 归档冲突策略（必须写死）

为了保证输入目录可追溯且不出现“悄悄覆盖”，归档时必须按 `payload.files[].sha256` 做一致性判定：
- 若目标文件不存在：写入。
- 若目标文件已存在且 sha256 相同：视为重复消息/重复附件，允许跳过覆盖，并仍可写 `ack status=SUCCEEDED`。
- 若目标文件已存在但 sha256 不同：视为“同路径不同物”（上游版本语义/路由异常），必须把该消息移入 `.deadletter/` 并产出 `alert.json type=INPUT_CONFLICT`（避免无声分叉）。

### payload 文件的收尾（避免 inbox 堆积）

输入归档成功后，允许把 inbox 根目录中该条消息引用的 payload 文件移动到：
- `inbox/<plan_id>/.processed/_payload/<message_id>/<original_path>`

说明：
- Heartbeat 只 claim `*.msg.json`，因此 payload 文件必须保持在 inbox 根目录，直到对应的 artifact envelope 被处理完毕。
- `original_path` 必须与 envelope 的 `payload.files[].path` 一致（保留相对路径层级，不做扁平化），避免同名文件冲突与审计丢失信息。
- 若 `payload.files[].path` 包含目录层级，必须在 `_payload/<message_id>/` 下按相同层级创建目录后再移动。
- 若移动目标已存在：
  - sha256 相同：允许跳过移动（视为已收尾）
  - sha256 不同：视为异常，进入 `.deadletter/` 并产出 `alert.json type=PAYLOAD_FINALIZE_CONFLICT`

## 命令执行（type=command，MVP 必须）

执行前置：
- 先写 `ack_<message_id>.json status=CONSUMED consumed_at=...`（原子写入；用于“已被 claim 且开始处理”的事实记录）。
- 从命令中判定输入是否满足（MVP 写死）：
  - 若存在 `payload.command.resolved_inputs`：以其为准（权威输入清单）
  - 否则回退到 `payload.command.required_inputs`（兼容字段）
  - 默认只在 `workspace/<plan_id>/inputs/` 与当前任务工作目录下匹配（不再直接依赖 inbox 根目录，避免文件随处理移动导致“输入忽然消失”）。

说明（避免双口径）：
- 即使 DAG v1.1 存在更强的 `inputs[] selector/pick_policy`，执行 Agent 也不应直接读取 DAG（避免跨目录依赖/版本不一致）。
- 若需要使用 selector/pick_policy，必须由规划/控制面角色在生成命令时“编译/解析”为可执行的 `resolved_inputs`；执行侧只消费命令中的“材料清单”。

输入不足时：
- 若 `wait_for_inputs=true`：不执行业务，写入 `task_state` 为 `BLOCKED_WAITING_INPUT`，并把该命令消息文件保留在 `.pending/`（或转移到一个 `.blocked/` 目录，若你们愿意扩展，但必须写死一种）。
- 若 `wait_for_inputs=false`：写入 `ack status=FAILED`（并可附带 `result.details` 指明缺失输入清单），把消息移动到 `.deadletter/`。

超时后的人类介入（必须写死）：
- 当 `wait_for_inputs=true` 且缺输入持续超过 `payload.command.timeout`：
  - 产出 `human_intervention_request.json`（模板：`doc/rule/templates/human_intervention_request.json`），在 `needed.files[]` 中列出“缺失输入清单/说明/敏感性”等（见下方映射规则）；
  - 同时写 `task_state=BLOCKED_WAITING_HUMAN`，并记录 `request_id`（用于 Monitor/Dashboard 关联）；
  - 可额外产出 `alert.json type=WAIT_FOR_INPUTS_TIMEOUT`（用于告警面板）。
说明：
- `human_intervention_request.json` 写入 `agents/<agent_id>/outbox/<plan_id>/human_intervention_request_<request_id>.json`，不依赖 DAG 路由投递，由系统程序收集并投递到 `agent_human_gateway`（见 PR-024/PR-025）。
- `alert.json` 写入 `agents/<agent_id>/outbox/<plan_id>/alert_<alert_id>.json`，由系统程序收集归档到 `system_runtime/alerts/<plan_id>/`（见 PR-024）。

### started_at 与超时计时规则（必须写死，避免分叉）

为保证“等待输入超时”在重启/恢复后依然可判定，写死如下规则：

- 当命令第一次进入 `BLOCKED_WAITING_INPUT` 时，Agent 必须在 `task_state.blocking.started_at` 写入一个 ISO 8601 时间戳（UTC，建议 `Z` 结尾）。
  - 该 `started_at` 表示“本命令开始等待输入”的起点，不等同于 envelope.created_at，也不等同于 ack.consumed_at。
- 后续每次心跳循环如果仍缺输入：
  - **不得**覆盖/重置 `blocking.started_at`（否则会导致永远不超时）
  - 只更新 `task_state.updated_at`（表示仍在等待/仍被检查）
- 超时判定：
  - `waited_seconds = now - blocking.started_at`
  - 若 `waited_seconds >= payload.command.timeout`：必须触发 Human 介入（产出 `human_intervention_request_*`、写 `BLOCKED_WAITING_HUMAN`、可选告警）
- 重启是否延续：
  - **必须延续**：Agent 重启后恢复扫描 `.pending/` 时，应优先读取已有 `task_state.blocking.started_at` 继续计时；不得因为重启而清零。
  - 若 `task_state` 丢失/损坏无法读取：允许回退使用 envelope.created_at 作为 `started_at`（但必须写一次告警 `alert type=TASK_STATE_CORRUPT_FALLBACK`，避免静默分叉）。

### 缺输入清单 → Human request 的映射规则（必须写死）

当命令缺输入时，必须能无歧义地产生 `human_intervention_request.needed.files[]`：

- 若存在 `payload.command.resolved_inputs`：
  - 对每个缺失且 `required=true` 的 item，追加一条 `needed.files[]`：
    - `name`：取 `paths[0]`
    - `description`：取 `description`，若为空则 `Required input: <input_name>`
    - `sensitivity`：取 `sensitivity`，若为空则 `"UNKNOWN"`
    - `deliver_to_agent_id`：允许留空/省略；Human Gateway 可按 plan 角色/上下文补齐或由人类选择（该字段不作为 schema 必填）
- 若仅有 `required_inputs`：
  - 对每个缺失文件名，追加一条 `needed.files[]`：
    - `name=<missing_file_name>`
    - `description="Required input file"`
    - `sensitivity="UNKNOWN"`

输入满足时：
- 执行 handler（由单一职责 Agent 的提示词/业务模块实现）。
- 执行结束必须把 ACK 升级为终态：
  - 成功：`status=SUCCEEDED finished_at=...`
  - 失败：`status=FAILED finished_at=...`（可附错误摘要）
- 最终把消息文件移动到 `.processed/`（无论成功/失败都必须归档，避免 inbox 堆积）。

## 阻塞与恢复（wait_for_inputs 的闭环，必须写死）

为避免“命令进入 `.pending/` 后永远不再被检查”的实现缺陷，Heartbeat 每轮必须额外执行：
- 扫描 `inbox/<plan_id>/.pending/` 中**未终态**的 `type=command` envelope（`*.msg.json`）：
  - 若此前因缺输入而 `BLOCKED_WAITING_INPUT`：重新判定输入是否满足；满足则继续执行并写终态 ACK。
  - 若进程崩溃导致只留下 `ack status=CONSUMED`：允许恢复执行（幂等由业务侧输出契约 + Router 去重保证）。

### 公平性与限流（必须写死）

每轮心跳必须按固定顺序处理，避免“阻塞任务霸占循环”或“新消息永远得不到处理”：
1. 优先处理 inbox 根目录新到的 envelope（最多 `max_new_messages_per_tick` 条，默认 50）
2. 再恢复检查 `.pending/` 中的阻塞/未终态命令（最多 `max_resume_messages_per_tick` 条，默认 10）

### 扫描顺序（必须写死）

为保证可重复性与跨平台一致性：
- inbox 根目录候选文件按文件名升序排序后再依次 claim。
- `.pending/` 恢复候选文件按文件名升序排序后再依次检查。

超时告警建议：
- 单条命令若 `CONSUMED` 后超过 `payload.command.timeout * 2` 仍未出现终态 ACK：写告警/请求人工介入（具体由 Monitor/PR-010 触发）

## ACK 文件口径（必须写死）

模板：`doc/rule/templates/ack.json`

约束：
- 文件名：`ack_<message_id>.json`（写入 `agents/<agent_id>/outbox/<plan_id>/`，由系统程序收集/展示）
- 允许两阶段更新：先 `CONSUMED`，后覆盖为 `SUCCEEDED/FAILED`（覆盖必须使用 tmp→rename，保证原子性）
- 终态不可回退：一旦写成 `SUCCEEDED/FAILED`，不得再改回 `CONSUMED`

补充（权威源口径）：
- 系统程序应把 ACK 归档到 `system_runtime/plans/<plan_id>/acks/`，Monitor/Dashboard 优先以该目录为权威源（见 `doc/develop/07_ack_and_message_state_machine.md` 与 PR-024）。

## 心跳与健康快照（必须写死）

目的：让系统监控不需要“猜测每个 Agent 的状态文件在哪里/叫什么”。

最小快照文件（建议）：
- 路径：`agents/<agent_id>/status_heartbeat.json`
- 最小字段建议包含：`agent_id`、`last_heartbeat`、`health`、`current_plan_ids[]`、`current_task_ids[]`、`last_error`

说明：
- 这是**本 Agent 自己写**的状态快照；系统程序（PR-024/PR-025）只读采集并汇总到 `system_runtime/agent_status/`。
- 模板/Schema：
  - `doc/rule/templates/status_heartbeat.json`
  - `doc/rule/templates/schemas/status_heartbeat.schema.json`

## task_state（任务状态快照，推荐但不强制）

若 Agent 希望让 Monitor/Dashboard 更准确地展示状态（特别是 BLOCKED/RUNNING 的原因），建议额外输出任务状态快照：
- 文件名：`task_state_<task_id>.json`
- 写入位置：`agents/<agent_id>/outbox/<plan_id>/`
- 模板/Schema：
  - `doc/rule/templates/task_state.json`
  - `doc/rule/templates/schemas/task_state.schema.json`

## Pytest

建议至少覆盖以下集成用例（均使用 `tmp_path` 构造 `agents/<agent_id>/...` 目录树）：

- 只处理 envelope：inbox 同时存在 payload 文件与 `*.msg.json`，Heartbeat 只 claim `*.msg.json`，不误搬 payload。
- 两阶段命名：claim→解析→rename 为 `<message_id>__<original_name>`；rename 冲突时追加 `__dup_<n>` 且不覆盖原文件。
- ACK 两阶段：开始处理写 `CONSUMED`，结束覆盖为 `SUCCEEDED/FAILED`；终态不可回退（再次执行不得改回 CONSUMED）。
- 崩溃恢复：仅存在 `ack status=CONSUMED` 的命令，重启后可恢复执行并写终态 ACK。
- wait_for_inputs 阻塞恢复：缺输入→`task_state=BLOCKED_WAITING_INPUT`；输入（artifact）到达后同一命令从 `.pending/` 被恢复并最终 `SUCCEEDED`。
- wait_for_inputs 超时→Human：超过 `payload.command.timeout` 后产出 `human_intervention_request_<request_id>.json` + `task_state=BLOCKED_WAITING_HUMAN`；可选产出 `alert_<alert_id>.json`。
- artifact 归档冲突：同路径不同 sha256 → `.deadletter/` + `alert type=INPUT_CONFLICT`；同 sha256 重复 → 允许跳过覆盖但仍写 ACK=SUCCEEDED。
- 公平性/限流：`max_new_messages_per_tick` 与 `max_resume_messages_per_tick` 生效（不会因 `.pending/` 恢复而饿死新消息）。
- payload 收尾：artifact 归档完成后 payload 文件被移动到 `.processed/_payload/<message_id>/...`，且不影响审计（保留原相对路径信息）。

## 与目录协议的对齐（必须）

本模块必须遵循 `doc/develop/02_storage_layout_and_atomic_io.md` 的 inbox 子目录协议：
- 只从 `inbox/<plan_id>/` 根目录挑选待处理文件
- claim 后移动到 `.pending/`
- 处理完成移动到 `.processed/`
- 无法解析/校验失败移动到 `.deadletter/` 并产出告警/请求
