# JSON Schemas

本目录提供 `doc/rule/templates/` 中各模板的 JSON Schema（draft 2020-12），用于自动校验：

- 生产方写入前校验
- 消费方处理前校验（失败→deadletter）
- 系统路由投递/归档前校验（失败→deadletter + alert）

文件列表：
- `message_envelope.schema.json`
- `command.schema.json`
- `task_dag.schema.json`
- `plan_manifest.schema.json`
- `plan_status.schema.json`
- `ack.schema.json`
- `alert.schema.json`
- `deadletter_entry.schema.json`
- `delivery_log_entry.schema.json`
- `active_dag_ref.schema.json`
- `decision_record.schema.json`
- `task_state.schema.json`
- `status_heartbeat.schema.json`
- `heartbeat_config.schema.json`
- `input_index.schema.json`
- `dag_review_result.schema.json`
- `artifact_validation_result.schema.json`
- `build_validation_result.schema.json`
- `deploy_validation_result.schema.json`
- `smoke_test_result.schema.json`
- `e2e_test_result.schema.json`
- `security_scan_result.schema.json`
- `release_manifest.schema.json`
- `human_intervention_request.schema.json`
- `human_intervention_response.schema.json`

提示：投递日志通常为 `deliveries.jsonl`（每行一个 `delivery_log_entry`）。
