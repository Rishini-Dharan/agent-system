#!/usr/bin/env python3
"""
Security Scan Script - Cross-platform security scanning
Runs Semgrep, Gitleaks, Trivy and generates structured reports
"""
import json
import subprocess
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import sqlite3


class SecurityScanner:
    def __init__(self, target_path: str = ".", output_dir: str = "reports/security"):
        self.target_path = Path(target_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scan_id = f"sec-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.db_path = Path("state/agent.db").resolve()
        
    def run_command(self, cmd: List[str], cwd: Path = None, timeout: int = 300) -> Dict[str, Any]:
        """Run command and return structured result"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or self.target_path
            )
            return {
                "status": "success" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": f"Command timed out after {timeout}s", "command": " ".join(cmd)}
        except Exception as e:
            return {"status": "error", "error": str(e), "command": " ".join(cmd)}
    
    def run_semgrep(self) -> Dict[str, Any]:
        """Run Semgrep SAST scan"""
        print(f"[*] Running Semgrep on {self.target_path}")
        result = self.run_command([
            "semgrep", "scan",
            "--config=auto",
            "--json",
            "--quiet",
            str(self.target_path)
        ])
        
        findings = []
        if result["status"] in ("success", "failed") and result["stdout"]:
            try:
                data = json.loads(result["stdout"])
                for r in data.get("results", []):
                    findings.append({
                        "tool": "semgrep",
                        "rule_id": r.get("check_id", ""),
                        "severity": r.get("extra", {}).get("severity", "INFO").upper(),
                        "file": r.get("path", ""),
                        "line": r.get("start", {}).get("line", 0),
                        "message": r.get("extra", {}).get("message", ""),
                        "cwe": r.get("extra", {}).get("metadata", {}).get("cwe", ""),
                        "remediation": r.get("extra", {}).get("metadata", {}).get("remediation", "")
                    })
            except json.JSONDecodeError:
                pass
        
        return {"tool": "semgrep", "result": result, "findings": findings}
    
    def run_gitleaks(self) -> Dict[str, Any]:
        """Run Gitleaks secret detection"""
        print(f"[*] Running Gitleaks on {self.target_path}")
        result = self.run_command([
            "gitleaks", "detect",
            "--source", str(self.target_path),
            "--report-format", "json",
            "--no-git",
            "--verbose"
        ])
        
        findings = []
        # Gitleaks writes to file, also check stdout
        report_file = self.target_path / ".gitleaks.json"
        if report_file.exists():
            try:
                with open(report_file) as f:
                    data = json.load(f)
                for r in data:
                    findings.append({
                        "tool": "gitleaks",
                        "rule_id": r.get("RuleID", ""),
                        "severity": "HIGH",
                        "file": r.get("File", ""),
                        "line": r.get("StartLine", 0),
                        "message": f"Secret detected: {r.get('Description', '')}",
                        "cwe": "CWE-798",
                        "remediation": "Remove secret from code, rotate credential, use env var"
                    })
            except json.JSONDecodeError:
                pass
        
        return {"tool": "gitleaks", "result": result, "findings": findings}
    
    def run_trivy_fs(self) -> Dict[str, Any]:
        """Run Trivy filesystem scan for vulnerabilities"""
        print(f"[*] Running Trivy FS on {self.target_path}")
        result = self.run_command([
            "trivy", "fs",
            "--format", "json",
            "--quiet",
            str(self.target_path)
        ])
        
        findings = []
        if result["status"] in ("success", "failed") and result["stdout"]:
            try:
                data = json.loads(result["stdout"])
                for target in data.get("Results", []):
                    for vuln in target.get("Vulnerabilities", []):
                        findings.append({
                            "tool": "trivy",
                            "rule_id": vuln.get("VulnerabilityID", ""),
                            "severity": vuln.get("Severity", "UNKNOWN").upper(),
                            "file": target.get("Target", ""),
                            "line": 0,
                            "message": f"{vuln.get('Title', '')}: {vuln.get('Description', '')[:200]}",
                            "cwe": "",
                            "cve": vuln.get("VulnerabilityID", ""),
                            "remediation": vuln.get("FixedVersion", "Update package")
                        })
            except json.JSONDecodeError:
                pass
        
        return {"tool": "trivy", "result": result, "findings": findings}
    
    def run_trivy_image(self, image: str) -> Dict[str, Any]:
        """Run Trivy container image scan"""
        print(f"[*] Running Trivy on image {image}")
        result = self.run_command([
            "trivy", "image",
            "--format", "json",
            "--quiet",
            image
        ])
        
        findings = []
        if result["status"] in ("success", "failed") and result["stdout"]:
            try:
                data = json.loads(result["stdout"])
                for target in data.get("Results", []):
                    for vuln in target.get("Vulnerabilities", []):
                        findings.append({
                            "tool": "trivy-image",
                            "rule_id": vuln.get("VulnerabilityID", ""),
                            "severity": vuln.get("Severity", "UNKNOWN").upper(),
                            "file": f"image:{image}",
                            "line": 0,
                            "message": f"{vuln.get('Title', '')}: {vuln.get('Description', '')[:200]}",
                            "cwe": "",
                            "cve": vuln.get("VulnerabilityID", ""),
                            "remediation": vuln.get("FixedVersion", "Update base image")
                        })
            except json.JSONDecodeError:
                pass
        
        return {"tool": "trivy-image", "result": result, "findings": findings}
    
    def save_report(self, all_findings: List[Dict], summary: Dict) -> str:
        """Save structured report"""
        report = {
            "scan_id": self.scan_id,
            "timestamp": datetime.now().isoformat(),
            "target_path": str(self.target_path),
            "summary": summary,
            "findings": all_findings
        }
        
        report_file = self.output_dir / f"{self.scan_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        # Also save latest symlink (skip on Windows if no permission)
        latest = self.output_dir / "latest.json"
        if latest.exists():
            latest.unlink()
        try:
            latest.symlink_to(report_file.name)
        except OSError:
            # Windows may not allow symlinks without admin - copy instead
            import shutil
            shutil.copy2(report_file, latest)
        
        return str(report_file)
    
    def save_to_db(self, all_findings: List[Dict], summary: Dict):
        """Save findings to SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert scan record
            cursor.execute("""
                INSERT INTO security_scans (scan_id, scan_type, target_path, tools_run, findings_count, critical_count, high_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.scan_id,
                "full",
                str(self.target_path),
                json.dumps(["semgrep", "gitleaks", "trivy"]),
                summary.get("total", 0),
                summary.get("critical", 0),
                summary.get("high", 0),
                "completed"
            ))
            
            # Insert findings
            for f in all_findings:
                cursor.execute("""
                    INSERT INTO security_findings (scan_id, tool, rule_id, severity, file_path, line_number, message, cwe, cve, remediation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.scan_id,
                    f.get("tool"),
                    f.get("rule_id"),
                    f.get("severity"),
                    f.get("file"),
                    f.get("line"),
                    f.get("message"),
                    f.get("cwe"),
                    f.get("cve"),
                    f.get("remediation")
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[!] Failed to save to DB: {e}")
    
    def run_all(self, include_image: str = None) -> Dict[str, Any]:
        """Run all security scans"""
        print(f"\n{'='*60}")
        print(f"Security Scan: {self.scan_id}")
        print(f"Target: {self.target_path}")
        print(f"{'='*60}\n")
        
        all_findings = []
        tool_results = {}
        
        # Run scans
        semgrep_result = self.run_semgrep()
        all_findings.extend(semgrep_result["findings"])
        tool_results["semgrep"] = semgrep_result["result"]
        
        gitleaks_result = self.run_gitleaks()
        all_findings.extend(gitleaks_result["findings"])
        tool_results["gitleaks"] = gitleaks_result["result"]
        
        trivy_result = self.run_trivy_fs()
        all_findings.extend(trivy_result["findings"])
        tool_results["trivy"] = trivy_result["result"]
        
        if include_image:
            trivy_img_result = self.run_trivy_image(include_image)
            all_findings.extend(trivy_img_result["findings"])
            tool_results["trivy-image"] = trivy_img_result["result"]
        
        # Summarize
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        summary = {
            "total": len(all_findings),
            "critical": sum(1 for f in all_findings if f.get("severity") == "CRITICAL"),
            "high": sum(1 for f in all_findings if f.get("severity") == "HIGH"),
            "medium": sum(1 for f in all_findings if f.get("severity") == "MEDIUM"),
            "low": sum(1 for f in all_findings if f.get("severity") == "LOW"),
            "info": sum(1 for f in all_findings if f.get("severity") == "INFO"),
            "by_tool": {}
        }
        
        for f in all_findings:
            tool = f.get("tool", "unknown")
            if tool not in summary["by_tool"]:
                summary["by_tool"][tool] = {"total": 0, "critical": 0, "high": 0}
            summary["by_tool"][tool]["total"] += 1
            if f.get("severity") == "CRITICAL":
                summary["by_tool"][tool]["critical"] += 1
            elif f.get("severity") == "HIGH":
                summary["by_tool"][tool]["high"] += 1
        
        # Save report
        report_path = self.save_report(all_findings, summary)
        self.save_to_db(all_findings, summary)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"SCAN COMPLETE: {self.scan_id}")
        print(f"{'='*60}")
        print(f"Total Findings: {summary['total']}")
        print(f"  CRITICAL: {summary['critical']}")
        print(f"  HIGH:     {summary['high']}")
        print(f"  MEDIUM:   {summary['medium']}")
        print(f"  LOW:      {summary['low']}")
        print(f"  INFO:     {summary['info']}")
        print(f"\nBy Tool:")
        for tool, stats in summary["by_tool"].items():
            print(f"  {tool}: {stats['total']} (CRITICAL: {stats['critical']}, HIGH: {stats['high']})")
        print(f"\nReport: {report_path}")
        print(f"{'='*60}\n")
        
        return {
            "scan_id": self.scan_id,
            "summary": summary,
            "findings": all_findings,
            "report_path": report_path,
            "tool_results": tool_results
        }


def main():
    parser = argparse.ArgumentParser(description="Security Scanner")
    parser.add_argument("--path", default=".", help="Target path to scan")
    parser.add_argument("--output", default="reports/security", help="Output directory")
    parser.add_argument("--image", help="Docker image to scan (optional)")
    parser.add_argument("--tools", nargs="+", default=["semgrep", "gitleaks", "trivy"], 
                       help="Tools to run")
    
    args = parser.parse_args()
    
    scanner = SecurityScanner(args.path, args.output)
    result = scanner.run_all(include_image=args.image)
    
    # Exit with error code if critical/high findings
    if result["summary"]["critical"] > 0 or result["summary"]["high"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()