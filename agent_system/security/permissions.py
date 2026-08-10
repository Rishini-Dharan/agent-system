"""
Security - Permission Manager
Manages permission levels and access control.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"
    SAFE_WRITE = "safe_write"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


# Permission hierarchy (higher index = more permissions)
PERMISSION_HIERARCHY = [
    PermissionLevel.BLOCKED,
    PermissionLevel.READ_ONLY,
    PermissionLevel.SAFE_WRITE,
    PermissionLevel.APPROVAL_REQUIRED,
]

# Permissions required for each level
PERMISSION_ACTIONS: Dict[PermissionLevel, Set[str]] = {
    PermissionLevel.READ_ONLY: {
        "read_file",
        "list_files",
        "grep",
        "git_status",
        "git_diff",
        "web_search",
        "read_docs",
    },
    PermissionLevel.SAFE_WRITE: {
        "read_file",
        "list_files",
        "grep",
        "git_status",
        "git_diff",
        "web_search",
        "read_docs",
        "write_file",
        "create_file",
        "run_tests",
        "pytest_run",
        "git_commit",
        "run_linter",
    },
    PermissionLevel.APPROVAL_REQUIRED: {
        "read_file",
        "list_files",
        "grep",
        "git_status",
        "git_diff",
        "web_search",
        "read_docs",
        "write_file",
        "create_file",
        "run_tests",
        "pytest_run",
        "git_commit",
        "run_linter",
        "git_push",
        "create_pr",
        "merge_pr",
        "install_package",
        "run_command",
        "send_notification",
        "modify_external_service",
    },
    PermissionLevel.BLOCKED: set(),
}


class PermissionManager:
    """Manages permission checks and enforcement."""
    
    def __init__(self):
        self._permission_cache: Dict[str, PermissionLevel] = {}
    
    def check_permission(
        self,
        agent_permission: PermissionLevel,
        required_permission: PermissionLevel,
    ) -> bool:
        """Check if agent permission satisfies required permission."""
        try:
            agent_idx = PERMISSION_HIERARCHY.index(agent_permission)
            required_idx = PERMISSION_HIERARCHY.index(required_permission)
            return agent_idx >= required_idx
        except ValueError:
            return False
    
    def get_allowed_actions(self, permission: PermissionLevel) -> Set[str]:
        """Get set of allowed actions for a permission level."""
        actions = set()
        for level in PERMISSION_HIERARCHY:
            if level == permission:
                actions.update(PERMISSION_ACTIONS.get(level, set()))
                break
            actions.update(PERMISSION_ACTIONS.get(level, set()))
        return actions
    
    def is_action_allowed(
        self,
        agent_permission: PermissionLevel,
        action: str,
    ) -> bool:
        """Check if a specific action is allowed."""
        allowed = self.get_allowed_actions(agent_permission)
        return action in allowed
    
    def get_permission_for_action(self, action: str) -> PermissionLevel:
        """Get minimum permission required for an action."""
        for level in PERMISSION_HIERARCHY:
            if action in PERMISSION_ACTIONS.get(level, set()):
                return level
        return PermissionLevel.APPROVAL_REQUIRED


# Global permission manager
_permission_manager = None


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager