"""
GitHub Agent
Specialized in Git operations, GitHub API interactions, and PR management.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    GitHubResult,
    Finding,
    Artifact,
    FindingType,
    Severity,
    ConfidenceLevel,
    AgentResultStatus,
    AgentName,
)
from agent_system.runtime import BaseAgent, AgentConfig
from agent_system.observability import get_logger


class GitHubAgent(BaseAgent):
    """GitHub agent - Git operations and GitHub API."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.github")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute GitHub task."""
        self.logger.info(f"GitHub agent starting task: {task.description[:100]}")
        
        # Determine task type
        task_type = self._determine_task_type(task, context)
        
        if task_type == "create_branch":
            result = await self._create_branch(task, context)
        elif task_type == "commit_changes":
            result = await self._commit_changes(task, context)
        elif task_type == "create_pr":
            result = await self._create_pr(task, context)
        elif task_type == "inspect_repo":
            result = await self._inspect_repo(task, context)
        elif task_type == "search_code":
            result = await self._search_code(task, context)
        else:
            result = await self._general_github(task, context)
        
        return result
    
    def _determine_task_type(self, task: Task, context: Dict[str, Any]) -> str:
        """Determine the type of GitHub task."""
        description = (task.description + " " + task.objective).lower()
        
        if any(kw in description for kw in ["branch", "create branch", "new branch"]):
            return "create_branch"
        elif any(kw in description for kw in ["commit", "commit changes", "stage"]):
            return "commit_changes"
        elif any(kw in description for kw in ["pr", "pull request", "create pr"]):
            return "create_pr"
        elif any(kw in description for kw in ["inspect", "repository", "repo info"]):
            return "inspect_repo"
        elif any(kw in description for kw in ["search", "find code", "grep"]):
            return "search_code"
        else:
            return "general_github"
    
    async def _create_branch(self, task: Task, context: Dict[str, Any]) -> GitHubResult:
        """Create a new branch."""
        branch_name = context.get("branch_name", f"feature/{task.task_id}")
        base_branch = context.get("base_branch", "main")
        
        # Use git tool
        result = await self._execute_tool("terminal_run", {
            "command": f"git checkout -b {branch_name} {base_branch}",
        })
        
        if not result.success:
            return GitHubResult(
                task_id=task.task_id,
                agent=AgentName.GITHUB,
                status=AgentResultStatus.FAILED,
                summary=f"Branch creation failed: {result.error}",
                errors=[result.error] if result.error else [],
            )
        
        return GitHubResult(
            task_id=task.task_id,
            agent=AgentName.GITHUB,
            status=AgentResultStatus.SUCCESS,
            summary=f"Created branch {branch_name} from {base_branch}",
            branch=branch_name,
        )
    
    async def _commit_changes(self, task: Task, context: Dict[str, Any]) -> GitHubResult:
        """Commit changes."""
        message = context.get("commit_message", f"Changes for task {task.task_id}")
        files = context.get("files", [])
        
        # Stage files
        if files:
            for f in files:
                await self._execute_tool("terminal_run", {"command": f"git add {f}"})
        else:
            await self._execute_tool("terminal_run", {"command": "git add -A"})
        
        # Commit
        result = await self._execute_tool("git_commit", {"message": message})
        
        if not result.success:
            return GitHubResult(
                task_id=task.task_id,
                agent=AgentName.GITHUB,
                status=AgentResultStatus.FAILED,
                summary=f"Commit failed: {result.error}",
                errors=[result.error] if result.error else [],
            )
        
        # Get commit hash
        hash_result = await self._execute_tool("terminal_run", {"command": "git rev-parse HEAD"})
        commit_hash = hash_result.result.get("stdout", "").strip() if hash_result.success else ""
        
        return GitHubResult(
            task_id=task.task_id,
            agent=AgentName.GITHUB,
            status=AgentResultStatus.SUCCESS,
            summary=f"Committed changes: {message}",
            commits=[commit_hash] if commit_hash else [],
        )
    
    async def _create_pr(self, task: Task, context: Dict[str, Any]) -> GitHubResult:
        """Create a pull request."""
        # This would use gh CLI
        title = context.get("pr_title", f"Changes for {task.task_id}")
        body = context.get("pr_body", f"Automated PR for task {task.task_id}")
        base = context.get("pr_base", "main")
        
        result = await self._execute_tool("terminal_run", {
            "command": f'gh pr create --title "{title}" --body "{body}" --base {base}',
        })
        
        if not result.success:
            return GitHubResult(
                task_id=task.task_id,
                agent=AgentName.GITHUB,
                status=AgentResultStatus.FAILED,
                summary=f"PR creation failed: {result.error}",
                errors=[result.error] if result.error else [],
            )
        
        pr_url = result.result.get("stdout", "").strip()
        
        return GitHubResult(
            task_id=task.task_id,
            agent=AgentName.GITHUB,
            status=AgentResultStatus.SUCCESS,
            summary=f"Created PR: {title}",
            pr_url=pr_url,
        )
    
    async def _inspect_repo(self, task: Task, context: Dict[str, Any]) -> GitHubResult:
        """Inspect repository."""
        status_result = await self._execute_tool("git_status", {})
        
        return GitHubResult(
            task_id=task.task_id,
            agent=AgentName.GITHUB,
            status=AgentResultStatus.SUCCESS,
            summary="Repository inspection complete",
            metadata={"status": status_result.result},
        )
    
    async def _search_code(self, task: Task, context: Dict[str, Any]) -> GitHubResult:
        """Search code in repository."""
        pattern = context.get("search_pattern", "")
        
        if not pattern:
            return GitHubResult(
                task_id=task.task_id,
                agent=AgentName.GITHUB,
                status=AgentResultStatus.FAILED,
                summary="No search pattern provided",
                errors=["Missing search_pattern in context"],
            )
        
        result = await self._execute_tool("grep", {"pattern": pattern})
        
        return GitHubResult(
            task_id=task.task_id,
            agent=AgentName.GITHUB,
            status=AgentResultStatus.SUCCESS if result.success else AgentResultStatus.FAILED,
            summary=f"Code search for '{pattern}'",
            metadata={"results": result.result},
            errors=[result.error] if not result.success and result.error else [],
        )
    
    async def _general_github(self, task: Task, context: Dict[str, Any]) -> GitHubResult:
        """General GitHub task fallback."""
        return GitHubResult(
            task_id=task.task_id,
            agent=AgentName.GITHUB,
            status=AgentResultStatus.SUCCESS,
            summary="General GitHub task completed",
        )


def create_github_agent(tool_manager=None) -> GitHubAgent:
    """Factory function to create GitHub agent."""
    models_config = get_config("models")
    github_config = models_config.get("github", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("github", {})
    
    config = AgentConfig(
        name=AgentName.GITHUB,
        description=agent_config.get("description", "Git operations and GitHub API"),
        permissions=agent_config.get("permissions", "APPROVAL_REQUIRED"),
        default_model=github_config.get("model", "deepseek/deepseek-chat"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 1),
        timeout=agent_config.get("timeout", 180),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return GitHubAgent(config, tool_manager)