# Troubleshooting Guide

## Quick Diagnostics

Run the built-in doctor command:

```bash
agent-system doctor
```

This checks:
- Python version and packages
- Environment variables
- API connectivity
- External tools (git, semgrep, gitleaks, trivy)
- File permissions

## Common Issues

### 1. API Key Issues

**Error**: `AuthenticationError: Invalid API key`

**Solutions**:
1. Verify key in `.env` file:
   ```bash
   cat .env | grep API_KEY
   ```
2. Check key validity on provider dashboard
3. Ensure no extra whitespace/newlines in `.env`
4. Verify environment variable name matches (`NVIDIA_API_KEY`, not `NVIDIA_KEY`)

**Error**: `ProviderError: No API key found for nvidia`

**Solution**: Add key to `.env`:
```bash
echo "NVIDIA_API_KEY=your_key_here" >> .env
```

### 2. Rate Limiting

**Error**: `RateLimitError: Rate limit exceeded`

**Solutions**:
1. Wait and retry (exponential backoff is automatic)
2. Check provider dashboard for quota
3. Switch to fallback provider (automatic)
4. Upgrade provider plan

**Configuration**: Adjust in `config/limits.yaml`:
```yaml
limits:
  providers:
    openrouter:
      requests_per_minute: 100  # Reduce if hitting limits
```

### 3. Model Unavailable

**Error**: `ModelUnavailableError: Model not found: nvidia/nemotron-3-ultra`

**Solutions**:
1. Check model name in `config/models.yaml`
2. Verify model exists on provider
3. Use fallback chain (automatic)
4. Update to available model

### 4. Context Length Exceeded

**Error**: `ContextLengthError: Context length exceeded`

**Solutions**:
1. Reduce `max_context_tokens` in `config/limits.yaml`
2. Use model with larger context window
4. Summarize context before sending

```yaml
limits:
  global:
    max_context_tokens: 16384  # Reduce from 32768
```

### 5. Tool Execution Failures

**Error**: `Tool execution failed: Command not found`

**Solutions**:
1. Install missing tool:
   ```bash
   # Semgrep
   pip install semgrep
   
   # Gitleaks
   # Download from GitHub releases
   
   # Trivy
   # Download from GitHub releases
   ```
2. Add to PATH
3. Verify with `agent-system doctor`

### 6. Database Issues

**Error**: `sqlite3.OperationalError: database is locked`

**Solutions**:
1. Ensure only one process uses database
2. Check file permissions on `state/agent_system.db`
3. Restart application

**Error**: `sqlite3.OperationalError: no such table`

**Solution**: Reinitialize database:
```bash
rm state/agent_system.db
agent-system doctor  # Recreates tables
```

### 7. Import Errors

**Error**: `ModuleNotFoundError: No module named 'agent_system'`

**Solutions**:
1. Install in development mode:
   ```bash
   pip install -e .
   ```
2. Check Python path
3. Use `python -m agent_system.cli` instead of `agent-system`

### 8. Playwright/Browser Issues

**Error**: `Playwright not installed`

**Solutions**:
```bash
pip install playwright
playwright install chromium
```

**Error**: `Browser launch failed`

**Solutions**:
1. Install system dependencies:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
   
   # Or use playwright install-deps
   playwright install-deps chromium
   ```

### 9. Git Issues

**Error**: `Git command failed: not a git repository`

**Solution**: Initialize git:
```bash
git init
git remote add origin <url>
```

**Error**: `Git push failed: permission denied`

**Solutions**:
1. Check SSH key / token
2. Verify remote URL
3. Check branch protection rules

### 10. Performance Issues

**Symptoms**: Slow response, high latency

**Solutions**:
1. Check provider status pages
2. Reduce `max_parallel_agents` in `config/limits.yaml`
3. Use faster models (Flash vs Pro)
5. Reduce context size

```yaml
limits:
  global:
    max_parallel_agents: 2  # Reduce from 4
  agents:
    coder:
      max_context_tokens: 16384  # Reduce from 32768
```

## Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG agent-system run "task"
```

Or in code:
```python
from agent_system.observability import configure_logging
configure_logging(log_level="DEBUG")
```

### View Logs

```bash
# Recent logs
agent-system logs --lines 100

# Specific agent logs
tail -f logs/agent.coder.log

# All logs
tail -f logs/*.log
```

### Inspect State

```bash
# View tasks
sqlite3 state/agent_system.db "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10;"

# View agent runs
sqlite3 state/agent_system.db "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 10;"

# View model usage
sqlite3 state/agent_system.db "SELECT * FROM model_usage WHERE date = date('now');"
```

### Profile Performance

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run task
asyncio.run(system.run_task("task"))

profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(20)
```

## Provider-Specific Issues

### NVIDIA NIM
- **Error**: `401 Unauthorized` → Check `NVIDIA_API_KEY`
- **Error**: `429 Rate Limited` → Wait, reduce concurrency
- **Endpoint**: `https://integrate.api.nvidia.com/v1`

### OpenRouter
- **Error**: `402 Payment Required` → Add credits or use free models
- **Error**: `Model not found` → Check model ID format (`provider/model`)
- **Free Models**: `deepseek/deepseek-chat`, `meta-llama/llama-3-8b-instruct`
- **Endpoint**: `https://openrouter.ai/api/v1`

### Z.ai
- **Error**: `401 Unauthorized` → Check `ZAI_API_KEY`
- **Models**: `glm-4.5`, `glm-4`
- **Endpoint**: `https://api.z.ai/v1`

### Google Gemini
- **Error**: `400 Invalid Argument` → Check model name format
- **Free Tier Limits**: 15 RPM, 32K TPM
- **Models**: `gemini-1.5-pro`, `gemini-1.5-flash`
- **Endpoint**: Native SDK (`google-generativeai`)

## Configuration Issues

### Config Not Loading
1. Check file exists: `ls config/*.yaml`
2. Validate YAML syntax: `python -c "import yaml; yaml.safe_load(open('config/models.yaml'))"`
3. Check for duplicate keys

### Environment Variables Not Read
1. Ensure `.env` in project root
2. Check variable names match exactly
3. Restart application after changes

## Getting Help

### Logs to Include
When reporting issues, include:
1. `agent-system doctor` output
2. Relevant log entries (with `LOG_LEVEL=DEBUG`)
3. Configuration files (sanitized)
4. Steps to reproduce

### Community Resources
- GitHub Issues: Report bugs
- Discussions: Ask questions
- Provider Documentation: API references