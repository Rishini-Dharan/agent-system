"""
Coder Agent
Specialized in code implementation, refactoring, bug fixes, and test creation.
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from agent_system.providers import Message


class CoderAgent(BaseAgent):
    """Coder agent - code implementation and modification with actual file operations."""

    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.coder")
        self.workspace = Path.cwd().resolve()

    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute coding task."""
        self.logger.info(f"Coder starting task: {task.description[:100]}")

        file_contents = await self._read_relevant_files(context)
        context["file_contents"] = file_contents

        repo_structure = await self._get_repo_structure()
        context["repo_structure"] = repo_structure

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

        if result.files_changed:
            await self._apply_and_validate(result)

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

    async def _read_relevant_files(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Read files specified in context or discover relevant files."""
        file_contents = {}

        for file_path in context.get("files", []):
            content = await self._read_file(file_path)
            if content is not None:
                file_contents[file_path] = content

        for pattern in context.get("globs", []):
            files = await self._glob_files(pattern)
            for f in files:
                content = await self._read_file(f)
                if content is not None:
                    file_contents[f] = content

        return file_contents

    async def _read_file(self, file_path: str) -> Optional[str]:
        """Read a file using fs_read tool."""
        if not self.tool_manager:
            return self._read_file_direct(file_path)

        result = await self.tool_manager.execute("fs_read", {"path": file_path})
        if result.success and result.result:
            return result.result.get("content")
        return self._read_file_direct(file_path)

    def _read_file_direct(self, file_path: str) -> Optional[str]:
        """Direct file read fallback."""
        try:
            full_path = (self.workspace / file_path).resolve()
            if not str(full_path).startswith(str(self.workspace)):
                return None
            if full_path.exists() and full_path.is_file():
                return full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return None

    async def _glob_files(self, pattern: str) -> List[str]:
        """Find files matching a glob pattern."""
        if not self.tool_manager:
            return self._glob_files_direct(pattern)

        result = await self.tool_manager.execute("fs_glob", {"pattern": pattern})
        if result.success and result.result:
            return result.result.get("files", [])
        return self._glob_files_direct(pattern)

    def _glob_files_direct(self, pattern: str) -> List[str]:
        """Direct glob fallback."""
        try:
            files = []
            for file_path in self.workspace.glob(pattern):
                if file_path.is_file():
                    rel_path = file_path.relative_to(self.workspace)
                    files.append(str(rel_path))
            return files
        except Exception:
            return []

    async def _get_repo_structure(self) -> Dict[str, Any]:
        """Get repository structure."""
        try:
            result = await self.tool_manager.execute("fs_list", {"path": ".", "pattern": "**/*"})
            if result.success and result.result:
                return {"files": result.result.get("files", [])}
        except Exception:
            pass

        try:
            files = []
            for file_path in self.workspace.rglob("*"):
                if file_path.is_file() and not any(part.startswith(".") for part in file_path.parts):
                    rel_path = file_path.relative_to(self.workspace)
                    files.append({"path": str(rel_path), "size": file_path.stat().st_size})
            return {"files": files}
        except Exception:
            return {"files": []}

    async def _implement_feature(self, task: Task, context: Dict[str, Any]) -> CodeResult:
        """Implement a new feature."""
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
5. Follow the project style guide
6. Return the COMPLETE file content for each modified file

Return structured JSON with:
- files_changed: list of file paths modified
- diff_summary: summary of changes
- tests_added: number of tests added
- confidence: your confidence in the implementation
- file_contents: object mapping file paths to their complete new content"""

        messages.append(Message(role="user", content=impl_prompt))

        result = await self._call_llm_structured(messages, CodeResult)
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
6. Return the COMPLETE file content for each modified file

Return structured JSON with fix details including file_contents."""

        messages.append(Message(role="user", content=fix_prompt))

        result = await self._call_llm_structured(messages, CodeResult)
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
5. Return the COMPLETE file content for each modified file

Return structured JSON with refactoring details including file_contents."""

        messages.append(Message(role="user", content=refactor_prompt))

        result = await self._call_llm_structured(messages, CodeResult)
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
6. Return the COMPLETE file content for each test file created

Return structured JSON with test details including file_contents."""

        messages.append(Message(role="user", content=test_prompt))

        result = await self._call_llm_structured(messages, CodeResult)
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
5. Return the COMPLETE file content for each modified file

Return structured JSON."""

        messages.append(Message(role="user", content=general_prompt))

        result = await self._call_llm_structured(messages, CodeResult)
        return result if isinstance(result, CodeResult) else CodeResult(**result.model_dump())

    async def _apply_and_validate(self, result: CodeResult) -> None:
        """Apply changes to files and run validation."""
        file_contents = getattr(result, "file_contents", {}) or {}

        for file_path, content in file_contents.items():
            await self._write_file(file_path, content)
            result.files_changed.append(file_path)

        python_files = [f for f in result.files_changed if f.endswith(".py")]
        if python_files:
            await self._validate_python_files(python_files, result)

        if result.tests_added > 0:
            await self._run_tests(result)

    async def _write_file(self, file_path: str, content: str) -> bool:
        """Write a file using fs_write tool."""
        if not self.tool_manager:
            return self._write_file_direct(file_path, content)

        result = await self.tool_manager.execute("fs_write", {"path": file_path, "content": content})
        return result.success

    def _write_file_direct(self, file_path: str, content: str) -> bool:
        """Direct file write fallback."""
        try:
            full_path = (self.workspace / file_path).resolve()
            if not str(full_path).startswith(str(self.workspace)):
                return False
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    async def _validate_python_files(self, files: List[str], result: CodeResult) -> None:
        """Validate Python files with syntax check, lint, and type check."""
        for file_path in files:
            full_path = (self.workspace / file_path).resolve()

            syntax_ok = await self._check_syntax(full_path)
            if not syntax_ok:
                result.lint_errors += 1
                result.findings.append(Finding(
                    type=FindingType.ISSUE,
                    claim=f"Syntax error in {file_path}",
                    severity=Severity.HIGH,
                    file_path=file_path,
                    confidence=ConfidenceLevel.HIGH,
                ))

            lint_errors = await self._run_ruff(full_path)
            result.lint_errors += lint_errors

            type_errors = await self._run_mypy(full_path)
            result.type_errors += type_errors

    async def _check_syntax(self, file_path: Path) -> bool:
        """Check Python syntax."""
        try:
            content = file_path.read_text(encoding="utf-8")
            ast.parse(content)
            return True
        except SyntaxError:
            return False
        except Exception:
            return False

    async def _run_ruff(self, file_path: Path) -> int:
        """Run ruff linter."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "ruff", "check", str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return len(stdout.decode().strip().split("\n")) if stdout else 1
        except Exception:
            pass
        return 0

    async def _run_mypy(self, file_path: Path) -> int:
        """Run mypy type checker."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "mypy", str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return len(stdout.decode().strip().split("\n")) if stdout else 1
        except Exception:
            pass
        return 0

    async def _run_tests(self, result: CodeResult) -> None:
        """Run tests after changes."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "-v", "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode() + stderr.decode()

            import re
            passed = len(re.findall(r"PASSED", output))
            failed = len(re.findall(r"FAILED", output))

            result.tests_passed = passed
            result.tests_failed = failed

            if failed > 0:
                result.findings.append(Finding(
                    type=FindingType.TEST_FAILURE,
                    claim=f"{failed} test(s) failed after changes",
                    severity=Severity.HIGH,
                    confidence=ConfidenceLevel.HIGH,
                ))
        except Exception:
            pass


def create_coder_agent(tool_manager=None) -> CoderAgent:
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