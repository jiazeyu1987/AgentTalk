# Agent Heartbeat and Event Loop Notes

This document captures known gaps in the current heartbeat/event loop description
and a tightened version suitable for implementation.

## Known gaps and risks

1) No clear "queue vs scan" boundary
   - Scanning inbox repeatedly without a stable queue can reprocess files
     or miss files during rename windows.
   - Fix: maintain a deterministic staging step (move to .pending).

2) Missing atomic claim protocol
   - Without an atomic claim, two workers can race on the same file.
   - Fix: "claim" by atomic rename into inbox/.pending/ or a per-task lock.

3) Insufficient idempotency coverage
   - Only mentioning message_id is not enough for repeated outputs
     or retries that reuse ids.
   - Fix: enforce message_id + sha256 as the primary dedupe key (idempotency_key is audit-only).

4) No back-pressure or fairness rules
   - A busy inbox can starve some tasks or agents.
   - Fix: bounded per-cycle processing and round-robin by plan_id/task_id.

5) Weak failure isolation
   - A single malformed message can crash the loop if not contained.
   - Fix: per-message try/catch with DLQ + alert on schema parse failures.

6) Dormant wakeup race
   - If the agent goes dormant while a message arrives, it may sleep past it.
   - Fix: wakeup listener watches inbox and emits a wake signal on file arrival.

7) Incomplete status semantics
   - "CONSUMED" vs "RUNNING" vs "BLOCKED" is not tied to concrete files.
   - Fix: define minimal files and timestamps for each transition.

8) Ambiguous input satisfaction
   - If multiple inputs match, the loop does not specify how to block.
   - Fix: enforce pick_policy and human intervention triggers.

## Proposed heartbeat loop (tightened)

### 1) Cycle start
- Record heartbeat timestamp in logs and agent_state.json.
- Determine mode: RUNNING/IDLE/DORMANT.

### 2) Discover new messages
- List inbox/<plan_id>/ files excluding .tmp and .processed/.pending.
- For each candidate, validate envelope or schema presence if required.

### 3) Atomic claim
- Atomically rename message payload + envelope into inbox/<plan_id>/.pending/.
- If rename fails, skip (another worker or process claimed it).

### 4) Dedup and admission
- Primary dedupe should happen at Router (deliveries.jsonl): message_id + sha256.
- Agent-side dedupe is only a safety net: if message_id was already consumed by this agent, skip execution and move to .processed/.
- If you still want an explicit record, write ACK=SUCCEEDED with result.details="SKIPPED_DUPLICATE" (ACK status stays CONSUMED/SUCCEEDED/FAILED).
- Enforce bounded per-cycle quota to avoid starvation.

### 5) Input check
- If task inputs not satisfied:
  - If wait_for_inputs: set state BLOCKED_WAITING_INPUT and requeue or park.
  - If ambiguous: emit human_intervention_request.json and block.

### 6) Dispatch
- Emit ACK: CONSUMED before invoking handler.
- Execute skill/handler in isolated workspace and trace all inputs/outputs.

### 7) Finalize
- On success: ACK SUCCEEDED, move message to .processed/.
- On failure: ACK FAILED; if retriable, allow retry policy; else DLQ + alert.

### 8) Idle and dormant
- If no work for N cycles: set IDLE.
- If idle timeout exceeded: set DORMANT and stop heartbeat loop,
  keeping only wakeup listener active.

## Minimal file contracts

- ACK files: ack_<message_id>.json
- Pending staging: inbox/<plan_id>/.pending/
- Processed archive: inbox/<plan_id>/.processed/
- Deadletter: inbox/<plan_id>/.deadletter/
- Task state: outbox/<plan_id>/task_state_<task_id>.json (or workspace trace)

## Notes for integration

- Ensure these behaviors align with PR-001/PR-003/PR-024.
- If multiple workers exist per agent, add a file lock or per-task mutex.
