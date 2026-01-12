# 03 Handler 插件接口（handler-module）

## 目的

把“单职责业务逻辑”与 Heartbeat 框架解耦：Heartbeat 负责消费/归档/ACK/阻塞；业务由 handler 实现。

## 约定

CLI 参数：`--handler-module <module>`

模块必须暴露一个名为 `handler` 的对象，且支持：

- `handle_command(envelope: dict, command: dict, context: dict) -> CommandResult`

其中 `CommandResult` 语义：

- `ok=True`：Heartbeat 写 `ack=SUCCEEDED` + `task_state=COMPLETED`
- `ok=False`：Heartbeat 写 `ack=FAILED` + `task_state=FAILED`

## Pytest

- `tests/test_interfaces.py::test_load_handler_requires_handler_object`

