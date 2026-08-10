"""
Agent Runtime - Tool Manager
Manages tool registration, execution, and permissions.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel

from agent_system.security import PermissionLevel, get_permission_manager
from agent_system.observability import get_logger, get_metrics


class ToolDefinition(BaseModel):
    """Definition of a tool."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    required_permission: PermissionLevel = PermissionLevel.READ_ONLY
    category: str = "general"
    timeout_seconds: int = 30
    async_execution: bool = True


class ToolResult(BaseModel):
    """Result of a tool execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0


class ToolManager:
    """Manages tool registration and execution."""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self.logger = get_logger("tool_manager")
        self.metrics = get_metrics()
        self.permission_manager = get_permission_manager()
    
    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        required_permission: PermissionLevel = PermissionLevel.READ_ONLY,
        category: str = "general",
        timeout_seconds: int = 30,
        async_execution: bool = True,
    ) -> None:
        """Register a tool."""
        if name in self._tools:
            self.logger.warning(f"Tool {name} already registered, overwriting")
        
        definition = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            required_permission=required_permission,
            category=category,
            timeout_seconds=timeout_seconds,
            async_execution=async_execution,
        )
        
        self._tools[name] = definition
        self._handlers[name] = handler
        self.logger.debug(f"Registered tool: {name} ({category})")
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            del self._handlers[name]
            return True
        return False
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition."""
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """List all registered tools."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get tool schemas for LLM function calling."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas
    
    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        agent_permissions: PermissionLevel = PermissionLevel.READ_ONLY,
    ) -> ToolResult:
        """Execute a tool."""
        start_time = time.time()
        
        # Check if tool exists
        if name not in self._tools:
            return ToolResult(
                success=False,
                error=f"Tool {name} not found",
                duration_ms=int((time.time() - start_time) * 1000),
            )
        
        tool = self._tools[name]
        handler = self._handlers[name]
        
        # Check permissions
        if not self.permission_manager.check_permission(agent_permissions, tool.required_permission):
            return ToolResult(
                success=False,
                error=f"Insufficient permissions: required {tool.required_permission.value}, have {agent_permissions.value}",
                duration_ms=int((time.time() - start_time) * 1000),
            )
        
        # Validate arguments against schema
        validation_error = self._validate_arguments(arguments, tool.parameters)
        if validation_error:
            return ToolResult(
                success=False,
                error=f"Invalid arguments: {validation_error}",
                duration_ms=int((time.time() - start_time) * 1000),
            )
        
        # Execute tool
        try:
            if tool.async_execution:
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(**arguments),
                        timeout=tool.timeout_seconds,
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(handler, **arguments),
                        timeout=tool.timeout_seconds,
                    )
            else:
                result = handler(**arguments)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.metrics.record_tool_call(
                tool_name=name,
                success=True,
                duration_ms=duration_ms,
            )
            
            return ToolResult(
                success=True,
                result=result,
                duration_ms=duration_ms,
            )
            
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            self.metrics.record_tool_call(
                tool_name=name,
                success=False,
                duration_ms=duration_ms,
                error="timeout",
            )
            return ToolResult(
                success=False,
                error=f"Tool timed out after {tool.timeout_seconds}s",
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.error(f"Tool {name} failed: {e}", exc_info=True)
            self.metrics.record_tool_call(
                tool_name=name,
                success=False,
                duration_ms=duration_ms,
                error=str(e),
            )
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
    
    def _validate_arguments(self, arguments: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
        """Validate arguments against JSON schema."""
        # Simple validation - check required fields
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        for field in required:
            if field not in arguments:
                return f"Missing required field: {field}"
        
        # Check for unexpected fields
        for field in arguments:
            if field not in properties:
                return f"Unexpected field: {field}"
        
        return None
    
    def get_tools_for_agent(self, agent_permissions: PermissionLevel) -> List[ToolDefinition]:
        """Get tools available for an agent's permission level."""
        return [
            tool for tool in self._tools.values()
            if self.permission_manager.check_permission(agent_permissions, tool.required_permission)
        ]


# Built-in tools
class BuiltinTools:
    """Collection of built-in tools."""
    
    @staticmethod
    def register_all(tool_manager: ToolManager) -> None:
        """Register all built-in tools."""
        # Filesystem tools
        tool_manager.register(
            name="fs_read",
            description="Read a file from the workspace",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                },
                "required": ["path"],
            },
            handler=BuiltinTools._fs_read,
            required_permission=PermissionLevel.READ_ONLY,
            category="filesystem",
        )
        
        tool_manager.register(
            name="fs_write",
            description="Write a file to the workspace",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
            handler=BuiltinTools._fs_write,
            required_permission=PermissionLevel.SAFE_WRITE,
            category="filesystem",
        )
        
        tool_manager.register(
            name="fs_list",
            description="List files in a directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to directory", "default": "."},
                    "pattern": {"type": "string", "description": "Glob pattern", "default": "**/*"},
                },
            },
            handler=BuiltinTools._fs_list,
            required_permission=PermissionLevel.READ_ONLY,
            category="filesystem",
        )
        
        tool_manager.register(
            name="fs_glob",
            description="Find files matching a glob pattern",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                },
                "required": ["pattern"],
            },
            handler=BuiltinTools._fs_glob,
            required_permission=PermissionLevel.READ_ONLY,
            category="filesystem",
        )
        
        # Terminal tools
        tool_manager.register(
            name="terminal_run",
            description="Run a command in the terminal",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                    "cwd": {"type": "string", "description": "Working directory", "default": "."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
                },
                "required": ["command"],
            },
            handler=BuiltinTools._terminal_run,
            required_permission=PermissionLevel.APPROVAL_REQUIRED,
            category="terminal",
            timeout_seconds=120,
        )
        
        # Git tools
        tool_manager.register(
            name="git_status",
            description="Get git status",
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=BuiltinTools._git_status,
            required_permission=PermissionLevel.READ_ONLY,
            category="git",
        )
        
        tool_manager.register(
            name="git_diff",
            description="Get git diff",
            parameters={
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "Show staged changes", "default": False},
                },
            },
            handler=BuiltinTools._git_diff,
            required_permission=PermissionLevel.READ_ONLY,
            category="git",
        )
        
        tool_manager.register(
            name="git_commit",
            description="Create a git commit",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Files to add"},
                },
                "required": ["message"],
            },
            handler=BuiltinTools._git_commit,
            required_permission=PermissionLevel.SAFE_WRITE,
            category="git",
        )
        
        # Search tools
        tool_manager.register(
            name="grep",
            description="Search for patterns in files",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "path": {"type": "string", "description": "Path to search", "default": "."},
                    "include": {"type": "string", "description": "File pattern to include"},
                },
                "required": ["pattern"],
            },
            handler=BuiltinTools._grep,
            required_permission=PermissionLevel.READ_ONLY,
            category="search",
        )
        
        # Testing tools
        tool_manager.register(
            name="pytest_run",
            description="Run pytest tests",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Test path", "default": "."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Additional pytest args"},
                },
            },
            handler=BuiltinTools._pytest_run,
            required_permission=PermissionLevel.SAFE_WRITE,
            category="testing",
            timeout_seconds=180,
        )
    
    # Filesystem handlers
    @staticmethod
    def _fs_read(path: str) -> Dict[str, Any]:
        import os
        from pathlib import Path
        
        workspace = Path(os.getcwd()).resolve()
        file_path = (workspace / path).resolve()
        
        # Security: ensure path is within workspace
        if not str(file_path).startswith(str(workspace)):
            return {"error": "Path outside workspace"}
        
        if not file_path.exists():
            return {"error": "File not found"}
        
        if not file_path.is_file():
            return {"error": "Not a file"}
        
        # Limit file size
        if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
            return {"error": "File too large"}
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
            return {"content": content, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _fs_write(path: str, content: str) -> Dict[str, Any]:
        import os
        from pathlib import Path
        
        workspace = Path(os.getcwd()).resolve()
        file_path = (workspace / path).resolve()
        
        # Security: ensure path is within workspace
        if not str(file_path).startswith(str(workspace)):
            return {"error": "Path outside workspace"}
        
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            file_path.write_text(content, encoding='utf-8')
            return {"success": True, "path": str(file_path), "size": len(content)}
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _fs_list(path: str = ".", pattern: str = "**/*") -> Dict[str, Any]:
        import os
        from pathlib import Path
        
        workspace = Path(os.getcwd()).resolve()
        dir_path = (workspace / path).resolve()
        
        if not str(dir_path).startswith(str(workspace)):
            return {"error": "Path outside workspace"}
        
        if not dir_path.exists() or not dir_path.is_dir():
            return {"error": "Directory not found"}
        
        try:
            files = []
            for file_path in dir_path.glob(pattern):
                if file_path.is_file():
                    rel_path = file_path.relative_to(workspace)
                    files.append({
                        "path": str(rel_path),
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                    })
            return {"files": files}
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _fs_glob(pattern: str) -> Dict[str, Any]:
        import os
        from pathlib import Path
        
        workspace = Path(os.getcwd()).resolve()
        
        try:
            files = []
            for file_path in workspace.glob(pattern):
                if file_path.is_file():
                    rel_path = file_path.relative_to(workspace)
                    files.append({
                        "path": str(rel_path),
                        "size": file_path.stat().st_size,
                    })
            return {"files": files}
        except Exception as e:
            return {"error": str(e)}
    
    # Terminal handlers
    @staticmethod
    def _terminal_run(command: str, cwd: str = ".", timeout: int = 60) -> Dict[str, Any]:
        import subprocess
        import os
        
        workspace = Path(os.getcwd()).resolve()
        work_dir = (workspace / cwd).resolve()
        
        if not str(work_dir).startswith(str(workspace)):
            return {"error": "Working directory outside workspace"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}
    
    # Git handlers
    @staticmethod
    def _git_status() -> Dict[str, Any]:
        import subprocess
        import os
        
        workspace = Path(os.getcwd()).resolve()
        
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _git_diff(staged: bool = False) -> Dict[str, Any]:
        import subprocess
        import os
        
        workspace = Path(os.getcwd()).resolve()
        
        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")
            
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _git_commit(message: str, files: List[str] = None) -> Dict[str, Any]:
        import subprocess
        import os
        
        workspace = Path(os.getcwd()).resolve()
        
        try:
            if files:
                for f in files:
                    subprocess.run(["git", "add", f], cwd=workspace, check=True)
            else:
                subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
            
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.CalledProcessError as e:
            return {"error": f"Git command failed: {e.stderr}"}
        except Exception as e:
            return {"error": str(e)}
    
    # Search handlers
    @staticmethod
    def _grep(pattern: str, path: str = ".", include: str = None) -> Dict[str, Any]:
        import subprocess
        import os
        
        workspace = Path(os.getcwd()).resolve()
        search_path = (workspace / path).resolve()
        
        if not str(search_path).startswith(str(workspace)):
            return {"error": "Path outside workspace"}
        
        try:
            cmd = ["grep", "-r", "-n", pattern]
            if include:
                cmd.extend(["--include", include])
            cmd.append(str(search_path))
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"error": str(e)}
    
    # Testing handlers
    @staticmethod
    def _pytest_run(path: str = ".", args: List[str] = None) -> Dict[str, Any]:
        import subprocess
        import os
        
        workspace = Path(os.getcwd()).resolve()
        test_path = (workspace / path).resolve()
        
        if not str(test_path).startswith(str(workspace)):
            return {"error": "Path outside workspace"}
        
        try:
            cmd = ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"]
            if args:
                cmd.extend(args)
            
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=180,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Tests timed out after 180s"}
        except Exception as e:
            return {"error": str(e)}