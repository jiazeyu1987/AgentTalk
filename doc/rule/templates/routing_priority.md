# Routing Priority（路由匹配优先级与默认行为）

本文件定义当 `task_dag.json` 同时存在 `nodes[].outputs[].deliver_to` 与 `routing_rules[]` 时，系统路由程序应如何确定最终投递目标，并规定未命中时的处理策略。

适用范围：
- 系统路由程序（PR-024）
- DAG/路由表（PR-002/PR-009，模板 `task_dag.json`）

## 1. 路由来源

系统路由程序可以从两处获得“投递目标”：

1. **显式目标**：`nodes[].outputs[].deliver_to`
2. **规则匹配**：`routing_rules[]`

## 2. 优先级规则（必须）

当两者同时存在时，按以下优先级计算最终 `deliver_to`：

1. **显式目标优先**：如果输出对象包含 `deliver_to` 且非空，则使用该列表作为最终目标。
2. **规则匹配兜底**：仅当 `deliver_to` 缺失或为空时，才使用 `routing_rules` 进行匹配计算。

理由：避免运行期“规则覆盖显式声明”造成不可预期投递。

## 3. routing_rules 的匹配顺序（必须）

当进入“规则匹配兜底”时：

- 按 `routing_rules` 的数组顺序自上而下匹配
- 取**第一条命中**作为结果（first-match-wins）

## 4. match字段约定（推荐最小集合）

为避免实现分叉，推荐 `match` 支持以下字段（任意子集）：
- `output_name`：完全匹配输出文件名（推荐最常用）
- `content_type`：MIME类型匹配
- `tag`：输出标签匹配（若你们后续引入标签体系）

## 5. 未命中/无目标时的默认行为（必须）

若最终无法得到非空 `deliver_to`：

- 将该输出对应的消息写入 `system_runtime/deadletter/<plan_id>/`
- 生成一条告警（`alert.json` 模板），类型建议为 `ROUTING_NO_TARGET`

不允许静默丢弃（silent drop）。

