"""
State Management - Database Layer
Async SQLite database operations for persistent workflow state.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from agent_system.state.models import (
    Base,
    TaskModel,
    SubTaskModel,
    AgentRunModel,
    WorkflowStateModel,
    AgentResultModel,
    ToolCallModel,
    ModelUsageModel,
    ApprovalRequestModel,
    ConflictInfoModel,
    CheckpointModel,
)
from agent_system.schemas import Task, SubTask, TaskStatus, AgentName


class DatabaseManager:
    """Manages async SQLite database operations."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to state/agent_system.db relative to project root
            project_root = Path(__file__).parent.parent.parent
            db_path = str(project_root / "state" / "agent_system.db")
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database engine and create tables."""
        if self._initialized:
            return
        
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False,
            pool_pre_ping=True,
        )
        
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        self._initialized = True
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._initialized = False
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if not self._initialized:
            await self.initialize()
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    # Task operations
    async def create_task(self, task: Task) -> TaskModel:
        """Create a new task."""
        async with self.session() as session:
            task_model = TaskModel(
                task_id=task.task_id,
                parent_task_id=task.parent_task_id,
                task_type=task.task_type,
                description=task.description,
                objective=task.objective,
                priority=task.priority,
                status=task.status,
                assigned_agent=task.assigned_agent,
                input_context=task.input_context,
                output=task.output,
                artifacts=task.artifacts,
                errors=task.errors,
                retry_count=task.retry_count,
                max_retries=task.max_retries,
                timeout_seconds=task.timeout_seconds,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                metadata=task.metadata,
            )
            session.add(task_model)
            await session.flush()
            return task_model
    
    async def get_task(self, task_id: str) -> Optional[TaskModel]:
        """Get a task by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.task_id == task_id)
            )
            return result.scalar_one_or_none()
    
    async def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        output: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        retry_count: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Update a task."""
        async with self.session() as session:
            values = {}
            if status is not None:
                values["status"] = status
            if output is not None:
                values["output"] = output
            if errors is not None:
                values["errors"] = errors
            if started_at is not None:
                values["started_at"] = started_at
            if completed_at is not None:
                values["completed_at"] = completed_at
            if retry_count is not None:
                values["retry_count"] = retry_count
            values.update(kwargs)
            
            if not values:
                return False
            
            result = await session.execute(
                update(TaskModel)
                .where(TaskModel.task_id == task_id)
                .values(**values)
            )
            return result.rowcount > 0
    
    async def get_tasks_by_status(self, status: TaskStatus, limit: int = 100) -> List[TaskModel]:
        """Get tasks by status."""
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.status == status)
                .order_by(TaskModel.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_child_tasks(self, parent_task_id: str) -> List[TaskModel]:
        """Get child tasks of a parent task."""
        async with self.session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.parent_task_id == parent_task_id)
                .order_by(TaskModel.created_at)
            )
            return list(result.scalars().all())
    
    # SubTask operations
    async def create_subtask(self, subtask: SubTask) -> SubTaskModel:
        """Create a new subtask."""
        async with self.session() as session:
            subtask_model = SubTaskModel(
                task_id=subtask.task_id,
                parent_task_id=subtask.parent_task_id,
                task_type=subtask.task_type,
                description=subtask.description,
                assigned_agent=subtask.assigned_agent,
                status=subtask.status,
                input_context=subtask.input_context,
                output=subtask.output,
                created_at=subtask.created_at,
                started_at=subtask.started_at,
                completed_at=subtask.completed_at,
                duration_ms=subtask.duration_ms,
                retry_count=subtask.retry_count,
                depends_on=subtask.depends_on,
            )
            session.add(subtask_model)
            await session.flush()
            return subtask_model
    
    async def get_subtask(self, task_id: str) -> Optional[SubTaskModel]:
        """Get a subtask by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(SubTaskModel).where(SubTaskModel.task_id == task_id)
            )
            return result.scalar_one_or_none()
    
    async def update_subtask(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        output: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        retry_count: Optional[int] = None,
    ) -> bool:
        """Update a subtask."""
        async with self.session() as session:
            values = {}
            if status is not None:
                values["status"] = status
            if output is not None:
                values["output"] = output
            if started_at is not None:
                values["started_at"] = started_at
            if completed_at is not None:
                values["completed_at"] = completed_at
            if duration_ms is not None:
                values["duration_ms"] = duration_ms
            if retry_count is not None:
                values["retry_count"] = retry_count
            
            if not values:
                return False
            
            result = await session.execute(
                update(SubTaskModel)
                .where(SubTaskModel.task_id == task_id)
                .values(**values)
            )
            return result.rowcount > 0
    
    async def get_subtasks_by_parent(self, parent_task_id: str) -> List[SubTaskModel]:
        """Get all subtasks for a parent task."""
        async with self.session() as session:
            result = await session.execute(
                select(SubTaskModel)
                .where(SubTaskModel.parent_task_id == parent_task_id)
                .order_by(SubTaskModel.created_at)
            )
            return list(result.scalars().all())
    
    # Agent Run operations
    async def record_agent_run(
        self,
        execution_id: str,
        task_id: str,
        agent: AgentName,
        provider: str,
        model: str,
        status: str,
        duration_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        error: Optional[str] = None,
        retry_count: int = 0,
        request_payload: Optional[Dict[str, Any]] = None,
        response_payload: Optional[Dict[str, Any]] = None,
    ) -> AgentRunModel:
        """Record an agent run."""
        async with self.session() as session:
            run = AgentRunModel(
                execution_id=execution_id,
                task_id=task_id,
                agent=agent,
                provider=provider,
                model=model,
                status=status,
                duration_ms=duration_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                error=error,
                retry_count=retry_count,
                request_payload=request_payload,
                response_payload=response_payload,
            )
            session.add(run)
            await session.flush()
            return run
    
    async def get_agent_runs(self, task_id: str) -> List[AgentRunModel]:
        """Get agent runs for a task."""
        async with self.session() as session:
            result = await session.execute(
                select(AgentRunModel)
                .where(AgentRunModel.task_id == task_id)
                .order_by(AgentRunModel.started_at)
            )
            return list(result.scalars().all())
    
    async def get_agent_runs_by_execution(self, execution_id: str) -> List[AgentRunModel]:
        """Get agent runs for an execution."""
        async with self.session() as session:
            result = await session.execute(
                select(AgentRunModel)
                .where(AgentRunModel.execution_id == execution_id)
                .order_by(AgentRunModel.started_at)
            )
            return list(result.scalars().all())
    
    # Agent Result operations
    async def save_agent_result(
        self,
        task_id: str,
        agent: AgentName,
        status: str,
        summary: str,
        findings: List[Dict[str, Any]],
        artifacts: List[Dict[str, Any]],
        recommendations: List[str],
        confidence: float,
        needs_followup: bool,
        followup_reason: Optional[str],
        duration_ms: int,
        token_usage: Optional[Dict[str, int]],
        model_used: Optional[str],
        provider_used: Optional[str],
        tool_calls: List[Dict[str, Any]],
        errors: List[str],
        metadata: Dict[str, Any],
    ) -> AgentResultModel:
        """Save an agent result."""
        async with self.session() as session:
            result = AgentResultModel(
                task_id=task_id,
                agent=agent,
                status=status,
                summary=summary,
                findings=findings,
                artifacts=artifacts,
                recommendations=recommendations,
                confidence=confidence,
                needs_followup=needs_followup,
                followup_reason=followup_reason,
                duration_ms=duration_ms,
                token_usage=token_usage,
                model_used=model_used,
                provider_used=provider_used,
                tool_calls=tool_calls,
                errors=errors,
                metadata=metadata,
            )
            session.add(result)
            await session.flush()
            return result
    
    async def get_agent_results(self, task_id: str) -> List[AgentResultModel]:
        """Get agent results for a task."""
        async with self.session() as session:
            result = await session.execute(
                select(AgentResultModel)
                .where(AgentResultModel.task_id == task_id)
                .order_by(AgentResultModel.created_at)
            )
            return list(result.scalars().all())
    
    # Workflow State operations
    async def save_workflow_state(
        self,
        workflow_id: str,
        workflow_name: str,
        definition: Dict[str, Any],
        current_step: Optional[str],
        status: TaskStatus,
        state_data: Dict[str, Any],
        step_results: Dict[str, Any],
    ) -> WorkflowStateModel:
        """Save or update workflow state."""
        async with self.session() as session:
            existing = await session.execute(
                select(WorkflowStateModel).where(WorkflowStateModel.workflow_id == workflow_id)
            )
            workflow = existing.scalar_one_or_none()
            
            if workflow:
                workflow.current_step = current_step
                workflow.status = status
                workflow.state_data = state_data
                workflow.step_results = step_results
                workflow.updated_at = datetime.utcnow()
                if status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                    workflow.completed_at = datetime.utcnow()
            else:
                workflow = WorkflowStateModel(
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    definition=definition,
                    current_step=current_step,
                    status=status,
                    state_data=state_data,
                    step_results=step_results,
                )
                session.add(workflow)
            
            await session.flush()
            return workflow
    
    async def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowStateModel]:
        """Get workflow state."""
        async with self.session() as session:
            result = await session.execute(
                select(WorkflowStateModel).where(WorkflowStateModel.workflow_id == workflow_id)
            )
            return result.scalar_one_or_none()
    
    # Tool Call operations
    async def record_tool_call(
        self,
        execution_id: str,
        task_id: str,
        agent: AgentName,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[Any],
        error: Optional[str],
        duration_ms: int,
    ) -> ToolCallModel:
        """Record a tool call."""
        async with self.session() as session:
            tool_call = ToolCallModel(
                execution_id=execution_id,
                task_id=task_id,
                agent=agent,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                error=error,
                duration_ms=duration_ms,
            )
            session.add(tool_call)
            await session.flush()
            return tool_call
    
    async def get_tool_calls(self, execution_id: str) -> List[ToolCallModel]:
        """Get tool calls for an execution."""
        async with self.session() as session:
            result = await session.execute(
                select(ToolCallModel)
                .where(ToolCallModel.execution_id == execution_id)
                .order_by(ToolCallModel.timestamp)
            )
            return list(result.scalars().all())
    
    # Model Usage operations
    async def record_model_usage(
        self,
        provider: str,
        model: str,
        agent: AgentName,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        error: bool = False,
    ) -> None:
        """Record model usage for cost tracking."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        async with self.session() as session:
            # Try to find existing record for today
            result = await session.execute(
                select(ModelUsageModel).where(
                    and_(
                        ModelUsageModel.date == today,
                        ModelUsageModel.provider == provider,
                        ModelUsageModel.model == model,
                        ModelUsageModel.agent == agent,
                    )
                )
            )
            usage = result.scalar_one_or_none()
            
            if usage:
                usage.request_count += 1
                usage.input_tokens += input_tokens
                usage.output_tokens += output_tokens
                usage.total_tokens += input_tokens + output_tokens
                usage.cost_usd += cost_usd
                if error:
                    usage.error_count += 1
                usage.updated_at = datetime.utcnow()
            else:
                usage = ModelUsageModel(
                    date=today,
                    provider=provider,
                    model=model,
                    agent=agent,
                    request_count=1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    cost_usd=cost_usd,
                    error_count=1 if error else 0,
                )
                session.add(usage)
    
    async def get_daily_usage(self, date: Optional[str] = None) -> List[ModelUsageModel]:
        """Get model usage for a date."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        async with self.session() as session:
            result = await session.execute(
                select(ModelUsageModel)
                .where(ModelUsageModel.date == date)
                .order_by(ModelUsageModel.provider, ModelUsageModel.model)
            )
            return list(result.scalars().all())
    
    async def get_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get usage summary for the last N days."""
        from datetime import timedelta
        
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        async with self.session() as session:
            result = await session.execute(
                select(
                    ModelUsageModel.provider,
                    ModelUsageModel.model,
                    func.sum(ModelUsageModel.request_count).label("total_requests"),
                    func.sum(ModelUsageModel.input_tokens).label("total_input_tokens"),
                    func.sum(ModelUsageModel.output_tokens).label("total_output_tokens"),
                    func.sum(ModelUsageModel.total_tokens).label("total_tokens"),
                    func.sum(ModelUsageModel.cost_usd).label("total_cost"),
                    func.sum(ModelUsageModel.error_count).label("total_errors"),
                )
                .where(ModelUsageModel.date >= start_date)
                .group_by(ModelUsageModel.provider, ModelUsageModel.model)
            )
            
            return [
                {
                    "provider": row.provider,
                    "model": row.model,
                    "requests": row.total_requests or 0,
                    "input_tokens": row.total_input_tokens or 0,
                    "output_tokens": row.total_output_tokens or 0,
                    "total_tokens": row.total_tokens or 0,
                    "cost_usd": row.total_cost or 0.0,
                    "errors": row.total_errors or 0,
                }
                for row in result
            ]
    
    # Approval Request operations
    async def create_approval_request(
        self,
        request_id: str,
        task_id: str,
        action_type: str,
        description: str,
        context: Dict[str, Any],
        requested_by: str,
        expires_at: Optional[datetime] = None,
    ) -> ApprovalRequestModel:
        """Create an approval request."""
        async with self.session() as session:
            request = ApprovalRequestModel(
                request_id=request_id,
                task_id=task_id,
                action_type=action_type,
                description=description,
                context=context,
                requested_by=requested_by,
                expires_at=expires_at,
            )
            session.add(request)
            await session.flush()
            return request
    
    async def get_approval_request(self, request_id: str) -> Optional[ApprovalRequestModel]:
        """Get an approval request."""
        async with self.session() as session:
            result = await session.execute(
                select(ApprovalRequestModel).where(ApprovalRequestModel.request_id == request_id)
            )
            return result.scalar_one_or_none()
    
    async def update_approval_request(
        self,
        request_id: str,
        status: str,
        approved_by: Optional[str] = None,
    ) -> bool:
        """Update an approval request."""
        async with self.session() as session:
            values = {"status": status}
            if approved_by:
                values["approved_by"] = approved_by
            if status in ("approved", "denied"):
                values["approved_at"] = datetime.utcnow()
            
            result = await session.execute(
                update(ApprovalRequestModel)
                .where(ApprovalRequestModel.request_id == request_id)
                .values(**values)
            )
            return result.rowcount > 0
    
    async def get_pending_approvals(self) -> List[ApprovalRequestModel]:
        """Get all pending approval requests."""
        async with self.session() as session:
            result = await session.execute(
                select(ApprovalRequestModel)
                .where(ApprovalRequestModel.status == "pending")
                .order_by(ApprovalRequestModel.requested_at)
            )
            return list(result.scalars().all())
    
    # Conflict operations
    async def record_conflict(
        self,
        conflict_id: str,
        task_id: str,
        agents: List[str],
        differing_outputs: Dict[str, Any],
        resolution_strategy: str,
    ) -> ConflictInfoModel:
        """Record a conflict between agents."""
        async with self.session() as session:
            conflict = ConflictInfoModel(
                conflict_id=conflict_id,
                task_id=task_id,
                agents=agents,
                differing_outputs=differing_outputs,
                resolution_strategy=resolution_strategy,
            )
            session.add(conflict)
            await session.flush()
            return conflict
    
    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: Dict[str, Any],
        resolved_by: str,
    ) -> bool:
        """Mark a conflict as resolved."""
        async with self.session() as session:
            result = await session.execute(
                update(ConflictInfoModel)
                .where(ConflictInfoModel.conflict_id == conflict_id)
                .values(
                    resolved=True,
                    resolution=resolution,
                    resolved_by=resolved_by,
                    resolved_at=datetime.utcnow(),
                )
            )
            return result.rowcount > 0
    
    async def get_unresolved_conflicts(self, task_id: Optional[str] = None) -> List[ConflictInfoModel]:
        """Get unresolved conflicts."""
        async with self.session() as session:
            query = select(ConflictInfoModel).where(ConflictInfoModel.resolved == False)
            if task_id:
                query = query.where(ConflictInfoModel.task_id == task_id)
            result = await session.execute(query.order_by(ConflictInfoModel.created_at))
            return list(result.scalars().all())
    
    # Checkpoint operations
    async def create_checkpoint(
        self,
        checkpoint_id: str,
        execution_id: str,
        step: str,
        state_snapshot: Dict[str, Any],
        description: str = "",
    ) -> CheckpointModel:
        """Create a checkpoint."""
        async with self.session() as session:
            checkpoint = CheckpointModel(
                checkpoint_id=checkpoint_id,
                execution_id=execution_id,
                step=step,
                state_snapshot=state_snapshot,
                description=description,
            )
            session.add(checkpoint)
            await session.flush()
            return checkpoint
    
    async def get_latest_checkpoint(self, execution_id: str) -> Optional[CheckpointModel]:
        """Get the latest checkpoint for an execution."""
        async with self.session() as session:
            result = await session.execute(
                select(CheckpointModel)
                .where(CheckpointModel.execution_id == execution_id)
                .order_by(CheckpointModel.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
    
    # Cleanup operations
    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old data."""
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        async with self.session() as session:
            # Delete old agent runs
            result = await session.execute(
                delete(AgentRunModel).where(AgentRunModel.started_at < cutoff)
            )
            deleted = result.rowcount
            
            # Delete old tool calls
            result = await session.execute(
                delete(ToolCallModel).where(ToolCallModel.timestamp < cutoff)
            )
            deleted += result.rowcount
            
            # Delete old model usage
            cutoff_date = cutoff.strftime("%Y-%m-%d")
            result = await session.execute(
                delete(ModelUsageModel).where(ModelUsageModel.date < cutoff_date)
            )
            deleted += result.rowcount
            
            return deleted


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


async def close_db_manager() -> None:
    """Close the global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None