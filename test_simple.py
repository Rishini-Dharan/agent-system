import ast

code = """
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
"""

ast.parse(code)
print('Simple dict OK')