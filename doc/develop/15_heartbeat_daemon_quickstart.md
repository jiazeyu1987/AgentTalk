# 15 Heartbeat 独立程序（MVP Quickstart）

本文件说明如何基于 `doc/develop/05_agent_heartbeat_and_dispatch.md` 的契约实现/运行一个独立 Heartbeat 程序。

## 依赖

- Python `>=3.10`
- 依赖安装：
  - 运行：`python -m pip install -e .`
  - 测试：`python -m pip install -r requirements-dev.txt`

## 目录准备（单个 Agent）

```
agents/
  <agent_id>/
    inbox/
      <plan_id>/
    outbox/
      <plan_id>/
    workspace/
      <plan_id>/
    heartbeat_config.json
```

配置文件参考模板：
- `doc/rule/templates/heartbeat_config.json`

说明：
- `status_heartbeat.json` 不需要预先创建；Heartbeat 每个 tick 会自动写入 `agents/<agent_id>/status_heartbeat.json`。
- `inbox/<plan_id>/.pending/.processed/.deadletter` 等子目录由 Heartbeat 自己创建与维护；系统路由程序只会写 `inbox/<plan_id>/` 根目录。

## 启动

从仓库根目录运行：

`python agenttalk_heartbeat.py --agent-root agents/<agent_id>`

可选参数：
- `--config agents/<agent_id>/heartbeat_config.json`
- `--schemas-base-dir doc/rule/templates/schemas`
- `--handler-module <python_module_name>`（模块内需暴露 `handler` 对象，提供 `handle_command(...)`）

注意（避免配置分叉）：
- `--schemas-base-dir` 仅用于“读取/校验 heartbeat_config.json”；真正用于校验消息的 schema 目录以 `heartbeat_config.json.schema_validation.schemas_base_dir` 为准（该路径按 config 文件所在目录 resolve）。

## 最小验证

- 准备一个 plan 目录（Heartbeat 扫描到 plan_id 的前提）：
  - `mkdir agents/<agent_id>/inbox/<plan_id>`
- 放入一条命令消息（建议直接用模板改字段）：
  - 模板：`doc/rule/templates/command_envelope.msg.json`
  - 保存为：`agents/<agent_id>/inbox/<plan_id>/cmd_001.msg.json`
- Heartbeat 处理后应出现：
  - `agents/<agent_id>/outbox/<plan_id>/ack_<message_id>.json`（默认 handler 会写 `SUCCEEDED`）
- 产物消息 `*.msg.json`（`type=artifact`）进入 `inbox/<plan_id>/` 后：
  - Heartbeat 会把 payload 文件归档到 `workspace/<plan_id>/inputs/...`
  - 更新 `workspace/<plan_id>/inputs/input_index.json`

可选：验证“产出文件+artifact envelope”的链路（用于联调 Router）
- 使用 `--handler-module agenttalk.command_runner.dummy_handler`
- 在 command 的 `payload.command.produces[]` 中声明要产出的文件（见 `doc/rule/templates/command.cmd.json`）

可选：验证 wait_for_inputs → Human 介入（不依赖 Router/Monitor）
- 在命令里设置：
  - `payload.command.wait_for_inputs=true`
  - `payload.command.required_inputs` 填入一个当前不存在的文件名（例如 `requirements.md`）
  - `payload.command.timeout` 设置一个较小值（例如 `5`）
- Heartbeat 将先写：
  - `agents/<agent_id>/outbox/<plan_id>/ack_<message_id>.json status=CONSUMED`
  - `agents/<agent_id>/outbox/<plan_id>/task_state_<task_id>.json state=BLOCKED_WAITING_INPUT`
- 当等待时间超过 timeout 后，将额外写：
  - `agents/<agent_id>/outbox/<plan_id>/human_intervention_request_<request_id>.json`
  - `agents/<agent_id>/outbox/<plan_id>/task_state_<task_id>.json state=BLOCKED_WAITING_HUMAN`

## 测试

`python -m pytest`
