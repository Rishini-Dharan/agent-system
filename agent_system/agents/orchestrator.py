"""
Orchestrator Agent
Central coordinator for task decomposition, planning, and agent delegation.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
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
from agent_system.state import get_db_manager


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

    # ============ Subagent Delegation Layer ============
    
    AGENT_MAP = {
        "researcher": "researcher",
        "coder": "coder",
        "github-agent": "github",
        "job-hunter": "researcher",  # Uses researcher for job search
        "browser-agent": "browser",
        "security-agent": "security",
        "reviewer": "reviewer",
    }
    
    async def delegate_to_agent(
        self, 
        agent_name: str, 
        prompt: str, 
        subtask: Optional[SubTask] = None
    ) -> AgentResult:
        """Generic delegation to any specialized agent."""
        mapped_agent = self.AGENT_MAP.get(agent_name.lower())
        if not mapped_agent:
            raise ValueError(f"Unknown agent: {agent_name}. Available: {list(self.AGENT_MAP.keys())}")
        
        self.logger.info(f"Delegating to {mapped_agent}: {prompt[:100]}")
        
        # Create subtask if not provided
        if subtask is None:
            subtask = SubTask(
                task_id=f"delegated-{uuid.uuid4().hex[:8]}",
                parent_task_id="",
                description=prompt,
                assigned_agent=AgentName(mapped_agent),
                status=TaskStatus.RUNNING,
                input_context={"delegated_prompt": prompt},
            )
        
        # Save subtask to database (running state)
        db = await get_db_manager()
        await db.create_subtask(subtask)
        
        try:
            # Route to appropriate agent via model router
            routing_context = RoutingContext(
                task_type=SchemaTaskType.CUSTOM,
                agent_name=mapped_agent,
            )
            
            router = ModelRouter()
            decision = await router.route(routing_context)
            
            # Create completion request
            from agent_system.providers import CompletionRequest, Message
            request = CompletionRequest(
                messages=[
                    Message(role="system", content=self._get_agent_system_prompt(mapped_agent)),
                    Message(role="user", content=prompt),
                ],
                model=decision.model,
                temperature=0.3,
                max_tokens=8192,
            )
            
            # Execute with fallback
            response = await router.execute_with_fallback(routing_context, request)
            
            # Parse response
            result = self._parse_agent_response(mapped_agent, response.content, subtask.task_id)
            
            # Update subtask to completed
            subtask.status = TaskStatus.SUCCESS
            subtask.output = result
            subtask.completed_at = datetime.now()
            if subtask.started_at:
                subtask.duration_ms = int((subtask.completed_at - subtask.started_at).total_seconds() * 1000)
            await db.update_subtask(subtask.task_id, status=TaskStatus.SUCCESS, output=result, completed_at=subtask.completed_at, duration_ms=subtask.duration_ms)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Delegation to {mapped_agent} failed: {e}")
            subtask.status = TaskStatus.FAILED
            subtask.errors.append(str(e))
            subtask.completed_at = datetime.now()
            await db.update_subtask(subtask.task_id, status=TaskStatus.FAILED, errors=subtask.errors, completed_at=subtask.completed_at)
            raise
    
    def _get_agent_system_prompt(self, agent_name: str) -> str:
        """Get system prompt for a specific agent."""
        agents_config = get_config("agents")
        agent_config = agents_config.get(agent_name, {})
        return agent_config.get("system_prompt", "")
    
    def _parse_agent_response(self, agent_name: str, content: str, task_id: str) -> AgentResult:
        """Parse agent response into structured result."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                data = {"summary": content, "findings": [], "status": "partial"}
        
        # Validate and create appropriate result type
        from agent_system.schemas.agent_result import validate_agent_result
        agent_enum = AgentName(agent_name)
        return validate_agent_result({**data, "task_id": task_id}, agent_enum)
    
    async def delegate_to_researcher(self, topic: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """Research tasks with structured prompt."""
        prompt = f"""Research the following topic and provide structured findings:

Topic: {topic}

Requirements:
1. Find accurate, verifiable information with citations
2. Distinguish between FACTS (direct from source) and INFERENCE (your analysis)
3. Compare multiple sources when possible
4. Return structured JSON with findings array

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "findings": [
    {{"claim": "...", "source_url": "...", "source_title": "...", "accessed_date": "YYYY-MM-DD", "type": "fact|inference", "confidence": "high|medium|low"}}
  ],
  "summary": "...",
  "recommendations": [],
  "confidence": 0.95
}}"""
        return await self.delegate_to_agent("researcher", prompt, subtask)
    
    async def delegate_to_coder(self, prompt: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """Coding tasks."""
        full_prompt = f"""Implement the following coding task:

{prompt}

Requirements:
1. Read and understand existing code before modifying
2. Follow project's coding conventions
3. Write tests for new functionality
4. Run existing tests to ensure no regressions
5. Return structured diff summary

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "files_changed": ["path/to/file"],
  "diff_summary": "...",
  "tests_added": 0,
  "tests_passed": 0,
  "tests_failed": 0,
  "lint_errors": 0,
  "type_errors": 0,
  "confidence": 0.9
}}"""
        return await self.delegate_to_agent("coder", full_prompt, subtask)
    
    async def delegate_to_github_agent(self, prompt: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """GitHub operations."""
        full_prompt = f"""Perform the following GitHub operation:

{prompt}

Requirements:
1. Use gh CLI for GitHub operations
2. Use git for local operations
3. NEVER auto-merge PRs
4. NEVER push without approval
5. Follow conventional commits

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "branch": "...",
  "commits": ["..."],
  "pr_url": "...",
  "files_changed": ["..."],
  "confidence": 0.95
}}"""
        return await self.delegate_to_agent("github-agent", full_prompt, subtask)
    
    async def delegate_to_job_hunter(self, prompt: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """Job search (uses researcher)."""
        full_prompt = f"""Search for job opportunities:

{prompt}

Requirements:
1. Search job boards and company career pages
2. Extract structured data (title, company, location, requirements, salary, URL)
3. Filter by relevance
4. Return structured JSON

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "findings": [
    {{"claim": "Job found: Title at Company", "source_url": "...", "source_title": "...", "accessed_date": "YYYY-MM-DD", "type": "fact", "confidence": "high"}}
  ],
  "summary": "...",
  "recommendations": []
}}"""
        return await self.delegate_to_agent("job-hunter", full_prompt, subtask)
    
    async def delegate_to_browser_agent(self, prompt: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """Browser automation."""
        full_prompt = f"""Navigate and extract data from web pages:

{prompt}

Requirements:
1. Use Playwright for browser automation
2. Extract structured data from pages
3. Handle dynamic content and JavaScript
4. Take screenshots when useful
5. Respect rate limits and robots.txt

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "url": "...",
  "extracted_data": {{}},
  "screenshots": ["..."],
  "confidence": 0.9
}}"""
        return await self.delegate_to_agent("browser-agent", full_prompt, subtask)
    
    async def delegate_to_security_agent(self, prompt: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """Security scans."""
        full_prompt = f"""Perform security analysis:

{prompt}

Requirements:
1. Run local security tools (Semgrep, Gitleaks, Trivy) and interpret output
2. Use LLM reasoning to identify issues tools might miss
3. Classify findings by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
4. Provide remediation guidance
5. NEVER silently suppress findings

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "findings": [
    {{"tool": "semgrep|gitleaks|trivy|llm", "rule_id": "...", "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file_path": "...", "line_number": 0, "message": "...", "cwe": "...", "cve": "...", "remediation": "..."}}
  ],
  "summary": "...",
  "scan_id": "...",
  "confidence": 0.9
}}"""
        return await self.delegate_to_agent("security-agent", full_prompt, subtask)
    
    async def delegate_to_reviewer(self, prompt: str, subtask: Optional[SubTask] = None) -> AgentResult:
        """Code reviews."""
        full_prompt = f"""Review the following code:

{prompt}

Requirements:
1. Review code for correctness, style, maintainability
2. Verify tests exist and pass
3. Check security scan results
4. Identify potential regressions
5. Look for: logic errors, edge cases, performance issues, security flaws
6. Provide clear approve/reject with reasoning
7. NEVER modify code - only review

Return format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "decision": "approve|reject|request_changes",
  "reasoning": "...",
  "issues_found": [
    {{"file": "path/to/file", "line": 0, "type": "bug|style|security|performance|test", "severity": "blocker|major|minor|suggestion", "message": "...", "suggestion": "..."}}
  ],
  "tests_reviewed": 0,
  "security_reviewed": true,
  "confidence": 0.95
}}"""
        return await self.delegate_to_agent("reviewer", full_prompt, subtask)
    
    # ============ Updated Existing Methods ============
    
    async def research(self, topic: str, context: Dict[str, Any] = None) -> AgentResult:
        """Research a topic using the researcher agent."""
        return await self.delegate_to_researcher(topic)
    
    async def code_task(self, prompt: str, context: Dict[str, Any] = None) -> AgentResult:
        """Execute a coding task using the coder agent."""
        return await self.delegate_to_coder(prompt)


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


# CLI for direct agent delegation
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        if len(sys.argv) < 3:
            print("Usage: python orchestrator.py delegate <agent> <prompt>")
            print("Agents: researcher, coder, github-agent, job-hunter, browser-agent, security-agent, reviewer")
            sys.exit(1)
        
        if sys.argv[1] == "delegate":
            agent_name = sys.argv[2]
            prompt = " ".join(sys.argv[3:])
            
            orchestrator = create_orchestrator_agent()
            
            method_map = {
                "researcher": orchestrator.delegate_to_researcher,
                "coder": orchestrator.delegate_to_coder,
                "github-agent": orchestrator.delegate_to_github_agent,
                "job-hunter": orchestrator.delegate_to_job_hunter,
                "browser-agent": orchestrator.delegate_to_browser_agent,
                "security-agent": orchestrator.delegate_to_security_agent,
                "reviewer": orchestrator.delegate_to_reviewer,
            }
            
            if agent_name not in method_map:
                print(f"Unknown agent: {agent_name}")
                print("Available: " + ", ".join(method_map.keys()))
                sys.exit(1)
            
            try:
                result = await method_map[agent_name](prompt)
                print(json.dumps(result.model_dump(), indent=2, default=str))
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            print(f"Unknown command: {sys.argv[1]}")
            sys.exit(1)
    
    asyncio.run(main())