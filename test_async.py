import ast

code = '''
import pytest_asyncio
from unittest.mock import Mock

@pytest_asyncio.fixture
async def mock_provider():
    mock = Mock()
    mock.complete.return_value = Mock(content='{"status": "success", "summary": "Done"}')
    return mock

@pytest_asyncio.fixture
async def mock_router_with_provider(mock_provider):
    test_config = {}
    return test_config
'''

ast.parse(code)
print('Minimal async fixture test passed!')