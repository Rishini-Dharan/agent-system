"""
Orchestrator Agent
Central coordinator for task decomposition, planning, and agent delegation.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from agent_system.config import get_config
from agent_system.router import ModelRouter, RoutingContext, TaskType, ComplexityLevel
from agent_system.schemas import (
    Task,
    SubTask,
    TaskStatus,
    TaskType as SchemaTaskType,
    AgentName,
    AgentResult,
    OrchestratorResult,
    Finding,
    Artifact,
    FindingType,
    Severity,
    ConfidenceLevel,
    AgentResultStatus,
    ExecutionMode,
    ConflictResolutionStrategy,
)
from agent_system.runtime import BaseAgent, AgentConfig
from agent_system.observability import get_logger


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent - central coordinator."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.router = ModelRouter()
        self.logger = get_logger("agent.orchestrator")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute orchestration logic."""
        self.logger.info(f"Orchestrator analyzing task: {task.description[:100]}")
        
        # Step 1: Analyze the task and create execution plan
        plan = await self._create_execution_plan(task, context)
        
        # Step 2: Create subtasks
        subtasks = await self._create_subtasks(task, plan)
        
        # Step 3: Execute subtasks (delegated to execution manager)
        # For now, return the plan for the execution manager to handle
        
        return OrchestratorResult(
            task_id=task.task_id,
            agent=AgentName.ORCHESTRATOR,
            status=AgentResultStatus.SUCCESS,
            summary=f"Created execution plan with {len(subtasks)} subtasks",
            findings=[
                Finding(
                    type=FindingType.RECOMMENDATION,
                    claim=f"Execution plan created with {len(subtasks)} subtasks",
                    description=plan.get("reasoning", ""),
                    confidence=ConfidenceLevel.HIGH,
                )
            ],
            artifacts=[
                Artifact(
                    path=f"plan_{task.task_id}.json",
                    type="execution_plan",
                    description="Execution plan",
                    metadata=plan,
                )
            ],
            recommendations=plan.get("recommendations", []),
            confidence=0.9,
            subtasks=[
                {
                    "task_id": st.task_id,
                    "description": st.description,
                    "assigned_agent": st.assigned_agent.value,
                    "depends_on": st.depends_on,
                }
                for st in subtasks
            ],
            next_action="continue",
            requires_approval=False,
        )
    
    async def _create_execution_plan(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create an execution plan using LLM."""
        
        # Build planning prompt
        messages = [
            self._build_system_message(),
            self._build_planning_prompt(task, context),
        ]
        
        # Call LLM for planning
        response = await self._call_llm(
            messages,
            temperature=0.3,
            max_tokens=4096,
        )
        
        try:
            plan = json.loads(response.content)
            return plan
        except json.JSONDecodeError:
            # Fallback plan
            return self._create_fallback_plan(task)
    
    def _build_system_message(self) -> str:
        return """You are the Orchestrator - the central coordinator of a multi-agent autonomous coding system.

Your job is to:
1. Analyze the user's objective and decompose it into subtasks
2. Select the appropriate specialized agent for each subtask
3. Decide sequential vs parallel execution
4. Identify dependencies between subtasks
5. Create a detailed execution plan

Available specialized agents:
- researcher: Technical research, documentation analysis, error investigation
- coder: Code implementation, refactoring, bug fixes, test creation
- reviewer: Code review, bug detection, security analysis, architecture review
- security: Vulnerability scanning, secret detection, dependency analysis
- tester: Test creation, execution, failure analysis, bug reproduction
- github: Git operations, branch management, PR preparation
- browser: Web navigation, documentation retrieval, website inspection

Return a JSON object with:
{
  "reasoning": "Your analysis of the task",
  "subtasks": [
    {
      "description": "Subtask description",
      "agent": "agent_name",
      "depends_on": ["other_subtask_ids"],
      "parallel": true/false,
      "priority": "high/medium/low"
    }
  ],
  "recommendations": ["Any recommendations for the workflow"]
}"""
    
    def _build_planning_prompt(self, task: Task, context: Dict[str, Any]) -> str:
        prompt = f"""Analyze this task and create an execution plan:

Task: {task.description}
Objective: {task.objective}
Task Type: {task.task_type.value if hasattr(task.task_type, 'value') else task.task_type}

Context:
{json.dumps(context.get("input_context", {}), indent=2)}

Previous Results:
{json.dumps(context.get("previous_results", []), indent=2)}

Create a detailed execution plan as JSON."""
        return prompt
    
    def _create_fallback_plan(self, task: Task) -> Dict[str, Any]:
        """Create a simple fallback plan."""
        # Simple heuristic based on task type
        task_type = task.task_type if isinstance(task.task_type, str) else str(task.task_type)
        
        if "research" in task_type.lower():
            subtasks = [
                {"description": f"Research: {task.description}", "agent": "researcher", "depends_on": [], "parallel": False, "priority": "high"},
            ]
        elif "code" in task_type.lower() or "implement" in task_type.lower():
            subtasks = [
                {"description": f"Research implementation approaches", "agent": "researcher", "depends_on": [], "parallel": False, "priority": "high"},
                {"description": f"Implement: {task.description}", "agent": "coder", "depends_on": [], "parallel": False, "priority": "high"},
                {"description": f"Write tests for implementation", "agent": "tester", "depends_on": [], "parallel": False, "priority": "medium"},
                {"description": f"Review implementation", "agent": "reviewer", "depends_on": [], "parallel": False, "priority": "medium"},
            ]
        elif "security" in task_type.lower():
            subtasks = [
                {"description": f"Security scan: {task.description}", "agent": "security", "depends_on": [], "parallel": False, "priority": "high"},
            ]
        elif "test" in task_type.lower():
            subtasks = [
                {"description": f"Create and run tests: {task.description}", "agent": "tester", "depends_on": [], "parallel": False, "priority": "high"},
            ]
        elif "review" in task_type.lower():
            subtasks = [
                {"description": f"Code review: {task.description}", "agent": "reviewer", "depends_on": [], "parallel": False, "priority": "high"},
            ]
        else:
            subtasks = [
                {"description": f"Analyze and plan: {task.description}", "agent": "orchestrator", "depends_on": [], "parallel": False, "priority": "high"},
            ]
        
        return {
            "reasoning": f"Fallback plan for {task_type}",
            "subtasks": subtasks,
            "recommendations": ["Review and adjust plan as needed"],
        }
    
    async def _create_subtasks(self, task: Task, plan: Dict[str, Any]) -> List[SubTask]:
        """Create subtask objects from plan."""
        subtasks = []
        
        for i, subtask_plan in enumerate(plan.get("subtasks", [])):
            subtask = SubTask(
                task_id=f"{task.task_id}-sub-{i}",
                parent_task_id=task.task_id,
                task_type=SchemaTaskType.CUSTOM,
                description=subtask_plan.get("description", ""),
                assigned_agent=AgentName(subtask_plan.get("agent", "orchestrator")),
                status=TaskStatus.PENDING,
                input_context={
                    "parent_task": task.description,
                    "parent_objective": task.objective,
                    "plan_step": i,
                },
                depends_on=subtask_plan.get("depends_on", []),
            )
            subtasks.append(subtask)
        
        return subtasks
    
    async def resolve_conflict(
        self,
        task_id: str,
        agent_outputs: Dict[AgentName, AgentResult],
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.ORCHESTRATOR_DECIDES,
    ) -> Dict[str, Any]:
        """Resolve conflicts between agent outputs."""
        self.logger.info(f"Resolving conflict for task {task_id}")
        
        # Build conflict resolution prompt
        messages = [
            self._build_system_message(),
            self._build_conflict_resolution_prompt(agent_outputs),
        ]
        
        response = await self._call_llm(
            messages,
            temperature=0.2,
            max_tokens=4096,
        )
        
        try:
            resolution = json.loads(response.content)
            return resolution
        except json.JSONDecodeError:
            # Default resolution
            return {
                "selected_agent": list(agent_outputs.keys())[0].value,
                "reason": "Failed to parse resolution, defaulting to first agent",
            }
    
    def _build_conflict_resolution_prompt(self, agent_outputs: Dict[AgentName, AgentResult]) -> str:
        outputs_str = {}
        for agent, result in agent_outputs.items():
            outputs_str[agent.value] = {
                "summary": result.summary,
                "findings": [f.claim for f in result.findings],
                "confidence": result.confidence,
                "recommendations": result.recommendations,
            }
        
        return f"""Multiple agents have produced conflicting outputs. Analyze and resolve:

Agent Outputs:
{json.dumps(outputs_str, indent=2)}

Return a JSON resolution:
{{
  "selected_agent": "agent_name",
  "reason": "Why this agent's output was chosen",
  "merged_findings": [...],
  "additional_recommendations": [...]
}}"""


def create_orchestrator_agent(tool_manager=None) -> OrchestratorAgent:
    """Factory function to create orchestrator agent."""
    models_config = get_config("models")
    orchestrator_config = models_config.get("orchestrator", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("orchestrator", {})
    
    config = AgentConfig(
        name=AgentName.ORCHESTRATOR,
        description=agent_config.get("description", "Central coordinator"),
        permissions=agent_config.get("permissions", "APPROVAL_REQUIRED"),
        default_model=orchestrator_config.get("model", "nvidia/nemotron-3-ultra"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 3),
        timeout=agent_config.get("timeout", 300),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return OrchestratorAgent(config, tool_manager)