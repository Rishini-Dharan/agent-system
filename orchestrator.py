#!/usr/bin/env python3
"""
Production Orchestrator - Real workflows using:
- opencode run --agent build (web search, coding)
- Python skills (SQLite, GitHub, Security)
"""
import sys
import json
import asyncio
import subprocess
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills.sqlite.main import execute, init_schema
from skills.github.main import run_gh, run_git
from security.scan import SecurityScanner


class Orchestrator:
    def __init__(self):
        self.task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        init_schema("all")
        # Initialize Playwright if available
        self.playwright_available = self._check_playwright()
    
    def _check_playwright(self):
        """Check if Playwright is available"""
        try:
            import playwright
            return True
        except ImportError:
            return False
    
    def log(self, msg):
        print(f"[{self.task_id}] {msg}")
    
    def create_task(self, description, assigned_agent="orchestrator"):
        execute(
            "INSERT INTO tasks (task_id, description, status, assigned_agent) VALUES (?, ?, ?, ?)",
            [self.task_id, description, "running", assigned_agent],
            fetch=False
        )
    
    def save_result(self, agent, subtask, status, output, duration_ms=0):
        execute(
            """INSERT INTO agent_results (task_id, agent_name, subtask, status, output, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [self.task_id, agent, subtask, status, json.dumps(output, default=str), duration_ms],
            fetch=False
        )
    
    def complete_task(self, status="completed"):
        execute(
            "UPDATE tasks SET status = ?, completed_date = ? WHERE task_id = ?",
            [status, datetime.now().isoformat(), self.task_id],
            fetch=False
        )
    
    # ===== INFERENCE ON STORED DATA =====
    
    def get_past_research(self, topic_keywords=None, limit=10):
        """Retrieve past research from database"""
        if topic_keywords:
            # Search in agent_results output
            results = execute("""
                SELECT ar.subtask, ar.output, ar.created_date 
                FROM agent_results ar
                WHERE ar.agent_name = 'researcher'
                AND ar.subtask LIKE ?
                ORDER BY ar.created_date DESC
                LIMIT ?
            """, [f"%{topic_keywords}%", limit])
        else:
            results = execute("""
                SELECT ar.subtask, ar.output, ar.created_date 
                FROM agent_results ar
                WHERE ar.agent_name = 'researcher'
                ORDER BY ar.created_date DESC
                LIMIT ?
            """, [limit])
        return results.get("rows", [])
    
    def get_past_code(self, limit=10):
        """Retrieve past code tasks"""
        results = execute("""
            SELECT ar.subtask, ar.output, ar.created_date 
            FROM agent_results ar
            WHERE ar.agent_name = 'coder'
            ORDER BY ar.created_date DESC
            LIMIT ?
        """, [limit])
        return results.get("rows", [])
    
    def get_past_scans(self, limit=5):
        """Retrieve past security scans"""
        results = execute("""
            SELECT scan_id, target_path, summary, created_date
            FROM security_scans
            ORDER BY created_date DESC
            LIMIT ?
        """, [limit])
        return results.get("rows", [])
    
    def reason_over_data(self, question, context_types=None):
        """
        Query stored data and use model to reason/infer
        context_types: list of ['research', 'code', 'security', 'jobs', 'github']
        """
        context = []
        
        if not context_types:
            context_types = ['research', 'code', 'security']
        
        if 'research' in context_types:
            past = self.get_past_research(limit=10)
            for r in past:
                context.append(f"RESEARCH ({r['created_date']}): {r['subtask']}\n{r['output'][:2000]}")
        
        if 'code' in context_types:
            past = self.get_past_code(limit=3)
            for r in past:
                context.append(f"CODE ({r['created_date']}): {r['subtask']}\n{r['output'][:1500]}")
        
        if 'security' in context_types:
            past = self.get_past_scans(limit=2)
            for r in past:
                context.append(f"SECURITY SCAN ({r['created_date']}): {r['scan_id']} - {r['summary']}")
        
        if 'jobs' in context_types:
            results = execute("SELECT title, company, score, status FROM jobs ORDER BY score DESC LIMIT 10")
            for r in results.get("rows", []):
                context.append(f"JOB: {r['title']} at {r['company']} - Score: {r['score']} - Status: {r['status']}")
        
        context_str = "\n\n---\n\n".join(context) if context else "No past data available."
        
        prompt = f"""You have access to historical agent data. Answer the question based on this context.

CONTEXT FROM PAST RUNS:
{context_str}

QUESTION: {question}

Provide a clear, structured answer citing specific past runs where relevant."""
        
        result = self.opencode_run("build", prompt)
        
        if result["status"] == "success":
            try:
                print("\n" + "="*80)
                print(f"INFERENCE RESULT: {question}")
                print("="*80)
                print(result["stdout"])
                print("="*80 + "\n")
            except UnicodeEncodeError:
                safe_output = result["stdout"].encode('ascii', 'replace').decode('ascii')
                print("\n" + "="*80)
                print(f"INFERENCE RESULT: {question}")
                print("="*80)
                print(safe_output)
                print("="*80 + "\n")
        
        return result
    
    def synthesize_research(self, topic):
        """Synthesize multiple past research runs on a topic"""
        past = self.get_past_research(topic, limit=10)
        if not past:
            return {"status": "no_data", "message": f"No past research on '{topic}'"}
        
        all_findings = []
        for r in past:
            all_findings.append(f"Run: {r['subtask']} ({r['created_date']})\n{r['output'][:3000]}")
        
        combined = "\n\n---\n\n".join(all_findings)
        
        prompt = f"""Synthesize findings from multiple research runs on "{topic}".

PAST RESEARCH RUNS:
{combined}

Provide:
1. Consolidated key findings (remove duplicates)
2. Conflicting information if any
3. Most recent/best sources
4. Gaps in knowledge
5. Recommended next research steps"""
        
        result = self.opencode_run("build", prompt)
        
        if result["status"] == "success":
            print("\n" + "="*80)
            print(f"SYNTHESIS: {topic}")
            print("="*80)
            print(result["stdout"])
            print("="*80 + "\n")
        
        return result
    
    # ===== BROWSER AUTOMATION (Direct Playwright) =====
    
    def browser_navigate(self, url, wait_for=None, screenshot=False):
        """Navigate to URL and extract content"""
        if not self.playwright_available:
            return {"status": "error", "message": "Playwright not installed. Run: pip install playwright && playwright install chromium"}
        
        script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("{url}", wait_until="networkidle")
"""
        if wait_for:
            script += f'        await page.wait_for_selector("{wait_for}")\n'
        
        script += """        content = await page.content()
        text = await page.inner_text("body")
        title = await page.title()
        url = page.url
"""
        if screenshot:
            script += f'        await page.screenshot(path="screenshot_{self.task_id}.png")\n'
        
        script += """        await browser.close()
        import json
        print(json.dumps({"title": title, "url": url, "text": text[:10000], "html": content[:20000]}))
        
asyncio.run(main())
"""
        try:
            result = subprocess.run(
                ["python", "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path(__file__).parent)
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout.strip())
                return {"status": "success", "data": data}
            else:
                return {"status": "failed", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def browser_interact(self, url, actions, screenshot=False):
        """
        Perform interactions on a page
        actions: list of dicts like:
          - {"action": "click", "selector": "button#submit"}
          - {"action": "fill", "selector": "input[name='email']", "value": "test@test.com"}
          - {"action": "wait", "selector": ".result"}
          - {"action": "extract", "selector": ".job-listing", "attr": "text"}
        """
        if not self.playwright_available:
            return {"status": "error", "message": "Playwright not installed"}
        
        # Build action script
        action_script = ""
        for i, act in enumerate(actions):
            a = act["action"]
            sel = act.get("selector", "")
            # Escape for Python string
            sel_escaped = sel.replace('"', '\\"').replace("'", "\\'")
            if a == "click":
                action_script += f'        await page.click("{sel_escaped}")\n'
            elif a == "fill":
                val = act.get("value", "").replace('"', '\\"').replace("'", "\\'")
                action_script += f'        await page.fill("{sel_escaped}", "{val}")\n'
            elif a == "wait":
                action_script += f'        await page.wait_for_selector("{sel_escaped}")\n'
            elif a == "extract":
                attr = act.get("attr", "text")
                if attr == "text":
                    action_script += f'        data_{i} = await page.locator("{sel_escaped}").inner_text()\n'
                else:
                    action_script += f'        data_{i} = await page.locator("{sel_escaped}").get_attribute("{attr}")\n'
        
        script = f"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("{url}", wait_until="networkidle")
{action_script}
        await browser.close()
        print(json.dumps({{ "extracted": [data_{i} for i in range({len(actions)})] }}))
        
asyncio.run(main())
"""
        try:
            result = subprocess.run(
                ["python", "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path(__file__).parent)
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout.strip())
                return {"status": "success", "data": data}
            else:
                return {"status": "failed", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def browser_search_jobs(self, query, max_pages=3):
        """Search job boards and extract listings"""
        # This would use browser_navigate + browser_interact
        # For now, use the web search approach which works
        return self.research(f"job listings {query}")
    
    def opencode_run(self, agent, prompt):
        """Run opencode agent and return output"""
        self.log(f"Running {agent}: {prompt[:80]}...")
        try:
            import platform
            import tempfile
            
            if platform.system() == "Windows":
                opencode_path = r"C:\Users\rishi\AppData\Roaming\npm\opencode.ps1"
                # Write prompt to temp file to avoid PowerShell escaping issues
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                    f.write(prompt)
                    prompt_file = f.name
                
                try:
                    cmd = ["powershell", "-Command", f"Get-Content '{prompt_file}' -Raw | & '{opencode_path}' run --agent {agent}"]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        cwd=str(Path(__file__).parent),
                        encoding='utf-8',
                        errors='replace'
                    )
                finally:
                    import os
                    os.unlink(prompt_file)
            else:
                env = os.environ.copy()
                result = subprocess.run(
                    ["opencode", "run", "--agent", agent, prompt],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=str(Path(__file__).parent),
                    env=env
                )
            return {
                "status": "success" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Command timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def research(self, topic):
        """Real web research using build agent"""
        self.create_task(f"Research: {topic}")
        
        prompt = f"""Search web for "{topic}" and return structured results with:
1. Source URL and title
2. Publication/access date
3. Key findings as bullet points
4. Distinguish facts from opinions
5. Cite all sources"""
        
        result = self.opencode_run("build", prompt)
        
        findings = []
        if result["status"] == "success":
            # Parse output into structured findings
            findings.append({
                "topic": topic,
                "sources_found": result["stdout"],
                "agent": "build",
                "raw_output": result["stdout"]
            })
            
            # ALSO PRINT TO CONSOLE (handle encoding)
            try:
                print("\n" + "="*80)
                print(f"RESEARCH RESULTS: {topic}")
                print("="*80)
                print(result["stdout"])
                print("="*80 + "\n")
            except UnicodeEncodeError:
                # Fallback: replace unencodable chars
                safe_output = result["stdout"].encode('ascii', 'replace').decode('ascii')
                print("\n" + "="*80)
                print(f"RESEARCH RESULTS: {topic}")
                print("="*80)
                print(safe_output)
                print("="*80 + "\n")
        
        self.save_result("researcher", topic, "completed", findings)
        self.complete_task("completed")
        return {"status": "success", "findings": findings, "raw": result}
    
    def code_task(self, prompt):
        """Real coding using build agent"""
        self.create_task(f"Code: {prompt}")
        
        result = self.opencode_run("build", prompt)
        
        output = result.get("stdout", "") if result else ""
        
        # PRINT TO CONSOLE (handle encoding)
        if output:
            try:
                print("\n" + "="*80)
                print(f"CODE TASK RESULT: {prompt[:60]}...")
                print("="*80)
                print(output)
                print("="*80 + "\n")
            except UnicodeEncodeError:
                safe_output = output.encode('ascii', 'replace').decode('ascii')
                print("\n" + "="*80)
                print(f"CODE TASK RESULT: {prompt[:60]}...")
                print("="*80)
                print(safe_output)
                print("="*80 + "\n")
        
        self.save_result("coder", prompt, "completed", {"output": output, "result": result})
        self.complete_task("completed")
        return result
    
    def github_workflow(self, issue_number, owner, repo):
        """Full GitHub issue → PR workflow"""
        self.create_task(f"GitHub #{issue_number} in {owner}/{repo}")
        
        # Get issue
        self.log(f"Fetching issue #{issue_number}...")
        issue_result = run_gh(["issue", "view", str(issue_number), "--repo", f"{owner}/{repo}", "--json", "title,body,labels"])
        if issue_result["status"] != "success":
            return {"status": "failed", "error": issue_result.get("error")}
        
        import json as json_lib
        issue = json_lib.loads(issue_result["stdout"])
        self.log(f"Issue: {issue['title']}")
        
        # Research context if needed
        research_result = self.research(f"implement fix for {issue['title']} {issue.get('body', '')[:500]}")
        
        # Create branch
        branch = f"issue-{issue_number}-{issue['title'][:30].lower().replace(' ', '-')}"
        self.log(f"Creating branch: {branch}")
        run_git(["fetch", "origin"])
        run_git(["checkout", "-b", branch, "origin/main"])
        
        # Implement fix
        code_prompt = f"""Implement fix for GitHub issue #{issue_number} in {owner}/{repo}:
Title: {issue['title']}
Body: {issue.get('body', 'No description')}
Labels: {', '.join([l['name'] for l in issue.get('labels', [])])}

Requirements:
- Follow existing code patterns in this repo
- Add tests
- Run existing tests to verify no regressions
- Use conventional commit messages"""
        
        self.log("Implementing fix...")
        code_result = self.code_task(code_prompt)
        
        # Security scan
        self.log("Running security scan...")
        scanner = SecurityScanner(".")
        scan_result = scanner.run_all()
        
        if scan_result["summary"]["critical"] > 0 or scan_result["summary"]["high"] > 0:
            self.log("SECURITY: Critical/High findings - fix required")
            return {"status": "security_failed", "scan": scan_result}
        
        # Commit and push
        self.log("Committing and pushing...")
        run_git(["add", "."])
        run_git(["commit", "-m", f"Fix #{issue_number}: {issue['title']}"])
        run_git(["push", "origin", branch])
        
        # Create PR
        pr_result = run_gh(["pr", "create", "--title", f"Fix #{issue_number}: {issue['title']}", 
                           "--body", f"Closes #{issue_number}\n\nFixes: {issue['title']}", "--base", "main", "--head", branch])
        
        self.complete_task("completed")
        return {
            "status": "success" if pr_result["status"] == "success" else "pr_failed",
            "branch": branch,
            "pr_url": pr_result.get("stdout", "").strip(),
            "scan": scan_result
        }
    
    def job_search(self, config_path="config/job_search.yaml"):
        """Daily job search workflow"""
        self.create_task("Daily job search")
        
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        all_jobs = []
        for keyword in config['search']['keywords']:
            for location in config['search']['locations']:
                query = f"{keyword} jobs {location} site:linkedin.com OR site:indeed.com OR site:github.com"
                self.log(f"Searching: {query}")
                result = self.research(query)
                all_jobs.append({"query": query, "result": result})
        
        self.complete_task("completed")
        return {"status": "success", "searches": len(all_jobs), "results": all_jobs}
    
    def security_scan(self, path=".", image=None):
        """Run security scan"""
        self.create_task(f"Security scan of {path}")
        
        scanner = SecurityScanner(path)
        result = scanner.run_all(include_image=image)
        
        # Results already printed by SecurityScanner class
        
        self.complete_task("completed")
        return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <command> [args...]")
        print("Commands:")
        print("  research <topic>                    - Real web research")
        print("  code <prompt>                       - Real coding task")
        print("  github <issue_number> <owner> <repo> - Full Issue→PR workflow")
        print("  jobs                                - Daily job search")
        print("  security [path] [image]             - Security scan")
        print("  infer <question> [--type research|code|security|jobs] - Reason over stored data")
        print("  synthesize <topic>                  - Synthesize past research on topic")
        print("  browse <url> [--wait selector] [--screenshot] - Navigate and extract")
        print("  interact <url> <actions_json>       - Browser interaction")
        sys.exit(1)
    
    cmd = sys.argv[1]
    orch = Orchestrator()
    
    if cmd == "research":
        topic = " ".join(sys.argv[2:])
        result = orch.research(topic)
        print(json.dumps({"status": result["status"]}, indent=2))
    
    elif cmd == "code":
        prompt = " ".join(sys.argv[2:])
        result = orch.code_task(prompt)
        print(json.dumps({"status": result["status"]}, indent=2))
    
    elif cmd == "github":
        if len(sys.argv) != 5:
            print("Usage: python orchestrator.py github <issue_number> <owner> <repo>")
            sys.exit(1)
        result = orch.github_workflow(int(sys.argv[2]), sys.argv[3], sys.argv[4])
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "jobs":
        result = orch.job_search()
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "security":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        image = sys.argv[3] if len(sys.argv) > 3 else None
        result = orch.security_scan(path, image)
        print(json.dumps({"scan_id": result["scan_id"], "summary": result["summary"]}, indent=2))
    
    elif cmd == "infer":
        # Parse args
        question = ""
        context_types = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--type":
                context_types = sys.argv[i+1].split(",")
                i += 2
            else:
                question += " " + sys.argv[i]
                i += 1
        question = question.strip()
        if not question:
            print("Usage: python orchestrator.py infer <question> [--type research,code,security,jobs]")
            sys.exit(1)
        result = orch.reason_over_data(question, context_types)
        print(json.dumps({"status": result["status"]}, indent=2))
    
    elif cmd == "synthesize":
        topic = " ".join(sys.argv[2:])
        result = orch.synthesize_research(topic)
        print(json.dumps({"status": result["status"]}, indent=2))
    
    elif cmd == "browse":
        if len(sys.argv) < 3:
            print("Usage: python orchestrator.py browse <url> [--wait selector] [--screenshot]")
            sys.exit(1)
        url = sys.argv[2]
        wait_for = None
        screenshot = False
        for i, arg in enumerate(sys.argv[3:], 3):
            if arg == "--wait" and i+1 < len(sys.argv):
                wait_for = sys.argv[i+1]
            elif arg == "--screenshot":
                screenshot = True
        result = orch.browser_navigate(url, wait_for, screenshot)
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "interact":
        if len(sys.argv) < 4:
            print('Usage: python orchestrator.py interact <url> <actions_json_file>')
            sys.exit(1)
        url = sys.argv[2]
        actions_file = sys.argv[3]
        with open(actions_file, 'r') as f:
            actions = json.load(f)
        result = orch.browser_interact(url, actions)
        print(json.dumps(result, indent=2, default=str))
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()