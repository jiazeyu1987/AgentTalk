# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

AgentTalk is a multi-agent collaboration system using file-based message passing for task coordination. The system consists of:

1. **Python Package** (`agenttalk/`): Core infrastructure modules for heartbeat, router, monitor, dashboard, and release coordination
2. **CLI Tools**: Standalone entry points for running system components
3. **Design Documentation** (`doc/`): Rules, DAG specifications, and process documentation defining the system architecture

**Current State**: This is an MVP implementation with core infrastructure in place. The system implements:
- **Heartbeat daemon** (`agenttalk.heartbeat`): Agent inbox polling, command execution, artifact production
- **Router** (`agenttalk.router`): Inter-agent message delivery, DAG-based routing
- **Monitor** (`agenttalk.monitor`): Plan status aggregation and tracking
- **Dashboard** (`agenttalk.dashboard`): FastAPI-based dashboard for monitoring
- **Release Coordinator** (`agenttalk.release`): Release workflow orchestration

---

## Development and Testing

### Installation

```bash
# Install dependencies
pip install -e .

# Install dev dependencies (for testing)
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_heartbeat.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_heartbeat.py::test_cli_parses_args_and_invokes_runner
```

### Starting System Components

**Heartbeat Daemon** (runs inside each agent):
```bash
python agenttalk_heartbeat.py --agent-root /path/to/agents/agent_xxx --schemas-base-dir doc/rule/templates/schemas
```

**Router** (system-wide message routing):
```bash
python agenttalk_router.py --agents-root /path/to/agents --system-runtime /path/to/system_runtime --schemas-base-dir doc/rule/templates/schemas
```

**Monitor** (plan status aggregation):
```bash
python agenttalk_monitor.py --agents-root /path/to/agents --system-runtime /path/to/system_runtime --schemas-base-dir doc/rule/templates/schemas
```

**Dashboard** (web UI):
```bash
python agenttalk_dashboard.py --system-runtime /path/to/system_runtime --host 127.0.0.1 --port 8000
```

### Creating a Test Agent

```bash
# 1. Create agent directory structure
mkdir -p agents/agent_test_myagent/{inbox,outbox,workspace}

# 2. Create heartbeat config
cat > agents/agent_test_myagent/heartbeat_config.json << EOF
{
  "schema_version": "1.0",
  "agent_id": "agent_test_myagent",
  "poll_interval_seconds": 10,
  "scan_mode": "allowlist_only",
  "allowlist": ["plan_001"],
  "max_new_messages_per_tick": 100,
  "max_resume_messages_per_tick": 50,
  "schema_validation_enabled": true,
  "schemas_base_dir": "doc/rule/templates/schemas"
}
EOF

# 3. Start the heartbeat daemon
python agenttalk_heartbeat.py --agent-root agents/agent_test_myagent
```

---

## Architecture

### System Components

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│  Heartbeat      │ ───> │   Router     │ <──> │  Agents         │
│  (per agent)    │      │ (system)     │      │  (inbox/outbox) │
└─────────────────┘      └──────────────┘      └─────────────────┘
                                                        ▲
                                                        │
┌─────────────────┐      ┌──────────────┐              │
│  Dashboard      │ <──> │   Monitor    │ <────────────┘
│  (FastAPI)      │      │ (system)     │
└─────────────────┘      └──────────────┘
```

### Package Structure

**`agenttalk/`** - Main Python package:
- `heartbeat/` - Agent inbox polling, command execution, artifact ingestion
  - `app.py` - Core heartbeat logic (`run_once`, `run_forever`)
  - `config.py` - Heartbeat configuration loading
  - `handlers.py` - Command handler interface (`CommandHandler`)
  - `state.py` - Task state and input index management
  - `io.py` - File I/O utilities (atomic operations, path handling)
  - `schema.py` - Schema registry and validation
- `router/` - Inter-agent message routing
  - `app.py` - Core router logic (DAG-based routing, delivery tracking)
  - `dag.py` - DAG parsing and task assignment lookup
  - `delivery_log.py` - Delivery log append-only storage
  - `schema.py` - Router-specific schema validation
- `monitor/` - Plan status aggregation and tracking
  - `app.py` - Monitor that aggregates agent states into plan status
- `dashboard/` - FastAPI dashboard for monitoring
  - `app.py` - FastAPI application factory
  - `storage.py` - Storage backend for plan status
- `command_runner/` - Command execution pipeline
  - `pipeline.py` - Artifact production and writing
  - `types.py` - Command result and artifact types
- `release/` - Release workflow orchestration
  - `app.py` - Release coordinator logic

### Directory Layout

```
agenttalk/
├── agenttalk/                    # Python package
│   ├── heartbeat/
│   ├── router/
│   ├── monitor/
│   ├── dashboard/
│   ├── command_runner/
│   └── release/
├── agents/                       # Agent working directories (runtime)
│   └── agent_xxx/
│       ├── inbox/               # Incoming messages (per plan)
│       ├── outbox/              # Outgoing messages (per plan)
│       ├── workspace/           # Task workspaces
│       └── heartbeat_config.json
├── system_runtime/               # System-wide runtime state
│   ├── plans/                   # Per-plan tracking
│   │   └── <plan_id>/
│   │       ├── deliveries.jsonl
│   │       ├── commands/
│   │       ├── acks/
│   │       ├── task_dag.json
│   │       └── plan_status.json
│   ├── alerts/                  # System alerts (per plan)
│   ├── deadletter/              # Failed messages (per plan)
│   └── status_heartbeat.json    # System heartbeat summary
├── doc/                         # Design documentation
│   ├── rule/                    # System rules (PR-001 to PR-026)
│   ├── DAG/                     # DAG specifications and semantics
│   └── rule/templates/          # JSON templates and schemas
├── tests/                       # Test suite
├── agenttalk_heartbeat.py       # CLI: Heartbeat daemon
├── agenttalk_router.py          # CLI: Router
├── agenttalk_monitor.py         # CLI: Monitor
├── agenttalk_dashboard.py       # CLI: Dashboard
└── pyproject.toml               # Project configuration
```

### Message Types and Flow

**Message Envelope** (`*.msg.json`):
- `type`: "command" | "artifact"
- `message_id`: Unique message identifier
- `plan_id`: Plan identifier
- `producer_agent_id`: Source agent
- `task_id`/`output_name`: Task and output context
- `payload`: Contains `command` or `files` metadata

**Message Flow**:
1. Producer writes message envelope to `outbox/<plan_id>/`
2. Router scans agent outboxes
3. Router validates envelope and schema
4. Router computes delivery targets from DAG or routing rules
5. Router atomically copies envelope + payloads to target inboxes
6. Router appends delivery record to `deliveries.jsonl`
7. Target agent's heartbeat discovers and processes the message

**Command Execution Flow**:
1. Router delivers command envelope to assigned agent's inbox
2. Agent heartbeat discovers command, checks inputs are available
3. Heartbeat invokes command handler via `CommandHandler.handle_command()`
4. Handler returns `CommandResult` with `ok` status and details
5. Heartbeat writes ACK and task state to outbox
6. If artifacts produced, writes artifact envelopes to outbox

### DAG-Based Routing

The system uses DAG (`task_dag.json`) for task routing:

- **Nodes**: Tasks with `task_id`, `assigned_agent_id`, `depends_on`, `inputs`, `outputs`
- **Edges**: Dependencies via `depends_on` and output routing via `outputs[].deliver_to`
- **Command delivery**: Router uses `assigned_agent_id` to route commands
- **Artifact delivery**: Router uses `outputs[].deliver_to` to route artifacts

See `doc/DAG/semantics.md` for detailed DAG execution semantics.

---

## Key Concepts

### Schema-Based Validation

All message types use JSON schemas from `doc/rule/templates/schemas/`:
- `message_envelope.schema.json` - Message envelope structure
- `command.schema.json` - Command payload structure
- `ack.schema.json` - Acknowledgment structure
- `task_dag.schema.json` - DAG structure
- `delivery_log_entry.schema.json` - Delivery log entries
- `status_heartbeat.schema.json` - Agent heartbeat status
- `plan_status.schema.json` - Plan status aggregation

Schema validation can be enabled/disabled via config.

### Atomic File Operations

The system uses atomic file operations for reliability:
- `atomic_write_json()` - Write with rename for atomicity
- `atomic_copy()` - Copy with temp file + rename
- `atomic_move()` - Move with temp file + rename
- `atomic_rename()` - Rename with temp file

This prevents partial reads during concurrent access.

### Command Handler Interface

Custom command handlers implement `CommandHandler` from `agenttalk.heartbeat.handlers`:

```python
from agenttalk.heartbeat.handlers import CommandHandler, CommandResult

class MyHandler(CommandHandler):
    def handle_command(self, envelope: dict, command: dict, context: dict) -> CommandResult:
        # Process command
        return CommandResult(ok=True, details={"output": "..."})
```

Pass to heartbeat via `--handler-module my_handler` (module must expose `handler`).

### Task States

Tasks progress through states:
- `PENDING` - Waiting for dependencies
- `RUNNING` - Currently executing
- `BLOCKED_WAITING_INPUT` - Missing required inputs
- `BLOCKED_WAITING_HUMAN` - Waiting for human intervention
- `COMPLETED` - Finished successfully
- `FAILED` - Execution failed

States are tracked via `task_state_*.json` files in agent outbox.

### Deadletter Handling

Failed messages are moved to `system_runtime/deadletter/<plan_id>/` with:
- Original file name and message_id
- Error code and message
- Suggested next action
- Retriable flag

---

## Key Documentation

### System Rules (PR-001 to PR-026)
Located in `doc/rule/`:
- **PR-001**: Inbox/outbox file transfer (only interaction method)
- **PR-002**: File transfer defined by task
- **PR-003**: Agent folder isolation (security boundary)
- **PR-007**: Unified execute command
- **PR-008**: Agent folder structure
- **PR-009**: Task distribution mechanism
- **PR-017**: Logging and traceability
- **PR-024**: Shared folder monitoring (system routing)
- **PR-025**: Agent lifecycle and plan monitoring

See `doc/rule/README.md` for complete index.

### DAG Specification
- `doc/DAG/semantics.md` - DAG execution semantics (task state machine, input matching, failure propagation)
- `doc/DAG/roadmap.md` - Implementation roadmap
- `doc/DAG/schemas/task_dag.v1.1.schema.json` - DAG schema

### Templates and Schemas
- `doc/rule/templates/` - Reusable JSON templates
- `doc/rule/templates/schemas/` - JSON schemas for all message types

---

## Common Tasks

### Adding a New Message Type

1. Create schema in `doc/rule/templates/schemas/<type>.schema.json`
2. Create template in `doc/rule/templates/<type>.json`
3. Update `SchemaRegistry` to include new schema
4. Add handler in router or heartbeat as needed

### Debugging Message Flow

```bash
# Check system runtime for delivery logs
cat system_runtime/plans/<plan_id>/deliveries.jsonl | jq .

# Check agent outbox for produced messages
ls agents/<agent_id>/outbox/<plan_id>/

# Check agent inbox for pending messages
ls agents/<agent_id>/inbox/<plan_id>/.pending/

# Check for deadlettered messages
ls system_runtime/deadletter/<plan_id>/
```

### Running End-to-End Test

```bash
# 1. Start router (in background)
python agenttalk_router.py --agents-root agents --system-runtime system_runtime &

# 2. Start agent heartbeat (in background)
python agenttalk_heartbeat.py --agent-root agents/agent_xxx &

# 3. Place command envelope in agent's inbox
# (Create appropriate command envelope file)

# 4. Check deliveries.jsonl for routing results
cat system_runtime/plans/<plan_id>/deliveries.jsonl
```
