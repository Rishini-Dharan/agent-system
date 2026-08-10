"""
Agent System - Multi-model autonomous coding agent platform.

A production-grade system for orchestrating specialized AI agents
with cloud-hosted LLMs for research, coding, review, and more.
"""
from agent_system.config import get_config, get_config_value
from agent_system.router import ModelRouter, RoutingContext, RoutingDecision, TaskType, ComplexityLevel
from agent_system.schemas import (
    AgentResult,
    ResearchResult,
    CodeResult,
    ReviewResult,
    SecurityResult,
    TestResult,
    GitHubResult,
    BrowserResult,
    OrchestratorResult,
    Task,
    SubTask,
    WorkflowState,
    ExecutionContext,
    TaskStatus,
    AgentName,
)
from agent_system.runtime import (
    ExecutionManager,
    ContextManager,
    ToolManager,
    BaseAgent,
    AgentRegistry,
    get_agent_registry,
)
from agent_system.agents import create_all_agents
from agent_system.state import get_db_manager, close_db_manager
from agent_system.observability import get_logger, get_metrics, configure_logging
from agent_system.security import get_permission_manager, get_command_guard

__version__ = "0.1.0"

__all__ = [
    # Config
    "get_config",
    "get_config_value",
    
    # Router
    "ModelRouter",
    "RoutingContext",
    "RoutingDecision",
    "TaskType",
    "ComplexityLevel",
    
    # Schemas
    "AgentResult",
    "ResearchResult",
    "CodeResult",
    "ReviewResult",
    "SecurityResult",
    "TestResult",
    "GitHubResult",
    "BrowserResult",
    "OrchestratorResult",
    "Task",
    "SubTask",
    "WorkflowState",
    "ExecutionContext",
    "TaskStatus",
    "AgentName",
    
    # Runtime
    "ExecutionManager",
    "ContextManager",
    "ToolManager",
    "BaseAgent",
    "AgentRegistry",
    "get_agent_registry",
    
    # Agents
    "create_all_agents",
    
    # State
    "get_db_manager",
    "close_db_manager",
    
    # Observability
    "get_logger",
    "get_metrics",
    "configure_logging",
    
    # Security
    "get_permission_manager",
    "get_command_guard",
]