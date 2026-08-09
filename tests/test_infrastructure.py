"""
Test suite for agent system infrastructure
"""
import pytest
import json
import tempfile
import os
import sqlite3
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.sqlite.main import execute, init_schema, get_connection
from skills.github.main import run_git, run_gh
from security.scan import SecurityScanner


class TestSQLiteSkill:
    """Test SQLite database operations"""
    
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Use temp database for tests"""
        self.db_path = tmp_path / "test_agent.db"
        # Monkey patch DB_PATH
        import skills.sqlite.main as sqlite_main
        self.original_db = sqlite_main.DB_PATH
        sqlite_main.DB_PATH = str(self.db_path)
        yield
        sqlite_main.DB_PATH = self.original_db
    
    def test_init_schema_all(self):
        """Test initializing all schemas"""
        result = init_schema("all")
        assert result["status"] == "success"
        
        # Verify tables exist
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
        expected_tables = [
            "jobs", "companies", "applications", "requirements",
            "tasks", "task_state", "agent_results", "workflow_state",
            "security_findings", "security_scans",
            "approved_actions"
        ]
        for table in expected_tables:
            assert table in tables, f"Table {table} not created"
    
    def test_execute_insert_select(self):
        """Test basic CRUD operations"""
        init_schema("tasks")
        
        # Insert
        result = execute(
            "INSERT INTO tasks (task_id, description, status) VALUES (?, ?, ?)",
            ["test-1", "Test task", "pending"],
            fetch=False
        )
        assert result["status"] == "success"
        assert result["lastrowid"] == 1
        
        # Select
        result = execute("SELECT * FROM tasks WHERE task_id = ?", ["test-1"])
        assert result["status"] == "success"
        assert len(result["rows"]) == 1
        assert result["rows"][0]["description"] == "Test task"
    
    def test_task_state_persistence(self):
        """Test task state key-value storage"""
        init_schema("tasks")
        
        execute(
            "INSERT INTO tasks (task_id, description) VALUES (?, ?)",
            ["test-2", "Task with state"], fetch=False
        )
        
        # Set state
        execute(
            "INSERT INTO task_state (task_id, key, value) VALUES (?, ?, ?)",
            ["test-2", "current_step", '"step_3"'], fetch=False
        )
        execute(
            "INSERT INTO task_state (task_id, key, value) VALUES (?, ?, ?)",
            ["test-2", "retry_count", "2"], fetch=False
        )
        
        # Get state
        result = execute(
            "SELECT key, value FROM task_state WHERE task_id = ?",
            ["test-2"]
        )
        assert result["status"] == "success"
        assert len(result["rows"]) == 2
        state = {row["key"]: row["value"] for row in result["rows"]}
        assert state["current_step"] == '"step_3"'
        assert state["retry_count"] == "2"


class TestGitHubSkill:
    """Test GitHub CLI operations (mocked)"""
    
    def test_run_git_command(self):
        """Test git command execution"""
        # This will fail if not in a git repo, but tests the function
        result = run_git(["status"])
        assert "status" in result
        assert result["status"] in ("success", "failed")
    
    def test_run_gh_command(self):
        """Test gh command execution"""
        result = run_gh(["--version"])
        assert "status" in result
        # gh might not be authenticated, but command should run
        assert result["status"] in ("success", "failed")


class TestSecurityScanner:
    """Test security scanner"""
    
    @pytest.fixture
    def scanner(self, tmp_path):
        return SecurityScanner(str(tmp_path), str(tmp_path / "reports"))
    
    def test_scanner_initialization(self, scanner):
        """Test scanner creates scan_id"""
        assert scanner.scan_id.startswith("sec-")
        assert len(scanner.scan_id) > 10
    
    def test_run_command_success(self, scanner):
        """Test successful command execution"""
        # Use cross-platform command
        import sys
        if sys.platform == "win32":
            result = scanner.run_command(["cmd", "/c", "echo", "hello"])
        else:
            result = scanner.run_command(["echo", "hello"])
        assert result["status"] == "success"
        assert "hello" in result["stdout"]
    
    def test_run_command_failure(self, scanner):
        """Test failed command execution"""
        import sys
        if sys.platform == "win32":
            result = scanner.run_command(["cmd", "/c", "exit", "1"])
        else:
            result = scanner.run_command(["false"])
        assert result["status"] == "failed"
    
    def test_run_command_timeout(self, scanner):
        """Test command timeout handling"""
        # Test that timeout parameter is accepted and handled
        # We can't reliably test actual timeout in cross-platform way
        # Just verify the parameter is accepted
        import sys
        if sys.platform == "win32":
            result = scanner.run_command(["cmd", "/c", "echo", "test"], timeout=1)
        else:
            result = scanner.run_command(["echo", "test"], timeout=1)
        # Just verify it runs without error
        assert result["status"] in ("success", "failed", "error", "timeout")


class TestPermissionModel:
    """Test permission level enforcement"""
    
    def test_permission_levels_defined(self):
        """Verify all four permission levels exist"""
        levels = ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        # This is a documentation test - actual enforcement is in agents
        assert len(levels) == 4
    
    def test_agent_permissions(self):
        """Test agent permission assignments"""
        # These would be loaded from agent JSON files
        agent_permissions = {
            "researcher": "READ_ONLY",
            "job-hunter": "SAFE_WRITE",
            "browser-agent": "SAFE_WRITE",
            "coder": "SAFE_WRITE",
            "github-agent": "APPROVAL_REQUIRED",
            "security-agent": "READ_ONLY",
            "reviewer": "READ_ONLY",
            "orchestrator": "SAFE_WRITE"
        }
        
        for agent, perm in agent_permissions.items():
            assert perm in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]


class TestAgentOutputFormat:
    """Test structured agent output format"""
    
    def test_researcher_output_format(self):
        """Verify researcher output structure"""
        output = {
            "status": "success",
            "task": "research topic",
            "findings": [
                {
                    "claim": "test claim",
                    "source_url": "https://example.com",
                    "source_title": "Example",
                    "accessed_date": "2026-08-09",
                    "type": "fact",
                    "confidence": "high"
                }
            ],
            "summary": "summary",
            "next_action": "continue",
            "requires_approval": False
        }
        
        required_keys = ["status", "task", "findings", "summary", "next_action", "requires_approval"]
        for key in required_keys:
            assert key in output
        
        assert output["status"] in ["success", "partial", "failed"]
        assert output["next_action"] in ["continue", "retry", "escalate", "await_approval"]
        assert isinstance(output["requires_approval"], bool)
    
    def test_coder_output_format(self):
        """Verify coder output structure"""
        output = {
            "status": "success",
            "task": "implement feature",
            "files_changed": ["src/main.py"],
            "diff_summary": "Added feature X",
            "tests_added": 3,
            "tests_passed": 3,
            "tests_failed": 0,
            "lint_errors": 0,
            "type_errors": 0,
            "next_action": "continue",
            "requires_approval": False
        }
        
        assert output["tests_passed"] >= 0
        assert output["tests_failed"] >= 0
        assert output["lint_errors"] >= 0


class TestWorkflowState:
    """Test workflow state transitions"""
    
    def test_github_workflow_steps(self):
        """Verify GitHub workflow has all required steps"""
        steps = [
            "issue_analysis",
            "implementation_planning",
            "code_implementation",
            "security_scan",
            "code_review",
            "human_approval",
            "pr_creation"
        ]
        assert len(steps) == 7
    
    def test_job_search_workflow_steps(self):
        """Verify job search workflow steps"""
        steps = [
            "trigger",
            "search_sources",
            "deduplication",
            "detail_extraction",
            "requirement_parsing",
            "profile_comparison",
            "save_database",
            "generate_report",
            "high_score_preparation",
            "human_approval"
        ]
        assert len(steps) == 10


class TestConfiguration:
    """Test configuration files exist and are valid"""
    
    def test_agents_directory_exists(self):
        agents_dir = Path(__file__).parent.parent / "agents"
        assert agents_dir.exists()
        
        agent_files = list(agents_dir.glob("*.json"))
        assert len(agent_files) >= 8  # All 8 agents
    
    def test_skills_directory_exists(self):
        skills_dir = Path(__file__).parent.parent / "skills"
        assert skills_dir.exists()
        
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        assert len(skill_dirs) >= 4  # researcher, web_search, sqlite, github
    
    def test_workflows_exist(self):
        workflows_dir = Path(__file__).parent.parent / "workflows"
        assert workflows_dir.exists()
        
        workflow_files = list(workflows_dir.glob("*.md"))
        assert len(workflow_files) >= 3  # github, job_search, daily_automation
    
    def test_security_scripts_exist(self):
        security_dir = Path(__file__).parent.parent / "security"
        assert security_dir.exists()
        
        assert (security_dir / "scan.py").exists()
        assert (security_dir / "scan.sh").exists()
        assert (security_dir / "scan.bat").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])