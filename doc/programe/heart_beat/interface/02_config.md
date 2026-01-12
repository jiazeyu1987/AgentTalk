# 02 配置接口（heartbeat_config.json）

## 文件

- 路径：`agents/<agent_id>/heartbeat_config.json`
- 模板：`doc/rule/templates/heartbeat_config.json`
- Schema：`doc/rule/templates/schemas/heartbeat_config.schema.json`

## 关键字段

- `agent_id`
- `poll_interval_seconds`
- `max_new_messages_per_tick` / `max_resume_messages_per_tick`
- `plans.scan_mode`：`auto | allowlist_only`
- `plans.allowlist`
- `schema_validation.enabled`
- `schema_validation.schemas_base_dir`（相对路径时以 config 文件所在目录为基准）

## Pytest

- `tests/test_interfaces.py::test_load_config_validates_and_resolves_schema_dir`

