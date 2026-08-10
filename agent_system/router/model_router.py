"""
Model Router
Routes tasks to appropriate models based on task type, complexity, and availability.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agent_system.config import get_config
from agent_system.providers import (
    BaseProvider,
    ProviderFactory,
    ProviderType,
    ModelCapability,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ModelUnavailableError,
)

logger = logging.getLogger(__name__)


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


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ModelOption:
    provider: ProviderType
    model: str
    priority: int = 0  # Lower = higher priority
    estimated_cost_per_1k_tokens: float = 0.0
    is_free: bool = False


@dataclass
class RoutingDecision:
    agent_name: str
    provider: ProviderType
    model: str
    fallback_options: List[ModelOption] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class RoutingContext:
    task_type: TaskType
    complexity: ComplexityLevel = ComplexityLevel.MEDIUM
    required_capabilities: List[ModelCapability] = field(default_factory=list)
    estimated_tokens: int = 0
    preferred_provider: Optional[ProviderType] = None
    excluded_providers: List[ProviderType] = field(default_factory=list)
    agent_name: Optional[str] = None
    previous_failures: List[str] = field(default_factory=list)


class ModelRouter:
    """Routes tasks to appropriate models with fallback support."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_config()
        self.routing_config = self.config.get("routing", {})
        self.models_config = self.config.get("models", {})
        self.limits_config = self.config.get("limits", {})
        self.fallback_chains = self.routing_config.get("fallback_chains", {})
        self.capability_requirements = self.routing_config.get("capability_requirements", {})
        self.complexity_routing = self.routing_config.get("complexity_routing", {})
        
        # Provider health cache
        self._provider_health: Dict[ProviderType, Tuple[bool, datetime]] = {}
        self._health_check_ttl = 300  # 5 minutes
    
    def route(self, context: RoutingContext) -> RoutingDecision:
        """Determine the best model for a task."""
        
        # If agent is specified, use agent's configured model
        if context.agent_name and context.agent_name in self.models_config:
            agent_config = self.models_config[context.agent_name]
            primary_provider = ProviderType(agent_config["provider"])
            primary_model = agent_config["model"]
            
            # Check if provider is excluded
            if primary_provider in context.excluded_providers:
                # Use fallback
                fallback_options = self._get_fallback_chain(context.agent_name)
                fallback_options = [f for f in fallback_options if f.provider not in context.excluded_providers]
                if fallback_options:
                    best_fallback = fallback_options[0]
                    return RoutingDecision(
                        agent_name=context.agent_name,
                        provider=best_fallback.provider,
                        model=best_fallback.model,
                        fallback_options=fallback_options[1:],
                        reasoning=f"Primary provider {primary_provider.value} excluded, using fallback",
                        confidence=0.8,
                    )
            
            # Check capabilities
            if not self._provider_supports_capabilities(primary_provider, context.required_capabilities):
                fallback_options = self._get_fallback_chain(context.agent_name)
                fallback_options = [f for f in fallback_options if self._provider_supports_capabilities(f.provider, context.required_capabilities)]
                if fallback_options:
                    best_fallback = fallback_options[0]
                    return RoutingDecision(
                        agent_name=context.agent_name,
                        provider=best_fallback.provider,
                        model=best_fallback.model,
                        fallback_options=fallback_options[1:],
                        reasoning=f"Primary provider lacks required capabilities, using fallback",
                        confidence=0.7,
                    )
            
            return RoutingDecision(
                agent_name=context.agent_name,
                provider=primary_provider,
                model=primary_model,
                fallback_options=self._get_fallback_chain(context.agent_name)[1:],
                reasoning=f"Using agent's configured model",
                confidence=1.0,
            )
        
        # Route by task type
        task_routes = self.routing_config.get("task_routes", {})
        task_key = context.task_type.value
        
        if task_key in task_routes:
            route_info = task_routes[task_key]
            primary_agent = route_info.get("primary_agent")
            
            if primary_agent and primary_agent in self.models_config:
                agent_config = self.models_config[primary_agent]
                primary_provider = ProviderType(agent_config["provider"])
                primary_model = agent_config["model"]
                
                # Check exclusions and capabilities
                if primary_provider not in context.excluded_providers:
                    if self._provider_supports_capabilities(primary_provider, context.required_capabilities):
                        return RoutingDecision(
                            agent_name=primary_agent,
                            provider=primary_provider,
                            model=primary_model,
                            fallback_options=self._get_fallback_chain(primary_agent)[1:],
                            reasoning=f"Task type {task_key} routed to {primary_agent}",
                            confidence=0.9,
                        )
                
                # Try fallback agents
                fallback_agents = route_info.get("fallback_agents", [])
                for fallback_agent in fallback_agents:
                    if fallback_agent in self.models_config:
                        fb_config = self.models_config[fallback_agent]
                        fb_provider = ProviderType(fb_config["provider"])
                        fb_model = fb_config["model"]
                        
                        if fb_provider not in context.excluded_providers:
                            if self._provider_supports_capabilities(fb_provider, context.required_capabilities):
                                return RoutingDecision(
                                    agent_name=fallback_agent,
                                    provider=fb_provider,
                                    model=fb_model,
                                    fallback_options=self._get_fallback_chain(fallback_agent)[1:],
                                    reasoning=f"Primary agent unavailable, using fallback {fallback_agent}",
                                    confidence=0.7,
                                )
        
        # Fallback to complexity-based routing
        return self._route_by_complexity(context)
    
    def _route_by_complexity(self, context: RoutingContext) -> RoutingDecision:
        """Route based on complexity level."""
        complexity_config = self.complexity_routing.get(context.complexity.value, {})
        preferred_providers = complexity_config.get("preferred_providers", [])
        
        for provider_name in preferred_providers:
            try:
                provider = ProviderType(provider_name)
                if provider in context.excluded_providers:
                    continue
                
                if not self._provider_supports_capabilities(provider, context.required_capabilities):
                    continue
                
                # Find a model for this provider
                model = self._find_model_for_provider(provider, context)
                if model:
                    # Find which agent this model belongs to
                    agent_name = self._find_agent_for_model(provider, model)
                    
                    return RoutingDecision(
                        agent_name=agent_name or "unknown",
                        provider=provider,
                        model=model,
                        fallback_options=self._get_fallback_chain(agent_name)[1:] if agent_name else [],
                        reasoning=f"Complexity-based routing: {context.complexity.value} -> {provider.value}/{model}",
                        confidence=0.6,
                    )
            except ValueError:
                continue
        
        # Last resort: any available provider
        for provider in ProviderType:
            if provider in context.excluded_providers:
                continue
            if not self._provider_supports_capabilities(provider, context.required_capabilities):
                continue
            
            model = self._find_model_for_provider(provider, context)
            if model:
                agent_name = self._find_agent_for_model(provider, model)
                return RoutingDecision(
                    agent_name=agent_name or "unknown",
                    provider=provider,
                    model=model,
                    fallback_options=[],
                    reasoning=f"Last resort routing: {provider.value}/{model}",
                    confidence=0.3,
                )
        
        raise ValueError("No suitable provider/model found for task")
    
    def _find_model_for_provider(self, provider: ProviderType, context: RoutingContext) -> Optional[str]:
        """Find a suitable model for a provider."""
        # Check models config for this provider
        for agent_name, agent_config in self.models_config.items():
            if agent_config.get("provider") == provider.value:
                return agent_config.get("model")
        
        # Check fallback chains
        for agent_name, fallbacks in self.fallback_chains.items():
            for fb in fallbacks:
                if fb.get("provider") == provider.value:
                    return fb.get("model")
        
        return None
    
    def _find_agent_for_model(self, provider: ProviderType, model: str) -> Optional[str]:
        """Find agent name for a provider/model combination."""
        for agent_name, agent_config in self.models_config.items():
            if agent_config.get("provider") == provider.value and agent_config.get("model") == model:
                return agent_name
        return None
    
    def _get_fallback_chain(self, agent_name: str) -> List[ModelOption]:
        """Get fallback chain for an agent."""
        fallbacks = self.fallback_chains.get(agent_name, [])
        return [
            ModelOption(
                provider=ProviderType(fb["provider"]),
                model=fb["model"],
                priority=i,
            )
            for i, fb in enumerate(fallbacks)
        ]
    
    def _provider_supports_capabilities(self, provider: ProviderType, capabilities: List[ModelCapability]) -> bool:
        """Check if provider supports all required capabilities."""
        if not capabilities:
            return True
        
        # Check capability requirements config
        for cap in capabilities:
            cap_config = self.capability_requirements.get(cap.value, {})
            required_providers = cap_config.get("required_providers", [])
            exclude_providers = cap_config.get("exclude_providers", [])
            
            if required_providers and provider.value not in required_providers:
                return False
            if provider.value in exclude_providers:
                return False
        
        return True
    
    async def get_provider_instance(self, decision: RoutingDecision) -> BaseProvider:
        """Get a provider instance for the routing decision."""
        return ProviderFactory.get_cached(
            decision.provider,
            decision.model,
            default_model=decision.model,
        )
    
    async def execute_with_fallback(
        self,
        context: RoutingContext,
        request: CompletionRequest,
    ) -> CompletionResponse:
        """Execute a request with automatic fallback on failure."""
        
        decision = self.route(context)
        last_error = None
        
        # Try primary
        for attempt in range(self.limits_config.get("retry", {}).get("max_retries", 3) + 1):
            try:
                provider = await self.get_provider_instance(decision)
                response = await provider.complete(request)
                logger.info(f"Request succeeded with {decision.provider.value}/{decision.model}")
                return response
            except (RateLimitError, ModelUnavailableError) as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Trying fallback...")
                # Try fallback
                if decision.fallback_options:
                    decision = RoutingDecision(
                        agent_name=decision.agent_name,
                        provider=decision.fallback_options[0].provider,
                        model=decision.fallback_options[0].model,
                        fallback_options=decision.fallback_options[1:],
                        reasoning=f"Fallback from {last_error.error_type}",
                        confidence=decision.confidence * 0.8,
                    )
                    continue
                else:
                    break
            except AuthenticationError as e:
                logger.error(f"Authentication error: {e}")
                raise
            except ProviderError as e:
                last_error = e
                if not e.retryable:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed (retryable): {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                last_error = ProviderError(
                    f"Unexpected error: {str(e)}",
                    decision.provider.value,
                    decision.model,
                    "unknown",
                    retryable=True,
                )
                logger.warning(f"Attempt {attempt + 1} failed (unexpected): {e}")
                await asyncio.sleep(2 ** attempt)
        
        # All attempts failed
        raise last_error or ProviderError(
            "All routing attempts failed",
            "unknown",
            "unknown",
            "routing_failed",
        )
    
    async def check_provider_health(self, provider: ProviderType) -> bool:
        """Check if a provider is healthy (cached)."""
        now = datetime.now()
        if provider in self._provider_health:
            healthy, checked_at = self._provider_health[provider]
            if (now - checked_at).total_seconds() < self._health_check_ttl:
                return healthy
        
        # Perform health check
        try:
            provider_instance = ProviderFactory.create(provider)
            healthy = await provider_instance.health_check()
            self._provider_health[provider] = (healthy, now)
            return healthy
        except Exception:
            self._provider_health[provider] = (False, now)
            return False
    
    def get_available_providers(self) -> List[ProviderType]:
        """Get list of providers with configured API keys."""
        available = []
        for provider in ProviderType:
            try:
                ProviderFactory.create(provider)
                available.append(provider)
            except ValueError:
                pass
        return available
    
    def get_routing_info(self) -> Dict[str, Any]:
        """Get current routing configuration info."""
        return {
            "configured_models": self.models_config,
            "fallback_chains": self.fallback_chains,
            "available_providers": [p.value for p in self.get_available_providers()],
            "capability_requirements": self.capability_requirements,
        }