"""
Security Agent
Specialized in security analysis, vulnerability scanning, and threat detection.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    SecurityResult,
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


class SecurityAgent(BaseAgent):
    """Security agent - vulnerability scanning and security analysis."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.security")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute security task."""
        self.logger.info(f"Security agent starting task: {task.description[:100]}")
        
        # Run security tools
        tool_results = await self._run_security_tools(task, context)
        
        # Analyze results with LLM
        analysis = await self._analyze_findings(task, context, tool_results)
        
        return analysis
    
    async def _run_security_tools(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run local security tools (semgrep, gitleaks, trivy)."""
        results = {}
        
        # Semgrep - static analysis
        semgrep_result = await self._run_semgrep()
        results["semgrep"] = semgrep_result
        
        # Gitleaks - secret detection
        gitleaks_result = await self._run_gitleaks()
        results["gitleaks"] = gitleaks_result
        
        # Trivy - vulnerability scanning
        trivy_result = await self._run_trivy()
        results["trivy"] = trivy_result
        
        return results
    
    async def _run_semgrep(self) -> Dict[str, Any]:
        """Run semgrep static analysis."""
        try:
            import subprocess
            import os
            
            workspace = Path(os.getcwd()).resolve()
            
            # Check if semgrep is available
            check = subprocess.run(["which", "semgrep"], capture_output=True)
            if check.returncode != 0:
                return {"status": "skipped", "reason": "semgrep not installed"}
            
            # Run semgrep with security rules
            result = subprocess.run(
                ["semgrep", "--config=auto", "--json", "."],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode == 0:
                return {"status": "success", "findings": json.loads(result.stdout)}
            else:
                return {"status": "error", "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "semgrep timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _run_gitleaks(self) -> Dict[str, Any]:
        """Run gitleaks secret detection."""
        try:
            import subprocess
            import os
            
            workspace = Path(os.getcwd()).resolve()
            
            check = subprocess.run(["which", "gitleaks"], capture_output=True)
            if check.returncode != 0:
                return {"status": "skipped", "reason": "gitleaks not installed"}
            
            result = subprocess.run(
                ["gitleaks", "detect", "--source", ".", "--report-format", "json"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode in (0, 1):  # 1 means findings found
                try:
                    return {"status": "success", "findings": json.loads(result.stdout)}
                except json.JSONDecodeError:
                    return {"status": "success", "findings": [], "raw_output": result.stdout}
            else:
                return {"status": "error", "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "gitleaks timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _run_trivy(self) -> Dict[str, Any]:
        """Run trivy vulnerability scanning."""
        try:
            import subprocess
            import os
            
            workspace = Path(os.getcwd()).resolve()
            
            check = subprocess.run(["which", "trivy"], capture_output=True)
            if check.returncode != 0:
                return {"status": "skipped", "reason": "trivy not installed"}
            
            result = subprocess.run(
                ["trivy", "fs", "--format", "json", "."],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=180,
            )
            
            if result.returncode == 0:
                return {"status": "success", "findings": json.loads(result.stdout)}
            else:
                return {"status": "error", "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "trivy timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _analyze_findings(
        self,
        task: Task,
        context: Dict[str, Any],
        tool_results: Dict[str, Any],
    ) -> SecurityResult:
        """Analyze security tool findings with LLM."""
        messages = self._build_messages(task, context)
        
        analysis_prompt = f"""Analyze the security scan results and provide a comprehensive security assessment.

Tool Results:
{json.dumps(tool_results, indent=2)}

Your analysis should:
1. Categorize findings by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
2. Identify false positives
3. Prioritize remediation efforts
4. Provide specific remediation guidance
5. Assess overall security posture

Return structured JSON with:
- findings: array of findings with tool, rule_id, severity, file_path, line_number, message, cwe, cve, remediation
- summary: overall security assessment
- critical_count, high_count, medium_count, low_count"""
        
        messages.append({"role": "user", "content": analysis_prompt})
        
        from agent_system.providers import Message
        msg_objects = [Message(role=m["role"], content=m["content"]) for m in messages]
        
        result = await self._call_llm_structured(msg_objects, SecurityResult)
        return result if isinstance(result, SecurityResult) else SecurityResult(**result.model_dump())


def create_security_agent(tool_manager=None) -> SecurityAgent:
    """Factory function to create security agent."""
    models_config = get_config("models")
    security_config = models_config.get("security", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("security", {})
    
    config = AgentConfig(
        name=AgentName.SECURITY,
        description=agent_config.get("description", "Security analysis and vulnerability scanning"),
        permissions=agent_config.get("permissions", "READ_ONLY"),
        default_model=security_config.get("model", "deepseek/deepseek-chat"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 1),
        timeout=agent_config.get("timeout", 180),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return SecurityAgent(config, tool_manager)