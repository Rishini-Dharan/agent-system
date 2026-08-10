import ast

code = '''
@pytest_asyncio.fixture
async def mock_router_with_provider(mock_provider):
    """Create a router with mocked provider."""
    test_config = {
        "routing": {
            "task_routes": {
                "research": {
                    "primary_agent": "researcher",
                    "fallback_agents": ["orchestrator"],
                },
            },
            "models": {
                "researcher": {"provider": "nvidia", "model": "model1"},
            },
            "limits": {
                "retry": {"max_retries": 3},
            },
        }
    router = ModelRouter(config=test_config)
    return router
'''

ast.parse(code)
print('Isolated function parses OK!')