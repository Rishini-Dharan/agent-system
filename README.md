# Agent System

A production-grade multi-model autonomous coding agent platform where cloud-hosted LLMs perform all intelligent work while the local machine handles orchestration, tool execution, state management, and coordination.

## Overview

```
                    USER
                      │
                      ▼
              ┌───────────────┐
              │ ORCHESTRATOR  │
              │     AGENT     │
              └───────┬───────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
      RESEARCHER    CODER      REVIEWER
          │           │           │
          ▼           ▼           ▼
      Cloud LLM    Cloud LLM    Cloud LLM
          │           │           │
          └───────────┼───────────┘
                      ▼
              ┌───────────────┐
              │ ORCHESTRATOR  │
              │   SYNTHESIS   │
              └───────┬───────┘
                      │
                      ▼
                 VALIDATION
                      │
               ┌──────┴──────┐
               │             │
             FAIL           PASS
               │             │
               ▼             ▼
             REPAIR       COMPLETE
```

## Features

- **Multi-Provider Support**: NVIDIA NIM, OpenRouter, Z.ai, Google Gemini
- **Specialized Agents**: Orchestrator, Researcher, Coder, Reviewer, Security, Tester, GitHub, Browser
- **Intelligent Routing**: Automatic model selection based on task type, complexity, and capabilities
- **Fallback Chains**: Automatic failover when models are unavailable
- **Structured Output**: Pydantic-validated JSON responses from all agents
- **Persistent State**: SQLite-based workflow state management
- **Security First**: Permission model, command guards, integrated scanners (Semgrep, Gitleaks, Trivy)
- **Observability**: Structured JSON logging, metrics collection
- **Cost Controls**: Rate limiting, token budgets, free-tier optimization
- **Parallel Execution**: Concurrent agent execution with dependency management
- **Conflict Resolution**: Multi-agent disagreement handling

## Quick Start

### Installation

```bash
git clone <repository>
cd agent_system_new
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` with your API keys:
```env
NVIDIA_API_KEY=your_nvidia_key
OPENROUTER_API_KEY=your_openrouter_key
ZAI_API_KEY=your_zai_key
GOOGLE_API_KEY=your_google_key
```

### Usage

```bash
# Run a single task
agent-system run "Create a REST API for user management"

# Run with specific agent
agent-system run "Fix the login bug" --agent coder

# Check system status
agent-system status

# Run diagnostics
agent-system doctor

# Run tests
agent-system test

# Show available agents
agent-system agents

# Show configured models
agent-system models

# Show logs
agent-system logs
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

## Configuration

See [CONFIGURATION.md](CONFIGURATION.md) for configuration options.

## Agents

See [AGENTS.md](AGENTS.md) for agent specifications.

## Providers

See [PROVIDERS.md](PROVIDERS.md) for provider setup.

## Security

See [SECURITY.md](SECURITY.md) for security model.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development guidelines.

## License

MIT License