# Agent System - User Documentation

**A lightweight local-first autonomous AI agent system for Windows/WSL2**

---

## Architecture

This system uses **OpenCode** as the primary orchestration layer with specialized agents for different tasks:

| Agent | Responsibility |
|-------|----------------|
| `orchestrator` | Task decomposition, delegation, state management |
| `researcher` | Web research, information extraction, source comparison |
| `job-hunter` | Job search, requirement extraction, scoring |
| `browser-agent` | Browser automation, navigation, form filling |
| `coder` | Code generation, bug fixes, tests, refactoring |
| `github-agent` | GitHub issues, branches, commits, PRs |
| `security-agent` | SAST, secret detection, vulnerability scanning |
| `reviewer` | Code review, test inspection, approval decisions |

---

## Installation

### Prerequisites (Already Installed)
- Windows 11 + WSL2 (Ubuntu 24.04)
- Git, Python 3.12, Node.js 22, npm
- OpenCode 1.18.15
- n8n (scheduler)
- Ollama with models: `qwen2.5-coder:3b`, `llama3.2:3b`
- Security tools: Semgrep, Gitleaks, Trivy
- Playwright Chromium
- GitHub CLI (`gh`)

### Verify Installation
```bash
# Check all tools
gh --version
ollama list
semgrep --version
gitleaks version
trivy version
npx playwright --version
n8n --version
opencode --version
```

---

## Configuration

### 1. OpenCode Config (`~/.config/opencode/opencode.jsonc`)
Already configured with:
- GitHub MCP (uses `GITHUB_TOKEN` env var)
- Playwright MCP (Chromium)

### 2. Environment Variables
Required in your shell profile:
```bash
GITHUB_TOKEN=ghp_xxx          # GitHub Personal Access Token
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx  # Alternative
```

### 3. Agent System Config (`agent-system/config/`)
Create `config/settings.yaml`:
```yaml
ollama:
  host: "http://localhost:11434"
  models:
    coder: "qwen2.5-coder:3b"
    general: "llama3.2:3b"

database:
  path: "state/agent.db"

logs:
  path: "logs/"
  level: "INFO"

security:
  semgrep_config: "auto"
  gitleaks_config: "default"
  trivy_severity: "HIGH,CRITICAL"

github:
  default_branch: "main"
  require_approval_for_pr: true
```

---

## Starting the Agent

### Interactive Mode (Orchestrator)
```bash
cd C:\Users\rishi\agent-system
opencode --agent orchestrator
```

### Run a Specific Task
```bash
opencode --agent researcher "Find latest AMD Ryzen 5 5000 series benchmarks"
opencode --agent job-hunter "Search for Python backend roles in Seattle"
opencode --agent coder "Fix the login bug in auth.py"
opencode --agent github-agent "Create PR for issue #42"
```

### Scheduled Workflows (n8n)
```bash
n8n start
# Then configure workflows in n8n UI at http://localhost:5678
```

---

## Adding a New Agent

1. Create agent definition in `agents/<name>.json`:
```json
{
  "name": "my-agent",
  "description": "What this agent does",
  "permissions": "READ_ONLY",
  "tools": ["opencode", "web_search"],
  "model": "qwen2.5-coder:3b",
  "prompt_template": "You are a specialized agent for {{task}}. {{instructions}}"
}
```

2. Register in orchestrator's delegation list

3. Test: `opencode --agent my-agent "test task"`

---

## Adding a Skill

Skills are reusable capabilities for OpenCode agents.

1. Create `skills/<name>/skill.yaml`:
```yaml
name: my-skill
description: Reusable capability
version: 1.0
tools:
  - name: my_tool
    description: Tool description
    parameters:
      type: object
      properties:
        input:
          type: string
    handler: "skills/my_skill/main.py::handler"
```

2. Implement handler in `skills/my_skill/main.py`

3. Reference in agent config: `skills: ["my-skill"]`

---

## Adding a Workflow

Workflows define multi-step processes.

1. Create `workflows/<name>.md` with:
   - Trigger (schedule, manual, event)
   - Steps with agent assignments
   - Data flow between steps
   - Approval gates
   - Output artifacts

2. Example: `workflows/github_issue_to_pr.md`

3. Register in n8n for scheduling or run manually via orchestrator

---

## GitHub Integration

### Authentication
```bash
gh auth login  # Uses browser or token
# Or set GITHUB_TOKEN env var
```

### Workflow: Issue → PR
```
1. GitHub Issue created
2. Orchestrator reads issue
3. Researcher gathers context
4. Coder implements fix
5. Tests run
6. Security scan
7. Reviewer approves
8. Human approval gate
9. GitHub-Agent creates PR
10. Human reviews/merges
```

**Never auto-merges.** Always requires human approval.

---

## Browser Integration

Uses Playwright via MCP (configured in OpenCode).

### Capabilities
- Navigate to URLs
- Fill forms
- Extract data (text, tables, links)
- Screenshot pages
- Wait for elements

### Hard Stops (Require Human)
- Final job application submit
- Financial transactions
- Account deletion
- Contract acceptance
- Important settings changes

### Usage
```bash
opencode --agent browser-agent "Go to linkedin.com/jobs and extract first 10 Python roles"
```

---

## Security Scanning

### Tools
| Tool | Purpose | Command |
|------|---------|---------|
| Semgrep | SAST | `semgrep scan --config=auto .` |
| Gitleaks | Secrets | `gitleaks detect --source .` |
| Trivy | Vulnerabilities | `trivy fs .` |

### Run All Scans
```bash
cd C:\Users\rishi\agent-system
python scripts/security_scan.py
```

### Reports
Output to `reports/security/` with timestamps.

### CI Integration
Add to GitHub Actions:
```yaml
- name: Security Scan
  run: |
    semgrep scan --config=auto --json=semgrep.json .
    gitleaks detect --source . --report-format json --report-path gitleaks.json
    trivy fs --format json --output trivy.json .
```

---

## Scheduling

### n8n Workflows
Pre-configured workflows in `workflows/`:
- `daily_morning.yaml` - Jobs, GitHub, health check
- `daily_evening.yaml` - Tests, security, summary
- `weekly.yaml` - Dependencies, issues, engineering report

### Import to n8n
1. Start n8n: `n8n start`
2. Open http://localhost:5678
3. Import workflow JSON files
4. Configure webhooks to trigger OpenCode
5. Activate workflows

### Manual Trigger
```bash
# Trigger daily workflow
curl -X POST http://localhost:5678/webhook/daily-morning
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Ollama connection refused | `ollama serve` in separate terminal |
| Models not found | `ollama pull qwen2.5-coder:3b llama3.2:3b` |
| GitHub CLI unauthenticated | `gh auth login` or check `GITHUB_TOKEN` |
| Playwright browser missing | `npx playwright install chromium` |
| Semgrep/Gitleaks/Trivy not found | Restart shell for PATH, or use full path |
| SQLite locked | Ensure single writer, check `state/` permissions |
| n8n webhook 404 | Check workflow active, webhook URL correct |
| RAM usage high | Use smaller models, close unused apps |

---

## Resource Usage

| Component | RAM (Idle) | RAM (Load) |
|-----------|------------|------------|
| Windows Base | ~3.5 GB | ~4 GB |
| WSL2 | ~1 GB | ~2 GB |
| Ollama (2 models) | ~4.7 GB | ~4.7 GB |
| OpenCode + Node | ~0.5 GB | ~1 GB |
| n8n | ~0.2 GB | ~0.5 GB |
| Security Tools | - | ~0.5 GB each |
| **Total** | **~10 GB** | **~13-14 GB** |

**Headroom:** ~2-3 GB on 16 GB system. Monitor with Task Manager.

---

## Security Considerations

1. **No secrets in code** - Use env vars only
2. **Approval gates** - All external actions require human approval
3. **Least privilege** - Agents run with minimal permissions
4. **Audit logging** - All actions logged to `logs/` as JSON
5. **Local-first** - Models run locally, no data leaves machine unless using cloud fallback
6. **Security scanning** - Automated on every code change
7. **No auto-merge** - PRs always require human review

---

## Directory Structure

```
agent-system/
├── AGENTS.md              # Architecture & rules
├── README.md              # This file
├── config/                # Settings, agent configs
├── agents/                # Agent definitions
├── skills/                # OpenCode skills
├── workflows/             # Workflow definitions
├── scripts/               # Python automation scripts
├── security/              # Scan scripts, rules
├── state/                 # SQLite database
├── logs/                  # Structured JSON logs
├── reports/               # Generated reports
│   └── security/          # Security scan reports
└── tests/                 # Unit/integration tests
```

---

## Next Steps

1. **Test each agent** individually
2. **Run a full workflow** (Issue → PR)
3. **Configure n8n schedules** for daily/weekly runs
4. **Add your resume/profile** for job-hunter
5. **Customize security rules** for your tech stack
6. **Set up notifications** (email, Slack, Discord)

---

*Generated 2026-08-09*