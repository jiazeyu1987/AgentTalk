# MVP 系统开发计划（模块化 + Pytest 可验证）

本目录从系统架构师视角给出 AgentTalk MVP 的模块化开发计划。目标是：
- 先把“文件即消息”的最小闭环跑通（inbox/outbox、路由、命令执行、状态汇总）
- 每个模块都有独立的 pytest 测试策略（单元/集成），可在本地稳定验证

模块列表（每个模块单独文件）：
- `doc/develop/00_architecture_overview.md`
- `doc/develop/01_schema_validation.md`
- `doc/develop/02_storage_layout_and_atomic_io.md`
- `doc/develop/03_message_envelope_and_identity.md`
- `doc/develop/04_router_delivery_and_dedup.md`
- `doc/develop/05_agent_heartbeat_and_dispatch.md`
- `doc/develop/06_command_execution_pipeline.md`
- `doc/develop/07_ack_and_message_state_machine.md`
- `doc/develop/08_plan_status_aggregation.md`
- `doc/develop/09_deadletter_and_alerts.md`
- `doc/develop/10_human_gateway_flow.md`
- `doc/develop/11_release_gates_and_manifest.md`
- `doc/develop/12_observability_and_traceability.md`
- `doc/develop/13_end_to_end_scenarios.md`
- `doc/develop/14_web_dashboard_viewer.md`

建议执行顺序：02 → 01 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 14 → 13

（实现对齐建议）：当 03–12 的核心链路已落地后，再补 13（端到端 pytest 场景集合）用于“总验收”，最后再扩展 14（Dashboard 的展示细节与可观测性口径）。
