# GitHub Issue to PR Workflow

**File:** `workflows/github_issue_to_pr.md`  
**Trigger:** Manual or GitHub webhook (issue opened)  
**Agents:** orchestrator → researcher → coder → security-agent → reviewer → github-agent  
**Approval Gates:** Human approval required before PR creation

---

## Workflow Steps

### 1. Issue Analysis (orchestrator → researcher)
- **Input:** GitHub issue number, repository
- **Action:** Fetch issue details, research context if needed
- **Output:** Structured issue understanding, acceptance criteria
- **Agent:** researcher (READ_ONLY)

### 2. Implementation Planning (orchestrator)
- **Input:** Issue understanding
- **Action:** Break down into coding tasks, identify files to modify
- **Output:** Implementation plan with subtasks
- **Agent:** orchestrator (SAFE_WRITE - state)

### 3. Code Implementation (coder)
- **Input:** Implementation plan
- **Action:** 
  - Inspect repository structure
  - Implement changes
  - Write/update tests
  - Run test suite
  - Run linter/type checker
- **Output:** Code changes, test results, diff summary
- **Agent:** coder (SAFE_WRITE - workspace)

### 4. Security Scan (security-agent)
- **Input:** Modified files
- **Action:** Run Semgrep, Gitleaks, Trivy on changed files
- **Output:** Security findings report
- **Agent:** security-agent (READ_ONLY)
- **Gate:** If CRITICAL/HIGH findings → request changes from coder

### 5. Code Review (reviewer)
- **Input:** Code changes, test results, security report
- **Action:** Review for correctness, style, security, regressions
- **Output:** Approve/Reject with reasoning
- **Agent:** reviewer (READ_ONLY)
- **Gate:** If Reject → return to coder with specific issues

### 6. Human Approval Gate (orchestrator)
- **Input:** Reviewer approval, all artifacts
- **Action:** Present summary to human for approval
- **Required:** Human confirms PR creation
- **Output:** Approval granted/denied

### 7. PR Creation (github-agent)
- **Input:** Approved changes, branch name
- **Action:** 
  - Create feature branch
  - Commit changes
  - Push branch
  - Create PR with template
- **Output:** PR URL, branch name
- **Agent:** github-agent (APPROVAL_REQUIRED for push/PR)
- **Note:** NEVER auto-merge

---

## PR Template

```markdown
## Description
Fixes #<issue_number>

## Changes
- <change 1>
- <change 2>

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security scan clean
- [ ] Code review approved

## Security
- [ ] No new secrets
- [ ] No new vulnerabilities
- [ ] Dependencies scanned

## Checklist
- [ ] Conventional commits
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

---

## State Management

SQLite tables updated:
- `tasks` - Main task record
- `agent_results` - Each agent's output
- `workflow_state` - Current step, data
- `security_findings` - Security scan results
- `approved_actions` - Human approvals

---

## Failure Handling

| Failure Point | Action |
|---------------|--------|
| Research fails | Retry with different queries, escalate |
| Implementation fails | Analyze error, retry (max 3), escalate |
| Tests fail | Return to coder with failures |
| Security findings | Return to coder for fixes |
| Review rejects | Return to coder with specific issues |
| Human denies approval | Stop workflow, record reason |
| PR creation fails | Retry, check permissions, escalate |

---

## Example Invocation

```bash
opencode --agent orchestrator "Execute github_issue_to_pr workflow for issue #42 in owner/repo"
```

Or via n8n webhook:
```bash
curl -X POST http://localhost:5678/webhook/github-issue-to-pr \
  -H "Content-Type: application/json" \
  -d '{"issue_number": 42, "owner": "myorg", "repo": "myrepo"}'
```