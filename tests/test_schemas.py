"""
Unit tests for schemas.
"""
import pytest
from datetime import datetime

from agent_system.schemas import (
    Task,
    TaskStatus,
    TaskType,
    TaskPriority,
    AgentName,
    AgentResult,
    ResearchResult,
    CodeResult,
    ReviewResult,
    Finding,
    Artifact,
    FindingType,
    Severity,
    ConfidenceLevel,
    AgentResultStatus,
    validate_agent_result,
    repair_agent_result,
)


class TestTaskSchema:
    """Tests for Task schema."""
    
    def test_create_task(self):
        task = Task(
            task_id="test-001",
            task_type=TaskType.CODE_IMPLEMENT,
            description="Implement feature X",
            objective="Create a new API endpoint",
            priority=TaskPriority.HIGH,
        )
        
        assert task.task_id == "test-001"
        assert task.task_type == TaskType.CODE_IMPLEMENT
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.HIGH
    
    def test_task_with_agent(self):
        task = Task(
            task_id="test-002",
            description="Test",
            objective="Test",
            assigned_agent=AgentName.CODER,
        )
        
        assert task.assigned_agent == AgentName.CODER


class TestFindingSchema:
    """Tests for Finding schema."""
    
    def test_create_finding(self):
        finding = Finding(
            type=FindingType.FACT,
            claim="Python 3.11 was released in October 2022",
            severity=Severity.INFO,
            confidence=ConfidenceLevel.HIGH,
            source_url="https://python.org",
        )
        
        assert finding.type == FindingType.FACT
        assert finding.confidence == ConfidenceLevel.HIGH
        assert finding.severity == Severity.INFO


class TestAgentResultSchemas:
    """Tests for agent result schemas."""
    
    def test_research_result(self):
        result = ResearchResult(
            task_id="test-001",
            agent=AgentName.RESEARCHER,
            status=AgentResultStatus.SUCCESS,
            summary="Found relevant information",
            findings=[
                Finding(
                    type=FindingType.FACT,
                    claim="Test fact",
                    confidence=ConfidenceLevel.HIGH,
                )
            ],
            sources_consulted=5,
            facts_found=3,
            inferences_made=2,
        )
        
        assert result.agent == AgentName.RESEARCHER
        assert result.sources_consulted == 5
        assert len(result.findings) == 1
    
    def test_code_result(self):
        result = CodeResult(
            task_id="test-001",
            agent=AgentName.CODER,
            status=AgentResultStatus.SUCCESS,
            summary="Implemented feature",
            files_changed=["src/main.py", "tests/test_main.py"],
            diff_summary="Added new function",
            tests_added=3,
            tests_passed=3,
        )
        
        assert result.files_changed == ["src/main.py", "tests/test_main.py"]
        assert result.tests_added == 3
    
    def test_review_result(self):
        result = ReviewResult(
            task_id="test-001",
            agent=AgentName.REVIEWER,
            status=AgentResultStatus.SUCCESS,
            summary="Code looks good",
            decision="approve",
            reasoning="All checks passed",
        )
        
        assert result.decision == "approve"
        assert result.security_reviewed is True
    
    def test_confidence_validation(self):
        # Test valid confidence
        result = AgentResult(
            task_id="test-001",
            agent=AgentName.ORCHESTRATOR,
            status=AgentResultStatus.SUCCESS,
            summary="Test",
            confidence=0.95,
        )
        assert result.confidence == 0.95
        
        # Test boundary values
        result = AgentResult(
            task_id="test-001",
            agent=AgentName.ORCHESTRATOR,
            status=AgentResultStatus.SUCCESS,
            summary="Test",
            confidence=0.0,
        )
        assert result.confidence == 0.0
        
        result = AgentResult(
            task_id="test-001",
            agent=AgentName.ORCHESTRATOR,
            status=AgentResultStatus.SUCCESS,
            summary="Test",
            confidence=1.0,
        )
        assert result.confidence == 1.0


class TestValidation:
    """Tests for validation functions."""
    
    def test_validate_agent_result(self):
        data = {
            "task_id": "test-001",
            "agent": "researcher",
            "status": "success",
            "summary": "Test research",
            "confidence": 0.9,
        }
        
        result = validate_agent_result(data, AgentName.RESEARCHER)
        
        assert isinstance(result, ResearchResult)
        assert result.agent == AgentName.RESEARCHER
    
    def test_repair_agent_result(self):
        # Incomplete data
        data = {
            "content": "Some response",
        }
        
        repaired = repair_agent_result(data, AgentName.CODER)
        
        assert "task_id" in repaired
        assert "status" in repaired
        assert "summary" in repaired
        assert "confidence" in repaired
        assert 0 <= repaired["confidence"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])