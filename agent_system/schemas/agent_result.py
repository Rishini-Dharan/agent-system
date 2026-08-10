"""
Schemas for Structured Agent Output
All agents must return structured JSON that validates against these models.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class AgentName(str, Enum):
    ORCHESTRATOR = "orchestrator"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    SECURITY = "security"
    TESTER = "tester"
    GITHUB = "github"
    BROWSER = "browser"


class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"
    SAFE_WRITE = "safe_write"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


class FindingType(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    ISSUE = "issue"
    VULNERABILITY = "vulnerability"
    BUG = "bug"
    TEST_FAILURE = "test_failure"
    SECURITY_FINDING = "security_finding"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    SUGGESTION = "suggestion"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AgentResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


# Base finding model
class Finding(BaseModel):
    type: FindingType
    claim: str
    description: Optional[str] = None
    severity: Optional[Severity] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    accessed_date: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    rule_id: Optional[str] = None
    cwe: Optional[str] = None
    cve: Optional[str] = None
    remediation: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Artifact model
class Artifact(BaseModel):
    path: str
    type: str  # file, diff, screenshot, report, etc.
    description: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Tool call model
class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


# Base agent result
class AgentResult(BaseModel):
    task_id: str
    agent: AgentName
    status: AgentResultStatus
    summary: str
    findings: List[Finding] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    needs_followup: bool = False
    followup_reason: Optional[str] = None
    duration_ms: int = 0
    token_usage: Optional[Dict[str, int]] = None
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# Specialized agent results
class ResearchResult(AgentResult):
    agent: AgentName = AgentName.RESEARCHER
    sources_consulted: int = 0
    facts_found: int = 0
    inferences_made: int = 0


class CodeResult(AgentResult):
    agent: AgentName = AgentName.CODER
    files_changed: List[str] = Field(default_factory=list)
    diff_summary: Optional[str] = None
    tests_added: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    lint_errors: int = 0
    type_errors: int = 0


class ReviewResult(AgentResult):
    agent: AgentName = AgentName.REVIEWER
    decision: str = "request_changes"  # approve, reject, request_changes
    reasoning: str = ""
    issues_found: List[Finding] = Field(default_factory=list)
    tests_reviewed: int = 0
    security_reviewed: bool = True


class SecurityResult(AgentResult):
    agent: AgentName = AgentName.SECURITY
    scan_id: Optional[str] = None
    tools_run: List[str] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


class TestResult(AgentResult):
    agent: AgentName = AgentName.TESTER
    tests_created: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    coverage: Optional[float] = None
    failures: List[Dict[str, Any]] = Field(default_factory=list)


class GitHubResult(AgentResult):
    agent: AgentName = AgentName.GITHUB
    branch: Optional[str] = None
    commits: List[str] = Field(default_factory=list)
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None


class BrowserResult(AgentResult):
    agent: AgentName = AgentName.BROWSER
    url: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    screenshots: List[str] = Field(default_factory=list)


class OrchestratorResult(AgentResult):
    agent: AgentName = AgentName.ORCHESTRATOR
    subtasks: List[Dict[str, Any]] = Field(default_factory=list)
    approvals_requested: int = 0
    approvals_granted: int = 0
    final_result: Optional[str] = None
    next_action: str = "complete"
    requires_approval: bool = False


# Task models
class Task(BaseModel):
    task_id: str
    parent_task_id: Optional[str] = None
    description: str
    objective: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[AgentName] = None
    input_context: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[AgentResult] = None
    artifacts: List[Artifact] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    test_results: Optional[TestResult] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SubTask(BaseModel):
    task_id: str
    parent_task_id: str
    description: str
    assigned_agent: AgentName
    status: TaskStatus = TaskStatus.PENDING
    input_context: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[AgentResult] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    retry_count: int = 0
    depends_on: List[str] = Field(default_factory=list)  # Other subtask IDs
    errors: List[str] = Field(default_factory=list)


class WorkflowState(BaseModel):
    workflow_id: str
    workflow_name: str
    current_step: str
    status: TaskStatus = TaskStatus.RUNNING
    state_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tasks: List[Task] = Field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0


# Validation functions
def validate_agent_result(result: Dict[str, Any], agent: AgentName) -> AgentResult:
    """Validate and parse agent result based on agent type."""
    result["agent"] = agent
    
    if agent == AgentName.RESEARCHER:
        return ResearchResult(**result)
    elif agent == AgentName.CODER:
        return CodeResult(**result)
    elif agent == AgentName.REVIEWER:
        return ReviewResult(**result)
    elif agent == AgentName.SECURITY:
        return SecurityResult(**result)
    elif agent == AgentName.TESTER:
        return TestResult(**result)
    elif agent == AgentName.GITHUB:
        return GitHubResult(**result)
    elif agent == AgentName.BROWSER:
        return BrowserResult(**result)
    elif agent == AgentName.ORCHESTRATOR:
        return OrchestratorResult(**result)
    else:
        return AgentResult(**result)


def repair_agent_result(result: Dict[str, Any], agent: AgentName) -> Dict[str, Any]:
    """Attempt to repair an invalid agent result."""
    repaired = result.copy()
    
    # Ensure required fields
    if "task_id" not in repaired:
        repaired["task_id"] = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    if "status" not in repaired:
        repaired["status"] = "failed"
    
    if "summary" not in repaired:
        repaired["summary"] = "No summary provided"
    
    if "confidence" not in repaired:
        repaired["confidence"] = 0.5
    else:
        repaired["confidence"] = max(0.0, min(1.0, float(repaired["confidence"])))
    
    if "findings" not in repaired:
        repaired["findings"] = []
    
    if "artifacts" not in repaired:
        repaired["artifacts"] = []
    
    if "recommendations" not in repaired:
        repaired["recommendations"] = []
    
    if "needs_followup" not in repaired:
        repaired["needs_followup"] = False
    
    if "metadata" not in repaired:
        repaired["metadata"] = {}
    
    return repaired