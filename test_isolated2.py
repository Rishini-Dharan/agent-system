code = '''
@pytest_asyncio.fixture
async def mock_router_with_provider(mock_provider):
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

import ast
ast.parse(code)
print('OK')