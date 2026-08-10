import ast

# Read the actual file content
with open('tests/test_router.py', 'r') as f:
    source = f.read()

# Extract just the async fixture function
lines = source.split('\n')
fixture_lines = []
in_fixture = False
for line in source.split('\n'):
    if '@pytest_asyncio.fixture' in line:
        in_fixture = True
    if in_fixture:
        print(f'Line: {line}')
    if in_fixture and line.strip() and not line.startswith(' ') and not line.startswith('\t') and '@' not in line and 'def ' not in line and '"""' not in line and line.strip():
        if not line.startswith(' ') and not line.startswith('\t'):
            break

# Just test the specific function
code = """@pytest_asyncio.fixture
async def mock_router_with_provider(mock_provider):
    \"\"\"Create a router with mocked provider.\"\"\"
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
"""

import ast
ast.parse(code)
print('OK')