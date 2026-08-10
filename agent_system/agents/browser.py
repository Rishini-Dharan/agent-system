"""
Browser Agent
Specialized in web navigation, data extraction, and browser automation.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    BrowserResult,
    Finding,
    Artifact,
    FindingType,
    Severity,
    ConfidenceLevel,
    AgentResultStatus,
    AgentName,
)
from agent_system.runtime import BaseAgent, AgentConfig
from agent_system.observability import get_logger


class BrowserAgent(BaseAgent):
    """Browser agent - web navigation and data extraction."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.browser")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute browser task."""
        self.logger.info(f"Browser agent starting task: {task.description[:100]}")
        
        # Determine task type
        task_type = self._determine_task_type(task, context)
        
        if task_type == "navigate":
            result = await self._navigate(task, context)
        elif task_type == "extract":
            result = await self._extract_data(task, context)
        elif task_type == "interact":
            result = await self._interact(task, context)
        elif task_type == "screenshot":
            result = await self._screenshot(task, context)
        else:
            result = await self._general_browser(task, context)
        
        return result
    
    def _determine_task_type(self, task: Task, context: Dict[str, Any]) -> str:
        """Determine the type of browser task."""
        description = (task.description + " " + task.objective).lower()
        
        if any(kw in description for kw in ["navigate", "go to", "visit", "open"]):
            return "navigate"
        elif any(kw in description for kw in ["extract", "scrape", "get data", "parse"]):
            return "extract"
        elif any(kw in description for kw in ["click", "fill", "submit", "interact", "form"]):
            return "interact"
        elif any(kw in description for kw in ["screenshot", "capture", "snapshot"]):
            return "screenshot"
        else:
            return "general_browser"
    
    async def _navigate(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Navigate to a URL."""
        url = context.get("url", "")
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided",
                errors=["Missing URL in context"],
            )
        
        # This would use Playwright - for now, simulate
        extracted_data = await self._simulate_navigation(url)
        
        return BrowserResult(
            task_id=task.task_id,
            agent=AgentName.BROWSER,
            status=AgentResultStatus.SUCCESS,
            summary=f"Navigated to {url}",
            url=url,
            extracted_data=extracted_data,
        )
    
    async def _extract_data(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Extract data from a page."""
        url = context.get("url", "")
        selectors = context.get("selectors", {})
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided for extraction",
                errors=["Missing URL in context"],
            )
        
        # Simulate extraction
        extracted_data = await self._simulate_extraction(url, selectors)
        
        return BrowserResult(
            task_id=task.task_id,
            agent=AgentName.BROWSER,
            status=AgentResultStatus.SUCCESS,
            summary=f"Extracted data from {url}",
            url=url,
            extracted_data=extracted_data,
        )
    
    async def _interact(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Interact with page elements."""
        url = context.get("url", "")
        actions = context.get("actions", [])
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided for interaction",
                errors=["Missing URL in context"],
            )
        
        # Simulate interaction
        extracted_data = await self._simulate_interaction(url, actions)
        
        return BrowserResult(
            task_id=task.task_id,
            agent=AgentName.BROWSER,
            status=AgentResultStatus.SUCCESS,
            summary=f"Interacted with {url}",
            url=url,
            extracted_data=extracted_data,
        )
    
    async def _screenshot(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Take a screenshot."""
        url = context.get("url", "")
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided for screenshot",
                errors=["Missing URL in context"],
            )
        
        # Simulate screenshot
        screenshot_path = f"screenshot_{task.task_id}.png"
        
        return BrowserResult(
            task_id=task.task_id,
            agent=AgentName.BROWSER,
            status=AgentResultStatus.SUCCESS,
            summary=f"Screenshot captured from {url}",
            url=url,
            screenshots=[screenshot_path],
        )
    
    async def _general_browser(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """General browser task fallback."""
        url = context.get("url", "unknown")
        
        return BrowserResult(
            task_id=task.task_id,
            agent=AgentName.BROWSER,
            status=AgentResultStatus.SUCCESS,
            summary=f"General browser task for {url}",
            url=url,
        )
    
    async def _simulate_navigation(self, url: str) -> Dict[str, Any]:
        """Simulate navigation (replace with actual Playwright)."""
        return {
            "url": url,
            "title": f"Page at {url}",
            "content_preview": "Content would be extracted here using Playwright",
        }
    
    async def _simulate_extraction(self, url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Simulate data extraction."""
        data = {"url": url}
        for key, selector in selectors.items():
            data[key] = f"Extracted content for {selector}"
        return data
    
    async def _simulate_interaction(self, url: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate interaction."""
        results = []
        for action in actions:
            results.append({
                "action": action.get("type", "unknown"),
                "selector": action.get("selector", ""),
                "result": "simulated",
            })
        return {"interactions": results}


def create_browser_agent(tool_manager=None) -> BrowserAgent:
    """Factory function to create browser agent."""
    models_config = get_config("models")
    browser_config = models_config.get("browser", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("browser", {})
    
    config = AgentConfig(
        name=AgentName.BROWSER,
        description=agent_config.get("description", "Web navigation and data extraction"),
        permissions=agent_config.get("permissions", "SAFE_WRITE"),
        default_model=browser_config.get("model", "gemini-1.5-flash"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 2),
        timeout=agent_config.get("timeout", 180),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return BrowserAgent(config, tool_manager)