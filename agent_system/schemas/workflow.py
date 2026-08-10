"""
Workflow and Execution Schemas
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"


class ConflictResolutionStrategy(str, Enum):
    HIGHEST_CONFIDENCE = "highest_confidence"
    MAJORITY_VOTE = "majority_vote"
    ORCHESTRATOR_DECIDES = "orchestrator_decides"
    EVIDENCE_BASED = "evidence_based"
    HUMAN_REQUIRED = "human_required"


class AgentExecution(BaseModel):
    execution_id: str
    task_id: str
    agent: str
    provider: str
    model: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
    retry_count: int = 0


class ConflictInfo(BaseModel):
    conflict_id: str
    task_id: str
    agents: List[str]
    differing_outputs: Dict[str, Any]
    resolution_strategy: ConflictResolutionStrategy
    resolved: bool = False
    resolution: Optional[Dict[str, Any]] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class ExecutionMetrics(BaseModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_duration_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    agent_executions: List[AgentExecution] = Field(default_factory=list)
    conflicts: List[ConflictInfo] = Field(default_factory=list)
    fallbacks_triggered: int = 0
    retries: int = 0


class ExecutionContext(BaseModel):
    execution_id: str
    objective: str
    mode: ExecutionMode = ExecutionMode.ADAPTIVE
    max_parallel_agents: int = 4
    max_agent_calls: int = 50
    timeout_seconds: int = 1800
    context_data: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ApprovalRequest(BaseModel):
    request_id: str
    task_id: str
    action_type: str  # git_push, create_pr, submit_job_app, send_email, install_package, destructive_command
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)
    requested_by: str
    status: str = "pending"  # pending, approved, denied, expired
    requested_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    expires_at: Optional[datetime] = None


class Checkpoint(BaseModel):
    checkpoint_id: str
    execution_id: str
    step: str
    state_snapshot: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)
    description: str = ""