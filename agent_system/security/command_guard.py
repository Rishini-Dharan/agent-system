"""
Security - Command Guard
Validates and sanitizes commands before execution.
"""
from __future__ import annotations

import re
import shlex
from typing import List, Optional, Set


class CommandGuard:
    """Guards against dangerous commands."""
    
    # Dangerous patterns that should be blocked
    DANGEROUS_PATTERNS = [
        # Destructive commands
        r'\brm\s+-rf\s+/',
        r'\brm\s+-rf\s+\*',
        r'\brm\s+-rf\s+~',
        r'\bformat\s+',
        r'\bmkfs\s+',
        r'\bdd\s+if=.*of=/dev/',
        r'\bshred\s+',
        r'\bwipe\s+',
        
        # Privilege escalation
        r'\bsudo\s+',
        r'\bsu\s+',
        r'\bdoas\s+',
        r'\bpkexec\s+',
        
        # Network attacks
        r'\bnmap\s+',
        r'\bnc\s+-l',
        r'\bnetcat\s+-l',
        r'\bsocat\s+',
        
        # Process manipulation
        r'\bkillall\s+',
        r'\bpkill\s+-9',
        r'\bkill\s+-9\s+1\b',
        
        # Filesystem attacks
        r'\bmount\s+',
        r'\bumount\s+',
        r'\bfdisk\s+',
        r'\bparted\s+',
        
        # Shell injection
        r';\s*rm\s+-rf',
        r'\|\s*sh\s*$',
        r'\|\s*bash\s*$',
        r'`.*rm\s+-rf',
        r'\$\(.*rm\s+-rf',
        
        # Data exfiltration
        r'\bcurl\s+.*\|\s*sh',
        r'\bwget\s+.*\|\s*sh',
        r'\bcurl\s+.*\|\s*bash',
        r'\bwget\s+.*\|\s*bash',
    ]
    
    # Commands that require explicit approval
    REQUIRES_APPROVAL = {
        'git push',
        'git push --force',
        'git push -f',
        'npm publish',
        'pip publish',
        'docker push',
        'kubectl apply',
        'terraform apply',
        'ansible-playbook',
        'systemctl',
        'service',
        'apt install',
        'apt-get install',
        'yum install',
        'dnf install',
        'brew install',
        'pip install',
        'npm install -g',
        'cargo install',
        'go install',
    }
    
    # Commands that are always blocked
    ALWAYS_BLOCKED = {
        'rm -rf /',
        'rm -rf /*',
        'format c:',
        'del /f /s /q',
        'shutdown',
        'reboot',
        'halt',
        'poweroff',
        'init 0',
        'init 6',
    }
    
    def __init__(self):
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS]
    
    def validate(self, command: str) -> tuple[bool, Optional[str]]:
        """
        Validate a command.
        Returns (is_safe, error_message).
        """
        if not command or not command.strip():
            return False, "Empty command"
        
        # Check always blocked
        for blocked in self.ALWAYS_BLOCKED:
            if blocked.lower() in command.lower():
                return False, f"Command contains blocked pattern: {blocked}"
        
        # Check dangerous patterns
        for pattern in self._compiled_patterns:
            if pattern.search(command):
                return False, f"Command matches dangerous pattern: {pattern.pattern}"
        
        # Check for shell injection attempts
        if self._has_shell_injection(command):
            return False, "Potential shell injection detected"
        
        return True, None
    
    def _has_shell_injection(self, command: str) -> bool:
        """Check for shell injection patterns."""
        injection_patterns = [
            r';\s*(rm|wget|curl|nc|bash|sh)',
            r'\|\s*(bash|sh|python|perl)\s*$',
            r'`[^`]*(rm|wget|curl)',
            r'\$\([^)]*(rm|wget|curl)',
            r'&&\s*(rm|wget|curl)',
            r'\|\|\s*(rm|wget|curl)',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        
        return False
    
    def requires_approval(self, command: str) -> bool:
        """Check if command requires approval."""
        cmd_lower = command.lower().strip()
        
        for approved_cmd in self.REQUIRES_APPROVAL:
            if cmd_lower.startswith(approved_cmd.lower()):
                return True
        
        return False
    
    def sanitize(self, command: str) -> str:
        """Sanitize command by removing dangerous elements."""
        # Remove command substitution
        command = re.sub(r'`[^`]*`', '', command)
        command = re.sub(r'\$\([^)]*\)', '', command)
        
        # Remove dangerous redirections
        command = re.sub(r'>\s*/dev/(null|zero|random|urandom)', '', command)
        
        return command.strip()
    
    def parse_command(self, command: str) -> List[str]:
        """Safely parse command into arguments."""
        try:
            return shlex.split(command)
        except ValueError:
            # Fallback to simple split
            return command.split()


# Global command guard
_command_guard = None


def get_command_guard() -> CommandGuard:
    """Get the global command guard."""
    global _command_guard
    if _command_guard is None:
        _command_guard = CommandGuard()
    return _command_guard