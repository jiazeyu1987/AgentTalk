# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

AgentTalk is a multi-agent collaboration system using LLMs to accomplish complex tasks through agent specialization and consensus-based decision making. The system enables autonomous task execution through a layered architecture with core programs (Python) and skills (LLM-driven).

**Key Design Philosophies**:
- **Core + Skills**: Core programs (100% stable Python) handle essential infrastructure; skills (flexible but may fail) handle business logic
- **Anti-Hallucination**: Agents block when lacking inputs instead of spinning or hallucinating
- **Wake-Up Mechanism**: Agents automatically wake when inputs become available
- **Resource Optimization**: Agents auto-dormant after idle timeout, wake on demand

**Important**: This is currently a **design and documentation phase**. The `template/agent_template/` directory contains reference implementations, but actual agents have not been deployed to `system/agents/` yet.

---

## Development and Testing

### Creating a Test Agent from Template

```bash
# 1. Copy the template to create a new agent
cp -r template/agent_template/ system/agents/agent_test_myagent/

# 2. Edit the agent configuration
vim system/agents/agent_test_myagent/agent_profile.json

# 3. Navigate to the agent directory
cd system/agents/agent_test_myagent/

# 4. Start the agent (foreground)
python core/main.py
```

### Agent Profile Configuration

Edit `agent_profile.json` to configure your agent:

```json
{
  "agent_id": "agent_test_myagent",
  "agent_name": "My Test Agent",
  "lifecycle": {
    "idle_timeout_seconds": 1800,
    "enable_dormant": true,
    "wakeup_check_interval": 10,
    "auto_wakeup_on_message": true
  },
  "heartbeat": {
    "interval_seconds": 10
  },
  "visibility_list": {
    "can_see": [],
    "can_be_seen_by": []
  }
}
```

### Starting and Stopping Agents

**Start an agent**:
```bash
cd system/agents/agent_xxx/
python core/main.py
```

**Stop an agent**:
- Press `Ctrl+C` to gracefully stop
- Or use: `kill -TERM $(cat .runtime/heartbeat.pid)`

### Checking Agent Status

```bash
# View agent state (requires jq)
cat agent_state.json | jq .

# Check recent heartbeat
tail -20 logs/activity.jsonl | grep heartbeat

# View all logs in real-time
tail -f logs/activity.jsonl

# View decision log
tail -50 logs/decision_log.jsonl

# Check for errors
grep ERROR logs/activity.jsonl | tail -20
```

### Wake Up a Dormant Agent

```bash
# Method 1: Send wakeup signal via Python (if implemented)
python -m core.wakeup_sender agent_xxx "Manual wakeup"

# Method 2: Create signal file directly
cat > system/agents/agent_xxx/inbox/wakeup_signal.json << EOF
{
  "type": "WAKEUP_SIGNAL",
  "from": "user",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "reason": "Manual wakeup"
}
EOF
```

---

## Architecture

### Agent Structure: Core Programs + Skills

```
Agent = Core Programs (Python) + Skills (skill.md + scripts/)
```

**Core Programs** (template/agent_template/core/):
- `main.py` - Agent entry point, initializes and starts all components
- `heartbeat_engine.py` - Periodically scans inbox/, dispatches messages to skills
- `trace_logger.py` - Records all activity, decisions, errors, LLM conversations
- `state_manager.py` - Maintains agent_state.json, manages status transitions
- `skill_dispatcher.py` - Routes messages to appropriate skills
- `wakeup_listener.py` - Monitors for wakeup signals when agent is dormant
- `wakeup_sender.py` - Sends wakeup signals to other agents (if implemented)

**Skills** (skills/):
- Business logic modules defined in `skill.md` files
- Optional `scripts/handler.py` for stable, direct Python execution
- See doc/agent_architecture_v2.md for details

**Critical Design Principle**: Use core programs (Python) for infrastructure that must be 100% stable. Use skills (skill.md) for flexible business logic that can tolerate intermittent failures.

### Agent Lifecycle

```
STOPPED → STARTING → RUNNING ↔ IDLE → DORMANT (idle timeout)
                                      ↑
                                      └── Wakeup signal
```

- **RUNNING**: Processing tasks (heartbeat active, normal resource usage)
- **IDLE**: No tasks, heartbeat running (low resource usage)
- **DORMANT**: Long idle, heartbeat stopped, only wakeup listener active (minimal usage)
- Auto-dormant after default 30 minutes of idle (configurable in agent_profile.json)

### Agent Visibility Lists

Each Agent has a **visibility list** defining which other Agents it can interact with. This is configured in `agent_profile.json`:

```json
{
  "visibility_list": {
    "can_see": ["agent_general_manager", "agent_developer_01"],
    "can_be_seen_by": ["agent_general_manager"]
  }
}
```

**Key principles**:
- Agents can only interact with those in their visibility list
- General Manager sees all managers, managers see GM + their team
- Different teams cannot see each other (unless configured)
- See `doc/code/normal/visibility_list.md` for details

### Directory Structure

```
agent_xxx_name/
├── core/                           # Core Python programs
│   ├── main.py                     # ⭐ Entry point
│   ├── heartbeat_engine.py
│   ├── trace_logger.py
│   ├── state_manager.py
│   ├── skill_dispatcher.py
│   ├── wakeup_listener.py
│   └── wakeup_sender.py
├── agent_profile.json              # Agent configuration
├── agent_state.json                # Runtime state (auto-generated)
├── skills/                         # Business logic skills
│   └── skill_xxx/
│       ├── skill.md                # Skill definition
│       ├── references/             # Reference docs
│       └── scripts/                # Optional Python handlers
├── templates/                      # Message/document/prompt templates
├── configs/                        # Configuration files
├── cache/                          # Cached data
├── inbox/                          # Incoming messages
├── outbox/                         # Outgoing messages
├── workspace/                      # Task workspaces
│   └── task_xxx/
│       ├── trace/                  # Execution traces
│       ├── inputs/, outputs/, work/
│       └── task_state.json
├── resources/                      # Static resources
├── logs/                           # Activity logs
│   ├── activity.jsonl              # All activities
│   ├── decision_log.jsonl          # Agent decisions
│   ├── error_chains.jsonl          # Error chains
│   └── llm_calls.jsonl             # LLM calls
└── .runtime/                       # Runtime files (not in git)
    ├── heartbeat.pid
    └── heartbeat.lock
```

### Message Flow

```
1. Message arrives in inbox/
   ↓
2. HeartbeatEngine scans (every 10s)
   ↓
3. SkillDispatcher routes to skill
   ↓
4. Skill processes (skill.md or scripts/handler.py)
   ↓
5. Message moved to inbox/.processed/
   ↓
6. Activity logged to logs/activity.jsonl
```

### File Types in Inbox

- `.msg.json` - Inter-agent messages (queued for processing)
- `.cmd.json` - Commands (executed immediately)
- `.sys.json` - System files (wakeup signals, etc.)
- Resource files (any ext) - Documents, data, configs referenced by messages

See `doc/code/file_type/README.md` for complete documentation.

---

## Key Concepts

### Core Programs vs Skills

| Aspect | Core Programs | Skills |
|--------|--------------|--------|
| **Stability** | ⭐⭐⭐⭐⭐ Must be 100% stable | ⭐⭐⭐ Can tolerate failure |
| **Implementation** | Python directly executed | skill.md + Claude Code |
| **Use Cases** | Infrastructure, essential functions | Business logic, flexible features |
| **Failure Handling** | Auto-retry, alerts | Log errors, manual intervention |
| **Examples** | Heartbeat, message routing, logging | Meeting convening, task assignment |

**Rule of thumb**: Use core programs for anything that must always work; use skills for complex, LLM-reasoning-dependent tasks.

### Six-Layer Traceability

All agent actions are traceable through:
1. **Activity** (logs/activity.jsonl) - What the agent did
2. **Decision** (logs/decision_log.jsonl) - Why the agent made decisions
3. **Execution** (workspace/task_xxx/trace/execution_trace.jsonl) - How the agent executed
4. **Input** (workspace/task_xxx/trace/input_trace.json) - What inputs were used
5. **Output** (workspace/task_xxx/trace/output_trace.json) - What outputs were produced
6. **Error** (logs/error_chains.jsonl) - Complete error chains

### Anti-Hallucination: INTERNAL vs EXTERNAL Knowledge

When agents need information, they classify as:
- **INTERNAL**: General knowledge (programming, APIs) - generate from LLM
- **EXTERNAL**: Business/user-specific (credentials, data) - must wait for user input

Agents block when lacking EXTERNAL knowledge, wake when inputs become available.

### Unified Task Template

Use the unified task template for assigning work to agents. See `doc/code/file_type/unified_task_template.md`:
- **Artifacts**: Abstract representation of work items (code, docs, data)
- **Artifact Roles**: source (to process), reference (consult), specification (follow)
- **Artifact Types**: source_code, document, data, config, etc.

---

## Creating New Agents and Skills

### Creating a New Agent

```bash
# 1. Copy template to create new agent
cp -r template/agent_template/ system/agents/agent_xxx_name/

# 2. Edit agent profile
vim system/agents/agent_xxx_name/agent_profile.json

# 3. (Optional) Add custom skills
mkdir -p system/agents/agent_xxx_name/skills/skill_yyy/

# 4. Start the agent
cd system/agents/agent_xxx_name/
python core/main.py
```

**Minimum agent_profile.json**:
```json
{
  "agent_id": "agent_xxx_name",
  "agent_name": "Human-readable name",
  "lifecycle": {
    "idle_timeout_seconds": 1800,
    "enable_dormant": true
  },
  "heartbeat": {
    "interval_seconds": 10
  },
  "visibility_list": {
    "can_see": [],
    "can_be_seen_by": []
  }
}
```

### Creating Skills

**Option 1: Stable Skill (scripts/handler.py)** - Use for critical functionality

```python
# skills/skill_xxx/scripts/handler.py
import sys
import json

def main():
    message = json.loads(sys.argv[1])
    # Process message
    return {"success": True, "result": "..."}

if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False))
```

**Option 2: Flexible Skill (skill.md)** - Use for business logic

```markdown
---
skill_name: skill_xxx
skill_version: 1.0.0
skill_type: business_logic
description: Skill description
inputs:
  - name: message
    type: object
outputs:
  - name: result
    type: object
---

# Skill Documentation

Detailed skill description...
```

---

## Design Patterns

### DO: Use scripts/handler.py for essential functions
- Stable, reliable, debuggable
- Direct Python execution
- Performance controlled

### DON'T: Use skill.md for critical infrastructure
- Depends on external Claude Code calls
- May fail intermittently
- Hard to debug

### DO: Block when waiting for inputs
```python
if not has_inputs():
    state_manager.update_state({"status": "BLOCKED_WAITING_INPUT"})
    wait_for_wakeup()
```

### DON'T: Spin or hallucinate when lacking inputs
```python
# WRONG: Wastes resources
while not has_inputs():
    time.sleep(1)

# WRONG: Generates fake data
if not has_inputs():
    data = generate_fake_data()  # Hallucination!
```

---

## Troubleshooting

### Agent Not Responding

```bash
# Check if heartbeat is running
ps aux | grep python | grep main.py

# Check logs
tail -100 logs/activity.jsonl

# Check for errors
grep ERROR logs/activity.jsonl
```

### Messages Not Processed

```bash
# Check inbox
ls inbox/*.json

# Check processing status
ls inbox/.pending/ inbox/.processed/

# Check skill dispatcher logs
grep "skill_" logs/activity.jsonl | tail -20
```

### Agent Stuck in DORMANT

```bash
# Send wakeup signal (see "Wake Up a Dormant Agent" above)

# Check wakeup listener is running
ps aux | grep wakeup_listener

# Verify inbox/ is writable
touch inbox/test.txt && rm inbox/test.txt
```

---

## Key Documentation

### Architecture and Design
- `doc/agent_architecture_v2.md` - Core program vs skills architecture
- `doc/agent_lifecycle_management.md` - Agent lifecycle and dormancy
- `doc/core_program_guide.md` - Core program usage guide
- `doc/code/normal/visibility_list.md` - Agent visibility lists
- `doc/code/normal/task_graph.md` - Task graph structure (deliverable dependencies)

### File Types and Messaging
- `doc/code/file_type/README.md` - Complete file type system documentation
- `doc/code/file_type/unified_task_template.md` - **Most important**: How to assign tasks
- `doc/code/file_type/message_types.md` - All message type definitions

### Agent Roles and Workflows
- `doc/code/general_manager/README.md` - GM workflow overview
- `doc/code/general_manager_workflow.md` - Detailed GM workflow
