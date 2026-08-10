"""
Coder Agent
Specialized in code implementation, refactoring, bug fixes, and test creation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    CodeResult,
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


class CoderAgent(BaseAgent):
    """Coder agent - code implementation and modification."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.coder")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute coding task."""
        self.logger.info(f"Coder starting task: {task.description[:100]}")
        
        # Determine coding task type
        task_type = self._determine_task_type(task, context)
        
        if task_type == "implement":
            result = await self._implement_feature(task, context)
        elif task_type == "bug_fix":
            result = await self._fix_bug(task, context)
        elif task_type == "refactor":
            result = await self._refactor_code(task, context)
        elif task_type == "test_creation":
            result = await self._create_tests(task, context)
        else:
            result = await self._general_coding(task, context)
        
        return result
    
    def _determine_task_type(self, task: Task, context: Dict[str, Any]) -> str:
        """Determine the type of coding task."""
        description = (task.description + " " + task.objective).lower()
        
        if any(kw in description for kw in ["implement", "create", "build", "add feature", "new"]):
            return "implement"
        elif any(kw in description for kw in ["fix", "bug", "issue", "error", "broken", "crash"]):
            return "bug_fix"
        elif any(kw in description for kw in ["refactor", "cleanup", "improve", "optimize", "restructure"]):
            return "refactor"
        elif any(kw in description for kw in ["test", "testing", "unit test", "integration test"]):
            return "test_creation"
        else:
            return "general_coding"
    
    async def _implement_feature(self, task: Task, context: Dict[str, Any]) -> CodeResult:
        """Implement a new feature."""
        # Get relevant files from context
        file_contents = context.get("file_contents", {})
        repo_structure = context.get("repo_structure", {})
        
        messages = self._build_messages(task, context)
        
        impl_prompt = f"""Implement the requested feature.

Repository Structure:
{json.dumps(repo_structure, indent=2)}

Relevant Files:
{json.dumps({k: v[:2000] for k, v in file_contents.items()}, indent=2)}

Requirements:
1. Follow existing code patterns and conventions
2. Write clean, maintainable code
3. Add appropriate error handling
4. Include logging where appropriate
5. Follow the project's style guide

Return structured JSON with:
- files_changed: list of file paths modified
- diff_summary: summary of changes
- tests_added: number of tests added
- confidence: your confidence in the implementation"""
        
        messages.append({"role": "user", "content": impl_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, CodeResult)
        return result if isinstance(result, CodeResult) else CodeResult(**result.model_dump())
    
    async def _fix_bug(self, task: Task, context: Dict[str, Any]) -> CodeResult:
        """Fix a bug."""
        file_contents = context.get("file_contents", {})
        
        messages = self._build_messages(task, context)
        
        fix_prompt = f"""Fix the reported bug.

Relevant Files:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Requirements:
1. Identify the root cause
2. Implement minimal fix
3. Ensure no regressions
4. Add test case if possible
5. Explain the fix in diff_summary

Return structured JSON with fix details."""
        
        messages.append({"role": "user", "content": fix_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, CodeResult)
        return result if isinstance(result, CodeResult) else CodeResult(**result.model_dump())
    
    async def _refactor_code(self, task: Task, context: Dict[str, Any]) -> CodeResult:
        """Refactor existing code."""
        file_contents = context.get("file_contents", {})
        
        messages = self._build_messages(task, context)
        
        refactor_prompt = f"""Refactor the code as requested.

Relevant Files:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Requirements:
1. Improve code quality without changing behavior
2. Follow best practices
3. Maintain test coverage
4. Document significant changes

Return structured JSON with refactoring details."""
        
        messages.append({"role": "user", "content": refactor_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, CodeResult)
        return result if isinstance(result, CodeResult) else CodeResult(**result.model_dump())
    
    async def _create_tests(self, task: Task, context: Dict[str, Any]) -> CodeResult:
        """Create tests for existing code."""
        file_contents = context.get("file_contents", {})
        test_frameworks = context.get("test_frameworks", [])
        
        messages = self._build_messages(task, context)
        
        test_prompt = f"""Create tests for the specified code.

Relevant Files:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Test Frameworks Detected: {test_frameworks}

Requirements:
1. Write comprehensive tests (unit, edge cases)
2. Follow existing test patterns
3. Aim for high coverage
4. Include both positive and negative cases
5. Use appropriate test framework

Return structured JSON with test details."""
        
        messages.append({"role": "user", "content": test_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, CodeResult)
        return result if isinstance(result, CodeResult) else CodeResult(**result.model_dump())
    
    async def _general_coding(self, task: Task, context: Dict[str, Any]) -> CodeResult:
        """General coding fallback."""
        messages = self._build_messages(task, context)
        
        general_prompt = """Complete the coding task as described.

Provide:
1. Implementation details
2. Files changed
3. Tests added
4. Any issues encountered

Return structured JSON."""
        
        messages.append({"role": "user", "content": general_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, CodeResult)
        return result if isinstance(result, CodeResult) else CodeResult(**result.model_dump())
    
    async def _apply_changes(self, result: CodeResult) -> Dict[str, Any]:
        """Apply code changes using filesystem tools."""
        # This would use the tool manager to write files
        # For now, return summary
        applied = {"files_written": 0, "errors": []}
        
        for file_path in result.files_changed:
            # Would write actual file content here
            applied["files_written"] += 1
        
        return applied


def create_coder_agent(tool_manager=None) -> CoderAgent:
    """Factory function to create coder agent."""
    models_config = get_config("models")
    coder_config = models_config.get("coder", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("coder", {})
    
    config = AgentConfig(
        name=AgentName.CODER,
        description=agent_config.get("description", "Code implementation and modification"),
        permissions=agent_config.get("permissions", "SAFE_WRITE"),
        default_model=coder_config.get("model", "glm-4.5"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 2),
        timeout=agent_config.get("timeout", 300),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return CoderAgent(config, tool_manager)