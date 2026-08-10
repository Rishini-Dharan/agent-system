"""
Researcher Agent
Specialized in technical research, documentation analysis, and information gathering.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from agent_system.config import get_config
from agent_system.schemas import (
    Task,
    AgentResult,
    ResearchResult,
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
from agent_system.providers import Message


class ResearcherAgent(BaseAgent):
    """Researcher agent - technical research and information gathering."""
    
    def __init__(self, config: AgentConfig, tool_manager=None):
        super().__init__(config, tool_manager)
        self.logger = get_logger("agent.researcher")
    
    async def execute(self, task: Task, context: Dict[str, Any]) -> AgentResult:
        """Execute research task."""
        self.logger.info(f"Researcher starting task: {task.description[:100]}")
        
        # Determine research approach
        research_type = self._determine_research_type(task, context)
        
        if research_type == "web_search":
            result = await self._web_research(task, context)
        elif research_type == "documentation":
            result = await self._documentation_research(task, context)
        elif research_type == "error_investigation":
            result = await self._error_investigation(task, context)
        elif research_type == "comparison":
            result = await self._comparison_research(task, context)
        else:
            result = await self._general_research(task, context)
        
        return result
    
    def _determine_research_type(self, task: Task, context: Dict[str, Any]) -> str:
        """Determine the type of research needed."""
        description = (task.description + " " + task.objective).lower()
        
        if any(kw in description for kw in ["documentation", "docs", "api reference", "api docs"]):
            return "documentation"
        elif any(kw in description for kw in ["error", "bug", "issue", "exception", "failed", "crash"]):
            return "error_investigation"
        elif any(kw in description for kw in ["compare", "comparison", "vs", "versus", "alternatives", "options"]):
            return "comparison"
        elif any(kw in description for kw in ["search", "find", "look up", "investigate"]):
            return "web_search"
        else:
            return "general_research"
    
    async def _web_research(self, task: Task, context: Dict[str, Any]) -> ResearchResult:
        """Perform web research using browser tool."""
        query = context.get("query", task.description)
        
        # Use browser tool to search
        search_results = await self._search_web(query)
        
        # Build context from search results
        research_context = self._build_research_context(search_results, query)
        
        messages = self._build_messages(task, context)
        
        # Add research-specific instructions with search results
        research_prompt = f"""Perform thorough web research on the given topic using the search results provided.

Query: {query}

Search Results:
{research_context}

Your research should:
1. Analyze the search results for authoritative sources (official docs, reputable sites, academic papers)
2. Extract key facts and findings
3. Distinguish between facts and opinions
4. Cite all sources with URLs
5. Assess confidence in each finding

Return structured JSON with findings array in this format:
{{
  "status": "success|partial|failed",
  "task": "description",
  "findings": [
    {{"claim": "...", "source_url": "...", "source_title": "...", "accessed_date": "YYYY-MM-DD", "type": "fact|inference", "confidence": "high|medium|low"}}
  ],
  "summary": "...",
  "recommendations": [],
  "confidence": 0.95
}}"""
        
        messages.append(Message(role="user", content=research_prompt))
        
        result = await self._call_llm_structured(
            messages,
            ResearchResult,
        )
        
        if isinstance(result, ResearchResult):
            return result
        return ResearchResult(**result.model_dump())
    
    async def _documentation_research(self, task: Task, context: Dict[str, Any]) -> ResearchResult:
        """Research documentation for a library/API."""
        query = context.get("query", task.description)
        
        # Search for documentation
        search_results = await self._search_web(f"{query} documentation")
        research_context = self._build_research_context(search_results, query)
        
        messages = self._build_messages(task, context)
        
        doc_prompt = f"""Research the documentation for the specified library/API using the search results.

Query: {query}

Search Results:
{research_context}

Focus on:
1. Official documentation sources
2. Key APIs, classes, functions
3. Usage examples
4. Common patterns and best practices
5. Version-specific information

Return structured JSON with findings array."""
        
        messages.append(Message(role="user", content=doc_prompt))
        
        result = await self._call_llm_structured(messages, ResearchResult)
        return result if isinstance(result, ResearchResult) else ResearchResult(**result.model_dump())
    
    async def _error_investigation(self, task: Task, context: Dict[str, Any]) -> ResearchResult:
        """Investigate an error or bug."""
        query = context.get("query", task.description)
        
        # Search for error
        search_results = await self._search_web(f"{query} error fix solution")
        research_context = self._build_research_context(search_results, query)
        
        messages = self._build_messages(task, context)
        
        error_prompt = f"""Investigate the reported error/bug using the search results.

Query: {query}

Search Results:
{research_context}

Focus on:
1. Search for the exact error message
2. Find similar issues on StackOverflow, GitHub Issues, forums
3. Identify root causes
4. Find workarounds or fixes
5. Check version compatibility issues

Return structured JSON with findings array."""
        
        messages.append(Message(role="user", content=error_prompt))
        
        result = await self._call_llm_structured(messages, ResearchResult)
        return result if isinstance(result, ResearchResult) else ResearchResult(**result.model_dump())
    
    async def _comparison_research(self, task: Task, context: Dict[str, Any]) -> ResearchResult:
        """Compare technologies/approaches."""
        query = context.get("query", task.description)
        
        # Search for comparison
        search_results = await self._search_web(f"{query} comparison vs alternatives")
        research_context = self._build_research_context(search_results, query)
        
        messages = self._build_messages(task, context)
        
        compare_prompt = f"""Compare the specified technologies/approaches using the search results.

Query: {query}

Search Results:
{research_context}

Provide:
1. Feature comparison matrix
2. Pros and cons of each
3. Performance characteristics
4. Community support and maturity
5. Migration considerations
6. Recommendation based on use case

Return structured JSON with findings array."""
        
        messages.append(Message(role="user", content=compare_prompt))
        
        result = await self._call_llm_structured(messages, ResearchResult)
        return result if isinstance(result, ResearchResult) else ResearchResult(**result.model_dump())
    
    async def _general_research(self, task: Task, context: Dict[str, Any]) -> ResearchResult:
        """General research fallback."""
        query = context.get("query", task.description)
        
        # Search for general info
        search_results = await self._search_web(query)
        research_context = self._build_research_context(search_results, query)
        
        messages = self._build_messages(task, context)
        
        general_prompt = f"""Research the given topic thoroughly using the search results.

Query: {query}

Search Results:
{research_context}

Provide:
1. Key findings with sources
2. Relevant technical details
3. Current best practices
4. Any warnings or caveats
5. Recommendations

Return structured JSON with findings array."""
        
        messages.append(Message(role="user", content=general_prompt))
        
        result = await self._call_llm_structured(messages, ResearchResult)
        return result if isinstance(result, ResearchResult) else ResearchResult(**result.model_dump())
    
    async def _search_web(self, query: str) -> List[Dict[str, Any]]:
        """Search the web using browser tool."""
        try:
            # Use the browser tool via tool manager
            if self.tool_manager:
                result = await self.tool_manager.execute("browser_navigate", {
                    "url": f"https://www.google.com/search?q={query}",
                    "wait_for": "networkidle",
                    "timeout": 30000,
                })
                
                if result.success and result.result:
                    extracted = result.result.get("extracted_data", {})
                    return [{
                        "query": query,
                        "url": "https://www.google.com/search?q=" + query,
                        "title": extracted.get("title", ""),
                        "content": extracted.get("text_content", "")[:2000],
                    }]
        except Exception as e:
            self.logger.warning(f"Browser search failed: {e}")
        
        # Fallback: return empty for LLM to handle
        return []
    
    def _build_research_context(self, search_results: List[Dict[str, Any]], query: str) -> str:
        """Build research context from search results."""
        if not search_results:
            return "No search results available. Use your knowledge to provide research."
        
        context_parts = [f"Search query: {query}\n"]
        for i, result in enumerate(search_results, 1):
            context_parts.append(f"Result {i}:")
            context_parts.append(f"  URL: {result.get('url', 'N/A')}")
            context_parts.append(f"  Title: {result.get('title', 'N/A')}")
            context_parts.append(f"  Content: {result.get('content', 'N/A')[:500]}")
            context_parts.append("")
        
        return "\n".join(context_parts)


def create_researcher_agent(tool_manager=None) -> ResearcherAgent:
    """Factory function to create researcher agent."""
    models_config = get_config("models")
    researcher_config = models_config.get("researcher", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("researcher", {})
    
    config = AgentConfig(
        name=AgentName.RESEARCHER,
        description=agent_config.get("description", "Technical research and information gathering"),
        permissions=agent_config.get("permissions", "READ_ONLY"),
        default_model=researcher_config.get("model", "deepseek/deepseek-chat"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 2),
        timeout=agent_config.get("timeout", 180),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return ResearcherAgent(config, tool_manager)