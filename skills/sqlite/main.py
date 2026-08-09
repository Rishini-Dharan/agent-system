"""
SQLite Skill - Database operations for agent state persistence
"""
import json
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import contextmanager


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "state", "agent.db")


SCHEMAS = {
    "jobs": """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT UNIQUE,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            currency TEXT DEFAULT 'USD',
            employment_type TEXT,
            experience_level TEXT,
            description TEXT,
            requirements TEXT,  -- JSON array
            url TEXT UNIQUE,
            source TEXT,
            posted_date TEXT,
            scraped_date TEXT DEFAULT CURRENT_TIMESTAMP,
            score INTEGER DEFAULT 0,
            match_reasons TEXT,  -- JSON array
            gaps TEXT,  -- JSON array
            status TEXT DEFAULT 'new'
        );
        
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            website TEXT,
            industry TEXT,
            size TEXT,
            location TEXT,
            description TEXT,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            company_id INTEGER REFERENCES companies(id),
            status TEXT DEFAULT 'preparing',
            applied_date TEXT,
            resume_version TEXT,
            cover_letter TEXT,
            notes TEXT,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            requirement TEXT NOT NULL,
            category TEXT,  -- 'required', 'preferred', 'nice_to_have'
            matched BOOLEAN DEFAULT FALSE,
            user_skill_level TEXT
        );
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            parent_task_id TEXT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            assigned_agent TEXT,
            input_data TEXT,  -- JSON
            output_data TEXT,  -- JSON
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            started_date TEXT,
            completed_date TEXT
        );
        
        CREATE TABLE IF NOT EXISTS task_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT REFERENCES tasks(task_id),
            key TEXT NOT NULL,
            value TEXT,  -- JSON
            updated_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS agent_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT REFERENCES tasks(task_id),
            agent_name TEXT NOT NULL,
            subtask TEXT,
            status TEXT,
            output TEXT,  -- JSON
            duration_ms INTEGER,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS workflow_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            current_step TEXT,
            state_data TEXT,  -- JSON
            status TEXT DEFAULT 'running',
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "security": """
        CREATE TABLE IF NOT EXISTS security_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT NOT NULL,
            tool TEXT NOT NULL,  -- 'semgrep', 'gitleaks', 'trivy'
            rule_id TEXT,
            severity TEXT,  -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
            file_path TEXT,
            line_number INTEGER,
            message TEXT,
            cwe TEXT,
            cve TEXT,
            remediation TEXT,
            status TEXT DEFAULT 'open',  -- 'open', 'acknowledged', 'fixed', 'false_positive'
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS security_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT UNIQUE NOT NULL,
            scan_type TEXT,  -- 'full', 'incremental', 'pr'
            target_path TEXT,
            tools_run TEXT,  -- JSON array
            findings_count INTEGER DEFAULT 0,
            critical_count INTEGER DEFAULT 0,
            high_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "approvals": """
        CREATE TABLE IF NOT EXISTS approved_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,  -- 'git_push', 'create_pr', 'submit_job_app', 'send_email', 'install_package', 'destructive_command'
            description TEXT NOT NULL,
            context TEXT,  -- JSON
            requested_by TEXT,  -- agent name
            approved_by TEXT,  -- 'human'
            approved_date TEXT,
            expires_date TEXT,
            status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'denied', 'expired'
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """
}


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(query: str, params: List = None, fetch: bool = True) -> Dict[str, Any]:
    """Execute a SQL query"""
    params = params or []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch:
                rows = cursor.fetchall()
                return {
                    "status": "success",
                    "rows": [dict(row) for row in rows],
                    "rowcount": cursor.rowcount,
                    "lastrowid": cursor.lastrowid
                }
            else:
                return {
                    "status": "success",
                    "rowcount": cursor.rowcount,
                    "lastrowid": cursor.lastrowid
                }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }


def init_schema(schema_name: str = "all") -> Dict[str, Any]:
    """Initialize database schema"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            if schema_name == "all":
                for schema_sql in SCHEMAS.values():
                    cursor.executescript(schema_sql)
            elif schema_name in SCHEMAS:
                cursor.executescript(SCHEMAS[schema_name])
            else:
                return {"status": "failed", "error": f"Unknown schema: {schema_name}"}
            
        return {"status": "success", "message": f"Schema '{schema_name}' initialized"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def backup(backup_path: str) -> Dict[str, Any]:
    """Backup database to file"""
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        return {"status": "success", "backup_path": backup_path}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def execute_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return execute(
        query=args.get("query", ""),
        params=args.get("params", []),
        fetch=args.get("fetch", True)
    )


def init_schema_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return init_schema(args.get("schema_name", "all"))


def backup_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return backup(args.get("backup_path", ""))


if __name__ == "__main__":
    # Test
    result = init_schema_handler({"schema_name": "all"})
    print(json.dumps(result, indent=2))