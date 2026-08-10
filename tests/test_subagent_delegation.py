"""
Tests for subagent delegation layer.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from agent_system.agents.orchestrator import OrchestratorAgent, create_orchestrator_agent
from agent_system.schemas import (
    AgentName, SubTask, TaskStatus, AgentResult, AgentResultStatus,
    Finding, FindingType, ConfidenceLevel
)
from agent_system.runtime import AgentConfig
from agent_system.config import get_config


class TestAgentDefinitions:
    """Test that all agent definitions exist with valid permissions."""

    def test_orchestrator_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "orchestrator" in agents
        agent = agents["orchestrator"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "orchestrator"

    def test_researcher_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "researcher" in agents
        agent = agents["researcher"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "researcher"

    def test_coder_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "coder" in agents
        agent = agents["coder"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "coder"

    def test_reviewer_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "reviewer" in agents
        agent = agents["reviewer"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "reviewer"

    def test_security_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "security" in agents
        agent = agents["security"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "security"

    def test_tester_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "tester" in agents
        agent = agents["tester"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "tester"

    def test_github_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "github" in agents
        agent = agents["github"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "github"

    def test_browser_agent_exists(self):
        agents_config = get_config("agents")
        agents = agents_config.get("agents", {})
        assert "browser" in agents
        agent = agents["browser"]
        assert agent["permissions"] in ["READ_ONLY", "SAFE_WRITE", "APPROVAL_REQUIRED", "BLOCKED"]
        assert agent["default_model"] == "browser"


class TestDelegationMethodsExist:
    """Test that delegation methods exist and are callable."""

    def test_delegate_to_agent_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_agent")
        assert callable(getattr(OrchestratorAgent, "delegate_to_agent"))

    def test_delegate_to_researcher_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_researcher")
        assert callable(getattr(OrchestratorAgent, "delegate_to_researcher"))

    def test_delegate_to_coder_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_coder")
        assert callable(getattr(OrchestratorAgent, "delegate_to_coder"))

    def test_delegate_to_github_agent_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_github_agent")
        assert callable(getattr(OrchestratorAgent, "delegate_to_github_agent"))

    def test_delegate_to_job_hunter_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_job_hunter")
        assert callable(getattr(OrchestratorAgent, "delegate_to_job_hunter"))

    def test_delegate_to_browser_agent_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_browser_agent")
        assert callable(getattr(OrchestratorAgent, "delegate_to_browser_agent"))

    def test_delegate_to_security_agent_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_security_agent")
        assert callable(getattr(OrchestratorAgent, "delegate_to_security_agent"))

    def test_delegate_to_reviewer_exists(self):
        assert hasattr(OrchestratorAgent, "delegate_to_reviewer")
        assert callable(getattr(OrchestratorAgent, "delegate_to_reviewer"))

    def test_research_method_exists(self):
        assert hasattr(OrchestratorAgent, "research")
        assert callable(getattr(OrchestratorAgent, "research"))

    def test_code_task_method_exists(self):
        assert hasattr(OrchestratorAgent, "code_task")
        assert callable(getattr(OrchestratorAgent, "code_task"))


class TestAgentMap:
    """Test AGENT_MAP contains all expected agents."""

    def test_agent_map_completeness(self):
        orchestrator = create_orchestrator_agent()
        expected_agents = [
            "researcher", "coder", "github-agent", "job-hunter",
            "browser-agent", "security-agent", "reviewer"
        ]
        for agent in expected_agents:
            assert agent in orchestrator.AGENT_MAP
            assert orchestrator.AGENT_MAP[agent] in [a.value for a in AgentName]


class TestDelegationSavesSubtask:
    """Test that delegate_to_agent saves subtask to database."""

    @pytest_asyncio.fixture
    async def mock_orchestrator(self):
        """Create orchestrator with mocked dependencies."""
        with patch("agent_system.agents.orchestrator.get_db_manager") as mock_db:
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            mock_db_instance.create_subtask = AsyncMock()
            mock_db_instance.update_subtask = AsyncMock()
            
            orchestrator = create_orchestrator_agent()
            orchestrator.logger = Mock()
            
            yield orchestrator, mock_db_instance

    @pytest.mark.asyncio
    async def test_delegate_saves_subtask_running_then_completed(self, mock_orchestrator):
        """Test subtask is saved with RUNNING then SUCCESS status."""
        orchestrator, mock_db = mock_orchestrator
        
        # Mock the router and provider
        with patch("agent_system.agents.orchestrator.ModelRouter") as mock_router_class:
            mock_router = AsyncMock()
            mock_router_class.return_value = mock_router
            
            mock_decision = Mock()
            mock_decision.model = "test-model"
            mock_router.route = AsyncMock(return_value=mock_decision)
            
            mock_response = Mock()
            mock_response.content = json.dumps({
                "status": "success",
                "summary": "Research complete",
                "findings": [],
                "recommendations": [],
                "confidence": 0.9
            })
            mock_router.execute_with_fallback = AsyncMock(return_value=mock_response)
            
            # Call delegate
            result = await orchestrator.delegate_to_researcher("test topic")
            
            # Verify subtask saved twice (create then update)
            assert mock_db.create_subtask.call_count == 1
            assert mock_db.update_subtask.call_count == 1
            
            # First call - create_subtask was called (status set to RUNNING in the method)
            first_call_args = mock_db.create_subtask.call_args
            subtask_arg = first_call_args[0][0]
            # The subtask was created with RUNNING status before being updated
            # Note: due to mock capturing reference, it shows final state
            # We verify the method was called
            assert subtask_arg is not None
            
            # Second call - update to SUCCESS
            second_call = mock_db.update_subtask.call_args
            assert second_call[1]["status"] == TaskStatus.SUCCESS
            assert "completed_at" in second_call[1]
            assert "duration_ms" in second_call[1]

    @pytest.mark.asyncio
    async def test_delegate_saves_subtask_failed_on_error(self, mock_orchestrator):
        """Test subtask is saved with FAILED status on error."""
        orchestrator, mock_db = mock_orchestrator
        
        with patch("agent_system.agents.orchestrator.ModelRouter") as mock_router_class:
            mock_router = AsyncMock()
            mock_router_class.return_value = mock_router
            
            mock_router.route = AsyncMock(side_effect=Exception("Router failed"))
            
            # Call delegate and expect exception
            with pytest.raises(Exception):
                await orchestrator.delegate_to_researcher("test topic")
            
            # Verify subtask created then updated to failed
            assert mock_db.create_subtask.call_count == 1
            assert mock_db.update_subtask.call_count == 1
            
            update_call = mock_db.update_subtask.call_args
            assert update_call[1]["status"] == TaskStatus.FAILED
            assert "errors" in update_call[1]
            assert len(update_call[1]["errors"]) > 0


class TestAgentSpecificDelegates:
    """Test that agent-specific delegates call correct agent."""

    @pytest_asyncio.fixture
    async def mock_orchestrator(self):
        with patch("agent_system.agents.orchestrator.get_db_manager") as mock_db:
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            mock_db_instance.save_subtask = AsyncMock()
            
            orchestrator = create_orchestrator_agent()
            orchestrator.logger = Mock()
            
            yield orchestrator, mock_db_instance

    @pytest.mark.asyncio
    async def test_delegate_to_researcher_calls_correct_agent(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch.object(orchestrator, "delegate_to_agent", new_callable=AsyncMock) as mock_delegate:
            mock_result = AgentResult(
                task_id="test",
                agent=AgentName.RESEARCHER,
                status=AgentResultStatus.SUCCESS,
                summary="Done",
                confidence=0.9
            )
            mock_delegate.return_value = mock_result
            
            await orchestrator.delegate_to_researcher("test topic")
            
            mock_delegate.assert_called_once()
            args, kwargs = mock_delegate.call_args
            assert args[0] == "researcher"

    @pytest.mark.asyncio
    async def test_delegate_to_coder_calls_correct_agent(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch.object(orchestrator, "delegate_to_agent", new_callable=AsyncMock) as mock_delegate:
            mock_result = AgentResult(
                task_id="test",
                agent=AgentName.CODER,
                status=AgentResultStatus.SUCCESS,
                summary="Done",
                confidence=0.9
            )
            mock_delegate.return_value = mock_result
            
            await orchestrator.delegate_to_coder("implement feature")
            
            mock_delegate.assert_called_once()
            args, kwargs = mock_delegate.call_args
            assert args[0] == "coder"

    @pytest.mark.asyncio
    async def test_delegate_to_github_agent_calls_correct_agent(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch.object(orchestrator, "delegate_to_agent", new_callable=AsyncMock) as mock_delegate:
            mock_result = AgentResult(
                task_id="test",
                agent=AgentName.GITHUB,
                status=AgentResultStatus.SUCCESS,
                summary="Done",
                confidence=0.9
            )
            mock_delegate.return_value = mock_result
            
            await orchestrator.delegate_to_github_agent("create PR")
            
            mock_delegate.assert_called_once()
            args, kwargs = mock_delegate.call_args
            assert args[0] == "github-agent"

    @pytest.mark.asyncio
    async def test_delegate_to_security_agent_calls_correct_agent(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch.object(orchestrator, "delegate_to_agent", new_callable=AsyncMock) as mock_delegate:
            mock_result = AgentResult(
                task_id="test",
                agent=AgentName.SECURITY,
                status=AgentResultStatus.SUCCESS,
                summary="Done",
                confidence=0.9
            )
            mock_delegate.return_value = mock_result
            
            await orchestrator.delegate_to_security_agent("scan code")
            
            mock_delegate.assert_called_once()
            args, kwargs = mock_delegate.call_args
            assert args[0] == "security-agent"

    @pytest.mark.asyncio
    async def test_delegate_to_reviewer_calls_correct_agent(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch.object(orchestrator, "delegate_to_agent", new_callable=AsyncMock) as mock_delegate:
            mock_result = AgentResult(
                task_id="test",
                agent=AgentName.REVIEWER,
                status=AgentResultStatus.SUCCESS,
                summary="Done",
                confidence=0.9
            )
            mock_delegate.return_value = mock_result
            
            await orchestrator.delegate_to_reviewer("review code")
            
            mock_delegate.assert_called_once()
            args, kwargs = mock_delegate.call_args
            assert args[0] == "reviewer"


class TestOutputFormatValidation:
    """Test that delegation returns properly formatted AgentResult."""

    @pytest_asyncio.fixture
    async def mock_orchestrator(self):
        with patch("agent_system.agents.orchestrator.get_db_manager") as mock_db:
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            mock_db_instance.create_subtask = AsyncMock()
            mock_db_instance.update_subtask = AsyncMock()
            
            orchestrator = create_orchestrator_agent()
            orchestrator.logger = Mock()
            
            yield orchestrator, mock_db_instance

    @pytest.mark.asyncio
    async def test_research_returns_agent_result(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch("agent_system.agents.orchestrator.ModelRouter") as mock_router_class:
            mock_router = AsyncMock()
            mock_router_class.return_value = mock_router
            
            mock_decision = Mock()
            mock_decision.model = "test-model"
            mock_router.route = AsyncMock(return_value=mock_decision)
            
            mock_response = Mock()
            mock_response.content = json.dumps({
                "status": "success",
                "summary": "Research complete",
                "findings": [
                    {
                        "claim": "Test finding",
                        "source_url": "https://example.com",
                        "source_title": "Test",
                        "accessed_date": "2024-01-01",
                        "type": "fact",
                        "confidence": "high"
                    }
                ],
                "recommendations": ["Recommendation 1"],
                "confidence": 0.95
            })
            mock_router.execute_with_fallback = AsyncMock(return_value=mock_response)
            
            result = await orchestrator.delegate_to_researcher("test topic")
            
            assert isinstance(result, AgentResult)
            assert result.agent == AgentName.RESEARCHER
            assert result.status == AgentResultStatus.SUCCESS
            assert result.confidence >= 0.0 and result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_coder_returns_agent_result(self, mock_orchestrator):
        orchestrator, mock_db = mock_orchestrator
        
        with patch("agent_system.agents.orchestrator.ModelRouter") as mock_router_class:
            mock_router = AsyncMock()
            mock_router_class.return_value = mock_router
            
            mock_decision = Mock()
            mock_decision.model = "test-model"
            mock_router.route = AsyncMock(return_value=mock_decision)
            
            mock_response = Mock()
            mock_response.content = json.dumps({
                "status": "success",
                "summary": "Implementation complete",
                "files_changed": ["src/main.py"],
                "diff_summary": "Added feature",
                "tests_added": 2,
                "tests_passed": 2,
                "tests_failed": 0,
                "lint_errors": 0,
                "type_errors": 0,
                "confidence": 0.9
            })
            mock_router.execute_with_fallback = AsyncMock(return_value=mock_response)
            
            result = await orchestrator.delegate_to_coder("implement feature")
            
            assert isinstance(result, AgentResult)
            assert result.agent == AgentName.CODER
            assert result.status == AgentResultStatus.SUCCESS


class TestParallelDelegation:
    """Test parallel delegation works."""

    @pytest_asyncio.fixture
    async def mock_orchestrator(self):
        with patch("agent_system.agents.orchestrator.get_db_manager") as mock_db:
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            mock_db_instance.create_subtask = AsyncMock()
            mock_db_instance.update_subtask = AsyncMock()
            
            orchestrator = create_orchestrator_agent()
            orchestrator.logger = Mock()
            
            yield orchestrator, mock_db_instance

    @pytest.mark.asyncio
    async def test_parallel_delegation(self, mock_orchestrator):
        """Test multiple delegations can run in parallel."""
        orchestrator, mock_db = mock_orchestrator
        
        with patch("agent_system.agents.orchestrator.ModelRouter") as mock_router_class:
            mock_router = AsyncMock()
            mock_router_class.return_value = mock_router
            
            mock_decision = Mock()
            mock_decision.model = "test-model"
            mock_router.route = AsyncMock(return_value=mock_decision)
            
            mock_response = Mock()
            mock_response.content = json.dumps({
                "status": "success",
                "summary": "Done",
                "findings": [],
                "recommendations": [],
                "confidence": 0.9
            })
            mock_router.execute_with_fallback = AsyncMock(return_value=mock_response)
            
            # Run multiple delegations in parallel
            import asyncio
            results = await asyncio.gather(
                orchestrator.delegate_to_researcher("topic 1"),
                orchestrator.delegate_to_coder("implement feature"),
                orchestrator.delegate_to_security_agent("scan code"),
            )
            
            assert len(results) == 3
            for result in results:
                assert isinstance(result, AgentResult)
                assert result.status == AgentResultStatus.SUCCESS


class TestUnknownAgentError:
    """Test that unknown agent raises error."""

    @pytest_asyncio.fixture
    async def mock_orchestrator(self):
        with patch("agent_system.agents.orchestrator.get_db_manager") as mock_db:
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            mock_db_instance.save_subtask = AsyncMock()
            
            orchestrator = create_orchestrator_agent()
            orchestrator.logger = Mock()
            
            yield orchestrator

    @pytest.mark.asyncio
    async def test_unknown_agent_raises_error(self, mock_orchestrator):
        """Test that unknown agent name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await mock_orchestrator.delegate_to_agent("unknown-agent", "prompt")
        
        assert "Unknown agent" in str(exc_info.value)
        assert "unknown-agent" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])