# Providers Reference

## Overview

Agent System supports multiple cloud LLM providers through a unified abstraction layer. Each provider implements the `BaseProvider` interface.

## Supported Providers

| Provider | Models | Free Tier | Strengths |
|----------|--------|-----------|-----------|
| NVIDIA NIM | Nemotron 3 Ultra, Nemotron 4, etc. | No | Reasoning, structured output |
| OpenRouter | DeepSeek, Llama, Mixtral, etc. | Yes (many models) | Model variety, free tier |
| Z.ai | GLM-4, GLM-4.5 | Yes | Coding, large context |
| Google | Gemini 1.5 Pro/Flash | Yes | Large context, multimodal |

## Provider Interface

All providers implement the `BaseProvider` abstract class:

```python
class BaseProvider(ABC):
    @abstractmethod
    async def complete(request: CompletionRequest) -> CompletionResponse
    
    @abstractmethod
    async def stream(request: CompletionRequest) -> AsyncIterator[StreamingChunk]
    
    @abstractmethod
    async def list_models() -> List[str]
    
    def supports_capability(self, capability: ModelCapability) -> bool
```

### Key Methods

- **`complete()`**: Single completion request
- **`stream()`**: Streaming response iterator
- **`list_models()`**: Available models
- **`supports_capability()`**: Capability checking

### Data Structures

```python
@dataclass
class CompletionRequest:
    messages: List[Message]
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)

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
```

## Provider Implementations

### 1. NVIDIA NIM (`nvidia.py`)

**Endpoint**: `https://integrate.api.nvidia.com/v1`

**Authentication**: Bearer token via `NVIDIA_API_KEY`

**Models**: Nemotron 3 Ultra, Nemotron 4, etc.

**Capabilities**:
- ✅ Tool Calling
- ✅ Structured Output
- ✅ Streaming
- ✅ Large Context (32K+)

**Rate Limits**: 60 RPM, 100K TPM

**Configuration**:
```yaml
providers:
  nvidia:
    base_url: "https://integrate.api.nvidia.com/v1"
    api_key_env: "NVIDIA_API_KEY"
    rate_limit_rpm: 60
    rate_limit_tpm: 100000
    supports_streaming: true
    supports_tools: true
    supports_structured_output: true
```

**Usage**:
```python
from agent_system.providers import ProviderFactory, ProviderType

provider = ProviderFactory.get_cached(
    ProviderType.NVIDIA,
    "nvidia/nemotron-3-ultra"
)

response = await provider.complete(request)
```

---

### 2. OpenRouter (`openrouter.py`)

**Endpoint**: `https://openrouter.ai/api/v1`

**Authentication**: Bearer token via `OPENROUTER_API_KEY`

**Models**: 100+ models including DeepSeek, Llama, Mixtral, etc.

**Free Tier**: Many models available free (DeepSeek, Llama 3, etc.)

**Capabilities**:
- ✅ Tool Calling
- ✅ Structured Output
- ✅ Streaming
- ✅ Large Context

**Rate Limits**: 100 RPM, 200K TPM

**Extra Headers**:
```yaml
extra_headers:
  HTTP-Referer: "https://agent-system.local"
  X-Title: "Agent System"
```

**Configuration**:
```yaml
providers:
  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"
    rate_limit_rpm: 100
    rate_limit_tpm: 200000
    supports_streaming: true
    supports_tools: true
    supports_structured_output: true
    extra_headers:
      HTTP-Referer: "https://agent-system.local"
      X-Title: "Agent System"
```

**Free Models**:
```yaml
free_models:
  - "deepseek/deepseek-chat"
  - "deepseek/deepseek-coder"
  - "meta-llama/llama-3-8b-instruct"
```

---

### 3. Z.ai (`zai.py`)

**Endpoint**: `https://api.z.ai/v1`

**Authentication**: Bearer token via `ZAI_API_KEY`

**Models**: GLM-4, GLM-4.5

**Free Tier**: Yes (GLM models)

**Capabilities**:
- ✅ Tool Calling
- ✅ Structured Output
- ✅ Streaming
- ✅ Large Context (128K+)

**Rate Limits**: 60 RPM, 100K TPM

**Configuration**:
```yaml
providers:
  zai:
    base_url: "https://api.z.ai/v1"
    api_key_env: "ZAI_API_KEY"
    rate_limit_rpm: 60
    rate_limit_tpm: 100000
    supports_streaming: true
    supports_tools: true
    supports_structured_output: true
```

---

### 4. Google Gemini (`google.py`)

**Endpoint**: `https://generativelanguage.googleapis.com/v1beta`

**Authentication**: API key via `GOOGLE_API_KEY` (uses native SDK)

**Models**: Gemini 1.5 Pro, Gemini 1.5 Flash

**Free Tier**: Yes (with limits: 15 RPM, 32K TPM)

**Capabilities**:
- ✅ Tool Calling
- ❌ Structured Output (uses native SDK approach)
- ✅ Streaming
- ✅ Large Context (1M+ tokens)

**Rate Limits**: 60 RPM, 250K TPM (paid), 15 RPM/32K TPM (free)

**Native SDK**: Uses `google-generativeai` Python package

**Configuration**:
```yaml
providers:
  google:
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    api_key_env: "GOOGLE_API_KEY"
    rate_limit_rpm: 60
    rate_limit_tpm: 250000
    supports_streaming: true
    supports_tools: true
    supports_structured_output: false
    use_native_sdk: true
```

---

## Adding New Providers

### 1. Create Provider Class

```python
# agent_system/providers/custom.py
from agent_system.providers.base import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    Message,
    ToolDefinition,
    ProviderType,
    ModelCapability,
    ProviderFactory,
)

class CustomProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str, default_model: str, **kwargs):
        capabilities = [
            ModelCapability.TOOL_CALLING,
            ModelCapability.STRUCTURED_OUTPUT,
            ModelCapability.STREAMING,
        ]
        super().__init__(
            provider_type=ProviderType.CUSTOM,
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            capabilities=capabilities,
            **kwargs
        )
    
    async def _make_request(self, request: CompletionRequest) -> CompletionResponse:
        # Implementation
        pass
    
    async def _make_streaming_request(self, request: CompletionRequest):
        # Implementation
        yield StreamingChunk(...)
    
    async def list_models(self) -> List[str]:
        # Implementation
        pass
    
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        # Convert to provider format
        pass
    
    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        # Convert to provider format
        pass
    
    def _parse_response(self, response: Dict[str, Any], model: str) -> CompletionResponse:
        # Parse provider response
        pass
    
    def _parse_streaming_chunk(self, chunk: Dict[str, Any]) -> StreamingChunk:
        # Parse streaming chunk
        pass

# Register with factory
ProviderFactory.register(ProviderType.CUSTOM, CustomProvider)
```

### 2. Add to ProviderType Enum

```python
# In agent_system/providers/base.py
class ProviderType(str, Enum):
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"
    ZAI = "zai"
    GOOGLE = "google"
    CUSTOM = "custom"  # Add new provider
```

### 3. Add Configuration

```yaml
# config/models.yaml
providers:
  custom:
    base_url: "https://api.custom.com/v1"
    api_key_env: "CUSTOM_API_KEY"
    rate_limit_rpm: 60
    rate_limit_tpm: 100000
    supports_streaming: true
    supports_tools: true
    supports_structured_output: true
```

### 4. Import and Register

```python
# agent_system/providers/__init__.py
from agent_system.providers import custom  # noqa: F401
```

---

## Provider Selection Logic

The `ModelRouter` selects providers based on:

1. **Agent Configuration**: Primary model from `models.yaml`
2. **Task Type**: Routing rules in `routing.yaml`
3. **Capabilities**: Required features (tool calling, structured output)
4. **Complexity**: Low/medium/high complexity preferences
5. **Availability**: Health checks and fallback chains
6. **Cost**: Free tier preference when enabled

### Fallback Chains

Configured in `routing.yaml`:

```yaml
fallback_chains:
  orchestrator:
    - provider: "nvidia"
      model: "nvidia/nemotron-3-ultra"
    - provider: "openrouter"
      model: "deepseek/deepseek-chat"
    - provider: "zai"
      model: "glm-4.5"
    - provider: "google"
      model: "gemini-1.5-pro"
```

### Capability Requirements

```yaml
capability_requirements:
  tool_calling:
    required_providers: ["nvidia", "openrouter", "zai"]
  structured_output:
    required_providers: ["nvidia", "openrouter", "zai"]
  large_context:
    min_context_window: 32768
    preferred_models: ["glm-4.5", "gemini-1.5-pro", "nemotron-3-ultra"]
```

---

## Rate Limiting

Each provider implements token-bucket rate limiting:

- **RPM**: Requests per minute
- **TPM**: Tokens per minute

The `BaseProvider` enforces limits automatically:

```python
async def _check_rate_limits(self, estimated_tokens: int = 0):
    # Waits if limits would be exceeded
    pass
```

### Free Tier Optimization

When `prefer_free_tier: true` in limits config:

1. Router prefers providers/models with free tiers
2. Falls back to paid only when free unavailable
3. Tracks usage per provider

---

## Error Handling

Providers raise specific exceptions:

```python
class ProviderError(Exception):
    provider: str
    model: str
    error_type: str  # "rate_limit", "authentication", "model_unavailable", etc.
    status_code: Optional[int]
    retryable: bool

class RateLimitError(ProviderError):
    retry_after: Optional[int]

class AuthenticationError(ProviderError):
    pass

class ModelUnavailableError(ProviderError):
    pass

class ContextLengthError(ProviderError):
    pass
```

The router automatically handles:
- Retries with exponential backoff
- Fallback to next provider in chain
- Non-retryable errors (auth, context length) propagate up

---

## Monitoring

Provider metrics collected automatically:

```python
metrics.record_model_call(
    agent="coder",
    provider="zai",
    model="glm-4.5",
    input_tokens=1500,
    output_tokens=800,
    latency_ms=1200,
    success=True,
    cost_usd=0.0
)
```

Available in metrics summary:
- Total calls per provider/model
- Success rates
- Average latency
- Token usage
- Cost tracking