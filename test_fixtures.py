import ast

code = (
    "@pytest_asyncio.fixture\n"
    "async def mock_provider():\n"
    "    mock = Mock()\n"
    "    mock.complete.return_value = Mock(content='status: success, summary: Done')\n"
    "    return mock\n"
    "\n"
    "@pytest_asyncio.fixture\n"
    "async def mock_router_with_provider(mock_provider):\n"
    "    \"\"\"Create a router with mocked provider.\"\"\"\n"
    "    test_config = {\n"
    "        \"routing\": {\n"
    "            \"task_routes\": {\n"
    "                \"research\": {\n"
    "                    \"primary_agent\": \"researcher\",\n"
    "                    \"fallback_agents\": [\"orchestrator\"],\n"
    "                },\n"
            "},\n"
    "            \"models\": {\n"
    "                \"researcher\": {\"provider\": \"nvidia\", \"model\": \"model1\"},\n"
    "            },\n"
    "            \"limits\": {\n"
    "                \"retry\": {\"max_retries\": 3},\n"
    "            },\n"
    "        }\n"
    "    router = ModelRouter(config=test_config)\n"
    "    return router\n"
)

ast.parse(code)
print('Fixtures parse OK!')