# AgentTalk基础原则索引

**最后更新**: 2025-01-08

---

## 原则分类

### 核心机制 (PR-001 ~ PR-009, PR-017 ~ PR-026)

1. [PR-001: 唯一的交互方式：inbox/outbox文件传递](./001_inbox_outbox_file_transfer.md)
2. [PR-002: 文件传递由任务文件规定](./002_file_transfer_defined_by_task.md)
3. [PR-003: 安全原则：每个Agent只能访问自己的文件夹](./003_agent_folder_isolation.md)
4. [PR-004: Plan级文件组织](./004_plan_level_organization.md)
5. [PR-005: 文件所有权和责任](./005_file_ownership.md)
6. [PR-006: 文件名保持原样](./006_filename_preservation.md)
7. [PR-007: 统一的执行命令](./007_unified_execute_command.md)
8. [PR-008: Agent文件夹结构](./008_agent_folder_structure.md)
9. [PR-009: 任务分配机制](./009_task_distribution_mechanism.md)
10. [PR-017: 日志追踪机制](./017_logging_traceability.md)
11. [PR-018: visibility_list文件格式](./018_visibility_list_format.md)
12. [PR-019: Claude Code调用机制](./019_claude_code_invocation.md)
13. [PR-020: 命令完整性保证机制](./020_command_integrity.md)
14. [PR-021: Agent能力自评机制](./021_agent_self_assessment.md)
15. [PR-022: 链式验证机制](./022_chain_validation.md)
16. [PR-023: 并发控制机制](./023_concurrency_control.md)
17. [PR-024: 系统路由与状态监控机制](./024_shared_folder_monitoring.md)
18. [PR-025: Agent生命周期管理和Plan监控机制](./025_agent_lifecycle_plan_monitoring.md)
19. [PR-026: Agent发现和手动配置机制](./026_agent_discovery_manual_configuration.md)

### 轮询机制 (PR-010 ~ PR-011)

19. [PR-010: 超时保护机制](./010_timeout_protection.md)
20. [PR-011: 统一的轮询工作方式](./011_unified_polling_mechanism.md)

### 性能与扩展性 (PR-014 ~ PR-016)

22. [PR-014: 性能优化策略](./014_performance_optimization.md)
23. [PR-015: 资源效率控制](./015_resource_efficiency.md)
24. [PR-016: 可扩展的架构](./016_extensible_architecture.md)

---

## 原则编号规则

原则编号格式: `PR-XXX`

- PR-001 ~ PR-099: 核心机制和基础原则
- PR-100 ~ PR-199: 事件处理相关
- PR-200 ~ PR-299: 轮询机制相关
- PR-300 ~ PR-399: 安全和可靠性
- PR-400 ~ PR-499: 性能优化
- PR-500 ~ PR-599: 扩展性设计

---

## 使用说明

### 查阅原则

1. 根据类别浏览上方的索引
2. 点击原则名称查看详细内容
3. 每个原则文件包含：
   - 原则ID
   - 来源文档
   - 类别
   - 原则描述
   - 详细说明
   - 关键要点
   - 典型应用

### 使用模板（推荐）

为避免“概念一致但落盘格式不一致”，`doc/rule/templates/` 提供一组可复用的JSON模板（消息信封、命令、DAG、plan清单、回执、告警、死信）。

- 模板索引：`doc/rule/templates/README.md`
- 评审与验收模板：`doc/rule/templates/dag_review_result.json`、`doc/rule/templates/artifact_validation_result.json`
- 发布门禁与放行模板：`doc/rule/templates/build_validation_result.json`、`doc/rule/templates/deploy_validation_result.json`、`doc/rule/templates/smoke_test_result.json`、`doc/rule/templates/e2e_test_result.json`、`doc/rule/templates/security_scan_result.json`、`doc/rule/templates/release_manifest.json`
- 人类介入模板：`doc/rule/templates/human_intervention_request.json`、`doc/rule/templates/human_intervention_response.json`

### 新增原则

当需要新增原则时：

1. 确定原则类别
2. 分配原则编号（PR-XXX）
3. 创建原则文件（格式参考现有文件）
4. 更新本索引文件
5. 在相关文档中引用该原则

---

## 原则之间关系

```
核心机制 (PR-001 ~ PR-009, PR-017 ~ PR-026)
    ↓
轮询机制 (PR-010 ~ PR-011)
    ↓
性能与扩展性 (PR-014 ~ PR-016)
```

- **核心机制**定义了AgentTalk系统的基础架构、交互方式、执行命令、文件夹结构、任务分配、日志追踪、能力声明、Claude Code集成、命令完整性、能力自评、链式验证、并发控制、系统路由与状态监控、Agent生命周期管理和Agent发现配置
- **轮询机制**是Agent的工作方式，扫描inbox并处理执行命令
- **性能与扩展性**确保系统高效运行和易于扩展

---

## 相关文档

- [文件传输机制](../file_transfer_mechanism.md)
- [Agent审查和等待机制](../agent_review_and_wait_mechanism.md)
- [Agent事件处理机制](../agent_event_handling_mechanism.md)

## Examples

- 端到端目录快照：`doc/rule/examples/README.md`
