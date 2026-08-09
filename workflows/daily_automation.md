# Daily Automation Workflows

**File:** `workflows/daily_automation.md`  
**Scheduler:** n8n (preferred) or Windows Task Scheduler  
**Workflows:** Morning, Evening, Weekly

---

## DAILY MORNING (8:00 AM)

### Trigger
- n8n Cron: Daily 8:00 AM
- Or Windows Task Scheduler: `0 8 * * *`

### Steps

1. **Job Search** (job-hunter)
   - Run `job_search` workflow
   - Output: Daily job report

2. **GitHub Notifications** (github-agent)
   - Check assigned issues
   - Check review requests
   - Check CI/CD failures on watched repos
   - Output: Notification summary

3. **Repository Health** (coder + security-agent)
   - For each configured repo:
     - Pull latest
     - Run tests
     - Check dependency updates
   - Output: Health report per repo

4. **Generate Daily Task List** (orchestrator)
   - Consolidate: Job matches, GitHub items, Repo issues
   - Prioritize by urgency/impact
   - Output: `reports/daily/tasks-YYYYMMDD.md`

5. **Daily Morning Report** (orchestrator)
   - Combine all above
   - Send notification (if configured)
   - Output: `reports/daily/morning-YYYYMMDD.md`

### n8n Workflow Structure
```json
{
  "name": "Daily Morning",
  "nodes": [
    {"name": "Cron", "type": "cron", "parameters": {"hour": 8}},
    {"name": "Job Search", "type": "httpRequest", "parameters": {"url": "http://localhost:5678/webhook/job-search"}},
    {"name": "GitHub Check", "type": "httpRequest", "parameters": {"url": "http://localhost:5678/webhook/github-check"}},
    {"name": "Repo Health", "type": "httpRequest", "parameters": {"url": "http://localhost:5678/webhook/repo-health"}},
    {"name": "Generate Report", "type": "httpRequest", "parameters": {"url": "http://localhost:5678/webhook/generate-daily-report"}}
  ]
}
```

---

## DAILY EVENING (6:00 PM)

### Trigger
- n8n Cron: Daily 18:00
- Or Windows Task Scheduler: `0 18 * * *`

### Steps

1. **Check Unfinished Tasks** (orchestrator)
   - Query `tasks` table for `status != 'completed'`
   - Identify blocked/stalled tasks
   - Output: Unfinished task list

2. **Run Repository Tests** (coder)
   - For each repo with `test_on_schedule: true`:
     - Pull latest
     - Run full test suite
     - Capture results
   - Output: Test results summary

3. **Security Scans** (security-agent)
   - Run on all configured repos
   - Incremental scan (changed files only)
   - Output: Security findings

4. **Summarize Changes** (orchestrator)
   - Git log since morning
   - Files changed
   - Commits made
   - PRs created/updated
   - Output: Change summary

5. **Evening Report** (orchestrator)
   - Combine: Unfinished tasks, test results, security findings, changes
   - Flag items needing attention
   - Output: `reports/daily/evening-YYYYMMDD.md`

6. **Cleanup** (orchestrator)
   - Archive old logs (>30 days)
   - Vacuum SQLite
   - Temp file cleanup

---

## WEEKLY (Monday 9:00 AM)

### Trigger
- n8n Cron: Weekly Monday 9:00
- Or Windows Task Scheduler: `0 9 * * 1`

### Steps

1. **Repository Deep Scan** (coder + security-agent)
   - Full dependency audit (Trivy)
   - Full SAST scan (Semgrep)
   - Secret scan full history (Gitleaks)
   - License compliance check
   - Output: Weekly security report

2. **Dependency Updates** (coder)
   - Check for outdated packages
   - Categorize: patch, minor, major
   - Create update PRs for patch/minor (auto)
   - Flag major for manual review
   - Output: Dependency report

3. **Open Issues Review** (github-agent)
   - List open issues across repos
   - Categorize: bug, feature, docs, stale
   - Identify stale (>30 days no activity)
   - Output: Issues report

4. **Open PRs Review** (github-agent)
   - List open PRs
   - Check: review status, CI, conflicts, age
   - Identify stale PRs (>14 days)
   - Output: PRs report

5. **Weekly Engineering Report** (orchestrator)
   - Combine all weekly data
   - Metrics: 
     - Commits this week
     - PRs opened/merged
     - Issues closed
     - Tests passing rate
     - Security findings trend
     - Job applications status
   - Output: `reports/weekly/engineering-YYYYMMDD.md`

6. **Strategic Planning** (orchestrator)
   - Review goals progress
   - Identify next week priorities
   - Output: `reports/weekly/plan-YYYYMMDD.md`

---

## Configuration

`config/scheduler.yaml`:
```yaml
timezone: "America/Los_Angeles"

morning:
  enabled: true
  time: "08:00"
  tasks:
    - job_search
    - github_notifications
    - repo_health
    - daily_task_list
    - morning_report

evening:
  enabled: true
  time: "18:00"
  tasks:
    - unfinished_tasks
    - repo_tests
    - security_scans
    - change_summary
    - evening_report
    - cleanup

weekly:
  enabled: true
  day: "monday"
  time: "09:00"
  tasks:
    - deep_security_scan
    - dependency_audit
    - issues_review
    - prs_review
    - engineering_report
    - strategic_plan

repos:
  - path: "~/projects/my-project"
    test_on_schedule: true
    security_scan: true
  - path: "~/projects/another-repo"
    test_on_schedule: false
    security_scan: true

notifications:
  enabled: true
  channels:
    - type: "file"
      path: "reports/notifications/"
    # - type: "email"
    #   to: "user@example.com"
    # - type: "webhook"
    #   url: "https://hooks.slack.com/..."
```

---

## Report Templates

### Morning Report (`reports/daily/morning-YYYYMMDD.md`)
```markdown
# Daily Morning Report - YYYY-MM-DD

## Job Matches (Top 5)
| Score | Title | Company | Location | Status |
|-------|-------|---------|----------|--------|
| 92 | Senior Python Engineer | Acme Corp | Remote | New |
| 87 | Backend Developer | TechCo | Seattle | Reviewing |

## GitHub Notifications
- 📋 3 assigned issues
- 👀 2 review requests
- ⚠️ 1 CI failure on my-project

## Repository Health
| Repo | Tests | Dependencies | Status |
|------|-------|--------------|--------|
| my-project | ✅ 42/42 | 3 outdated | Healthy |
| another-repo | ⏭️ Skipped | 1 critical | Needs attention |

## Today's Priorities
1. Review PR #123 (security fix)
2. Apply to Acme Corp role
3. Investigate CI failure on my-project
```

### Evening Report (`reports/daily/evening-YYYYMMDD.md`)
```markdown
# Daily Evening Report - YYYY-MM-DD

## Unfinished Tasks
- [ ] Task #45: Implement OAuth (blocked on review)
- [ ] Task #46: Update dependencies (in progress)

## Test Results
| Repo | Passed | Failed | Coverage |
|------|--------|--------|----------|
| my-project | 42 | 0 | 87% |

## Security Findings
- 🔴 1 CRITICAL: SQL injection in user_input.py:45
- 🟡 3 MEDIUM: Outdated dependencies

## Changes Today
- 3 commits on feature/oauth
- PR #124 created: Fix SQL injection
- 2 files modified

## Action Items for Tomorrow
1. Fix SQL injection (CRITICAL)
2. Complete OAuth implementation
3. Review dependency updates
```

### Weekly Report (`reports/weekly/engineering-YYYYMMDD.md`)
```markdown
# Weekly Engineering Report - Week of YYYY-MM-DD

## Metrics
| Metric | This Week | Last Week | Trend |
|--------|-----------|-----------|-------|
| Commits | 23 | 18 | 📈 +28% |
| PRs Opened | 5 | 3 | 📈 +67% |
| PRs Merged | 4 | 2 | 📈 +100% |
| Issues Closed | 7 | 5 | 📈 +40% |
| Test Pass Rate | 98% | 95% | 📈 +3% |
| Critical Security | 1 | 0 | 📉 New |

## Security Summary
- New findings: 12 (1 CRITICAL, 4 HIGH, 7 MEDIUM)
- Fixed: 8
- Outstanding: 4

## Dependency Updates
- Patch: 12 applied
- Minor: 3 PRs created
- Major: 2 flagged for review

## Job Search
- New listings: 47
- Applications prepared: 3
- Interviews scheduled: 1

## Next Week Priorities
1. Resolve CRITICAL security finding
2. Merge pending PRs
3. Complete OAuth feature
4. Review major dependency updates
```

---

## n8n Import

Import these workflows in n8n:
1. `workflows/n8n/daily-morning.json`
2. `workflows/n8n/daily-evening.json`
3. `workflows/n8n/weekly.json`

Or create manually using the structure above.