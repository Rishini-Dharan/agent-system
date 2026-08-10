"""
Test configuration and fixtures.
"""
import pytest
import asyncio
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def sample_task():
    """Provide a sample task for testing."""
    from agent_system.schemas import Task, TaskStatus, TaskType, AgentName
    from datetime import datetime
    
    return Task(
        task_id="test-task-001",
        task_type=TaskType.CUSTOM,
        description="Test task",
        objective="Test objective",
        status=TaskStatus.PENDING,
        assigned_agent=AgentName.ORCHESTRATOR,
    )


@pytest.fixture
def mock_config():
    """Provide mock configuration."""
    return {
        "models": {
            "orchestrator": {
                "provider": "nvidia",
                "model": "nvidia/nemotron-3-ultra",
            },
            "researcher": {
                "provider": "openrouter",
                "model": "deepseek/deepseek-chat",
            },
        },
        "agents": {
            "orchestrator": {
                "name": "orchestrator",
                "description": "Test orchestrator",
                "permissions": "APPROVAL_REQUIRED",
                "default_model": "orchestrator",
                "capabilities": [],
            },
        },
    }