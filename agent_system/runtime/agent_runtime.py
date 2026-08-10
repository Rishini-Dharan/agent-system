"""
Agent Runtime - Base Agent Class
Abstract base class for all specialized agents.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from agent_system.config import get_config
from agent_system.providers import (
    BaseProvider,
    ProviderFactory,
    ProviderType,
    ModelCapability,
    CompletionRequest,
    CompletionResponse,
    Message,
    ToolDefinition,
    ProviderError,
)
from agent_system.router import ModelRouter, RoutingContext, TaskType, ComplexityLevel
from agent_system.schemas import (
    AgentResult,
    AgentName,
    Task,
    Finding,
    Artifact,
    ToolCall,
    AgentResultStatus,
    FindingType,
    Severity,
    ConfidenceLevel,
    validate_agent_result,
    repair_agent_result,
)
from agent_system.state import get_db_manager
from agent_system.tools import ToolManager
from agent_system.observability import get_logger, get_metrics


class AgentConfig(BaseModel):
    """Configuration for an agent."""
    name: AgentName
    description: str
    permissions: str
    default_model: str
    fallback_models: List[str] = []
    capabilities: List[str] = []
    max_parallel_subtasks: int = 1
    timeout: int = 300
    system_prompt: str = ""
    required_capabilities: List[ModelCapability] = []


class BaseAgent(ABC):
    """Abstract base class for all agents."""
    
    def __init__(
        self,
        config: AgentConfig,
        tool_manager: Optional[ToolManager] = None,
    ):
        self.config = config
        self.name = config.name
        self.tool_manager = tool_manager or ToolManager()
        self.router = ModelRouter()
        self.logger = get_logger(f"agent.{self.name.value}")
        self.metrics = get_metrics()
        self._provider_cache: Dict[str, BaseProvider] = {}
    
    @abstractmethod
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute the agent's main logic."""
        pass
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return self.config.system_prompt
    
    def _build_messages(
        self,
        task: Task,
        context: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> List[Message]:
        """Build messages for the LLM."""
        messages = [
            Message(role="system", content=self._get_system_prompt()),
        ]
        
        # Add context if provided
        if additional_context:
            messages.append(Message(
                role="user",
                content=f"Context:\n{additional_context}",
            ))
        
        # Add task description
        messages.append(Message(
            role="user",
            content=f"Task: {task.description}\nObjective: {task.objective}",
        ))
        
        # Add input context
        if task.input_context:
            messages.append(Message(
                role="user",
                content=f"Input Context:\n{json.dumps(task.input_context, indent=2)}",
            ))
        
        return messages
    
    async def _get_provider(self, model: str) -> BaseProvider:
        """Get or create a provider instance."""
        cache_key = f"{self.config.default_model}:{model}"
        if cache_key not in self._provider_cache:
            # Determine provider from model config
            models_config = get_config("models")
            provider_name = None
            for agent_name, agent_config in models_config.items():
                if agent_config.get("model") == model:
                    provider_name = agent_config.get("provider")
                    break
            
            if not provider_name:
                # Try to infer from config
                for agent_name in self.config.fallback_models:
                    agent_config = models_config.get(agent_name, {})
                    if agent_config.get("model") == model:
                        provider_name = agent_config.get("provider")
                        break
            
            if not provider_name:
                # Default to first available
                provider_name = "openrouter"
            
            try:
                provider = ProviderFactory.get_cached(
                    ProviderType(provider_name),
                    model,
                    default_model=model,
                )
                self._provider_cache[cache_key] = provider
            except ValueError as e:
                raise ProviderError(
                    f"Failed to create provider for model {model}: {str(e)}",
                    provider_name,
                    model,
                    "provider_creation_failed",
                )
        
        return self._provider_cache[cache_key]
    
    async def _call_llm(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> CompletionResponse:
        """Call the LLM with the given messages."""
        model = model or self.config.default_model
        
        # Get model config for temperature/max_tokens defaults
        models_config = get_config("models")
        model_config = {}
        for agent_name, agent_config in models_config.items():
            if agent_config.get("model") == model:
                model_config = agent_config
                break
        
        temperature = temperature if temperature is not None else model_config.get("temperature", 0.7)
        max_tokens = max_tokens or model_config.get("max_tokens")
        timeout = model_config.get("timeout", 120)
        
        # Build routing context
        routing_context = RoutingContext(
            task_type=TaskType.CUSTOM,
            complexity=ComplexityLevel.MEDIUM,
            required_capabilities=self.config.required_capabilities,
            agent_name=self.name.value,
        )
        
        # Create request
        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            stream=stream,
        )
        
        # Execute with fallback
        start_time = time.time()
        try:
            response = await asyncio.wait_for(
                self.router.execute_with_fallback(routing_context, request),
                timeout=timeout,
            )
            
            # Record metrics
            self.metrics.record_model_call(
                agent=self.name.value,
                provider=response.provider,
                model=response.model,
                input_tokens=response.usage.get("prompt_tokens", 0) if response.usage else 0,
                output_tokens=response.usage.get("completion_tokens", 0) if response.usage else 0,
                latency_ms=response.latency_ms,
                success=True,
            )
            
            return response
            
        except asyncio.TimeoutError:
            self.metrics.record_model_call(
                agent=self.name.value,
                provider="unknown",
                model=model,
                latency_ms=int((time.time() - start_time) * 1000),
                success=False,
                error="timeout",
            )
            raise ProviderError(
                f"LLM call timed out after {timeout}s",
                "unknown",
                model,
                "timeout",
                retryable=True,
            )
        except Exception as e:
            self.metrics.record_model_call(
                agent=self.name.value,
                provider="unknown",
                model=model,
                latency_ms=int((time.time() - start_time) * 1000),
                success=False,
                error=str(e),
            )
            raise
    
    async def _call_llm_structured(
        self,
        messages: List[Message],
        result_type: Type[AgentResult],
        model: Optional[str] = None,
        **kwargs
    ) -> AgentResult:
        """Call LLM and parse structured output."""
        # Add instruction for structured output
        structured_instruction = f"""
You must respond with a valid JSON object that matches this schema:
{result_type.model_json_schema()}

Do not include any extra text, explanations, or markdown formatting.
Return ONLY the JSON object.
"""
        messages_with_instruction = messages + [
            Message(role="user", content=structured_instruction)
        ]
        
        # Try to use structured output if provider supports it
        provider = await self._get_provider(model or self.config.default_model)
        
        if provider.supports_capability(ModelCapability.STRUCTURED_OUTPUT):
            response_format = {"type": "json_object"}
            response = await self._call_llm(
                messages_with_instruction,
                model=model,
                response_format=response_format,
                **kwargs
            )
        else:
            response = await self._call_llm(
                messages_with_instruction,
                model=model,
                **kwargs
            )
        
        # Parse and validate response
        try:
            result_data = json.loads(response.content)
            result_data["task_id"] = result_data.get("task_id", str(uuid.uuid4()))
            result = validate_agent_result(result_data, self.name)
            return result
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON response: {e}. Attempting repair...")
            # Try to extract JSON from response
            repaired = self._attempt_json_repair(response.content)
            if repaired:
                try:
                    result_data = json.loads(repaired)
                    result_data["task_id"] = result_data.get("task_id", str(uuid.uuid4()))
                    return validate_agent_result(result_data, self.name)
                except json.JSONDecodeError:
                    pass
            
            # Try repair function
            try:
                repaired_data = repair_agent_result(
                    {"content": response.content} if isinstance(response.content, str) else {},
                    self.name
                )
                return validate_agent_result(repaired_data, self.name)
            except Exception:
                pass
            
            # Return error result
            return AgentResult(
                task_id=str(uuid.uuid4()),
                agent=self.name,
                status=AgentResultStatus.FAILED,
                summary=f"Failed to parse LLM response: {str(e)}",
                findings=[Finding(
                    type=FindingType.ISSUE,
                    claim="JSON parsing failed",
                    description=str(e),
                    severity=Severity.HIGH,
                    confidence=ConfidenceLevel.HIGH,
                )],
                confidence=0.0,
                errors=[str(e)],
            )
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return AgentResult(
                task_id=str(uuid.uuid4()),
                agent=self.name,
                status=AgentResultStatus.FAILED,
                summary=f"Validation failed: {str(e)}",
                findings=[Finding(
                    type=FindingType.ISSUE,
                    claim="Validation failed",
                    description=str(e),
                    severity=Severity.HIGH,
                    confidence=ConfidenceLevel.HIGH,
                )],
                confidence=0.0,
                errors=[str(e)],
            )
    
    def _attempt_json_repair(self, text: str) -> Optional[str]:
        """Attempt to extract valid JSON from text."""
        # Try to find JSON object in text
        import re
        
        # Look for JSON object
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        # Try to fix common issues
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        
        return None
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool through the tool manager."""
        return await self.tool_manager.execute(tool_name, arguments)
    
    async def _save_result(self, task_id: str, result: AgentResult) -> None:
        """Save agent result to database."""
        try:
            db = await get_db_manager()
            await db.save_agent_result(
                task_id=task_id,
                agent=result.agent,
                status=result.status.value,
                summary=result.summary,
                findings=[f.model_dump() for f in result.findings],
                artifacts=[a.model_dump() for a in result.artifacts],
                recommendations=result.recommendations,
                confidence=result.confidence,
                needs_followup=result.needs_followup,
                followup_reason=result.followup_reason,
                duration_ms=result.duration_ms,
                token_usage=result.token_usage,
                model_used=result.model_used,
                provider_used=result.provider_used,
                tool_calls=[tc.model_dump() for tc in result.tool_calls],
                errors=result.errors,
                metadata=result.metadata,
            )
        except Exception as e:
            self.logger.error(f"Failed to save result: {e}")
    
    async def run(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Main entry point to run the agent."""
        start_time = time.time()
        self.logger.info(f"Starting task {task.task_id}: {task.description[:100]}")
        
        try:
            result = await self.execute(task, context)
            result.duration_ms = int((time.time() - start_time) * 1000)
            
            # Save to database
            await self._save_result(task.task_id, result)
            
            self.logger.info(f"Completed task {task.task_id} with status {result.status.value}")
            return result
            
        except Exception as e:
            self.logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status=AgentResultStatus.FAILED,
                summary=f"Agent execution failed: {str(e)}",
                findings=[Finding(
                    type=FindingType.ISSUE,
                    claim="Agent execution failed",
                    description=str(e),
                    severity=Severity.CRITICAL,
                    confidence=ConfidenceLevel.HIGH,
                )],
                confidence=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)],
            )


class AgentRegistry:
    """Registry for managing agent instances."""
    
    def __init__(self):
        self._agents: Dict[AgentName, BaseAgent] = {}
        self._configs: Dict[AgentName, AgentConfig] = {}
        self._tool_manager: Optional[ToolManager] = None
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[agent.name] = agent
        self._configs[agent.name] = agent.config
    
    def get(self, name: AgentName) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(name)
    
    def get_config(self, name: AgentName) -> Optional[AgentConfig]:
        """Get agent configuration."""
        return self._configs.get(name)
    
    def list_agents(self) -> List[AgentName]:
        """List all registered agents."""
        return list(self._agents.keys())
    
    def set_tool_manager(self, tool_manager: ToolManager) -> None:
        """Set the tool manager for all agents."""
        self._tool_manager = tool_manager
        for agent in self._agents.values():
            agent.tool_manager = tool_manager
    
    async def initialize_all(self) -> None:
        """Initialize all agents."""
        for agent in self._agents.values():
            if hasattr(agent, 'initialize'):
                await agent.initialize()
    
    async def shutdown_all(self) -> None:
        """Shutdown all agents."""
        for agent in self._agents.values():
            if hasattr(agent, 'shutdown'):
                await agent.shutdown()


# Global registry instance
_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry