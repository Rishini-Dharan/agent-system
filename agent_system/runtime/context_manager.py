"""
Agent Runtime - Context Manager
Manages context preparation and retrieval for agents.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agent_system.state import get_db_manager
from agent_system.schemas import Task, AgentName, Artifact
from agent_system.observability import get_logger


class ContextManager:
    """Manages context preparation for agents."""
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.logger = get_logger("context_manager")
        self._file_cache: Dict[str, str] = {}
        self._repo_structure_cache: Optional[Dict[str, Any]] = None
    
    async def prepare_context(
        self,
        task: Task,
        agent: AgentName,
        max_files: int = 20,
        max_tokens: int = 16000,
    ) -> Dict[str, Any]:
        """Prepare context for an agent based on task and agent type."""
        
        context = {
            "task": task.model_dump(),
            "agent": agent.value,
            "workspace_root": str(self.workspace_root),
        }
        
        # Add agent-specific context
        if agent == AgentName.CODER or agent == AgentName.REVIEWER:
            context.update(await self._prepare_code_context(task, max_files, max_tokens))
        elif agent == AgentName.RESEARCHER:
            context.update(await self._prepare_research_context(task))
        elif agent == AgentName.SECURITY:
            context.update(await self._prepare_security_context(task))
        elif agent == AgentName.TESTER:
            context.update(await self._prepare_test_context(task))
        elif agent == AgentName.GITHUB:
            context.update(await self._prepare_github_context(task))
        elif agent == AgentName.BROWSER:
            context.update(await self._prepare_browser_context(task))
        elif agent == AgentName.ORCHESTRATOR:
            context.update(await self._prepare_orchestrator_context(task))
        
        # Add relevant previous results
        context["previous_results"] = await self._get_relevant_results(task, agent)
        
        return context
    
    async def _prepare_code_context(
        self,
        task: Task,
        max_files: int,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Prepare context for code-related tasks."""
        context = {}
        
        # Get repository structure
        repo_structure = await self._get_repo_structure()
        context["repo_structure"] = repo_structure
        
        # Find relevant files based on task description
        relevant_files = await self._find_relevant_files(task, max_files)
        context["relevant_files"] = relevant_files
        
        # Read file contents (with token budget)
        file_contents = {}
        tokens_used = 0
        
        for file_path in relevant_files:
            content = await self._read_file(file_path)
            if content:
                # Rough token estimation
                file_tokens = len(content) // 4
                if tokens_used + file_tokens > max_tokens:
                    break
                file_contents[file_path] = content
                tokens_used += file_tokens
        
        context["file_contents"] = file_contents
        context["tokens_used"] = tokens_used
        
        # Get recent changes if any
        context["recent_changes"] = await self._get_recent_changes()
        
        return context
    
    async def _prepare_research_context(self, task: Task) -> Dict[str, Any]:
        """Prepare context for research tasks."""
        return {
            "search_keywords": self._extract_keywords(task.description),
            "task_type": "research",
        }
    
    async def _prepare_security_context(self, task: Task) -> Dict[str, Any]:
        """Prepare context for security tasks."""
        context = await self._prepare_code_context(task, max_files=50, max_tokens=32000)
        context["security_tools"] = ["semgrep", "gitleaks", "trivy"]
        return context
    
    async def _prepare_test_context(self, task: Task) -> Dict[str, Any]:
        """Prepare context for testing tasks."""
        context = await self._prepare_code_context(task, max_files=30, max_tokens=24000)
        context["test_frameworks"] = await self._detect_test_frameworks()
        return context
    
    async def _prepare_github_context(self, task: Task) -> Dict[str, Any]:
        """Prepare context for GitHub tasks."""
        return {
            "repo_info": await self._get_repo_info(),
            "branch_info": await self._get_branch_info(),
        }
    
    async def _prepare_browser_context(self, task: Task) -> Dict[str, Any]:
        """Prepare context for browser tasks."""
        return {
            "urls_to_visit": self._extract_urls(task.description),
            "task_type": "browser",
        }
    
    async def _prepare_orchestrator_context(self, task: Task) -> Dict[str, Any]:
        """Prepare context for orchestrator tasks."""
        db = await get_db_manager()
        
        # Get recent tasks
        recent_tasks = await db.get_tasks_by_status(TaskStatus.SUCCESS, limit=10)
        failed_tasks = await db.get_tasks_by_status(TaskStatus.FAILED, limit=5)
        
        return {
            "recent_successful_tasks": [
                {
                    "task_id": t.task_id,
                    "description": t.description,
                    "agent": t.assigned_agent.value if t.assigned_agent else None,
                }
                for t in recent_tasks
            ],
            "recent_failed_tasks": [
                {
                    "task_id": t.task_id,
                    "description": t.description,
                    "errors": t.errors,
                }
                for t in failed_tasks
            ],
            "available_agents": [a.value for a in AgentName],
        }
    
    async def _get_relevant_results(self, task: Task, agent: AgentName) -> List[Dict[str, Any]]:
        """Get relevant previous results for the task."""
        # This would query the database for similar tasks
        # For now, return empty list
        return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        import re
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # Filter common words
        stopwords = {"the", "and", "for", "with", "this", "that", "task", "description"}
        keywords = [w for w in words if w not in stopwords]
        # Return unique, most frequent
        from collections import Counter
        return [w for w, _ in Counter(keywords).most_common(10)]
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        import re
        url_pattern = r'https?://[^\s]+'
        return re.findall(url_pattern, text)
    
    async def _get_repo_structure(self) -> Dict[str, Any]:
        """Get repository structure."""
        if self._repo_structure_cache is not None:
            return self._repo_structure_cache
        
        structure = {"files": [], "dirs": []}
        
        for root, dirs, files in os.walk(self.workspace_root):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            rel_root = Path(root).relative_to(self.workspace_root)
            if str(rel_root) != ".":
                structure["dirs"].append(str(rel_root))
            
            for file in files:
                if not file.startswith('.'):
                    rel_path = rel_root / file
                    structure["files"].append(str(rel_path))
        
        self._repo_structure_cache = structure
        return structure
    
    async def _find_relevant_files(self, task: Task, max_files: int) -> List[str]:
        """Find files relevant to the task."""
        keywords = self._extract_keywords(task.description + " " + task.objective)
        structure = await self._get_repo_structure()
        
        scored_files = []
        for file_path in structure["files"]:
            score = 0
            file_lower = file_path.lower()
            
            for keyword in keywords:
                if keyword in file_lower:
                    score += 1
            
            # Boost certain file types
            if file_path.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs')):
                score += 0.5
            
            if score > 0:
                scored_files.append((file_path, score))
        
        # Sort by score and return top files
        scored_files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in scored_files[:max_files]]
    
    async def _read_file(self, file_path: str) -> Optional[str]:
        """Read a file with caching."""
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        
        full_path = self.workspace_root / file_path
        try:
            if full_path.exists() and full_path.is_file():
                # Limit file size to 100KB
                if full_path.stat().st_size > 100 * 1024:
                    return None
                
                content = full_path.read_text(encoding='utf-8', errors='replace')
                self._file_cache[file_path] = content
                return content
        except Exception as e:
            self.logger.warning(f"Failed to read {file_path}: {e}")
        
        return None
    
    async def _get_recent_changes(self) -> List[Dict[str, Any]]:
        """Get recent git changes."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "--oneline", "-10", "--name-only"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return [{"raw": result.stdout}]
        except Exception:
            pass
        return []
    
    async def _detect_test_frameworks(self) -> List[str]:
        """Detect test frameworks in the project."""
        frameworks = []
        
        # Check for common test files
        structure = await self._get_repo_structure()
        files = structure["files"]
        
        if any(f.startswith("test_") or f.endswith("_test.py") for f in files):
            frameworks.append("pytest")
        
        if any("jest" in f.lower() or "vitest" in f.lower() for f in files):
            frameworks.append("jest")
        
        if any("cargo" in f.lower() for f in files):
            frameworks.append("cargo test")
        
        return frameworks
    
    async def _get_repo_info(self) -> Dict[str, Any]:
        """Get repository information."""
        info = {}
        
        try:
            import subprocess
            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                info["remote_url"] = result.stdout.strip()
            
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                info["current_branch"] = result.stdout.strip()
        except Exception:
            pass
        
        return info
    
    async def _get_branch_info(self) -> Dict[str, Any]:
        """Get branch information."""
        info = {}
        
        try:
            import subprocess
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                info["status"] = result.stdout.strip()
        except Exception:
            pass
        
        return info
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self._file_cache.clear()
        self._repo_structure_cache = None