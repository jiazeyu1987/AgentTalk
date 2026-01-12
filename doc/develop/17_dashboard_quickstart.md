# 17 Dashboard（MVP Quickstart）

本文件说明如何运行 `14_web_dashboard_viewer.md` 对应的 Dashboard API（只读）。

## 依赖

- Python `>=3.10`
- 安装依赖：`python -m pip install -e .`

## 运行

`python agenttalk_dashboard.py --system-runtime system_runtime --host 127.0.0.1 --port 8000`

打开：
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/api/plans`

## 最小验证（无需真实跑 Router/Monitor/Heartbeat）

准备一个最小目录树（示例 plan_id=plan_1）：
- `system_runtime/plans/plan_1/plan_status.json`
- `system_runtime/plans/plan_1/deliveries.jsonl`
- `system_runtime/plans/plan_1/decisions/*.json`
- `system_runtime/plans/plan_1/acks/*.json`
- `system_runtime/plans/plan_1/release_manifest.json`
- `system_runtime/agent_status/agent_a.json`

启动 Dashboard 后用 API 验证：
- `GET /api/plans`
- `GET /api/plans/plan_1/status`
- `GET /api/plans/plan_1/deliveries?limit=50&offset=0`
- `GET /api/plans/plan_1/decisions`
- `GET /api/plans/plan_1/acks`
- `GET /api/plans/plan_1/release_manifest`
- `GET /api/agents`、`GET /api/agents/agent_a`

## 测试

`python -m pytest -k dashboard`
