"""
Agents Package
"""
from agent_system.agents.orchestrator import OrchestratorAgent, create_orchestrator_agent
from agent_system.agents.researcher import ResearcherAgent, create_researcher_agent
from agent_system.agents.coder import CoderAgent, create_coder_agent
from agent_system.agents.reviewer import ReviewerAgent, create_reviewer_agent
from agent_system.agents.security import SecurityAgent, create_security_agent
from agent_system.agents.tester import TesterAgent, create_tester_agent
from agent_system.agents.github import GitHubAgent, create_github_agent
from agent_system.agents.browser import BrowserAgent, create_browser_agent

__all__ = [
    "OrchestratorAgent",
    "create_orchestrator_agent",
    "ResearcherAgent",
    "create_researcher_agent",
    "CoderAgent",
    "create_coder_agent",
    "ReviewerAgent",
    "create_reviewer_agent",
    "SecurityAgent",
    "create_security_agent",
    "TesterAgent",
    "create_tester_agent",
    "GitHubAgent",
    "create_github_agent",
    "BrowserAgent",
    "create_browser_agent",
]


def create_all_agents(tool_manager=None) -> dict:
    """Create all agents and return them as a dictionary."""
    return {
        "orchestrator": create_orchestrator_agent(tool_manager),
        "researcher": create_researcher_agent(tool_manager),
        "coder": create_coder_agent(tool_manager),
        "reviewer": create_reviewer_agent(tool_manager),
        "security": create_security_agent(tool_manager),
        "tester": create_tester_agent(tool_manager),
        "github": create_github_agent(tool_manager),
        "browser": create_browser_agent(tool_manager),
    }