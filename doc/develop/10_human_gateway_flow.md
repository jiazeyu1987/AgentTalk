# 10 Human Gateway 流程模块

## 目标

把“缺材料/缺标准/需审批”转换成可落盘请求：
- 任何 agent 可在 outbox 写 `human_intervention_request.json`
- 系统投递到 `agents/agent_human_gateway/inbox/<plan_id>/`
- 人类回填 `human_intervention_response.json` + 附件
- 系统按 response 的 `provided_files[].deliver_to_agent_id` 投递附件（保持“Agent 只消费 envelope”的原则）

## 责任边界与落盘路径（必须写死）

### 1) Request（任意 Agent → Human Gateway）

- 发起方：任意 Agent（通常是被阻塞的执行 Agent）
- 写入位置：`agents/<agent_id>/outbox/<plan_id>/human_intervention_request_<request_id>.json`
- 系统程序（Router）处理：
  - 归档到：`system_runtime/plans/<plan_id>/human_requests/human_intervention_request_<request_id>.json`
  - 投递到：`agents/agent_human_gateway/inbox/<plan_id>/human_intervention_request_<request_id>.json`

### 2) Response（Human → Human Gateway → 目标 Agent）

- 人类回填位置（MVP 约定）：
  - `agents/agent_human_gateway/outbox/<plan_id>/human_intervention_response_<request_id>.json`
  - 附件文件与 response 同目录（例如 `agents/agent_human_gateway/outbox/<plan_id>/requirements.md`）
- 系统程序（Router）处理：
  - 归档 response 到：`system_runtime/plans/<plan_id>/human_responses/human_intervention_response_<request_id>.json`
  - 对每个 `provided_files[]`：向目标 Agent 注入一条 **artifact message envelope** + payload 文件：
    - payload：复制到 `agents/<deliver_to_agent_id>/inbox/<plan_id>/<file_name>`
    - envelope：写到 `agents/<deliver_to_agent_id>/inbox/<plan_id>/msg_human_<request_id>_<sha12>.msg.json`
      - `envelope.type=artifact`
      - `envelope.task_id="human_gateway"`
      - `envelope.output_name=<request_id>`
      - `payload.files[].path=<file_name>`
  - 同时写入 `deliveries.jsonl status=DELIVERED`（from=`agent_human_gateway`）用于审计/回放
  - 写入处理完成标记：`system_runtime/plans/<plan_id>/human_responses/.processed/<request_id>.json`（避免重复注入）

## Pytest

- 集成：发起 request → 投递到 `agent_human_gateway` inbox → 回填 response+附件 → 系统注入 artifact envelope 到目标 agent inbox → 目标 agent heartbeat ingest 成为可用输入
