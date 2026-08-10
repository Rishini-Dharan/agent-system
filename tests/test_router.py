"""
Unit tests for model router.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock

from agent_system.router import ModelRouter, RoutingContext, TaskType, ComplexityLevel
from agent_system.schemas import AgentName, TaskType as SchemaTaskType
from agent_system.providers import ProviderType, ModelCapability


MOCK_ROUTER_CONFIG = """{
    "routing": {
        "task_routes": {
            "research": {
                "primary_agent": "researcher",
                "fallback_agents": ["orchestrator"]
            }
        },
        "models": {
            "researcher": {"provider": "nvidia", "model": "model1"}
        },
        "limits": {
            "retry": {"max_retries": 3}
        }
    },
    "complexity_routing": {
        "medium": {
            "preferred_providers": ["nvidia"]
        }
    },
    "models": {
        "researcher": {"provider": "nvidia", "model": "model1"}
    }
}"""

ROUTER_CONFIG = """{
    "routing": {
        "task_routes": {
            "research": {
                "primary_agent": "researcher",
                "fallback_agents": ["orchestrator"]
            },
            "code_implement": {
                "primary_agent": "coder",
                "fallback_agents": ["reviewer"]
            }
        },
        "fallback_chains": {
            "orchestrator": [
                {"provider": "nvidia", "model": "model1"},
                {"provider": "openrouter", "model": "model2"}
            ]
        },
        "capability_requirements": {
            "tool_calling": {
                "required_providers": ["nvidia", "openrouter"]
            },
            "structured_output": {
                "exclude_providers": ["google"]
            }
        },
        "complexity_routing": {
            "high": {
                "preferred_providers": ["nvidia"]
            }
        }
    },
    "models": {
        "orchestrator": {"provider": "nvidia", "model": "model1"},
        "researcher": {"provider": "openrouter", "model": "model2"},
        "coder": {"provider": "zai", "model": "model3"}
    },
    "limits": {
        "retry": {"max_retries": 3}
    }
}"""


@pytest_asyncio.fixture
async def mock_provider():
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value=Mock(content='status: success, summary: Done', provider='nvidia', model='model1', latency_ms=100))
    return mock


@pytest_asyncio.fixture
async def mock_router_with_provider(mock_provider):
    test_config = json.loads(MOCK_ROUTER_CONFIG)
    router = ModelRouter(config=test_config)
    return router


class TestModelRouter:

    @pytest.fixture
    def router(self):
        test_config = json.loads(ROUTER_CONFIG)
        router = ModelRouter(config=test_config)
        yield router

    def test_route_by_task_type(self, router):
        context = RoutingContext(task_type=SchemaTaskType.RESEARCH)
        decision = router.route(context)
        assert decision.agent_name == "researcher"
        assert decision.provider == ProviderType.OPENROUTER

    def test_route_by_agent_name(self, router):
        context = RoutingContext(task_type=SchemaTaskType.CUSTOM, agent_name="orchestrator")
        decision = router.route(context)
        assert decision.agent_name == "orchestrator"
        assert decision.provider == ProviderType.NVIDIA

    def test_excluded_providers(self, router):
        context = RoutingContext(task_type=SchemaTaskType.RESEARCH, excluded_providers=[ProviderType.OPENROUTER])
        decision = router.route(context)
        assert decision.provider != ProviderType.OPENROUTER

    def test_required_capabilities(self, router):
        context = RoutingContext(task_type=SchemaTaskType.CUSTOM, required_capabilities=[ModelCapability.TOOL_CALLING])
        decision = router.route(context)
        assert decision.provider in [ProviderType.NVIDIA, ProviderType.OPENROUTER]

    def test_fallback_chain(self, router):
        fallbacks = router._get_fallback_chain("orchestrator")
        assert len(fallbacks) == 2
        assert fallbacks[0].provider == ProviderType.NVIDIA
        assert fallbacks[1].provider == ProviderType.OPENROUTER

    def test_provider_supports_capabilities(self, router):
        assert router._provider_supports_capabilities(ProviderType.NVIDIA, [ModelCapability.TOOL_CALLING])
        assert not router._provider_supports_capabilities(ProviderType.GOOGLE, [ModelCapability.STRUCTURED_OUTPUT])

    def test_get_available_providers(self, router):
        with patch("agent_system.providers.ProviderFactory.create") as mock_create:
            mock_create.side_effect = [Mock(), Mock(), ValueError("No key"), ValueError("No key")]
            available = router.get_available_providers()
            assert ProviderType.NVIDIA in available
            assert ProviderType.OPENROUTER in available

    @pytest.mark.asyncio
    async def test_execute_with_fallback_success(self, mock_router_with_provider, mock_provider):
        with patch.object(mock_router_with_provider, "get_provider_instance", return_value=mock_provider):
            context = RoutingContext(task_type=SchemaTaskType.RESEARCH)
            from agent_system.providers import CompletionRequest, Message
            request = CompletionRequest(messages=[Message(role="user", content="Test")], model="model1")
            response = await mock_router_with_provider.execute_with_fallback(context, request)
            assert response is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])