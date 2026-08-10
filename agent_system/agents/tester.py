"""
Tester Agent
Specialized in test creation, execution, and failure analysis.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    TestResult,
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


class TesterAgent(BaseAgent):
    """Tester agent - test creation, execution, and failure analysis."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.tester")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute testing task."""
        self.logger.info(f"Tester starting task: {task.description[:100]}")
        
        # Determine test task type
        task_type = self._determine_task_type(task, context)
        
        if task_type == "create_tests":
            result = await self._create_tests(task, context)
        elif task_type == "run_tests":
            result = await self._run_tests(task, context)
        elif task_type == "analyze_failures":
            result = await self._analyze_failures(task, context)
        elif task_type == "debug_failure":
            result = await self._debug_failure(task, context)
        else:
            result = await self._general_testing(task, context)
        
        return result
    
    def _determine_task_type(self, task: Task, context: Dict[str, Any]) -> str:
        """Determine the type of testing task."""
        description = (task.description + " " + task.objective).lower()
        
        if any(kw in description for kw in ["create test", "write test", "add test", "test creation"]):
            return "create_tests"
        elif any(kw in description for kw in ["run test", "execute test", "test run"]):
            return "run_tests"
        elif any(kw in description for kw in ["analyze failure", "failure analysis", "test failure"]):
            return "analyze_failures"
        elif any(kw in description for kw in ["debug", "reproduce", "investigate failure"]):
            return "debug_failure"
        else:
            return "general_testing"
    
    async def _create_tests(self, task: Task, context: Dict[str, Any]) -> TestResult:
        """Create tests for code."""
        file_contents = context.get("file_contents", {})
        test_frameworks = context.get("test_frameworks", ["pytest"])
        
        messages = self._build_messages(task, context)
        
        create_prompt = f"""Create comprehensive tests for the specified code.

Code to Test:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Test Frameworks: {test_frameworks}

Requirements:
1. Write unit tests for all public functions/methods
2. Include edge case tests
3. Test error conditions
4. Follow existing test patterns in the project
5. Use appropriate test framework ({test_frameworks[0] if test_frameworks else 'pytest'})
6. Aim for high coverage

Return structured JSON with:
- tests_created: number of tests created
- files_created: list of test file paths
- coverage_estimate: estimated coverage percentage"""
        
        messages.append({"role": "user", "content": create_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, TestResult)
        return result if isinstance(result, TestResult) else TestResult(**result.model_dump())
    
    async def _run_tests(self, task: Task, context: Dict[str, Any]) -> TestResult:
        """Run existing tests."""
        # Use tool manager to run tests
        test_result = await self._execute_tool("pytest_run", {"path": "."})
        
        if not test_result.success:
            return TestResult(
                task_id=task.task_id,
                agent=AgentName.TESTER,
                status=AgentResultStatus.FAILED,
                summary=f"Test execution failed: {test_result.error}",
                tests_passed=0,
                tests_failed=0,
                errors=[test_result.error] if test_result.error else [],
            )
        
        # Parse test output
        output = test_result.result.get("stdout", "")
        return self._parse_test_output(task, output)
    
    async def _analyze_failures(self, task: Task, context: Dict[str, Any]) -> TestResult:
        """Analyze test failures."""
        test_output = context.get("test_output", "")
        file_contents = context.get("file_contents", {})
        
        messages = self._build_messages(task, context)
        
        analyze_prompt = f"""Analyze the test failures and provide recommendations.

Test Output:
{test_output}

Relevant Code:
{json.dumps({k: v[:3000] for k, v in file_contents.items()}, indent=2)}

Provide:
1. Root cause analysis for each failure
2. Steps to reproduce
3. Suggested fixes
4. Whether it's a test issue or code issue

Return structured JSON with failures array."""
        
        messages.append({"role": "user", "content": analyze_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, TestResult)
        return result if isinstance(result, TestResult) else TestResult(**result.model_dump())
    
    async def _debug_failure(self, task: Task, context: Dict[str, Any]) -> TestResult:
        """Debug a specific test failure."""
        return await self._analyze_failures(task, context)
    
    async def _general_testing(self, task: Task, context: Dict[str, Any]) -> TestResult:
        """General testing fallback."""
        # Try running tests first
        result = await self._run_tests(task, context)
        
        if result.tests_failed > 0:
            # Analyze failures
            analysis = await self._analyze_failures(task, {**context, "test_output": result.failures})
            return analysis
        
        return result
    
    def _parse_test_output(self, task: Task, output: str) -> TestResult:
        """Parse pytest output to extract results."""
        import re
        
        # Basic parsing for pytest output
        passed = 0
        failed = 0
        errors = []
        failures = []
        
        # Look for pytest summary line
        summary_pattern = r'(\d+) passed|(\d+) failed|(\d+) error'
        for match in re.finditer(summary_pattern, output):
            if match.group(1):
                passed += int(match.group(1))
            if match.group(2):
                failed += int(match.group(2))
            if match.group(3):
                failed += int(match.group(3))
        
        # Extract failure details
        failure_pattern = r'(FAILED|ERROR)\s+([^\s:]+)'
        for match in re.finditer(failure_pattern, output):
            failures.append({
                "test_name": match.group(2),
                "type": match.group(1).lower(),
            })
        
        return TestResult(
            task_id=task.task_id,
            agent=AgentName.TESTER,
            status=AgentResultStatus.SUCCESS if failed == 0 else AgentResultStatus.FAILED,
            summary=f"Tests: {passed} passed, {failed} failed",
            tests_created=0,
            tests_passed=passed,
            tests_failed=failed,
            failures=failures,
        )


def create_tester_agent(tool_manager=None) -> TesterAgent:
    """Factory function to create tester agent."""
    models_config = get_config("models")
    tester_config = models_config.get("tester", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("tester", {})
    
    config = AgentConfig(
        name=AgentName.TESTER,
        description=agent_config.get("description", "Test creation, execution, and failure analysis"),
        permissions=agent_config.get("permissions", "SAFE_WRITE"),
        default_model=tester_config.get("model", "gemini-1.5-pro"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 2),
        timeout=agent_config.get("timeout", 300),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return TesterAgent(config, tool_manager)