"""
Unit tests for security module.
"""
import pytest
from pathlib import Path

from agent_system.security import (
    PermissionLevel,
    PermissionManager,
    CommandGuard,
    get_permission_manager,
    get_command_guard,
)


class TestPermissionManager:
    """Tests for PermissionManager."""
    
    def test_permission_hierarchy(self):
        """Test permission hierarchy."""
        pm = PermissionManager()
        
        # Higher permissions should include lower
        assert pm.check_permission(PermissionLevel.APPROVAL_REQUIRED, PermissionLevel.READ_ONLY)
        assert pm.check_permission(PermissionLevel.SAFE_WRITE, PermissionLevel.READ_ONLY)
        assert not pm.check_permission(PermissionLevel.READ_ONLY, PermissionLevel.SAFE_WRITE)
        assert not pm.check_permission(PermissionLevel.BLOCKED, PermissionLevel.READ_ONLY)
    
    def test_allowed_actions(self):
        """Test getting allowed actions."""
        pm = PermissionManager()
        
        read_only_actions = pm.get_allowed_actions(PermissionLevel.READ_ONLY)
        assert "read_file" in read_only_actions
        assert "write_file" not in read_only_actions
        
        safe_write_actions = pm.get_allowed_actions(PermissionLevel.SAFE_WRITE)
        assert "read_file" in safe_write_actions
        assert "write_file" in safe_write_actions
        assert "git_push" not in safe_write_actions
        
        approval_actions = pm.get_allowed_actions(PermissionLevel.APPROVAL_REQUIRED)
        assert "git_push" in approval_actions
    
    def test_action_allowed(self):
        """Test specific action checking."""
        pm = PermissionManager()
        
        assert pm.is_action_allowed(PermissionLevel.READ_ONLY, "read_file")
        assert not pm.is_action_allowed(PermissionLevel.READ_ONLY, "write_file")
        assert pm.is_action_allowed(PermissionLevel.SAFE_WRITE, "write_file")
        assert not pm.is_action_allowed(PermissionLevel.SAFE_WRITE, "git_push")
        assert pm.is_action_allowed(PermissionLevel.APPROVAL_REQUIRED, "git_push")
    
    def test_minimum_permission(self):
        """Test getting minimum permission for action."""
        pm = PermissionManager()
        
        assert pm.get_permission_for_action("read_file") == PermissionLevel.READ_ONLY
        assert pm.get_permission_for_action("write_file") == PermissionLevel.SAFE_WRITE
        assert pm.get_permission_for_action("git_push") == PermissionLevel.APPROVAL_REQUIRED
        assert pm.get_permission_for_action("unknown_action") == PermissionLevel.APPROVAL_REQUIRED


class TestCommandGuard:
    """Tests for CommandGuard."""
    
    def test_safe_commands(self):
        """Test that safe commands pass."""
        guard = CommandGuard()
        
        safe_commands = [
            "ls -la",
            "git status",
            "git diff",
            "python test.py",
            "pytest tests/",
            "echo hello",
        ]
        
        for cmd in safe_commands:
            is_safe, error = guard.validate(cmd)
            assert is_safe, f"Command '{cmd}' should be safe: {error}"
    
    def test_blocked_commands(self):
        """Test that dangerous commands are blocked."""
        guard = CommandGuard()
        
        blocked_commands = [
            "rm -rf /",
            "rm -rf /*",
            "format c:",
            "shutdown",
            "reboot",
        ]
        
        for cmd in blocked_commands:
            is_safe, error = guard.validate(cmd)
            assert not is_safe, f"Command '{cmd}' should be blocked"
    
    def test_shell_injection(self):
        """Test shell injection detection."""
        guard = CommandGuard()
        
        injection_commands = [
            "ls; rm -rf /",
            "echo test | bash",
            "`rm -rf /`",
            "$(rm -rf /)",
            "ls && rm -rf /",
        ]
        
        for cmd in injection_commands:
            is_safe, error = guard.validate(cmd)
            assert not is_safe, f"Command '{cmd}' should be blocked: {error}"
    
    def test_requires_approval(self):
        """Test approval requirement detection."""
        guard = CommandGuard()
        
        approval_commands = [
            "git push",
            "git push --force",
            "npm publish",
            "pip install package",
            "apt install package",
        ]
        
        for cmd in approval_commands:
            assert guard.requires_approval(cmd), f"Command '{cmd}' should require approval"
        
        safe_commands = [
            "git status",
            "git diff",
            "ls -la",
        ]
        
        for cmd in safe_commands:
            assert not guard.requires_approval(cmd), f"Command '{cmd}' should not require approval"
    
    def test_sanitize(self):
        """Test command sanitization."""
        guard = CommandGuard()
        
        cmd = "echo test `rm -rf /`"
        sanitized = guard.sanitize(cmd)
        assert "`rm -rf /`" not in sanitized
        
        cmd = "echo test $(rm -rf /)"
        sanitized = guard.sanitize(cmd)
        assert "$(rm -rf /)" not in sanitized
    
    def test_parse_command(self):
        """Test command parsing."""
        guard = CommandGuard()
        
        args = guard.parse_command('echo "hello world"')
        assert args == ["echo", "hello world"]
        
        args = guard.parse_command("ls -la")
        assert args == ["ls", "-la"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])