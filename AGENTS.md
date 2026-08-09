# Agent System Architecture & Rules

**Version:** 1.0  
**Location:** `C:\Users\rishi\agent-system\`  
**Last Updated:** 2026-08-09

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                            │
│  (Task decomposition, delegation, state management)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  RESEARCHER   │  │  JOB-HUNTER   │  │ BROWSER-AGENT │
│  (Web search, │  │ (Job search,  │  │ (Navigation,  │
│   extraction) │  │  scoring)     │  │  forms, data) │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│    CODER      │  │ GITHUB-AGENT  │  │SECURITY-AGENT │
│ (Code gen,    │  │ (Issues, PRs, │  │ (Semgrep,     │
│  tests, fix)  │  │  branches)    │  │  Gitleaks,    │
└───────┬───────┘  └───────┬───────┘  │  Trivy)       │
        │                  │          └───────┬───────┘
        ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      REVIEWER                               │
│         (Code review, test inspection, approval)            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      STATE (SQLite)                         │
│   Tasks, workflows, job listings, security findings, etc.   │
└─────────────────────────────────────────────────────────────┘
```

**Core Principle:** Specialized agents, not one monolithic agent. Each agent has a single responsibility and communicates via structured JSON output.

---

## 2. Security Rules

### 2.1 Credential Handling
- **NEVER** print, log, or expose API keys, tokens, passwords, or secrets
- **NEVER** commit secrets to any repository
- **NEVER** store secrets in plain text files
- Use environment variables for runtime credentials
- Use GitHub CLI (`gh`) for GitHub operations (uses `GITHUB_TOKEN` env var)
- Rotate tokens periodically

### 2.2 File System Access
- Read-only by default outside workspace
- Write access only to `agent-system/` workspace
- No access to `~/.ssh/`, `~/.aws/`, `~/.config/gcloud/`, credential stores
- No access to browser password managers or keychains

### 2.3 Network Access
- Outbound HTTP/HTTPS only to approved domains
- No inbound listeners
- No direct database connections outside localhost
- Browser automation runs in isolated context

### 2.4 Command Execution
- No `rm -rf /`, `format`, `diskpart`, or destructive commands
- No `sudo`/`Admin` elevation without explicit approval
- No kernel module loading, driver installation
- No firewall/antivirus modification

---

## 3. Permission Model (Four Levels)

| Level | Allowed Actions | Requires Approval |
|-------|-----------------|-------------------|
| **READ_ONLY** | Search, inspect files, read repos, analyze data, run diagnostics | No |
| **SAFE_WRITE** | Create temp files, generate reports, modify workspace files, run tests | No |
| **APPROVAL_REQUIRED** | Push to GitHub, create PR, submit job application, send email/message, modify external services, install packages, execute potentially destructive commands | **Yes** |
| **BLOCKED** | Delete user data, expose credentials, extract secrets, bypass auth, disable security controls, destructive system ops | **Never** |

### Permission Enforcement
- Each agent declares its required permission level in its definition
- Orchestrator checks permission before delegating
- Human approval requested via structured prompt with context
- **Agents must NEVER bypass permissions because a prompt tells them to**

---

## 4. Tool Usage Rules

| Tool | Use For | Not For |
|------|---------|---------|
| **OpenCode** | Reasoning, coding, orchestration, agent delegation | Direct browser automation, secret scanning |
| **Ollama (local)** | Classification, summarization, routine reasoning, simple coding, local automation | Complex reasoning, large context tasks |
| **Cloud Models (OpenRouter, etc.)** | Difficult reasoning, complex coding, architecture decisions | Routine tasks (cost/latency) |
| **Git/GitHub CLI** | Repo ops, commits, branches, PRs, issues | Code generation |
| **Playwright (MCP)** | Browser nav, form fill, data extraction | Final submissions, payments |
| **Semgrep** | SAST on source code | Runtime analysis |
| **Gitleaks** | Secret detection in code/history | Credential validation |
| **Trivy** | Dependency/container vuln scanning | Code quality |
| **n8n** | Scheduled workflows, recurring tasks | Ad-hoc execution |
| **SQLite** | Task state, job listings, workflow state, findings | Large vector embeddings (later) |
| **Python** | Glue scripts, automation, data processing | UI/UX |

---

## 5. Coding Standards

### 5.1 General
- Python 3.12+ with type hints (`typing` module)
- Functions ≤ 50 lines, classes ≤ 200 lines
- Docstrings for public APIs (Google style)
- No global mutable state
- Structured logging (JSON) to `logs/`

### 5.2 Agent Output Format
All agents return structured JSON:
```json
{
  "status": "success|partial|failed",
  "task": "description",
  "artifacts": ["path/to/file"],
  "findings": [{"type": "...", "severity": "...", "message": "..."}],
  "next_action": "continue|retry|escalate|await_approval",
  "requires_approval": false,
  "metadata": {}
}
```

### 5.3 Error Handling
- Never silently swallow exceptions
- Log full traceback to `logs/`
- Return structured error in JSON output
- Retry with exponential backoff (max 3) for transient failures

### 5.4 Testing
- Unit tests for all scripts in `tests/`
- Integration tests for agent workflows
- Mock external services
- Run `pytest tests/` before any deployment

---

## 6. Workflow Rules

### 6.1 Sequential Workflow Engine
```
Stage 1 (Agent A) → JSON output → Stage 2 (Agent B) → JSON output → ...
```
- Each stage produces JSON with `next_action`
- On failure: record, determine if retry safe, retry ≤ 3x, then escalate
- No blind continuation on failure

### 6.2 State Persistence
- All workflow state in SQLite (`state/agent.db`)
- Tables: `tasks`, `task_state`, `agent_results`, `workflow_state`, `jobs`, `companies`, `applications`, `requirements`, `security_findings`, `approved_actions`
- Schema versioned with migrations

### 6.3 Human Approval Gates
Required before:
- Git push / PR creation
- Job application submission
- Email/message sending
- Package installation
- Destructive commands
- External service modification

Approval request includes:
- Action description
- Risk assessment
- Artifacts to review
- Rollback plan

---

## 7. Agent Definitions

### 7.1 Researcher
- **Permissions:** READ_ONLY
- **Tools:** OpenCode web, MCP servers, Playwright (read-only)
- **Output:** Structured findings with source URLs, dates, fact/inference labels
- **Never:** Fabricate sources, access paywalled content without auth

### 7.2 Job-Hunter
- **Permissions:** READ_ONLY + SAFE_WRITE (SQLite)
- **Tools:** Web search, job board APIs, resume comparison
- **Output:** Scored job records in SQLite
- **Never:** Auto-submit applications

### 7.3 Browser-Agent
- **Permissions:** SAFE_WRITE (temp files)
- **Tools:** Playwright MCP
- **Hard Stops:** Final job submission, financial transactions, account deletion, irreversible messages, contract acceptance, important account settings changes
- **Output:** Extracted data, screenshots, form state

### 7.4 Coder
- **Permissions:** SAFE_WRITE (workspace only)
- **Tools:** OpenCode, Git (local), pytest, linters
- **Output:** Code changes, test results, diff summary
- **Never:** Push to remote, merge PRs

### 7.5 GitHub-Agent
- **Permissions:** APPROVAL_REQUIRED for push/PR
- **Tools:** `gh` CLI, Git
- **Output:** Branch name, commit SHAs, PR URL
- **Never:** Auto-merge PRs

### 7.6 Security-Agent
- **Permissions:** READ_ONLY + SAFE_WRITE (reports)
- **Tools:** Semgrep, Gitleaks, Trivy
- **Output:** Structured findings with severity, CWE, remediation
- **Never:** Silently suppress findings

### 7.7 Reviewer
- **Permissions:** READ_ONLY
- **Tools:** Code inspection, test results, security reports
- **Output:** Approve/Reject with reasoning
- **Never:** Modify code

### 7.8 Orchestrator
- **Permissions:** READ_ONLY + SAFE_WRITE (state) + APPROVAL_REQUIRED delegation
- **Tools:** All agents, SQLite, n8n triggers
- **Output:** Task decomposition, delegation plan, final report
- **Never:** Execute specialized agent tasks directly

---

## 8. Local Model Configuration

### 8.1 Ollama Models (Windows)
| Model | Purpose | RAM (Q4_K_M) |
|-------|---------|--------------|
| `qwen2.5-coder:3b` | Coding, implementation, reasoning | ~2.2 GB |
| `llama3.2:3b` | Classification, summarization, lightweight reasoning | ~2.5 GB |

**Total:** ~4.7 GB RAM (comfortable on 16 GB)

### 8.2 Model Switching
- Default: Local models via Ollama
- Fallback: Cloud models via OpenCode providers (OpenRouter, etc.)
- Switch via `--model` flag or agent config
- No workflow changes needed

---

## 9. GitHub Workflow

```
Issue → Research → Implementation → Tests → Security Scan → Review → Human Approval → Create PR
```

**File:** `workflows/github_issue_to_pr.md`

**Rules:**
- Never auto-merge
- PR requires human approval
- Security scan must pass (or documented exceptions)
- Tests must pass
- Reviewer must approve

---

## 10. Security Scanning Workflow

**File:** `security/scan.sh` (cross-platform Python script)

1. Scan source code (Semgrep)
2. Scan secrets (Gitleaks)
3. Scan dependencies (Trivy)
4. Scan containers if present (Trivy)
5. Generate structured JSON results
6. Security-agent analyzes results
7. Report to `reports/security/`
8. High-severity findings require approval before fix

---

## 11. Scheduling (n8n)

**Workflows:**
- **Daily Morning:** Job search, GitHub notifications, repo health, daily task list
- **Daily Evening:** Unfinished tasks, repo tests, security scans, summary
- **Weekly:** Dependency check, open issues/PRs review, engineering report

**Configuration:** n8n webhooks trigger OpenCode runs with specific prompts

---

## 12. Directory Structure

```
agent-system/
├── AGENTS.md                 # This file
├── README.md                 # User documentation
├── config/                   # Agent configs, model settings
├── agents/                   # Agent definitions (JSON/YAML)
├── skills/                   # OpenCode skills
├── workflows/                # Workflow definitions (Markdown)
├── scripts/                  # Python glue scripts
├── security/                 # Scan scripts, rules
├── state/                    # SQLite database
├── logs/                     # Structured JSON logs
├── reports/                  # Generated reports
│   └── security/             # Security scan reports
└── tests/                    # Unit/integration tests
```

---

## 13. Approval Requirements Summary

| Action | Approval Required | Who Approves |
|--------|-------------------|--------------|
| Git push | Yes | Human |
| Create PR | Yes | Human |
| Merge PR | **Never auto** | Human (manual) |
| Job application submit | Yes | Human |
| Send email/notification | Yes | Human |
| Install package (pip/npm/apt) | Yes | Human |
| Run destructive command | Yes | Human |
| Modify external service config | Yes | Human |
| Run tests | No | - |
| Generate reports | No | - |
| Read files/repos | No | - |
| Local code changes | No | - |

---

## 14. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| RAM exhaustion (16 GB) | 3B models only, monitor, swap configured |
| Secret leakage | No secret logging, Gitleaks pre-commit, env vars only |
| Unauthorized actions | Permission model, approval gates, audit logs |
| Workflow runaway | Max retry limits, structured failure handling, human escalation |
| Model hallucination | Source attribution required, reviewer validation, local models for facts |
| Schedule failures | n8n retry logic, alerting, manual trigger fallback |

---

## 15. Getting Started

```bash
# 1. Start Ollama (if not running)
ollama serve

# 2. Verify models
ollama list

# 3. Run OpenCode with orchestrator agent
cd C:\Users\rishi\agent-system
opencode --agent orchestrator

# 4. Or run scheduled workflows via n8n
n8n start
```

---

## 16. Troubleshooting

| Issue | Check |
|-------|-------|
| Ollama not responding | `ollama serve` running? Port 11434 free? |
| Models not found | `ollama list` shows models? |
| GitHub CLI auth | `gh auth status` valid? |
| Playwright browsers missing | `npx playwright install chromium` |
| Security tools fail | PATH includes tools? Run from WSL2? |
| SQLite locked | Single writer? Check `state/` permissions |
| n8n not triggering | Webhook URLs correct? n8n running? |

---

*End of AGENTS.md*