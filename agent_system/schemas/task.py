"""
Task and Workflow Schemas
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agent_system.schemas.agent_result import TaskStatus, AgentName


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(str, Enum):
    RESEARCH = "research"
    CODE_IMPLEMENT = "code_implement"
    CODE_REVIEW = "code_review"
    SECURITY_SCAN = "security_scan"
    TESTING = "testing"
    GITHUB_OPS = "github_ops"
    WEB_BROWSE = "web_browse"
    PLANNING = "planning"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    CUSTOM = "custom"


class Task(BaseModel):
    task_id: str
    parent_task_id: Optional[str] = None
    task_type: TaskType = TaskType.CUSTOM
    description: str
    objective: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[AgentName] = None
    input_context: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)  # Paths to artifacts
    errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SubTask(BaseModel):
    task_id: str
    parent_task_id: str
    task_type: TaskType = TaskType.CUSTOM
    description: str
    assigned_agent: AgentName
    status: TaskStatus = TaskStatus.PENDING
    input_context: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    retry_count: int = 0
    depends_on: List[str] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    step_id: str
    name: str
    description: str
    agent: AgentName
    input_mapping: Dict[str, str] = Field(default_factory=dict)  # workflow_state_key -> task_input_key
    output_mapping: Dict[str, str] = Field(default_factory=dict)  # task_output_key -> workflow_state_key
    condition: Optional[str] = None  # Python expression for conditional execution
    parallel: bool = False
    depends_on: List[str] = Field(default_factory=list)  # Step IDs


class WorkflowDefinition(BaseModel):
    workflow_id: str
    name: str
    description: str
    version: str = "1.0"
    steps: List[WorkflowStep] = Field(default_factory=list)
    entry_step: Optional[str] = None
    exit_steps: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    workflow_id: str
    workflow_name: str
    definition: WorkflowDefinition
    current_step: Optional[str] = None
    status: TaskStatus = TaskStatus.RUNNING
    state_data: Dict[str, Any] = Field(default_factory=dict)
    step_results: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    tasks: List[Task] = Field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0


class ExecutionPlan(BaseModel):
    plan_id: str
    objective: str
    tasks: List[Task] = Field(default_factory=list)
    parallel_groups: List[List[str]] = Field(default_factory=list)  # Groups of task_ids that can run in parallel
    estimated_duration_seconds: int = 0
    required_agents: List[AgentName] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)