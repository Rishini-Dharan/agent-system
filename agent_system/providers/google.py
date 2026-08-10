"""
Google Gemini Provider Implementation
Uses native Google Generative AI SDK
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import (
    GenerateContentResponse,
    AsyncGenerateContentResponse,
    Tool as GoogleTool,
    FunctionDeclaration,
)

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


class GoogleProvider(BaseProvider):
    """Google Gemini API provider using native SDK."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        default_model: str = "gemini-1.5-pro",
        **kwargs
    ):
        capabilities = [
            ModelCapability.TOOL_CALLING,
            ModelCapability.STREAMING,
            ModelCapability.LARGE_CONTEXT,
            # Note: Google uses native SDK for structured output, not JSON schema
        ]
        super().__init__(
            provider_type=ProviderType.GOOGLE,
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            capabilities=capabilities,
            **kwargs
        )
        
        # Configure the SDK
        genai.configure(api_key=api_key)
        self._model_cache: Dict[str, genai.GenerativeModel] = {}
    
    def _get_model(self, model_name: str) -> genai.GenerativeModel:
        if model_name not in self._model_cache:
            self._model_cache[model_name] = genai.GenerativeModel(model_name)
        return self._model_cache[model_name]
    
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to Google format."""
        formatted = []
        for msg in messages:
            if msg.role == "system":
                # Google handles system instructions separately
                continue
            formatted_msg = {
                "role": "user" if msg.role == "user" else "model",
                "parts": [{"text": msg.content}],
            }
            formatted.append(formatted_msg)
        return formatted
    
    def _format_tools(self, tools: List[ToolDefinition]) -> List[GoogleTool]:
        """Convert tools to Google format."""
        function_declarations = []
        for tool in tools:
            func_decl = FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
            function_declarations.append(func_decl)
        
        if function_declarations:
            return [GoogleTool(function_declarations=function_declarations)]
        return []
    
    def _parse_response(self, response: GenerateContentResponse, model: str) -> CompletionResponse:
        """Parse Google response."""
        if not response.candidates:
            raise ProviderError(
                "No candidates in response",
                self.provider_type.value,
                model,
                "invalid_response",
            )
        
        candidate = response.candidates[0]
        content_parts = candidate.content.parts if candidate.content else []
        
        text_content = ""
        tool_calls = None
        
        for part in content_parts:
            if hasattr(part, "text") and part.text:
                text_content += part.text
            elif hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": f"call_{len(tool_calls)}",
                    "name": fc.name,
                    "arguments": dict(fc.args) if fc.args else {},
                })
        
        finish_reason = "stop"
        if candidate.finish_reason:
            finish_reason_map = {
                1: "stop",
                2: "max_tokens",
                3: "safety",
                4: "recitation",
                5: "other",
            }
            finish_reason = finish_reason_map.get(candidate.finish_reason, "stop")
        
        # Usage metadata
        usage = None
        if response.usage_metadata:
            usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count,
            }
        
        return CompletionResponse(
            content=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            model=model,
            provider=self.provider_type.value,
            raw_response=response,
        )
    
    def _parse_streaming_chunk(self, chunk: GenerateContentResponse) -> StreamingChunk:
        """Parse Google streaming chunk."""
        if not chunk.candidates:
            return StreamingChunk(is_final=False)
        
        candidate = chunk.candidates[0]
        content_parts = candidate.content.parts if candidate.content else []
        
        text_content = ""
        tool_calls = None
        
        for part in content_parts:
            if hasattr(part, "text") and part.text:
                text_content += part.text
            elif hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": f"call_{len(tool_calls)}",
                    "name": fc.name,
                    "arguments": dict(fc.args) if fc.args else {},
                })
        
        finish_reason = None
        if candidate.finish_reason:
            finish_reason_map = {
                1: "stop",
                2: "max_tokens",
                3: "safety",
                4: "recitation",
                5: "other",
            }
            finish_reason = finish_reason_map.get(candidate.finish_reason, "stop")
        
        return StreamingChunk(
            content=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            is_final=finish_reason is not None,
        )
    
    async def _make_request(self, request: CompletionRequest) -> CompletionResponse:
        model = self._get_model(request.model)
        
        # Build generation config
        generation_config = {
            "temperature": request.temperature,
        }
        if request.max_tokens:
            generation_config["max_output_tokens"] = request.max_tokens
        
        # Format messages - separate system instruction
        system_instruction = None
        contents = []
        
        for msg in request.messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [msg.content]})
        
        tools = None
        if request.tools:
            tools = self._format_tools(request.tools)
        
        try:
            response = await model.generate_content_async(
                contents=contents,
                generation_config=generation_config,
                tools=tools,
                system_instruction=system_instruction,
            )
            return self._parse_response(response, request.model)
            
        except Exception as e:
            error_str = str(e).lower()
            if "api key" in error_str or "authentication" in error_str or "permission" in error_str:
                raise AuthenticationError(
                    f"Authentication error: {str(e)}",
                    self.provider_type.value,
                    request.model,
                )
            elif "quota" in error_str or "rate limit" in error_str or "429" in error_str:
                raise RateLimitError(
                    f"Rate limit exceeded: {str(e)}",
                    self.provider_type.value,
                    request.model,
                )
            elif "not found" in error_str or "model" in error_str:
                raise ModelUnavailableError(
                    f"Model not available: {str(e)}",
                    self.provider_type.value,
                    request.model,
                )
            elif "timeout" in error_str or "deadline" in error_str:
                raise ProviderError(
                    f"Timeout: {str(e)}",
                    self.provider_type.value,
                    request.model,
                    "timeout",
                    retryable=True,
                )
            else:
                raise ProviderError(
                    f"API error: {str(e)}",
                    self.provider_type.value,
                    request.model,
                    "api_error",
                    retryable=True,
                )
    
    async def _make_streaming_request(self, request: CompletionRequest) -> AsyncIterator[StreamingChunk]:
        model = self._get_model(request.model)
        
        generation_config = {
            "temperature": request.temperature,
        }
        if request.max_tokens:
            generation_config["max_output_tokens"] = request.max_tokens
        
        system_instruction = None
        contents = []
        
        for msg in request.messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [msg.content]})
        
        tools = None
        if request.tools:
            tools = self._format_tools(request.tools)
        
        try:
            response_stream = await model.generate_content_async(
                contents=contents,
                generation_config=generation_config,
                tools=tools,
                system_instruction=system_instruction,
                stream=True,
            )
            
            async for chunk in response_stream:
                yield self._parse_streaming_chunk(chunk)
                
        except Exception as e:
            error_str = str(e).lower()
            if "api key" in error_str or "authentication" in error_str:
                raise AuthenticationError(
                    f"Authentication error: {str(e)}",
                    self.provider_type.value,
                    request.model,
                )
            elif "quota" in error_str or "rate limit" in error_str:
                raise RateLimitError(
                    f"Rate limit exceeded: {str(e)}",
                    self.provider_type.value,
                    request.model,
                )
            else:
                raise ProviderError(
                    f"Streaming error: {str(e)}",
                    self.provider_type.value,
                    request.model,
                    "api_error",
                    retryable=True,
                )
    
    async def list_models(self) -> List[str]:
        try:
            models = genai.list_models()
            return [m.name.replace("models/", "") for m in models if "generateContent" in m.supported_generation_methods]
        except Exception:
            return []


# Register with factory
ProviderFactory.register(ProviderType.GOOGLE, GoogleProvider)