# Job Search Workflow

**File:** `workflows/job_search.md`  
**Trigger:** Scheduled (daily morning via n8n) or Manual  
**Agents:** orchestrator → job-hunter → browser-agent (for detail extraction)  
**Approval Gates:** Human approval required before application submission

---

## Workflow Steps

### 1. Scheduled Trigger (n8n)
- **Schedule:** Daily 8:00 AM local time
- **Action:** Trigger orchestrator with job search task
- **Parameters:** Search keywords, locations, filters from config

### 2. Search Job Sources (job-hunter)
- **Sources:** LinkedIn, Indeed, Glassdoor, company career pages, GitHub Jobs, Wellfound, etc.
- **Queries:** Configurable per user profile (e.g., "Python backend", "Remote", "Senior")
- **Filters:** Date posted (last 24h), location, salary range, experience level
- **Output:** Raw job listings with URLs
- **Agent:** job-hunter (READ_ONLY + SAFE_WRITE for SQLite)

### 3. Deduplication (job-hunter)
- **Method:** Match by company + title + location (fuzzy)
- **Action:** Keep most complete listing, merge sources
- **Output:** Deduplicated job list

### 4. Detail Extraction (browser-agent → job-hunter)
- **For each new job:** Navigate to job URL
- **Extract:** Full description, requirements, benefits, application process
- **Hard Stop:** Browser-agent stops before any application submission
- **Output:** Structured job details
- **Agent:** browser-agent (SAFE_WRITE - temp files)

### 5. Requirement Parsing (job-hunter)
- **Action:** Extract structured requirements:
  - Required skills (must have)
  - Preferred skills (nice to have)
  - Experience years
  - Education
  - Certifications
  - Soft skills
- **Store:** In `requirements` table linked to job

### 6. Profile Comparison (job-hunter)
- **Input:** User profile (skills, experience, preferences from config)
- **Algorithm:** 
  - Required skills match: 40%
  - Preferred skills match: 20%
  - Experience level: 20%
  - Location preference: 10%
  - Salary expectation: 10%
- **Output:** Score 0-100 for each job

### 7. Save to Database (job-hunter)
- **Tables:** `jobs`, `companies`, `requirements`
- **Update:** Existing records if re-scraped
- **Index:** For fast querying

### 8. Generate Daily Report (job-hunter)
- **Content:** 
  - Total jobs found
  - New jobs today
  - Top 10 matches (score > 70)
  - Companies hiring
  - Skill gaps analysis
- **Format:** Markdown + JSON
- **Output:** `reports/jobs/daily-YYYYMMDD.md`

### 9. High-Score Job Preparation (job-hunter)
- **Trigger:** Score > 80
- **Action:** 
  - Generate tailored resume bullets
  - Draft cover letter template
  - Identify application questions
  - Prepare portfolio links
- **Output:** Application package in `state/applications/`
- **Gate:** STOP - Request human approval

### 10. Human Review & Approval
- **Action:** Present top matches and prepared applications
- **Human Decides:** Apply / Skip / Modify
- **If Apply:** Browser-agent fills application (with human oversight)
- **Record:** Application status in `applications` table

---

## Database Schema (SQLite)

```sql
-- Jobs table (in skills/sqlite/main.py)
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE,  -- Source-specific ID
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    currency TEXT DEFAULT 'USD',
    employment_type TEXT,  -- full-time, contract, part-time
    experience_level TEXT,  -- entry, mid, senior, lead
    description TEXT,
    requirements TEXT,  -- JSON array
    url TEXT UNIQUE,
    source TEXT,  -- linkedin, indeed, etc.
    posted_date TEXT,
    scraped_date TEXT DEFAULT CURRENT_TIMESTAMP,
    score INTEGER DEFAULT 0,
    match_reasons TEXT,  -- JSON array
    gaps TEXT,  -- JSON array
    status TEXT DEFAULT 'new'  -- new, reviewing, applying, applied, rejected, offer
);

CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    website TEXT,
    industry TEXT,
    size TEXT,
    location TEXT,
    description TEXT,
    created_date TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    company_id INTEGER REFERENCES companies(id),
    status TEXT DEFAULT 'preparing',  -- preparing, submitted, interview, offer, rejected
    applied_date TEXT,
    resume_version TEXT,
    cover_letter TEXT,
    notes TEXT,
    created_date TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE requirements (
    id INTEGER PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    requirement TEXT NOT NULL,
    category TEXT,  -- 'required', 'preferred', 'nice_to_have'
    matched BOOLEAN DEFAULT FALSE,
    user_skill_level TEXT  -- 'expert', 'proficient', 'familiar', 'none'
);
```

---

## Configuration

`config/job_search.yaml`:
```yaml
search:
  keywords:
    - "Python backend"
    - "FastAPI"
    - "Django"
    - "Software Engineer"
  locations:
    - "Remote"
    - "Seattle, WA"
    - "San Francisco, CA"
  exclude_keywords:
    - "unpaid"
    - "internship"
    - "volunteer"
  experience_years: 5
  salary_min: 120000

sources:
  - linkedin
  - indeed
  - glassdoor
  - github_jobs
  - wellfound

profile:
  skills:
    - name: "Python"
      level: "expert"
      years: 8
    - name: "FastAPI"
      level: "proficient"
      years: 3
    - name: "PostgreSQL"
      level: "expert"
      years: 7
    - name: "Docker"
      level: "proficient"
      years: 5
    - name: "AWS"
      level: "familiar"
      years: 3
  preferences:
    remote: true
    hybrid: true
    onsite: false
    visa_sponsorship: false

scoring:
  weights:
    required_skills: 0.4
    preferred_skills: 0.2
    experience: 0.2
    location: 0.1
    salary: 0.1
  thresholds:
    auto_prepare: 80
    notify: 70
    archive: 40
```

---

## n8n Workflow

```json
{
  "name": "Daily Job Search",
  "nodes": [
    {
      "name": "Cron",
      "type": "n8n-nodes-base.cron",
      "parameters": {
        "triggerTimes": {
          "item": [{"hour": 8, "minute": 0}]
        }
      }
    },
    {
      "name": "Trigger Orchestrator",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://localhost:5678/webhook/job-search",
        "jsonParameters": true,
        "options": {},
        "bodyParametersJson": {
          "task": "daily_job_search",
          "config": "config/job_search.yaml"
        }
      }
    }
  ],
  "connections": {
    "Cron": {"main": [["Trigger Orchestrator"]]}
  }
}
```

---

## Example Invocation

```bash
# Manual run
opencode --agent orchestrator "Run daily job search workflow with config/job_search.yaml"

# Via n8n webhook
curl -X POST http://localhost:5678/webhook/job-search \
  -H "Content-Type: application/json" \
  -d '{"task": "daily_job_search"}'
```

---

## Output Artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| Daily Report | `reports/jobs/daily-YYYYMMDD.md` | Human-readable summary |
| Job Data | `state/agent.db` | SQLite with all jobs |
| Applications | `state/applications/` | Prepared application packages |
| Skill Gaps | `reports/jobs/skill-gaps-YYYYMMDD.md` | Missing skills analysis |