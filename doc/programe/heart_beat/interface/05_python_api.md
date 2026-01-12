# 05 Python API 接口（agenttalk.heartbeat）

## 可调用函数

- `agenttalk.heartbeat.tick_plan(ctx, plan_id)`：对单个 plan 执行一轮处理（不 sleep）
- `agenttalk.heartbeat.run_once(ctx)`：发现 plans → 写 `status_heartbeat.json` → 逐 plan tick 一轮
- `agenttalk.heartbeat.discover_plans(ctx)`：按配置发现计划列表
- `agenttalk.heartbeat.run_forever(...)`：常驻进程
- `agenttalk.heartbeat.load_handler(module)`：加载 handler 插件

## Pytest

- `tests/test_interfaces.py::test_run_once_writes_status_heartbeat`

