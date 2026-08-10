"""
Agent Runtime - Execution Manager
Manages task execution, parallel execution, and workflow orchestration.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from agent_system.config import get_config
from agent_system.router import ModelRouter, RoutingContext, TaskType, ComplexityLevel
from agent_system.schemas import (
    Task,
    SubTask,
    TaskStatus,
    TaskType as SchemaTaskType,
    AgentName,
    ExecutionContext,
    ExecutionMode,
    ExecutionMetrics,
    AgentExecution,
    ConflictInfo,
    ConflictResolutionStrategy,
    ApprovalRequest,
)
from agent_system.state import get_db_manager
from agent_system.runtime.agent_runtime import BaseAgent, AgentRegistry, get_agent_registry
from agent_system.runtime.context_manager import ContextManager
from agent_system.observability import get_logger, get_metrics


class ExecutionManager:
    """Manages execution of tasks and workflows."""
    
    def __init__(
        self,
        agent_registry: Optional[AgentRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        max_parallel_agents: int = 4,
    ):
        self.agent_registry = agent_registry or get_agent_registry()
        self.context_manager = context_manager or ContextManager()
        self.router = ModelRouter()
        self.max_parallel_agents = max_parallel_agents
        self.logger = get_logger("execution_manager")
        self.metrics = get_metrics()
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    async def initialize(self) -> None:
        """Initialize the execution manager."""
        self._semaphore = asyncio.Semaphore(self.max_parallel_agents)
        await self.agent_registry.initialize_all()
    
    async def shutdown(self) -> None:
        """Shutdown the execution manager."""
        # Cancel all running tasks
        for task in self._running_tasks.values():
            task.cancel()
        
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        
        await self.agent_registry.shutdown_all()
    
    async def execute_task(self, task: Task, context: Optional[Dict[str, Any]] = None) -> Task:
        """Execute a single task."""
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        
        self.logger.info(f"Executing task {task.task_id} (execution: {execution_id})")
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        await self._update_task_in_db(task)
        
        # Get agent
        agent = self.agent_registry.get(task.assigned_agent)
        if not agent:
            task.status = TaskStatus.FAILED
            task.errors.append(f"Agent {task.assigned_agent} not found")
            task.completed_at = datetime.utcnow()
            await self._update_task_in_db(task)
            return task
        
        # Prepare context
        full_context = context or {}
        agent_context = await self.context_manager.prepare_context(task, task.assigned_agent)
        full_context.update(agent_context)
        
        # Execute with semaphore for concurrency control
        async with self._semaphore:
            try:
                result = await agent.run(task, full_context)
                
                # Update task with result
                task.output = result.model_dump()
                task.artifacts = [a.path for a in result.artifacts]
                task.errors = result.errors
                
                if result.status == AgentResultStatus.SUCCESS:
                    task.status = TaskStatus.SUCCESS
                elif result.status == AgentResultStatus.PARTIAL:
                    task.status = TaskStatus.SUCCESS  # Partial is still success
                else:
                    task.status = TaskStatus.FAILED
                
                # Record metrics
                self.metrics.record_task_completion(
                    task_id=task.task_id,
                    agent=task.assigned_agent.value,
                    status=task.status.value,
                    duration_ms=result.duration_ms,
                )
                
            except Exception as e:
                self.logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
                task.status = TaskStatus.FAILED
                task.errors.append(str(e))
                
                self.metrics.record_task_completion(
                    task_id=task.task_id,
                    agent=task.assigned_agent.value,
                    status=TaskStatus.FAILED.value,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
        
        task.completed_at = datetime.utcnow()
        await self._update_task_in_db(task)
        
        return task
    
    async def execute_subtasks_parallel(
        self,
        subtasks: List[SubTask],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[SubTask]:
        """Execute multiple subtasks in parallel."""
        self.logger.info(f"Executing {len(subtasks)} subtasks in parallel")
        
        # Create tasks for each subtask
        async def run_subtask(subtask: SubTask) -> SubTask:
            # Convert to Task for execution
            task = Task(
                task_id=subtask.task_id,
                parent_task_id=subtask.parent_task_id,
                task_type=subtask.task_type,
                description=subtask.description,
                objective=subtask.description,  # Use description as objective
                assigned_agent=subtask.assigned_agent,
                input_context=subtask.input_context,
            )
            
            completed_task = await self.execute_task(task, context)
            
            # Update subtask with results
            subtask.status = completed_task.status
            subtask.output = completed_task.output
            subtask.started_at = completed_task.started_at
            subtask.completed_at = completed_task.completed_at
            subtask.duration_ms = int(
                (subtask.completed_at - subtask.started_at).total_seconds() * 1000
            ) if subtask.started_at and subtask.completed_at else 0
            
            return subtask
        
        # Run all subtasks concurrently
        results = await asyncio.gather(
            *[run_subtask(st) for st in subtasks],
            return_exceptions=True,
        )
        
        # Handle exceptions
        completed_subtasks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Subtask {subtasks[i].task_id} failed: {result}")
                subtasks[i].status = TaskStatus.FAILED
                subtasks[i].errors.append(str(result))
                completed_subtasks.append(subtasks[i])
            else:
                completed_subtasks.append(result)
        
        return completed_subtasks
    
    async def execute_subtasks_sequential(
        self,
        subtasks: List[SubTask],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[SubTask]:
        """Execute multiple subtasks sequentially."""
        self.logger.info(f"Executing {len(subtasks)} subtasks sequentially")
        
        completed_subtasks = []
        accumulated_context = context or {}
        
        for subtask in subtasks:
            # Add previous results to context
            if completed_subtasks:
                accumulated_context["previous_subtask_results"] = [
                    {
                        "task_id": st.task_id,
                        "status": st.status.value,
                        "output": st.output,
                    }
                    for st in completed_subtasks
                ]
            
            # Convert to Task for execution
            task = Task(
                task_id=subtask.task_id,
                parent_task_id=subtask.parent_task_id,
                task_type=subtask.task_type,
                description=subtask.description,
                objective=subtask.description,
                assigned_agent=subtask.assigned_agent,
                input_context=subtask.input_context,
            )
            
            completed_task = await self.execute_task(task, accumulated_context)
            
            # Update subtask with results
            subtask.status = completed_task.status
            subtask.output = completed_task.output
            subtask.started_at = completed_task.started_at
            subtask.completed_at = completed_task.completed_at
            subtask.duration_ms = int(
                (subtask.completed_at - subtask.started_at).total_seconds() * 1000
            ) if subtask.started_at and subtask.completed_at else 0
            
            completed_subtasks.append(subtask)
            
            # Stop on failure if configured
            if subtask.status == TaskStatus.FAILED:
                self.logger.warning(f"Subtask {subtask.task_id} failed, stopping sequential execution")
                break
        
        return completed_subtasks
    
    async def execute_workflow(
        self,
        workflow_id: str,
        workflow_name: str,
        objective: str,
        steps: List[Dict[str, Any]],
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionContext:
        """Execute a multi-step workflow."""
        execution_id = str(uuid.uuid4())
        
        exec_context = ExecutionContext(
            execution_id=execution_id,
            objective=objective,
            mode=ExecutionMode.ADAPTIVE,
            max_parallel_agents=self.max_parallel_agents,
            context_data=initial_context or {},
        )
        
        self.logger.info(f"Starting workflow {workflow_name} (execution: {execution_id})")
        
        # Save initial workflow state
        db = await get_db_manager()
        await db.save_workflow_state(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            definition={"steps": steps},
            current_step=None,
            status=TaskStatus.RUNNING,
            state_data=exec_context.context_data,
            step_results={},
        )
        
        completed_steps = []
        step_results = {}
        
        for step_def in steps:
            step_id = step_def.get("step_id", str(uuid.uuid4()))
            step_name = step_def.get("name", "unnamed")
            agent_name = AgentName(step_def.get("agent", "orchestrator"))
            step_context = step_def.get("context", {})
            
            # Check dependencies
            depends_on = step_def.get("depends_on", [])
            if depends_on:
                # Wait for dependencies (in sequential workflow)
                for dep_id in depends_on:
                    if dep_id not in step_results:
                        self.logger.warning(f"Dependency {dep_id} not found for step {step_id}")
            
            # Update workflow state
            await db.save_workflow_state(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                definition={"steps": steps},
                current_step=step_id,
                status=TaskStatus.RUNNING,
                state_data=exec_context.context_data,
                step_results=step_results,
            )
            
            # Prepare step context
            merged_context = {**exec_context.context_data, **step_context}
            merged_context["workflow_id"] = workflow_id
            merged_context["step_id"] = step_id
            
            # Create task for step
            task = Task(
                task_id=f"{workflow_id}-{step_id}",
                parent_task_id=workflow_id,
                task_type=SchemaTaskType.CUSTOM,
                description=step_def.get("description", step_name),
                objective=step_def.get("objective", objective),
                assigned_agent=agent_name,
                input_context=merged_context,
            )
            
            # Execute step
            completed_task = await self.execute_task(task, merged_context)
            
            # Record results
            step_results[step_id] = completed_task.output
            exec_context.context_data.update(completed_task.output or {})
            
            if completed_task.status == TaskStatus.SUCCESS:
                completed_steps.append(step_id)
                exec_context.metrics.completed_tasks += 1
            else:
                exec_context.metrics.failed_tasks += 1
                # Decide whether to continue or stop
                if step_def.get("required", True):
                    self.logger.error(f"Required step {step_id} failed, stopping workflow")
                    break
            
            exec_context.metrics.total_tasks += 1
        
        # Final workflow state
        final_status = TaskStatus.SUCCESS if exec_context.metrics.failed_tasks == 0 else TaskStatus.FAILED
        exec_context.metrics.total_duration_ms = int(
            (datetime.utcnow() - exec_context.created_at).total_seconds() * 1000
        )
        
        await db.save_workflow_state(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            definition={"steps": steps},
            current_step=None,
            status=final_status,
            state_data=exec_context.context_data,
            step_results=step_results,
        )
        
        exec_context.completed_at = datetime.utcnow()
        exec_context.status = final_status
        
        self.logger.info(f"Workflow {workflow_name} completed with status {final_status.value}")
        
        return exec_context
    
    async def resolve_conflict(
        self,
        task_id: str,
        agent_results: Dict[AgentName, Any],
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.ORCHESTRATOR_DECIDES,
    ) -> Dict[str, Any]:
        """Resolve conflicts between agent outputs."""
        self.logger.info(f"Resolving conflict for task {task_id} using {strategy.value}")
        
        conflict_id = str(uuid.uuid4())
        agents = list(agent_results.keys())
        differing_outputs = {k.value: v for k, v in agent_results.items()}
        
        # Save conflict
        db = await get_db_manager()
        await db.record_conflict(
            conflict_id=conflict_id,
            task_id=task_id,
            agents=[a.value for a in agents],
            differing_outputs=differing_outputs,
            resolution_strategy=strategy.value,
        )
        
        # Apply resolution strategy
        if strategy == ConflictResolutionStrategy.HIGHEST_CONFIDENCE:
            # Find result with highest confidence
            best_agent = max(
                agent_results.keys(),
                key=lambda a: agent_results[a].get("confidence", 0) if isinstance(agent_results[a], dict) else 0
            )
            resolution = {"selected_agent": best_agent.value, "reason": "highest_confidence"}
            
        elif strategy == ConflictResolutionStrategy.EVIDENCE_BASED:
            # Find result with most evidence/citations
            best_agent = max(
                agent_results.keys(),
                key=lambda a: len(agent_results[a].get("findings", [])) if isinstance(agent_results[a], dict) else 0
            )
            resolution = {"selected_agent": best_agent.value, "reason": "most_evidence"}
            
        elif strategy == ConflictResolutionStrategy.ORCHESTRATOR_DECIDES:
            # Ask orchestrator to decide
            orchestrator = self.agent_registry.get(AgentName.ORCHESTRATOR)
            if orchestrator:
                # Create a task for the orchestrator to resolve
                resolution_task = Task(
                    task_id=f"{task_id}-conflict-{conflict_id}",
                    parent_task_id=task_id,
                    task_type=SchemaTaskType.CUSTOM,
                    description=f"Resolve conflict between agents: {', '.join(a.value for a in agents)}",
                    objective="Analyze the differing outputs and decide on the best approach",
                    assigned_agent=AgentName.ORCHESTRATOR,
                    input_context={
                        "conflict_id": conflict_id,
                        "agent_outputs": differing_outputs,
                    },
                )
                result = await self.execute_task(resolution_task)
                resolution = result.output or {"selected_agent": agents[0].value, "reason": "orchestrator_default"}
            else:
                resolution = {"selected_agent": agents[0].value, "reason": "no_orchestrator"}
        
        else:
            # Default to first agent
            resolution = {"selected_agent": agents[0].value, "reason": "default"}
        
        # Update conflict as resolved
        await db.resolve_conflict(conflict_id, resolution, "execution_manager")
        
        return resolution
    
    async def request_approval(
        self,
        task_id: str,
        action_type: str,
        description: str,
        context: Dict[str, Any],
        requested_by: str,
    ) -> ApprovalRequest:
        """Request human approval for an action."""
        request_id = str(uuid.uuid4())
        
        request = ApprovalRequest(
            request_id=request_id,
            task_id=task_id,
            action_type=action_type,
            description=description,
            context=context,
            requested_by=requested_by,
        )
        
        db = await get_db_manager()
        await db.create_approval_request(
            request_id=request_id,
            task_id=task_id,
            action_type=action_type,
            description=description,
            context=context,
            requested_by=requested_by,
        )
        
        self.logger.info(f"Approval requested: {request_id} for {action_type}")
        
        # In a real implementation, this would notify a human
        # For now, we'll auto-approve for demo purposes
        # await self._wait_for_approval(request_id)
        
        return request
    
    async def _update_task_in_db(self, task: Task) -> None:
        """Update task in database."""
        try:
            db = await get_db_manager()
            await db.update_task(
                task_id=task.task_id,
                status=task.status,
                output=task.output,
                errors=task.errors,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )
        except Exception as e:
            self.logger.error(f"Failed to update task in DB: {e}")
    
    def get_running_tasks(self) -> List[str]:
        """Get list of running task IDs."""
        return list(self._running_tasks.keys())
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            return True
        return False