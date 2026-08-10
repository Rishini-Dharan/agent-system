# Configuration Guide

## Overview

Agent System uses YAML configuration files in the `config/` directory. All configurations are loaded via `ConfigManager` with caching. Environment variables can override YAML values.

## Configuration Files

| File | Purpose |
|------|---------|
| `models.yaml` | Model and provider assignments |
| `agents.yaml` | Agent definitions and permissions |
| `routing.yaml` | Task routing rules and fallbacks |
| `limits.yaml` | Rate limits and cost controls |

## Models Configuration (`models.yaml`)

Defines which model each agent uses and provider settings.

```yaml
models:
  # Agent-specific model assignments
  orchestrator:
    provider: "nvidia"
    model: "nvidia/nemotron-3-ultra"
    temperature: 0.3
    max_tokens: 8192
    timeout: 120
    capabilities: ["reasoning", "tool_calling", "structured_output"]
  
  researcher:
    provider: "openrouter"
    model: "deepseek/deepseek-chat"
    temperature: 0.2
    max_tokens: 8192
    capabilities: ["web_search", "analysis", "summarization", "tool_calling"]

  coder:
    provider: "zai"
    model: "glm-4.5"
    temperature: 0.2
    max_tokens: 16384
    timeout: 180
    capabilities: ["coding", "tool_calling", "structured_output", "large_context"]

  reviewer:
    provider: "nvidia"
    model: "nvidia/nemotron-3-ultra"
    temperature: 0.1
    max_tokens: 8192
    capabilities: ["reasoning", "code_analysis", "security_review", "structured_output"]

  # ... other agents

providers:
  nvidia:
    base_url: "https://integrate.api.nvidia.com/v1"
    api_key_env: "NVIDIA_API_KEY"
    models_endpoint: "/models"
    chat_endpoint: "/chat/completions"
    supports_streaming: true
    supports_tools: true
    supports_structured_output: true
    rate_limit_rpm: 60
    rate_limit_tpm: 100000

  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"
    rate_limit_rpm: 100
    rate_limit_tpm: 200000
    extra_headers:
      HTTP-Referer: "https://agent-system.local"
      X-Title: "Agent System"

  zai:
    base_url: "https://api.z.ai/v1"
    api_key_env: "ZAI_API_KEY"
    rate_limit_rpm: 60
    rate_limit_tpm: 100000

  google:
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    api_key_env: "GOOGLE_API_KEY"
    use_native_sdk: true
    _sdk: true
    rate_limit_rpm: 60
    rate_limit_tpm: 250000
    free_tier: true
    free_tier_limits:
      requests_per_minute: 15
      tokens_per_minute: 32000
```

### Model Fields

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | Yes | Provider name (nvidia, openrouter, zai, google) |
| `model` | Yes | Model identifier |
| `temperature` | No | Sampling temperature (0.0-2.0) |
| `max_tokens` | No | Maximum output tokens |
| `timeout` | No | Request timeout in seconds |
| `capabilities` | No | List of required capabilities |

### Provider Fields

| Field | Required | Description |
|-------|----------|-------------|
| `base_url` | Yes | API base URL |
| `api_key_env` | Yes | Environment variable name for API key |
| `rate_limit_rpm` | No | Requests per minute |
| `rate_limit_tpm` | No | Tokens per minute |
| `supports_streaming` | No | Streaming support |
| `supports_tools` | No | Tool calling support |
| `supports_structured_output` | No | JSON schema enforcement |
| `extra_headers` | No | Additional HTTP headers |

## Agents Configuration (`agents.yaml`)

Defines agent behavior, permissions, and model assignments.

```yaml
agents:
  orchestrator:
    name: "orchestrator"
    description: "Central coordinator - task decomposition, planning, agent delegation, conflict resolution"
    permissions: "APPROVAL_REQUIRED"
    default_model: "orchestrator"
    fallback_models: ["reviewer", "researcher"]
    capabilities:
      - "task_decomposition"
      - "planning"
      - "agent_delegation"
      - "conflict_resolution"
      - "workflow_management"
      - "approval_coordination"
    max_parallel_subtasks: 3
    timeout: 300
    system_prompt: |
      You are the Orchestrator - the central coordinator...
```

### Agent Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Agent identifier |
| `description` | Yes | Human-readable description |
| `permissions` | Yes | Permission level (READ_ONLY, SAFE_WRITE, APPROVAL_REQUIRED, BLOCKED) |
| `default_model` | Yes | Model key from models.yaml |
| `fallback_models` | No | Fallback model keys |
| `capabilities` | No | List of capability strings |
| `max_parallel_subtasks` | No | Max concurrent subtasks |
| `timeout` | No | Task timeout in seconds |
| `system_prompt` | No | System prompt for the agent |

### Permission Levels

| Level | Description | Use Cases |
|-------|-------------|-----------|
| `READ_ONLY` | Read-only operations | Researcher, Reviewer, Security |
| `SAFE_WRITE` | Write files, run tests, commit locally | Coder, Tester, Browser |
| `APPROVAL_REQUIRED` | Git push, PR creation, package install | Orchestrator, GitHub |
| `BLOCKED` | Destructive commands, credential access | None (explicit only) |

## Routing Configuration (`routing.yaml`)

Controls how tasks are routed to agents and models.

```yaml
routing:
  # Task type to agent mapping
  task_routes:
    research:
      primary_agent: "researcher"
      fallback_agents: ["orchestrator", "browser"]
      complexity_threshold: "low"
    
    code_implement:
      primary_agent: "coder"
      fallback_agents: ["tester", "orchestrator"]
      complexity_threshold: "medium"
    
    code_review:
      primary_agent: "reviewer"
      fallback_agents: ["security", "orchestrator"]
      complexity_threshold: "medium"
    
    security_scan:
      primary_agent: "security"
      fallback_agents: ["reviewer", "orchestrator"]
      complexity_threshold: "low"
    
    testing:
      primary_agent: "tester"
      fallback_agents: ["coder", "orchestrator"]
      complexity_threshold: "medium"
    
    github_ops:
      primary_agent: "github"
      fallback_agents: ["orchestrator", "coder"]
      complexity_threshold: "low"
    
    web_browse:
      primary_agent: "browser"
      fallback_agents: ["researcher", "orchestrator"]
      complexity_threshold: "low"
    
    planning:
      primary_agent: "orchestrator"
      fallback_agents: ["reviewer", "researcher"]
      complexity_threshold: "high"
    
    debugging:
      primary_agent: "coder"
      fallback_agents: ["tester", "orchestrator"]
      complexity_threshold: "high"
    
    architecture:
      primary_agent: "orchestrator"
      fallback_agents: ["reviewer", "coder"]
      complexity_threshold: "high"

  # Complexity-based model selection
  complexity_routing:
    low:
      preferred_providers: ["openrouter", "google"]
      max_tokens: 4096
      temperature: 0.2
    
    medium:
      preferred_providers: ["nvidia", "zai", "openrouter"]
      max_tokens: 8192
      temperature: 0.2
    
    high:
      preferred_providers: ["nvidia", "zai"]
      max_tokens: 16384
      temperature: 0.1

  # Capability requirements
  capability_requirements:
    tool_calling:
      required_providers: ["nvidia", "openrouter", "zai"]
      exclude_providers: []
    
    structured_output:
      required_providers: ["nvidia", "openrouter", "zai"]
      exclude_providers: ["google"]
    
    large_context:
      min_context_window: 32768
      preferred_models: ["glm-4.5", "gemini-1.5-pro", "nemotron-3-ultra"]
    
    web_search:
      required_agents: ["researcher", "browser"]
    
    code_execution:
      required_agents: ["coder", "tester"]
    
    git_operations:
      required_agents: ["github"]

  # Fallback chains (provider -> model)
  fallback_chains:
    orchestrator:
      - provider: "nvidia"
        model: "nvidia/nemotron-3-ultra"
      - provider: "openrouter"
        model: "deepseek/deepseek-chat"
      - provider: "zai"
        model: "glm-4.5"
      - provider: "google"
        model: "gemini-1.5-pro"
    
    researcher:
      - provider: "openrouter"
        model: "deepseek/deepseek-chat"
      - provider: "google"
        model: "gemini-1.5-pro"
      - provider: "nvidia"
        model: "nvidia/nemotron-3-ultra"
    
    coder:
      - provider: "zai"
        model: "glm-4.5"
      - provider: "openrouter"
        model: "deepseek/deepseek-coder"
      - provider: "google"
        model: "gemini-1.5-pro"
      - provider: "nvidia"
        model: "nvidia/nemotron-3-ultra"
    
    # ... other agents

  # Parallel execution rules
  parallel_execution:
    independent_task_types:
      - "research"
      - "security_scan"
      - "code_review"
    
    dependent_task_types:
      - "code_implement"
      - "testing"
      - "github_ops"
    
    max_parallel_by_type:
      research: 3
      security_scan: 2
      code_review: 1
      code_implement: 2
      testing: 2
      web_browse: 2
```

## Limits Configuration (`limits.yaml`)

Controls rate limits, costs, and resource usage.

```yaml
limits:
  # Global limits
  global:
    max_agent_calls_per_task: 50
    max_parallel_agents: 4
    max_retries: 3
    max_context_tokens: 32768
    max_output_tokens: 8192
    request_timeout_seconds: 180
    daily_request_limit: 1000
    daily_token_limit: 1000000
    max_task_duration_seconds: 1800

  # Per-provider limits
  providers:
    nvidia:
      requests_per_minute: 60
      tokens_per_minute: 100000
      max_concurrent_requests: 5
      cost_per_1k_input_tokens: 0.0001
      cost_per_1k_output_tokens: 0.0002
      free_tier: false
    
    openrouter:
      requests_per_minute: 100
      tokens_per_minute: 200000
      max_concurrent_requests: 10
      cost_per_1k_input_tokens: 0.0
      cost_per_1k_output_tokens: 0.0
      free_tier: true
      free_models:
        - "deepseek/deepseek-chat"
        - "deepseek/deepseek-coder"
    
    zai:
      requests_per_minute: 60
      tokens_per_minute: 100000
      max_concurrent_requests: 5
      cost_per_1k_input_tokens: 0.0
      cost_per_1k_output_tokens: 0.0
      free_tier: true
    
    google:
      requests_per_minute: 60
      tokens_per_minute: 250000
      max_concurrent_requests: 10
      cost_per_1k_input_tokens: 0.000125
      cost_per_1k_output_tokens: 0.000375
      free_tier: true
      free_tier_limits:
        requests_per_minute: 15
        tokens_per_minute: 32000

  # Per-agent limits
  agents:
    orchestrator:
      max_calls_per_task: 20
      max_retries: 3
      timeout_seconds: 300
      max_context_tokens: 32768
      max_output_tokens: 8192
    
    researcher:
      max_calls_per_task: 10
      max_retries: 3
      timeout_seconds: 180
      max_context_tokens: 16384
      max_output_tokens: 4096
    
    coder:
      max_calls_per_task: 15
      max_retries: 3
      timeout_seconds: 300
      max_context_tokens: 32768
      max_output_tokens: 16384
    
    reviewer:
      max_calls_per_task: 5
      max_retries: 2
      timeout_seconds: 180
      max_context_tokens: 16384
      max_output_tokens: 4096
    
    security:
      max_calls_per_task: 5
      max_retries: 2
      timeout_seconds: 180
      max_context_tokens: 16384
      max_output_tokens: 4096
    
    tester:
      max_calls_per_task: 10
      max_retries: 3
      timeout_seconds: 300
      max_context_tokens: 16384
      max_output_tokens: 8192
    
    github:
      max_calls_per_task: 5
      max_retries: 2
      timeout_seconds: 180
      max_context_tokens: 8192
      max_output_tokens: 4096
    
    browser:
      max_calls_per_task: 10
      max_retries: 2
      timeout_seconds: 180
      max_context_tokens: 8192
      max_output_tokens: 4096

  # Retry configuration
  retry:
    base_delay_seconds: 1
    max_delay_seconds: 60
    exponential_base: 2
    jitter: true
    retry_on:
      - "timeout"
      - "rate_limit"
      - "server_error"
      - "connection_error"
    do_not_retry_on:
      - "invalid_request"
      - "authentication_error"
      - "permission_denied"
      - "model_not_found"
      - "context_length_exceeded"

  # Fallback configuration
  fallback:
    enabled: true
    max_fallbacks: 3
    fallback_on:
      - "rate_limit"
      - "server_error"
      - "model_unavailable"
      - "timeout"
    do_not_fallback_on:
      - "invalid_request"
      - "authentication_error"
      - "permission_denied"
    prefer_free_tier: true

  # Cost tracking
  cost_tracking:
    enabled: true
    alert_threshold_usd: 10.0
    daily_budget_usd: 50.0
    per_task_budget_usd: 5.0
    track_by:
      - "provider"
      - "model"
      - "agent"
      - "task"
```

## Environment Variables

Required API keys (set in `.env`):

```bash
# Cloud Provider API Keys
NVIDIA_API_KEY=your_nvidia_nim_key
OPENROUTER_API_KEY=your_openrouter_key
ZAI_API_KEY=your_zai_key
GOOGLE_API_KEY=your_google_key

# Optional: Override default model IDs
# NVIDIA_MODEL=nemotron-3-ultra
# OPENROUTER_RESEARCHER_MODEL=deepseek/deepseek-chat
# ZAI_CODER_MODEL=glm-4.5
# GOOGLE_REVIEWER_MODEL=gemini-1.5-pro

# Optional: Custom endpoints (if using self-hosted or proxied)
# NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# ZAI_BASE_URL=https://api.z.ai/v1
# GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

### Required vs Optional

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_API_KEY` | Yes* | For Nemotron models |
| `OPENROUTER_API_KEY` | Yes* | For DeepSeek, Llama, etc. |
| `ZAI_API_KEY` | Yes* | For GLM models |
| `GOOGLE_API_KEY` | Yes* | For Gemini models |

*At least one API key is required for the system to function.

## Configuration Loading Priority

1. Environment variables (highest)
2. Local config files (`config/*.local.yaml`) - gitignored
3. Main config files (`config/*.yaml`)
4. Defaults (lowest)

## Validation

Configurations are validated at startup:
- Required fields present
- Valid provider names
- Valid model identifiers
- Consistent cross-references

Invalid configurations cause startup failure with clear error messages.