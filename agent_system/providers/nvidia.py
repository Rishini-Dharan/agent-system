"""
NVIDIA NIM Provider Implementation
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from agent_system.providers.base import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    Message,
    ModelCapability,
    ProviderError,
    ProviderType,
    RateLimitError,
    AuthenticationError,
    ModelUnavailableError,
    StreamingChunk,
    ToolDefinition,
    ProviderFactory,
)


class NVIDIAProvider(BaseProvider):
    """NVIDIA NIM API provider."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        default_model: str = "nvidia/nemotron-3-ultra",
        **kwargs
    ):
        capabilities = [
            ModelCapability.TOOL_CALLING,
            ModelCapability.STRUCTURED_OUTPUT,
            ModelCapability.STREAMING,
            ModelCapability.LARGE_CONTEXT,
        ]
        super().__init__(
            provider_type=ProviderType.NVIDIA,
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            capabilities=capabilities,
            **kwargs
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    **self.extra_headers,
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            formatted_msg = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.name:
                formatted_msg["name"] = msg.name
            if msg.tool_calls:
                formatted_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id
            formatted.append(formatted_msg)
        return formatted
    
    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
    
    def _parse_response(self, response: Dict[str, Any], model: str) -> CompletionResponse:
        choices = response.get("choices", [])
        if not choices:
            raise ProviderError(
                "No choices in response",
                self.provider_type.value,
                model,
                "invalid_response",
            )
        
        choice = choices[0]
        message = choice.get("message", {})
        
        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"]),
                }
                for tc in message["tool_calls"]
            ]
        
        usage = response.get("usage")
        if usage:
            usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        
        return CompletionResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
            model=model,
            provider=self.provider_type.value,
            raw_response=response,
        )
    
    def _parse_streaming_chunk(self, chunk: Dict[str, Any]) -> StreamingChunk:
        choices = chunk.get("choices", [])
        if not choices:
            return StreamingChunk(is_final=False)
        
        choice = choices[0]
        delta = choice.get("delta", {})
        
        content = delta.get("content", "")
        tool_calls = None
        
        if delta.get("tool_calls"):
            tool_calls = [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"]),
                }
                for tc in delta["tool_calls"]
            ]
        
        finish_reason = choice.get("finish_reason")
        
        return StreamingChunk(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            is_final=finish_reason is not None,
        )
    
    async def _make_request(self, request: CompletionRequest) -> CompletionResponse:
        payload = {
            "model": request.model,
            "messages": self._format_messages(request.messages),
            "temperature": request.temperature,
            "stream": False,
        }
        
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        
        if request.tools:
            payload["tools"] = self._format_tools(request.tools)
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice
        
        if request.response_format:
            payload["response_format"] = request.response_format
        
        payload.update(request.extra_params)
        
        try:
            response = await self.client.post("/chat/completions", json=payload)
            
            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid API key",
                    self.provider_type.value,
                    request.model,
                )
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(
                    "Rate limit exceeded",
                    self.provider_type.value,
                    request.model,
                    retry_after=int(retry_after) if retry_after else None,
                )
            elif response.status_code == 404:
                raise ModelUnavailableError(
                    f"Model not found: {request.model}",
                    self.provider_type.value,
                    request.model,
                )
            elif response.status_code >= 400:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                raise ProviderError(
                    f"API error: {error_data.get('error', {}).get('message', response.text)}",
                    self.provider_type.value,
                    request.model,
                    "api_error",
                    status_code=response.status_code,
                    retryable=response.status_code >= 500,
                )
            
            data = response.json()
            return self._parse_response(data, request.model)
            
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Request timeout: {str(e)}",
                self.provider_type.value,
                request.model,
                "timeout",
                retryable=True,
            )
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Connection error: {str(e)}",
                self.provider_type.value,
                request.model,
                "connection_error",
                retryable=True,
            )
    
    async def _make_streaming_request(self, request: CompletionRequest) -> AsyncIterator[StreamingChunk]:
        payload = {
            "model": request.model,
            "messages": self._format_messages(request.messages),
            "temperature": request.temperature,
            "stream": True,
        }
        
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        
        if request.tools:
            payload["tools"] = self._format_tools(request.tools)
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice
        
        payload.update(request.extra_params)
        
        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid API key",
                        self.provider_type.value,
                        request.model,
                    )
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise RateLimitError(
                        "Rate limit exceeded",
                        self.provider_type.value,
                        request.model,
                        retry_after=int(retry_after) if retry_after else None,
                    )
                elif response.status_code >= 400:
                    error_text = await response.aread()
                    raise ProviderError(
                        f"API error: {error_text.decode()}",
                        self.provider_type.value,
                        request.model,
                        "api_error",
                        status_code=response.status_code,
                        retryable=response.status_code >= 500,
                    )
                
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            yield StreamingChunk(is_final=True)
                            break
                        try:
                            chunk = json.loads(data_str)
                            yield self._parse_streaming_chunk(chunk)
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Streaming timeout: {str(e)}",
                self.provider_type.value,
                request.model,
                "timeout",
                retryable=True,
            )
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Connection error: {str(e)}",
                self.provider_type.value,
                request.model,
                "connection_error",
                retryable=True,
            )
    
    async def list_models(self) -> List[str]:
        try:
            response = await self.client.get("/models")
            if response.status_code == 200:
                data = response.json()
                return [model["id"] for model in data.get("data", [])]
            return []
        except Exception:
            return []


# Register with factory
ProviderFactory.register(ProviderType.NVIDIA, NVIDIAProvider)