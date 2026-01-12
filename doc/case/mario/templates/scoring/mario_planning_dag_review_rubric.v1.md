# Mario DAG 评审评分模板 v1

criteria_version: `mario_planning_dag_review_rubric.v1`

用途：用于 DAG 评审命令（`score_required=true`）。评审者必须按本模板输出 `score_breakdown`，不得自由发挥。

## 总分与判定

- 总分：0-100
- 建议阈值：
  - `APPROVE`: >= 80 且无阻塞项
  - `REVISE`: 50-79 或存在非阻塞缺陷
  - `REJECT`: < 50 或存在阻塞项

## 分项（建议 5 项各 20 分）

1) 可执行性（0-20）
- 20：每个 task 都有明确的执行描述，可落为命令消息 `cmd_*.msg.json`（envelope `type=command`），无歧义
- 10：多数可落地，但存在少量“做什么不清楚/产物不明确”
- 0：大量任务不可执行/描述抽象

2) 输入闭合（0-20）
- 20：所有 task 的必需输入都能通过 `inputs selector + pick_policy` 唯一解析
- 10：存在少量输入歧义或 delivered_at/score 等关键信息缺失
- 0：大量输入缺失/歧义导致无法推进

3) 输出闭合与命名稳定（0-20）
- 20：关键产物文件名稳定、可追溯；idempotency_key 与版本策略明确
- 10：存在少量产物命名/版本策略缺失
- 0：产物不闭合或重复产物不可控

4) 路由完整性（0-20）
- 20：每个输出的接收者集合可计算且完整（`outputs[].deliver_to`/`routing_rules` 闭合），无漏发/误发风险
- 10：少量输出接收者不完整，但不阻塞核心链路
- 0：关键输出无明确接收者，导致链路断裂

5) 门禁与可发布路径（0-20）
- 20：DAG评审、验收、发布门禁证据链清晰，可判定通过/阻塞条件
- 10：门禁存在但证据/阈值不完整
- 0：无门禁或门禁不可计算

## 输出格式要求（review_result / dag_review_result）

必须包含：
- `criteria_version`
- `score`
- `score_breakdown[]`：每项包含 `key/name/score/max/notes`
- `decision`：APPROVE/REVISE/REJECT
- `issues[]`：每条 issue 需标注 severity + suggestion

建议 `score_breakdown.key` 取值：
- `executability` `inputs` `outputs` `routing` `gates`
