"""
Reviewer Agent
Specialized in code review, bug detection, security analysis, and architecture review.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    ReviewResult,
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


class ReviewerAgent(BaseAgent):
    """Reviewer agent - code review and quality assurance."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.reviewer")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute review task."""
        self.logger.info(f"Reviewer starting task: {task.description[:100]}")
        
        # Determine review type
        review_type = self._determine_review_type(task, context)
        
        if review_type == "code_review":
            result = await self._code_review(task, context)
        elif review_type == "security_review":
            result = await self._security_review(task, context)
        elif review_type == "architecture_review":
            result = await self._architecture_review(task, context)
        elif review_type == "test_review":
            result = await self._test_review(task, context)
        else:
            result = await self._general_review(task, context)
        
        return result
    
    def _determine_review_type(self, task: Task, context: Dict[str, Any]) -> str:
        """Determine the type of review needed."""
        description = (task.description + " " + task.objective).lower()
        
        if any(kw in description for kw in ["security", "vulnerability", "audit", "secure"]):
            return "security_review"
        elif any(kw in description for kw in ["architecture", "design", "structure", "patterns"]):
            return "architecture_review"
        elif any(kw in description for kw in ["test", "testing", "coverage", "quality"]):
            return "test_review"
        elif any(kw in description for kw in ["review", "pr", "pull request", "changes"]):
            return "code_review"
        else:
            return "general_review"
    
    async def _code_review(self, task: Task, context: Dict[str, Any]) -> ReviewResult:
        """Perform code review."""
        file_contents = context.get("file_contents", {})
        diff = context.get("diff", "")
        
        messages = self._build_messages(task, context)
        
        review_prompt = f"""Perform a thorough code review.

Code Changes (Diff):
{diff}

Full File Context:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Review Checklist:
1. Correctness - Does the code work as intended?
2. Style - Does it follow project conventions?
3. Maintainability - Is it easy to understand and modify?
4. Performance - Any obvious performance issues?
5. Security - Any security vulnerabilities?
6. Tests - Are there adequate tests?
7. Edge cases - Are edge cases handled?
8. Error handling - Is error handling appropriate?
9. Logging - Is logging adequate?
10. Documentation - Are changes documented?

Return structured JSON with:
- decision: "approve", "reject", or "request_changes"
- reasoning: explanation of decision
- issues_found: array of issues with file, line, type, severity, message, suggestion"""
        
        messages.append({"role": "user", "content": review_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, ReviewResult)
        return result if isinstance(result, ReviewResult) else ReviewResult(**result.model_dump())
    
    async def _security_review(self, task: Task, context: Dict[str, Any]) -> ReviewResult:
        """Perform security-focused review."""
        file_contents = context.get("file_contents", {})
        security_findings = context.get("security_findings", [])
        
        messages = self._build_messages(task, context)
        
        security_prompt = f"""Perform a security-focused code review.

Security Tool Findings:
{json.dumps(security_findings, indent=2)}

Code to Review:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Focus on:
1. Authentication and authorization issues
2. Input validation and sanitization
3. SQL injection, XSS, CSRF vulnerabilities
4. Secrets management (API keys, passwords, tokens)
5. Cryptographic practices
6. Dependency vulnerabilities
7. Permission and access control
8. Data exposure risks
9. Logging of sensitive information

Return structured JSON with security issues."""
        
        messages.append({"role": "user", "content": security_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, ReviewResult)
        return result if isinstance(result, ReviewResult) else ReviewResult(**result.model_dump())
    
    async def _architecture_review(self, task: Task, context: Dict[str, Any]) -> ReviewResult:
        """Perform architecture review."""
        repo_structure = context.get("repo_structure", {})
        file_contents = context.get("file_contents", {})
        
        messages = self._build_messages(task, context)
        
        arch_prompt = f"""Perform an architecture review.

Repository Structure:
{json.dumps(repo_structure, indent=2)}

Key Files:
{json.dumps({k: v[:2000] for k, v in list(file_contents.items())[:10]}, indent=2)}

Evaluate:
1. Overall architecture and design patterns
2. Separation of concerns
3. Modularity and cohesion
4. Scalability and extensibility
5. Technical debt indicators
6. Consistency with project standards
7. Integration points and dependencies

Return structured JSON with architectural findings."""
        
        messages.append({"role": "user", "content": arch_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, ReviewResult)
        return result if isinstance(result, ReviewResult) else ReviewResult(**result.model_dump())
    
    async def _test_review(self, task: Task, context: Dict[str, Any]) -> ReviewResult:
        """Review test quality."""
        file_contents = context.get("file_contents", {})
        test_results = context.get("test_results", {})
        
        messages = self._build_messages(task, context)
        
        test_prompt = f"""Review test quality and coverage.

Test Files:
{json.dumps({k: v[:3000] for k, v in file_contents.items() if 'test' in k.lower()}, indent=2)}

Test Results:
{json.dumps(test_results, indent=2)}

Evaluate:
1. Test coverage (what's tested vs what's not)
2. Test quality (meaningful assertions, not just coverage)
3. Edge case coverage
4. Test organization and readability
5. Flaky test indicators
6. Integration vs unit test balance
7. Mock usage appropriateness

Return structured JSON with test review findings."""
        
        messages.append({"role": "user", "content": test_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, ReviewResult)
        return result if isinstance(result, ReviewResult) else ReviewResult(**result.model_dump())
    
    async def _general_review(self, task: Task, context: Dict[str, Any]) -> ReviewResult:
        """General review fallback."""
        messages = self._build_messages(task, context)
        
        general_prompt = """Perform a general code review.

Evaluate the code for:
1. Correctness
2. Style and conventions
3. Maintainability
4. Security
5. Performance
6. Tests

Return structured JSON with review findings."""
        
        messages.append({"role": "user", "content": general_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, ReviewResult)
        return result if isinstance(result, ReviewResult) else ReviewResult(**result.model_dump())


def create_reviewer_agent(tool_manager=None) -> ReviewerAgent:
    """Factory function to create reviewer agent."""
    models_config = get_config("models")
    reviewer_config = models_config.get("reviewer", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("reviewer", {})
    
    config = AgentConfig(
        name=AgentName.REVIEWER,
        description=agent_config.get("description", "Code review and quality assurance"),
        permissions=agent_config.get("permissions", "READ_ONLY"),
        default_model=reviewer_config.get("model", "nvidia/nemotron-3-ultra"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 1),
        timeout=agent_config.get("timeout", 180),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return ReviewerAgent(config, tool_manager)