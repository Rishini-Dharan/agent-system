# Security Model

## Overview

Agent System implements a defense-in-depth security model with multiple layers of protection.

## Permission Model

Four-tier permission system:

| Level | Description | Capabilities | Agents |
|-------|-------------|--------------|--------|
| **BLOCKED** | No access | None | N/A |
| **READ_ONLY** | Read-only operations | File read, search, git status, web search | Researcher, Reviewer, Security |
| **SAFE_WRITE** | Safe write operations | File write, test execution, local git commit | Coder, Tester, Browser |
| **APPROVAL_REQUIRED** | Requires human approval | Git push, PR creation, package install, external commands | Orchestrator, GitHub |

### Permission Hierarchy

```
BLOCKED < READ_ONLY < SAFE_WRITE < APPROVAL_REQUIRED
```

Higher levels inherit all capabilities of lower levels.

### Permission Enforcement

```python
from agent_system.security import get_permission_manager, PermissionLevel

pm = get_permission_manager()

# Check if agent can perform action
if pm.check_permission(agent_permission, required_permission):
    # Allow
    pass

# Check specific action
if pm.is_action_allowed(agent_permission, "git_push"):
    # Allow
    pass
```

## Command Guard

Prevents dangerous command execution:

### Blocked Patterns
- `rm -rf /`, `rm -rf /*`
- `format`, `mkfs`, `dd` to devices
- `shutdown`, `reboot`, `halt`
- Privilege escalation (`sudo`, `su`)
- Shell injection (`; rm -rf`, `| bash`, `$(cmd)`)

### Approval Required
- `git push` (including force push)
- Package installation (`pip install`, `npm install`, `apt install`)
- External service modification
- Destructive commands

### Implementation

```python
from agent_system.security import get_command_guard

guard = get_command_guard()

# Validate command
is_safe, error = guard.validate("rm -rf /tmp/test")
if not is_safe:
    raise SecurityError(f"Command blocked: {error}")

# Check if approval needed
if guard.requires_approval("git push origin main"):
    await request_approval(...)
```

## Secret Protection

### API Key Handling
- Keys stored in `.env` (never committed)
- Loaded via environment variables only
- Never logged or printed
- Not passed to agents in prompts

### Configuration
```python
# .env.example
NVIDIA_API_KEY=
OPENROUTER_API_KEY=
ZAI_API_KEY=
GOOGLE_API_KEY=

# .gitignore includes .env
```

### Runtime Protection
- Keys masked in logs
- Not included in serialized state
- Scrubbed from error messages

## Security Scanners

Integrated tools run automatically:

### Semgrep (Static Analysis)
- Security rule sets
- Custom rule support
- Language-agnostic

```bash
semgrep --config=auto --json .
```

### Gitleaks (Secret Detection)
- 100+ secret patterns
- Git history scanning
- Configurable rules

```bash
gitleaks detect --source . --report-format json
```

### Trivy (Vulnerability Scanning)
- Dependency vulnerabilities
- Container image scanning
- CVE database

```bash
trivy fs --format json .
```

### Security Agent Integration

```python
security_results = await security_agent.execute(task, context)
# Results include findings from all three tools
```

## File System Sandbox

### Workspace Restriction
- All file operations relative to workspace root
- Path traversal prevented (`../` blocked)
- Absolute paths resolved and validated

```python
# In tool manager
workspace = Path.cwd().resolve()
file_path = (workspace / user_path).resolve()

if not str(file_path).startswith(str(workspace)):
    raise SecurityError("Path outside workspace")
```

### Size Limits
- Max file read: 10MB
- Max file write: 10MB
- Prevents resource exhaustion

## Network Security

### Outbound Only
- No inbound listeners
- HTTP/HTTPS only to configured endpoints
- DNS resolution for provider endpoints only

### Provider Endpoints
| Provider | Endpoint |
|----------|----------|
| NVIDIA | `https://integrate.api.nvidia.com` |
| OpenRouter | `https://openrouter.ai` |
| Z.ai | `https://api.z.ai` |
| Google | `https://generativelanguage.googleapis.com` |

## Audit Logging

All security-relevant events logged:

```json
{
  "timestamp": "2026-08-09T18:00:00Z",
  "event": "command_blocked",
  "command": "rm -rf /",
  "agent": "coder",
  "reason": "matches blocked pattern"
}
```

Events tracked:
- Command validation (allowed/blocked)
- Approval requests/grants
- Secret scan results
- File access (read/write)
- Provider authentication

## Best Practices

### For Developers
1. Never hardcode API keys
2. Use `.env` for local development
3. Run `agent-system doctor` before deployment
4. Review security scan results regularly

### For Deployment
1. Use secrets management (Vault, AWS Secrets Manager)
2. Restrict network egress to provider endpoints
3. Enable audit logging
4. Set resource limits (CPU, memory, disk)
4. Run as non-root user

### For Operations
1. Monitor approval request queue
2. Review blocked command attempts
3. Track security scan trends
4. Rotate API keys periodically

## Security Checklist

- [ ] All API keys in `.env` (not committed)
- [ ] `.env` in `.gitignore`
- [ ] Command guard enabled
- [ ] Permission model enforced
- [ ] Security scanners configured
- [ ] Approval gates for sensitive actions
- [ ] Audit logging enabled
- [ ] Network egress restricted
- [ ] Resource limits set
- [ ] Regular security scans scheduled