# Schema Versioning（版本与兼容策略）

本文件定义 `schema_version` 的版本规则，用于保证不同Agent与系统路由/监控程序对JSON文件的解析一致、可升级、可回滚。

适用范围（所有结构化文件）：
- 执行命令：`cmd_*.json`（见 `command.cmd.json`）
- 消息信封：`*.msg.json` / `*.meta.json`（见 `message_envelope.msg.json`）
- DAG/路由表：`task_dag.json`
- Plan清单：`plan_manifest.json`
- 回执：`ack_*.json`
- 告警：`alert_*.json`
- 死信条目：`deadletter_entry.json`

## 版本号格式

- `schema_version` 使用语义化版本：`MAJOR.MINOR`（例如 `1.0`、`1.1`、`2.0`）
- 不使用补丁号（Patch）。补丁级变更仅限**文档修正/示例修正**，不改变Schema。

## 兼容性规则

### 向后兼容（MINOR增加）

允许的变更（接收方无需升级即可安全忽略）：
- 新增可选字段
- 为枚举新增值（前提：接收方对未知值有降级/忽略策略）
- 放宽校验（例如允许null/空数组）

禁止的变更：
- 改变已有字段含义
- 改变已有字段类型
- 将可选字段改为必需字段

### 不兼容（MAJOR增加）

发生以下任一情况必须提升MAJOR：
- 删除字段
- 字段类型变化（string→object等）
- 字段语义变化（同字段不同含义）
- 必填字段集合变化
- 路由/状态机行为变化导致旧实现产生错误动作

## 处理未知版本

接收方（Agent或系统程序）对未知/不支持版本必须采取确定性行为：

- **不支持的MAJOR**：进入死信（`inbox/<plan_id>/.deadletter/` 或 `system_runtime/deadletter/<plan_id>/`），并生成告警（见 `alert.json`）。
- **更高的MINOR**：允许尝试解析；若缺少关键字段或校验失败则进入死信并告警。

## 字段扩展约定

为减少破坏性变更，建议：
- 新增字段尽量放在新对象下（例如 `routing.*`、`correlation.*`、`policies.*`）
- 保留未知字段（不要在转发/归档时丢弃），以便链路端到端保留信息

## 与JSON Schema的关系

`doc/rule/templates/schemas/` 提供对应的JSON Schema文件，用于自动校验：
- 生产方在写入前校验
- 消费方在处理前校验（失败→deadletter）
- 系统路由在投递/归档前校验（失败→deadletter + alert）

