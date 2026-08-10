"""
Browser Agent
Specialized in web navigation, data extraction, and browser automation.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    """Browser agent - web navigation and data extraction with Playwright."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.browser")
        self._browser = None
        self._context = None
        self._page = None
    
    async def _ensure_browser(self):
        """Ensure browser is launched."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                self._page = await self._context.new_page()
            except ImportError:
                raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
            except Exception as e:
                raise RuntimeError(f"Failed to launch browser: {e}")
    
    async def _cleanup_browser(self):
        """Clean up browser resources."""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if hasattr(self, '_playwright'):
                await self._playwright.stop()
        except Exception as e:
            self.logger.warning(f"Browser cleanup error: {e}")
        finally:
            self._browser = None
            self._context = None
            self._page = None
            self._playwright = None
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute browser task."""
        self.logger.info(f"Browser agent starting task: {task.description[:100]}")
        
        await self._ensure_browser()
        
        try:
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
        finally:
            await self._cleanup_browser()
    
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
        """Navigate to a URL and extract basic info."""
        url = context.get("url", "")
        wait_for = context.get("wait_for", "networkidle")
        timeout = context.get("timeout", 30000)
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided",
                errors=["Missing URL in context"],
            )
        
        try:
            await self._page.goto(url, wait_until=wait_for, timeout=timeout)
            
            # Extract basic page info
            title = await self._page.title()
            content = await self._page.content()
            
            # Get text content (first 5000 chars)
            text_content = await self._page.evaluate("() => document.body.innerText")
            if len(text_content) > 5000:
                text_content = text_content[:5000] + "... [truncated]"
            
            extracted_data = {
                "url": url,
                "title": title,
                "text_content": text_content,
                "content_length": len(content),
            }
            
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.SUCCESS,
                summary=f"Navigated to {url} - {title}",
                url=url,
                extracted_data=extracted_data,
            )
        except Exception as e:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary=f"Navigation failed: {str(e)}",
                url=url,
                errors=[str(e)],
            )
    
    async def _extract_data(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Extract data from a page using selectors."""
        url = context.get("url", "")
        selectors = context.get("selectors", {})
        wait_for = context.get("wait_for", "networkidle")
        timeout = context.get("timeout", 30000)
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided for extraction",
                errors=["Missing URL in context"],
            )
        
        try:
            await self._page.goto(url, wait_until=wait_for, timeout=timeout)
            
            extracted_data = {"url": url}
            
            # Extract using CSS selectors
            for key, selector in selectors.items():
                try:
                    elements = await self._page.query_selector_all(selector)
                    if elements:
                        if len(elements) == 1:
                            extracted_data[key] = await elements[0].inner_text()
                        else:
                            extracted_data[key] = [await el.inner_text() for el in elements]
                    else:
                        extracted_data[key] = None
                except Exception as e:
                    extracted_data[key] = f"Error: {str(e)}"
            
            # Also extract all links if not specified
            if "links" not in selectors:
                try:
                    links = await self._page.evaluate("""
                        () => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                            text: a.innerText.trim(),
                            href: a.href
                        })).slice(0, 50)
                    """)
                    extracted_data["links"] = links
                except Exception:
                    pass
            
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.SUCCESS,
                summary=f"Extracted data from {url}",
                url=url,
                extracted_data=extracted_data,
            )
        except Exception as e:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary=f"Extraction failed: {str(e)}",
                url=url,
                errors=[str(e)],
            )
    
    async def _interact(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Interact with page elements."""
        url = context.get("url", "")
        actions = context.get("actions", [])
        wait_for = context.get("wait_for", "networkidle")
        timeout = context.get("timeout", 30000)
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided for interaction",
                errors=["Missing URL in context"],
            )
        
        if not actions:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No actions provided for interaction",
                errors=["Missing actions in context"],
            )
        
        try:
            await self._page.goto(url, wait_until=wait_for, timeout=timeout)
            
            results = []
            for action in actions:
                action_type = action.get("type", "")
                selector = action.get("selector", "")
                
                try:
                    if action_type == "click":
                        await self._page.click(selector, timeout=5000)
                        results.append({"action": "click", "selector": selector, "result": "success"})
                    elif action_type == "fill":
                        value = action.get("value", "")
                        await self._page.fill(selector, value, timeout=5000)
                        results.append({"action": "fill", "selector": selector, "result": "success"})
                    elif action_type == "select":
                        value = action.get("value", "")
                        await self._page.select_option(selector, value, timeout=5000)
                        results.append({"action": "select", "selector": selector, "result": "success"})
                    elif action_type == "hover":
                        await self._page.hover(selector, timeout=5000)
                        results.append({"action": "hover", "selector": selector, "result": "success"})
                    elif action_type == "wait":
                        await self._page.wait_for_selector(selector, timeout=10000)
                        results.append({"action": "wait", "selector": selector, "result": "success"})
                    elif action_type == "eval":
                        script = action.get("script", "")
                        result = await self._page.evaluate(script)
                        results.append({"action": "eval", "result": result})
                    else:
                        results.append({"action": action_type, "selector": selector, "result": f"unknown action type: {action_type}"})
                except Exception as e:
                    results.append({"action": action_type, "selector": selector, "result": f"error: {str(e)}"})
            
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.SUCCESS,
                summary=f"Completed {len(actions)} interactions on {url}",
                url=url,
                extracted_data={"interactions": results},
            )
        except Exception as e:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary=f"Interaction failed: {str(e)}",
                url=url,
                errors=[str(e)],
            )
    
    async def _screenshot(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """Take a screenshot."""
        url = context.get("url", "")
        full_page = context.get("full_page", True)
        path = context.get("path", f"screenshot_{task.task_id}.png")
        wait_for = context.get("wait_for", "networkidle")
        timeout = context.get("timeout", 30000)
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided for screenshot",
                errors=["Missing URL in context"],
            )
        
        try:
            await self._page.goto(url, wait_until=wait_for, timeout=timeout)
            
            # Ensure directory exists
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            
            await self._page.screenshot(path=path, full_page=full_page)
            
            # Also get base64 for embedding
            screenshot_bytes = await self._page.screenshot(full_page=full_page)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.SUCCESS,
                summary=f"Screenshot captured from {url}",
                url=url,
                screenshots=[path],
                extracted_data={"screenshot_base64": screenshot_b64},
            )
        except Exception as e:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary=f"Screenshot failed: {str(e)}",
                url=url,
                errors=[str(e)],
            )
    
    async def _general_browser(self, task: Task, context: Dict[str, Any]) -> BrowserResult:
        """General browser task - navigate and return page content."""
        url = context.get("url", "")
        
        if not url:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary="No URL provided",
                errors=["Missing URL in context"],
            )
        
        try:
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            
            title = await self._page.title()
            text_content = await self._page.evaluate("() => document.body.innerText")
            if len(text_content) > 10000:
                text_content = text_content[:10000] + "... [truncated]"
            
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.SUCCESS,
                summary=f"Loaded {url} - {title}",
                url=url,
                extracted_data={
                    "url": url,
                    "title": title,
                    "text_content": text_content,
                },
            )
        except Exception as e:
            return BrowserResult(
                task_id=task.task_id,
                agent=AgentName.BROWSER,
                status=AgentResultStatus.FAILED,
                summary=f"General browser task failed: {str(e)}",
                url=url,
                errors=[str(e)],
            )


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