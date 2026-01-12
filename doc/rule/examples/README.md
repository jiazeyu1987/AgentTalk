# Examples（端到端样例）

本目录给出“只用文件传递”的端到端目录快照样例，减少实现歧义。

## Example A：DAG流水线成功完成

**规划者（GM）输出（概念）**
- `task_dag.json`：见 `doc/rule/templates/task_dag.json`
- `plan_manifest.json`：见 `doc/rule/templates/plan_manifest.json`
- 命令消息：`cmd_*.msg.json`（envelope `type=command`，见 `doc/rule/templates/command_envelope.msg.json`）

**DAG评审关口（属于“方案生成→多人评审→修订→再评审→放行”的通用流程一环）**
- 规划者投递 `dag_review_request.cmd.json` 给专家评审角色（见 `doc/rule/templates/dag_review_request.cmd.json`）
- 专家输出 `dag_review_result.json`（APPROVE/REVISE/REJECT，见 `doc/rule/templates/dag_review_result.json`）
- 仅当APPROVE后，再投递执行命令给各执行Agent

**目录快照（简化）**

```
agents/
  agent_backend_developer/
    inbox/
      plan_a3f5b2c8/
        cmd_task_003_001.json
        requirements.md
        database_schema.json
    outbox/
      plan_a3f5b2c8/
        msg_20250108T103000Z_0001/
          backend_package.zip
          message.meta.json            # 同结构于 message_envelope.msg.json

  agent_testing_engineer/
    inbox/
      plan_a3f5b2c8/
        msg_20250108T103000Z_0001/
          backend_package.zip
          message.meta.json
    outbox/
      plan_a3f5b2c8/
        ack_msg_20250108T103000Z_0001.json
        artifact_validation_result.json    # PASS/REJECT（见模板）
        tested_backend_report.json
```

**系统运行目录（简化）**

```
system_runtime/
  plans/
    plan_a3f5b2c8/
      task_dag.json
      plan_manifest.json
      plan_status.json
      deliveries.jsonl                # 每行一条，见 delivery_log_entry.json
  artifacts/
    plan_a3f5b2c8/
      build_validation_result.json
      deploy_validation_result.json
      smoke_test_result.json
      e2e_test_result.json
      security_scan_result.json
      release_manifest.json
      tested_backend_report.json
```

## Example B：路由缺失进入死信 + 修复后回放

**问题**
- 某输出没有 `deliver_to`，且 `routing_rules` 未命中 → 系统路由无法确定目标

**系统处理**
- 写入 `system_runtime/deadletter/<plan_id>/...`
- 生成 `alert.json`（type=ROUTING_NO_TARGET）

**修复与回放**
- 修复 `task_dag.json`（补充 deliver_to 或 routing_rules）
- 按 `doc/rule/templates/replay_procedure.md` 回放

```
system_runtime/
  deadletter/
    plan_a3f5b2c8/
      dlq_20250108T104000Z_0001.json   # 结构见 deadletter_entry.json
  plans/
    plan_a3f5b2c8/
      replay_requests.jsonl
      deliveries.jsonl                 # 回放会产生新的delivery_id
```

## Example C：重复投递被去重（幂等）

**场景**
- 生产方重复写入同一 `message_id`（或同一 `idempotency_key`）的消息

**系统处理**
- 以 `message_id + sha256` 为主去重键（`idempotency_key` 仅用于审计与可读关联）
- 在 `deliveries.jsonl` 记录 `SKIPPED_DUPLICATE`（重复消息去重）与 `SKIPPED_SUPERSEDED`（旧命令丢弃）
- 不再次投递到目标inbox

## Example D：缺外部文件/标准 → Human Gateway介入

**场景**
- 发布工程师缺少 `.env.staging` 或缺少“安全扫描高危是否可接受”的决策

**系统处理**
- 生成 `human_intervention_request.json` 并投递给 `agent_human_gateway`

```
agents/
  agent_human_gateway/
    inbox/
      plan_a3f5b2c8/
        human_intervention_request.json
    outbox/
      plan_a3f5b2c8/
        human_intervention_response.json
        .env.staging
```

**路由解除阻塞**
- 系统路由按 `human_intervention_response.json.provided_files[].deliver_to_agent_id` 投递文件到目标Agent inbox
- 目标Agent收到后继续执行发布门禁/测试

模板参考：
- `doc/rule/templates/human_intervention_request.json`
- `doc/rule/templates/human_intervention_response.json`
