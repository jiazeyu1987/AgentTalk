# 11 发布门禁与 release_manifest 模块

## 目标

实现“可发布”判定：
- 汇总 required gates 的证据文件（build/deploy/smoke/e2e/security 等）
- 由 Release Coordinator 产出 `release_manifest.json decision=APPROVE|REJECT`（并同时产出 `decision_record.json decision_type=RELEASE` 作为审计时间线）

## 输入与证据来源（MVP 约定）

- `plan_manifest.json`（控制面）：`system_runtime/plans/<plan_id>/plan_manifest.json`
  - 发布门禁的 required gates 来源：`plan_manifest.json.policies.release_gates_required[]`
  - 约定：该列表中若包含 `release_manifest.json` / `decision_record.json`（自举项），Release Coordinator 在判定时必须忽略这两项（否则形成循环依赖）。
- 门禁证据文件（数据面）：由各验证 Agent 产出并投递到 Release Coordinator，最终落在 Release Coordinator 的 workspace inputs：
  - `agents/<release_coordinator_id>/workspace/<plan_id>/inputs/input_index.json`（用于定位文件存储路径）
  - 证据文件示例：`build_validation_result.json`、`smoke_test_result.json` 等（模板见 `doc/rule/templates/`）

## 输出与归档（避免 Monitor/Dashboard 分叉）

### Release Coordinator 输出（写入 agent outbox）

- `agents/<release_coordinator_id>/outbox/<plan_id>/release_manifest_<release_id>.json`
- `agents/<release_coordinator_id>/outbox/<plan_id>/decision_record_<decision_id>.json`（`decision_type=RELEASE`）

### 系统归档（Router 收集；不走 DAG 路由）

- 历史归档：
  - `system_runtime/plans/<plan_id>/releases/release_manifest_<release_id>.json`
  - `system_runtime/plans/<plan_id>/decisions/decision_record_<decision_id>.json`
- 最新指针（Dashboard/外部读取的权威入口）：
  - `system_runtime/plans/<plan_id>/release_manifest.json`（指向最新 created_at 的 release_manifest）

## 与“评审超时默认通过”策略的边界（必须说明）

本模块的发布门禁不继承“评审超时默认通过”的策略：
- 评审阶段允许“超时默认通过”是评审协调员的策略选择（应由 `plan_manifest.json.policies.timeouts.dag_review` 明确；仍需记录缺席与告警/补评）。
- 发布门禁阶段（release）默认是**硬门禁/失败即停**（建议 `plan_manifest.json.policies.timeouts.release_gate.default_decision=REJECT`）：缺任一 required gate 证据或存在 REJECT，则不得 APPROVE。

## 判定规则（MVP 最小）

- 若缺任一 required gate 证据文件：`decision=REJECT`
- 若任一证据文件的 `decision != PASS`：`decision=REJECT`
- 仅当所有 required gates 都存在且 `decision=PASS`：`decision=APPROVE`

## Pytest

- 集成：缺任一 required gate → 不生成 APPROVE
- 集成：全部 PASS → 生成 APPROVE
