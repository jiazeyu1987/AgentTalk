# 13 端到端场景（pytest 集成用例集合）

## 场景A：最小链路

- agentA 收到 cmd → 产出 output → router 投递给 agentB → agentB ACK

对应用例：`tests/test_end_to_end_command_to_delivery.py`

## 场景B：等待输入

- cmd wait_for_inputs=true，先缺输入 → BLOCKED
- 后补输入文件 → 自动执行 → SUCCEEDED

对应用例：`tests/test_heartbeat.py`（wait_for_inputs）

## 场景C：评审→修订→再评审→放行→执行

- reviewers 产出 dag_review_result（按模板）
- review coordinator 汇总放行
- 才投递执行命令

MVP 落盘要求（避免口径分叉）：
- reviewer 输出 `dag_review_result.json`（模板：`doc/rule/templates/dag_review_result.json`）
- coordinator 必须输出 `decision_record.json decision_type=DAG_REVIEW`（模板：`doc/rule/templates/decision_record.json`）
- Router 归档 decision_record 到 `system_runtime/plans/<plan_id>/decisions/`

对应用例（最小链路：评审两轮→发布门禁→归档）：`tests/test_end_to_end_review_revision_release_flow.py`

## 场景D：Human Gateway

- 缺外部材料 → request → response → 解除阻塞

对应用例：`tests/test_human_gateway_flow.py`

## Pytest 结构建议

- `tests/unit/`：纯函数/解析/判定
- `tests/integration/`：router/agent/monitor 在 tmp_path 下跑一轮或多轮
