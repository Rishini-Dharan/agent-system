"""
Security - Scanners
Integration with security scanning tools.
"""
from __future__ import annotations

import json
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_system.observability import get_logger


class SecurityScanner:
    """Base class for security scanners."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"scanner.{name}")
    
    def is_available(self) -> bool:
        """Check if scanner is available."""
        try:
            subprocess.run(
                ["which", self.name],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def scan(self, path: str = ".") -> Dict[str, Any]:
        """Run scan. Override in subclass."""
        raise NotImplementedError


class SemgrepScanner(SecurityScanner):
    """Semgrep static analysis scanner."""
    
    def __init__(self):
        super().__init__("semgrep")
    
    def scan(self, path: str = ".", config: str = "auto") -> Dict[str, Any]:
        """Run semgrep scan."""
        if not self.is_available():
            return {"status": "skipped", "reason": "semgrep not installed"}
        
        workspace = Path(path).resolve()
        
        try:
            result = subprocess.run(
                [
                    "semgrep",
                    f"--config={config}",
                    "--json",
                    "--quiet",
                    str(workspace),
                ],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=workspace,
            )
            
            if result.returncode in (0, 1):  # 1 = findings found
                try:
                    data = json.loads(result.stdout)
                    return {
                        "status": "success",
                        "tool": "semgrep",
                        "results": data.get("results", []),
                        "errors": data.get("errors", []),
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "error",
                        "error": "Failed to parse semgrep output",
                        "raw_output": result.stdout[:5000],
                    }
            else:
                return {
                    "status": "error",
                    "error": result.stderr,
                    "returncode": result.returncode,
                }
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "semgrep timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class GitleaksScanner(SecurityScanner):
    """Gitleaks secret detection scanner."""
    
    def __init__(self):
        super().__init__("gitleaks")
    
    def scan(self, path: str = ".") -> Dict[str, Any]:
        """Run gitleaks scan."""
        if not self.is_available():
            return {"status": "skipped", "reason": "gitleaks not installed"}
        
        workspace = Path(path).resolve()
        
        try:
            result = subprocess.run(
                [
                    "gitleaks",
                    "detect",
                    "--source",
                    str(workspace),
                    "--report-format",
                    "json",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=workspace,
            )
            
            # Gitleaks returns 0 if no leaks, 1 if leaks found
            if result.returncode in (0, 1):
                try:
                    findings = json.loads(result.stdout) if result.stdout.strip() else []
                    return {
                        "status": "success",
                        "tool": "gitleaks",
                        "results": findings,
                        "leaks_found": len(findings),
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "success",
                        "tool": "gitleaks",
                        "results": [],
                        "raw_output": result.stdout[:5000],
                    }
            else:
                return {
                    "status": "error",
                    "error": result.stderr,
                    "returncode": result.returncode,
                }
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "gitleaks timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class TrivyScanner(SecurityScanner):
    """Trivy vulnerability scanner."""
    
    def __init__(self):
        super().__init__("trivy")
    
    def scan(self, path: str = ".") -> Dict[str, Any]:
        """Run trivy filesystem scan."""
        if not self.is_available():
            return {"status": "skipped", "reason": "trivy not installed"}
        
        workspace = Path(path).resolve()
        
        try:
            result = subprocess.run(
                [
                    "trivy",
                    "fs",
                    "--format",
                    "json",
                    "--quiet",
                    str(workspace),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=workspace,
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    return {
                        "status": "success",
                        "tool": "trivy",
                        "results": data.get("Results", []),
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "error",
                        "error": "Failed to parse trivy output",
                        "raw_output": result.stdout[:5000],
                    }
            else:
                return {
                    "status": "error",
                    "error": result.stderr,
                    "returncode": result.returncode,
                }
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "trivy timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class CompositeScanner:
    """Runs multiple scanners and aggregates results."""
    
    def __init__(self):
        self.scanners = [
            SemgrepScanner(),
            GitleaksScanner(),
            TrivyScanner(),
        ]
        self.logger = get_logger("scanner.composite")
    
    def run_all(self, path: str = ".") -> Dict[str, Any]:
        """Run all available scanners."""
        results = {
            "scan_id": f"scan-{int(os.times().elapsed)}",
            "scanners": {},
            "summary": {
                "total_findings": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
            },
        }
        
        for scanner in self.scanners:
            self.logger.info(f"Running {scanner.name}...")
            scanner_result = scanner.scan(path)
            results["scanners"][scanner.name] = scanner_result
            
            # Aggregate findings
            if scanner_result.get("status") == "success":
                findings = self._extract_findings(scanner.name, scanner_result)
                for finding in findings:
                    results["summary"]["total_findings"] += 1
                    severity = finding.get("severity", "info").lower()
                    if severity in results["summary"]:
                        results["summary"][severity] += 1
        
        return results
    
    def _extract_findings(self, tool: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract normalized findings from scanner result."""
        findings = []
        
        if tool == "semgrep":
            for r in result.get("results", []):
                findings.append({
                    "tool": "semgrep",
                    "rule_id": r.get("check_id", ""),
                    "severity": r.get("extra", {}).get("severity", "INFO").upper(),
                    "file_path": r.get("path", ""),
                    "line_number": r.get("start", {}).get("line", 0),
                    "message": r.get("extra", {}).get("message", ""),
                    "cwe": r.get("extra", {}).get("metadata", {}).get("cwe", ""),
                })
        
        elif tool == "gitleaks":
            for r in result.get("results", []):
                findings.append({
                    "tool": "gitleaks",
                    "rule_id": r.get("RuleID", ""),
                    "severity": "HIGH",  # Secrets are typically high
                    "file_path": r.get("File", ""),
                    "line_number": r.get("StartLine", 0),
                    "message": f"Secret detected: {r.get('Description', '')}",
                })
        
        elif tool == "trivy":
            for r in result.get("results", []):
                for vuln in r.get("Vulnerabilities", []):
                    findings.append({
                        "tool": "trivy",
                        "rule_id": vuln.get("VulnerabilityID", ""),
                        "severity": vuln.get("Severity", "UNKNOWN").upper(),
                        "file_path": r.get("Target", ""),
                        "line_number": 0,
                        "message": vuln.get("Title", ""),
                        "cve": vuln.get("VulnerabilityID", ""),
                        "cwe": "",
                    })
        
        return findings


def run_security_scan(path: str = ".") -> Dict[str, Any]:
    """Run all security scans."""
    scanner = CompositeScanner()
    return scanner.run_all(path)