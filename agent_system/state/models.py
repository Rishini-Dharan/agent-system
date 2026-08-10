"""
State Management - Database Models
SQLAlchemy models for persistent workflow state.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Float,
    Boolean,
    Index,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import declarative_base, relationship

from agent_system.schemas import TaskStatus, AgentName, PermissionLevel, TaskType, TaskPriority

Base = declarative_base()


class TaskModel(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    parent_task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=True, index=True)
    task_type = Column(SQLEnum(TaskType), nullable=False, default=TaskType.CUSTOM)
    description = Column(Text, nullable=False)
    objective = Column(Text, nullable=False)
    priority = Column(SQLEnum(TaskPriority), nullable=False, default=TaskPriority.NORMAL)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    assigned_agent = Column(SQLEnum(AgentName), nullable=True, index=True)
    input_context = Column(JSON, nullable=False, default={})
    output = Column(JSON, nullable=True)
    artifacts = Column(JSON, nullable=False, default=[])
    errors = Column(JSON, nullable=False, default=[])
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    timeout_seconds = Column(Integer, nullable=False, default=300)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    task_metadata = Column(JSON, nullable=False, default={})
    
    # Relationships
    parent = relationship("TaskModel", remote_side=[task_id], backref="children")
    agent_runs = relationship("AgentRunModel", back_populates="task", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_tasks_status_created", "status", "created_at"),
        Index("ix_tasks_agent_status", "assigned_agent", "status"),
    )


class SubTaskModel(Base):
    __tablename__ = "subtasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    parent_task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    task_type = Column(SQLEnum(TaskType), nullable=False, default=TaskType.CUSTOM)
    description = Column(Text, nullable=False)
    assigned_agent = Column(SQLEnum(AgentName), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    input_context = Column(JSON, nullable=False, default={})
    output = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    depends_on = Column(JSON, nullable=False, default=[])
    errors = Column(JSON, nullable=False, default=[])
    
    __table_args__ = (
        Index("ix_subtasks_parent_status", "parent_task_id", "status"),
    )


class AgentRunModel(Base):
    __tablename__ = "agent_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    agent = Column(SQLEnum(AgentName), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    
    task = relationship("TaskModel", back_populates="agent_runs")
    
    __table_args__ = (
        Index("ix_agent_runs_task_agent", "task_id", "agent"),
        Index("ix_agent_runs_execution", "execution_id"),
    )


class WorkflowStateModel(Base):
    __tablename__ = "workflow_states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String(64), unique=True, nullable=False, index=True)
    workflow_name = Column(String(128), nullable=False)
    definition = Column(JSON, nullable=False)
    current_step = Column(String(64), nullable=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.RUNNING, index=True)
    state_data = Column(JSON, nullable=False, default={})
    step_results = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_workflow_status_updated", "status", "updated_at"),
    )


class AgentResultModel(Base):
    __tablename__ = "agent_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    agent = Column(SQLEnum(AgentName), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    summary = Column(Text, nullable=False)
    findings = Column(JSON, nullable=False, default=[])
    artifacts = Column(JSON, nullable=False, default=[])
    recommendations = Column(JSON, nullable=False, default=[])
    confidence = Column(Float, nullable=False, default=0.0)
    needs_followup = Column(Boolean, nullable=False, default=False)
    followup_reason = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    token_usage = Column(JSON, nullable=True)
    model_used = Column(String(128), nullable=True)
    provider_used = Column(String(64), nullable=True)
    tool_calls = Column(JSON, nullable=False, default=[])
    errors = Column(JSON, nullable=False, default=[])
    result_metadata = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_agent_results_task_agent", "task_id", "agent"),
        Index("ix_agent_results_created", "created_at"),
    )


class ToolCallModel(Base):
    __tablename__ = "tool_calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False, index=True)
    agent = Column(SQLEnum(AgentName), nullable=False)
    tool_name = Column(String(128), nullable=False)
    arguments = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_tool_calls_execution", "execution_id"),
        Index("ix_tool_calls_task", "task_id"),
    )


class ModelUsageModel(Base):
    __tablename__ = "model_usage"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False)
    agent = Column(SQLEnum(AgentName), nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    error_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_model_usage_date_provider_model", "date", "provider", "model", unique=True),
    )


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), unique=True, nullable=False, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    action_type = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
    context = Column(JSON, nullable=False, default={})
    requested_by = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_approval_status_requested", "status", "requested_at"),
    )


class ConflictInfoModel(Base):
    __tablename__ = "conflicts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conflict_id = Column(String(64), unique=True, nullable=False, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    agents = Column(JSON, nullable=False)
    differing_outputs = Column(JSON, nullable=False)
    resolution_strategy = Column(String(64), nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    resolution = Column(JSON, nullable=True)
    resolved_by = Column(String(64), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_conflicts_task_resolved", "task_id", "resolved"),
    )


class CheckpointModel(Base):
    __tablename__ = "checkpoints"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    checkpoint_id = Column(String(64), unique=True, nullable=False, index=True)
    execution_id = Column(String(64), nullable=False, index=True)
    step = Column(String(64), nullable=False)
    state_snapshot = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_checkpoints_execution", "execution_id"),
    )