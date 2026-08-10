"""
Provider Abstraction Layer
Base classes and interfaces for cloud LLM providers.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field

from agent_system.config import get_config


class ProviderType(str, Enum):
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"
    ZAI = "zai"
    GOOGLE = "google"


class ModelCapability(str, Enum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    LARGE_CONTEXT = "large_context"
    WEB_SEARCH = "web_search"
    CODE_EXECUTION = "code_execution"


@dataclass
class Message:
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema


@dataclass
class CompletionRequest:
    messages: List[Message]
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[str] = None  # auto, none, required, or specific tool name
    response_format: Optional[Dict[str, Any]] = None  # For structured output
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class CompletionResponse:
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str = "stop"
    usage: Optional[Dict[str, int]] = None
    model: str = ""
    provider: str = ""
    latency_ms: int = 0
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class StreamingChunk:
    content: str = ""
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None
    is_final: bool = False


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        provider: str,
        model: str,
        error_type: str = "unknown",
        status_code: Optional[int] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.error_type = error_type
        self.status_code = status_code
        self.retryable = retryable


class RateLimitError(ProviderError):
    def __init__(self, message: str, provider: str, model: str, retry_after: Optional[int] = None):
        super().__init__(message, provider, model, "rate_limit", retryable=True)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    def __init__(self, message: str, provider: str, model: str):
        super().__init__(message, provider, model, "authentication", retryable=False)


class ModelUnavailableError(ProviderError):
    def __init__(self, message: str, provider: str, model: str):
        super().__init__(message, provider, model, "model_unavailable", retryable=True)


class ContextLengthError(ProviderError):
    def __init__(self, message: str, provider: str, model: str):
        super().__init__(message, provider, model, "context_length_exceeded", retryable=False)


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(
        self,
        provider_type: ProviderType,
        api_key: str,
        base_url: str,
        default_model: str,
        capabilities: List[ModelCapability],
        rate_limit_rpm: int = 60,
        rate_limit_tpm: int = 100000,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.provider_type = provider_type
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.capabilities = capabilities
        self.rate_limit_rpm = rate_limit_rpm
        self.rate_limit_tpm = rate_limit_tpm
        self.extra_headers = extra_headers or {}
        
        # Rate limiting state
        self._request_times: List[float] = []
        self._token_counts: List[tuple[float, int]] = []  # (timestamp, tokens)
        self._lock = asyncio.Lock()

    @abstractmethod
    async def _make_request(self, request: CompletionRequest) -> CompletionResponse:
        """Make the actual API request. Implemented by subclasses."""
        pass

    @abstractmethod
    async def _make_streaming_request(self, request: CompletionRequest) -> AsyncIterator[StreamingChunk]:
        """Make a streaming API request. Implemented by subclasses."""
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models. Implemented by subclasses."""
        pass

    @abstractmethod
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Format messages for provider's API. Implemented by subclasses."""
        pass

    @abstractmethod
    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Format tools for provider's API. Implemented by subclasses."""
        pass

    @abstractmethod
    def _parse_response(self, response: Dict[str, Any], model: str) -> CompletionResponse:
        """Parse provider response. Implemented by subclasses."""
        pass

    @abstractmethod
    def _parse_streaming_chunk(self, chunk: Dict[str, Any]) -> StreamingChunk:
        """Parse streaming chunk. Implemented by subclasses."""
        pass

    def supports_capability(self, capability: ModelCapability) -> bool:
        return capability in self.capabilities

    async def _check_rate_limits(self, estimated_tokens: int = 0) -> None:
        """Check and enforce rate limits."""
        async with self._lock:
            now = time.time()
            
            # Clean old entries (older than 1 minute)
            minute_ago = now - 60
            self._request_times = [t for t in self._request_times if t > minute_ago]
            self._token_counts = [(t, c) for t, c in self._token_counts if t > minute_ago]
            
            # Check RPM
            if len(self._request_times) >= self.rate_limit_rpm:
                wait_time = 60 - (now - self._request_times[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self._check_rate_limits(estimated_tokens)
            
            # Check TPM
            total_tokens = sum(c for _, c in self._token_counts)
            if total_tokens + estimated_tokens > self.rate_limit_tpm:
                # Find when enough tokens will be available
                for i, (t, c) in enumerate(self._token_counts):
                    total_tokens -= c
                    if total_tokens + estimated_tokens <= self.rate_limit_tpm:
                        wait_time = 60 - (now - t)
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)
                        return await self._check_rate_limits(estimated_tokens)
                # If we get here, wait a bit and retry
                await asyncio.sleep(1)
                return await self._check_rate_limits(estimated_tokens)
            
            # Record this request
            self._request_times.append(now)
            if estimated_tokens > 0:
                self._token_counts.append((now, estimated_tokens))

    def _estimate_tokens(self, messages: List[Message], max_tokens: Optional[int] = None) -> int:
        """Rough token estimation for rate limiting."""
        total_chars = sum(len(m.content) for m in messages)
        # Rough estimate: 1 token ≈ 4 characters
        estimated = total_chars // 4
        if max_tokens:
            estimated += max_tokens
        return max(estimated, 100)  # Minimum estimate

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Complete a chat request with rate limiting and error handling."""
        # Use default model if not specified
        if not request.model:
            request.model = self.default_model
        
        # Estimate tokens for rate limiting
        estimated_tokens = self._estimate_tokens(request.messages, request.max_tokens)
        await self._check_rate_limits(estimated_tokens)
        
        # Make request
        start_time = time.time()
        try:
            response = await self._make_request(request)
            response.latency_ms = int((time.time() - start_time) * 1000)
            response.provider = self.provider_type.value
            return response
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                f"Unexpected error: {str(e)}",
                self.provider_type.value,
                request.model,
                "unknown",
                retryable=True,
            )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamingChunk]:
        """Stream a chat request."""
        if not request.model:
            request.model = self.default_model
        
        if not self.supports_capability(ModelCapability.STREAMING):
            # Fallback: complete and yield as single chunk
            response = await self.complete(request)
            yield StreamingChunk(content=response.content, finish_reason=response.finish_reason, is_final=True)
            return
        
        estimated_tokens = self._estimate_tokens(request.messages, request.max_tokens)
        await self._check_rate_limits(estimated_tokens)
        
        start_time = time.time()
        try:
            async for chunk in self._make_streaming_request(request):
                yield chunk
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                f"Streaming error: {str(e)}",
                self.provider_type.value,
                request.model,
                "unknown",
                retryable=True,
            )

    async def health_check(self) -> bool:
        """Check if provider is available."""
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False


class ProviderFactory:
    """Factory for creating provider instances."""
    
    _providers: Dict[ProviderType, Type[BaseProvider]] = {}
    _instances: Dict[str, BaseProvider] = {}
    
    @classmethod
    def register(cls, provider_type: ProviderType, provider_class: Type[BaseProvider]) -> None:
        cls._providers[provider_type] = provider_class
    
    @classmethod
    def create(
        cls,
        provider_type: ProviderType,
        api_key: Optional[str] = None,
        **kwargs
    ) -> BaseProvider:
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        # Get config
        config = get_config()
        provider_config = config.get("providers", {}).get(provider_type.value, {})
        
        # Use provided api_key or get from config/env
        if api_key is None:
            api_key_env = provider_config.get("api_key_env", f"{provider_type.value.upper()}_API_KEY")
            api_key = os.getenv(api_key_env, "")
        
        if not api_key:
            raise ValueError(f"No API key found for {provider_type.value}")
        
        # Create instance
        provider_class = cls._providers[provider_type]
        instance = provider_class(
            provider_type=provider_type,
            api_key=api_key,
            base_url=provider_config.get("base_url", ""),
            default_model=kwargs.get("default_model", ""),
            capabilities=[ModelCapability(c) for c in provider_config.get("capabilities", [])],
            rate_limit_rpm=provider_config.get("rate_limit_rpm", 60),
            rate_limit_tpm=provider_config.get("rate_limit_tpm", 100000),
            extra_headers=provider_config.get("extra_headers"),
        )
        
        return instance
    
    @classmethod
    def get_cached(
        cls,
        provider_type: ProviderType,
        model: str,
        **kwargs
    ) -> BaseProvider:
        """Get or create a cached provider instance."""
        cache_key = f"{provider_type.value}:{model}"
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls.create(provider_type, **kwargs)
        return cls._instances[cache_key]
    
    @classmethod
    def clear_cache(cls) -> None:
        cls._instances.clear()


# Import provider implementations to register them
def _import_providers():
    from agent_system.providers import nvidia, openrouter, zai, google  # noqa: F401

_import_providers()