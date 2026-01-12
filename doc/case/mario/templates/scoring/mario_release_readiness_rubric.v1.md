# Mario 发布准备度评分模板 v1

criteria_version: `mario_release_readiness_rubric.v1`

用途：用于发布/门禁协调员或发布负责人在“发布前”做最终准备度评估（`score_required=true` 或作为 release_manifest 的评估依据）。

## 总分与判定

- 总分：0-100
- 建议阈值：
  - `APPROVE`: >= 85
  - `REVISE`: 60-84
  - `REJECT`: < 60

## 分项（每项 0-25，共 4 项）

1) 交付物完整性（0-25）
- 25：交付包/运行方式/说明齐全
- 15：交付物基本可用但缺少说明或可重复性证据
- 0：交付物不完整或无法运行

2) 门禁证据齐全（0-25）
- 25：build/deploy/smoke/e2e/security 等证据齐全且 PASS
- 15：证据齐全但存在低风险告警
- 0：缺关键证据或存在 REJECT

3) 回滚与可追溯（0-25）
- 25：版本标识清晰，产物哈希可追溯，问题可定位
- 15：有基本追溯但信息不全
- 0：无法追溯或版本混乱

4) 风险接受（0-25）
- 25：已知风险清单完整，必要时有人类接受记录
- 15：风险有记录但缺明确接受/处理策略
- 0：存在重大未评估风险

## 输出格式要求

必须输出：
- `criteria_version`
- `score`
- `score_breakdown[]`
- `decision`: APPROVE/REVISE/REJECT
- `evidence_refs[]`（引用关键证据文件名+sha256）
