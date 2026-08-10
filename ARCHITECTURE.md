# Architecture

## System Architecture

Agent System follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
├─────────────────────────────────────────────────────────────┤
│                    Execution Manager                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │Orchestr.│  │Research.│  │  Coder  │  │Reviewer │  ...   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│       └────────────┼────────────┼────────────┘              │
│                    ▼            ▼                           │
│            ┌─────────────────────────┐                       │
│            │      Model Router       │                       │
│            └───────────┬─────────────┘                       │
│                        │                                     │
│        ┌───────────────┼───────────────┐                     │
│        ▼               ▼               ▼                     │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐               │
│   │ NVIDIA  │     │OpenRouter│     │ Z.ai    │    ...       │
│   └─────────┘     └─────────┘     └─────────┘               │
│                    ▲               ▲                           │
│                    │               │                           │
│            ┌───────┴───────────────┴───────┐                 │
│            │      Provider Abstraction      │                 │
│            └───────────────┬────────────────┘                 │
│                            │                                  │
│        ┌───────────────────┼───────────────────┐             │
│        ▼                   ▼                   ▼             │
│   ┌─────────┐         ┌─────────┐         ┌─────────┐      │
│   │ Context │         │  Tool   │         │  State  │      │
│   │ Manager │         │ Manager │         │ Manager │      │
│   └─────────┘         └─────────┘         └─────────┘      │
```

## Core Components

### 1. Model Router (`agent_system/router/model_router.py`)

Central routing logic that determines which model/provider handles each task.

**Key Responsibilities:**
- Task type to agent mapping
- Capability-based provider selection
- Complexity-based model selection
- Fallback chain management
- Provider health checking

**Routing Decision Factors:**
- Task type (research, coding, review, security, etc.)
- Required capabilities (tool calling, structured output, large context)
- Complexity level (low, medium, high)
- Provider availability and health
- Cost optimization (prefer free tiers)

### 2. Provider Abstraction (`agent_system/providers/`)

Unified interface for all cloud LLM providers.

**Base Interface (`base.py`):**
```python
class BaseProvider(ABC):
    async def complete(request: CompletionRequest) -> CompletionResponse
    async def stream(request: CompletionRequest) -> AsyncIterator[StreamingChunk]
    async def list_models() -> List[str]
    def supports_capability(capability: ModelCapability) -> bool
```

**Implementations:**
- `nvidia.py` - NVIDIA NIM API (OpenAI-compatible)
- `openrouter.py` - OpenRouter API (OpenAI-compatible)
- `zai.py` - Z.ai API (OpenAI-compatible)
- `google.py` - Google Gemini (native SDK)

**Capabilities:**
- `TOOL_CALLING` - Function calling support
- `STRUCTURED_OUTPUT` - JSON schema enforcement
- `STREAMING` - Streaming responses
- `LARGE_CONTEXT` - 32K+ token context windows

### 3. Agent Runtime (`agent_system/runtime/`)

Manages agent lifecycle and execution.

**Components:**
- `agent_runtime.py` - Base agent class with LLM interaction
- `context_manager.py` - Task-specific context preparation
- `execution_manager.py` - Task/workflow execution, parallel processing
- `tool_manager.py` - Tool registration, permission checking, execution

**Agent Base Class:**
```python
class BaseAgent(ABC):
    async def execute(task: Task, context: Dict) -> AgentResult
    async def _call_llm(messages, ...) -> CompletionResponse
    async def _call_llm_structured(messages, result_type) -> AgentResult
```

### 4. Specialized Agents (`agent_system/agents/`)

Each agent implements specific domain logic:

| Agent | Purpose | Default Model | Permissions |
|-------|---------|---------------|-------------|
| Orchestrator | Task decomposition, planning, coordination | Nemotron 3 Ultra | APPROVAL_REQUIRED |
| Researcher | Web search, documentation analysis | DeepSeek (OpenRouter) | READ_ONLY |
| Coder | Implementation, refactoring, tests | GLM-4.5 (Z.ai) | SAFE_WRITE |
| Reviewer | Code review, bug detection, security | Nemotron 3 Ultra | READ_ONLY |
| Security | Vulnerability scanning, secret detection | DeepSeek (OpenRouter) | READ_ONLY |
| Tester | Test creation, execution, failure analysis | Gemini 1.5 Pro | SAFE_WRITE |
| GitHub | Git operations, PR management | DeepSeek (OpenRouter) | APPROVAL_REQUIRED |
| Browser | Web navigation, data extraction | Gemini 1.5 Flash | SAFE_WRITE |

### 5. Schemas (`agent_system/schemas/`)

Pydantic models for all structured data:

- `agent_result.py` - Agent output validation
- `task.py` - Task and workflow definitions
- `workflow.py` - Execution context, metrics, approvals

### 6. State Management (`agent_system/state/`)

SQLite-based persistence using SQLAlchemy async:

**Models:**
- `TaskModel` - Task definitions and status
- `SubTaskModel` - Subtask tracking
- `AgentRunModel` - LLM call records
- `WorkflowStateModel` - Workflow progress
- `AgentResultModel` - Structured agent outputs
- `ToolCallModel` - Tool execution records
- `ModelUsageModel` - Cost and token tracking
- `ApprovalRequestModel` - Human approval gates
- `ConflictInfoModel` - Agent disagreement records
- `CheckpointModel` - Execution snapshots

### 7. Security (`agent_system/security/`)

Multi-layered security:

**Permissions (`permissions.py`):**
- Four-tier model (BLOCKED → READ_ONLY → SAFE_WRITE → APPROVAL_REQUIRED)
- Action-based permission checking

**Command Guard (`command_guard.py`):**
- Blocks dangerous patterns (rm -rf, shell injection, privilege escalation)
- Approval-required command detection
- Command sanitization

**Scanners (`scanners.py`):**
- Semgrep (static analysis)
- Gitleaks (secret detection)
- Trivy (vulnerability scanning)

### 7. Observability (`agent_system/observability/`)

**Logger (`logger.py`):**
- Structured JSON logging via structlog
- Specialized methods for agent calls, tool calls, fallbacks, conflicts

**Metrics (`metrics.py`):**
- Per-agent call tracking
- Latency, token usage, cost aggregation
- Success rates, fallback counts

### 8. Security (`agent_system/security/`)

### 9. Configuration (`agent_system/config.py`, `config/`)

YAML-based configuration with environment variable overrides.

## Data Flow

### Task Execution Flow

```
1. User Request
   │
   ▼
2. CLI parses request → creates Task
   │
   ▼
3. Orchestrator analyzes task
   │
   ▼
4. Model Router selects agent/model
   │
   ▼
5. Context Manager prepares context
   │
   ▼
6. Agent executes (with LLM calls via Provider)
   │
   ▼
7. Tool Manager executes tools (if needed)
   │
   ▼
8. Result validated against schema
   │
   ▼
9. State Manager persists result
   │
   ▼
10. Metrics recorded
   │
   ▼
11. Return to Orchestrator for next step
```

### Workflow Execution

```
1. Workflow Definition (steps with dependencies)
   │
   ▼
2. Execution Manager creates ExecutionContext
   │
   ▼
3. For each step (respecting dependencies):
   a. Prepare context (merge workflow state + step context)
   b. Execute assigned agent
   c. Store step results in workflow state
   d. Update metrics
   │
   ▼
4. Parallel execution for independent steps
   │
   ▼
5. Conflict resolution if agents disagree
   │
   ▼
6. Approval gates for sensitive actions
   │
   ▼
7. Final workflow state saved
```

## Configuration System

YAML-based configuration in `config/`:

| File | Purpose |
|------|---------|
| `models.yaml` | Model and provider assignments |
| `agents.yaml` | Agent definitions and permissions |
| `routing.yaml` | Task routing rules and fallbacks |
| `limits.yaml` | Rate limits and cost controls |

All configs loaded via `ConfigManager` with caching. Environment variables override YAML values.

## Extension Points

1. **New Providers**: Implement `BaseProvider`, register with `ProviderFactory`
2. **New Agents**: Subclass `BaseAgent`, add to `agents.yaml`, register in `create_all_agents()`
3. **New Tools**: Register with `ToolManager.register()`
4. **New Scanners**: Subclass `SecurityScanner`
4. **New Task Types**: Add to `TaskType` enum and `routing.yaml`