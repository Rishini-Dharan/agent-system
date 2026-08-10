# Development Guide

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- API keys for at least one provider
- Optional: Semgrep, Gitleaks, Trivy for security scanning

### Installation

```bash
# Clone repository
git clone <repository>
cd agent_system_new

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"

# Install Playwright
playwright install chromium

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### Project Structure

```
agent_system_new/
├── agent_system/           # Main package
│   ├── agents/            # Specialized agents
│   ├── config.py          # Configuration loading
│   ├── cli.py             # CLI entry point
│   ├── observability/     # Logging and metrics
│   ├── providers/         # LLM provider implementations
│   ├── router/            # Model routing logic
│   ├── runtime/           # Agent execution runtime
│   ├── schemas/           # Pydantic models
│   ├── security/          # Security controls
│   └── state/             # Database models and manager
├── config/                # YAML configuration files
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── .env.example           # Environment template
├── pyproject.toml         # Project metadata
└── README.md
```

## Development Workflow

### Code Style

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Type checking
mypy agent_system
```

### Pre-commit Hooks

```bash
# Install
pre-commit install

# Run manually
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=agent_system --cov-report=html

# Run specific test file
pytest tests/test_router.py -v

# Run async tests
pytest tests/test_router.py -v --asyncio-mode=auto
```

### Adding New Features

#### 1. New Agent

```bash
# 1. Create agent class
# agent_system/agents/new_agent.py

# 2. Add to agents/__init__.py
from agent_system.agents.new_agent import NewAgent, create_new_agent

# 3. Add configuration
# config/agents.yaml
# config/models.yaml

# 4. Register in create_all_agents()
```

#### 2. New Provider

```bash
# 1. Create provider class
# agent_system/providers/custom.py

# 2. Add to providers/__init__.py
from agent_system.providers import custom  # noqa: F401

# 3. Add to ProviderType enum (base.py)

# 3. Add configuration
# config/models.yaml

# 4. Test with router
```

#### 3. New Tool

```python
# In tool_manager.py or separate file
tool_manager.register(
    name="my_tool",
    description="Tool description",
    parameters={"type": "object", "properties": {...}},
    handler=my_handler_function,
    required_permission=PermissionLevel.SAFE_WRITE,
    category="custom",
)
```

#### 4. New Scanner

```python
# agent_system/security/scanners.py
class NewScanner(SecurityScanner):
    def scan(self, path: str = ".") -> Dict[str, Any]:
        # Implementation
        pass

# Add to CompositeScanner
```

## Configuration Management

### Adding New Config Files

```python
# config/new_config.yaml
new_section:
  key: value

# In code
from agent_system.config import get_config
config = get_config("new_config")
```

### Environment-Specific Config

Create `config/models.local.yaml` for local overrides (gitignored).

## Database Migrations

### Adding New Tables

```python
# agent_system/state/models.py
class NewModel(Base):
    __tablename__ = "new_table"
    # columns...

# Run migration
alembic revision --autogenerate -m "Add new table"
alembic upgrade head
```

Or manually:
```python
# In database.py init_schema()
# Add new schema to SCHEMAS dict
```

## Debugging

### VS Code Configuration

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Agent System",
      "type": "python",
      "request": "launch",
      "module": "agent_system.cli",
      "args": ["run", "test task"],
      "console": "integratedTerminal",
      "env": {
        "LOG_LEVEL": "DEBUG"
      }
    }
  ]
}
```

### Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run code
asyncio.run(system.run_task("task"))

profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(20)
```

## Performance Optimization

### Profiling Targets

1. **Provider Latency**: Monitor `latency_ms` in metrics
2. **Token Usage**: Track input/output tokens per agent
3. **Database Queries**: Check for N+1 queries
4. **Context Size**: Monitor `max_context_tokens` usage

### Optimization Strategies

1. **Caching**: Add caching for repeated operations
2. **Batching**: Combine multiple LLM calls
3. **Parallel Execution**: Increase `max_parallel_agents`
4. **Context Truncation**: Implement smart context trimming

## Monitoring

### Key Metrics

- Task success rate
- Average latency per agent
- Token usage and cost
- Fallback frequency
- Error rates by type

### Alerting

Configure alerts for:
- Daily cost exceeding budget
- Error rate > 5%
- Latency > 30s
- No successful tasks in 1 hour

## Contributing

### Pull Request Process

1. Fork repository
2. Create feature branch
3. Make changes
4. Run tests and linting
5. Update documentation
6. Submit PR

### Code Review Checklist

- [ ] Tests pass
- [ ] Linting passes
- [ ] Type checking passes
- [ ] Documentation updated
- [ ] No hardcoded secrets
- [ ] Proper error handling
- [ ] Logging added for new operations

### Code Review Checklist

- [ ] Tests pass
- [ ] Linting passes
- [ ] Type checking passes
- [ ] Documentation updated
- [ ] No hardcoded secrets
- [ ] Proper error handling
- [ ] Logging added for new operations

## Security Considerations

### Code Review

- No hardcoded credentials
- Input validation on all user inputs
- Path traversal prevention
- SQL injection prevention (parameterized queries)

### Dependency Management

```bash
# Check for vulnerabilities
pip-audit

# Update dependencies
pip install -U package
```