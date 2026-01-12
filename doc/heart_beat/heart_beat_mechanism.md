# 心跳与事件循环机制说明

## 机制用途

心跳/事件循环是 Agent 的运行核心，用于持续扫描 inbox、原子认领消息、判断输入是否满足、调度
skill/handler 执行任务、写 ACK 与状态，并驱动 IDLE/DORMANT 生命周期切换。

## 注意事项

- 必须原子认领，避免并发重复处理或丢消息。
- 必须做幂等去重（主键：message_id + sha256；idempotency_key 仅用于审计与可读关联）。
- 缺少必需输入时必须阻塞，严禁“假执行”或臆造。
- 每条消息隔离处理，单条异常不能拖垮主循环。
- 严格遵守文件隔离与文件传递规则（PR-001/PR-003）。
- 每轮处理设上限，避免拥塞导致饥饿。

## 输入

1) Inbox 消息
   - `inbox/<plan_id>/` 下的 payload 文件
   - 需要时的信封文件（message envelope）
   - 命令文件（`*.cmd.json`）

2) 计划与策略
   - `task_dag.json`：依赖、输入选择、输出投递、失败策略
   - `plan_manifest.json`：全局策略（重试、门禁、发布规则）

3) 运行期信号
   - DORMANT 状态下的唤醒信号
   - 系统下发的重试/重规划请求（若路由至该 Agent）

## 输出

1) ACK 与状态
   - `ack_<message_id>.json`：记录 CONSUMED/SUCCEEDED/FAILED 等状态
   - `task_state_<task_id>.json` 或 workspace trace 状态
   - `agent_state.json`：心跳与生命周期状态

2) 产出文件
   - 写入 `outbox/<plan_id>/` 的输出 payload
   - 可选的 envelope/metadata 文件

3) 异常与升级
   - `.deadletter/` 死信条目
   - 阻塞时的告警或 `human_intervention_request.json`

## 接口

1) 文件系统接口（主接口）
   - 读取：`inbox/`, `task_dag.json`, `plan_manifest.json`
   - 写入：`outbox/`, `ack_*.json`, 日志/trace, 任务状态, DLQ 条目

2) Skill/handler 调度接口
   - 输入：解析后的消息 + 解析后的 inputs + 任务上下文
   - 输出：产物文件 + 执行状态 + 证据文件

3) 监控接口
   - 输出心跳时间戳与任务推进状态供系统监控汇总
