"""
Observability - Metrics
Metrics collection and reporting.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_system.observability.logger import get_logger


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Metrics for a specific agent."""
    agent_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    fallbacks_triggered: int = 0
    retries: int = 0
    last_call: Optional[datetime] = None
    
    def record_call(
        self,
        success: bool,
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record a call."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_latency_ms += latency_ms
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost_usd
        self.last_call = datetime.utcnow()
    
    def record_fallback(self) -> None:
        self.fallbacks_triggered += 1
    
    def record_retry(self) -> None:
        self.retries += 1
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "fallbacks_triggered": self.fallbacks_triggered,
            "retries": self.retries,
            "last_call": self.last_call.isoformat() if self.last_call else None,
        }


@dataclass
class TaskMetrics:
    """Metrics for task execution."""
    task_id: str
    agent_name: str
    status: str
    duration_ms: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """Collects and aggregates metrics."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._agent_metrics: Dict[str, AgentMetrics] = {}
        self._task_metrics: List[TaskMetrics] = []
        self._custom_metrics: List[MetricPoint] = []
        self._start_time = datetime.utcnow()
        self.logger = get_logger("metrics")
    
    def record_model_call(
        self,
        agent: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        success: bool,
        cost_usd: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        """Record a model API call."""
        with self._lock:
            if agent not in self._agent_metrics:
                self._agent_metrics[agent] = AgentMetrics(agent_name=agent)
            
            self._agent_metrics[agent].record_call(
                success=success,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )
            
            # Log the call
            self.logger.log_agent_call(
                agent=agent,
                provider=provider,
                model=model,
                task_id="",  # Would be passed in real usage
                latency_ms=latency_ms,
                status="success" if success else "failed",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
    
    def record_task_completion(
        self,
        task_id: str,
        agent: str,
        status: str,
        duration_ms: int,
    ) -> None:
        """Record task completion."""
        with self._lock:
            self._task_metrics.append(TaskMetrics(
                task_id=task_id,
                agent_name=agent,
                status=status,
                duration_ms=duration_ms,
            ))
            
            self.logger.log_task_complete(
                task_id=task_id,
                agent=agent,
                status=status,
                duration_ms=duration_ms,
            )
    
    def record_tool_call(
        self,
        tool_name: str,
        agent: str,
        task_id: str,
        duration_ms: int,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record a tool call."""
        self.logger.log_tool_call(
            tool_name=tool_name,
            agent=agent,
            task_id=task_id,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
    
    def record_fallback(
        self,
        agent: str,
        from_provider: str,
        from_model: str,
        to_provider: str,
        to_model: str,
        reason: str,
    ) -> None:
        """Record a fallback event."""
        with self._lock:
            if agent in self._agent_metrics:
                self._agent_metrics[agent].record_fallback()
        
        self.logger.log_fallback(
            from_provider=from_provider,
            from_model=from_model,
            to_provider=to_provider,
            to_model=to_model,
            reason=reason,
        )
    
    def record_retry(self, agent: str) -> None:
        """Record a retry."""
        with self._lock:
            if agent in self._agent_metrics:
                self._agent_metrics[agent].record_retry()
    
    def record_conflict(
        self,
        task_id: str,
        agents: List[str],
        resolution_strategy: str,
    ) -> None:
        """Record a conflict."""
        self.logger.log_conflict(
            task_id=task_id,
            agents=agents,
            resolution_strategy=resolution_strategy,
        )
    
    def record_approval_request(
        self,
        request_id: str,
        task_id: str,
        action_type: str,
    ) -> None:
        """Record an approval request."""
        self.logger.log_approval_request(
            request_id=request_id,
            task_id=task_id,
            action_type=action_type,
        )
    
    def get_agent_metrics(self, agent: str) -> Optional[AgentMetrics]:
        """Get metrics for an agent."""
        with self._lock:
            return self._agent_metrics.get(agent)
    
    def get_all_agent_metrics(self) -> Dict[str, AgentMetrics]:
        """Get all agent metrics."""
        with self._lock:
            return dict(self._agent_metrics)
    
    def get_task_metrics(self, limit: int = 100) -> List[TaskMetrics]:
        """Get recent task metrics."""
        with self._lock:
            return self._task_metrics[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall metrics summary."""
        with self._lock:
            total_calls = sum(m.total_calls for m in self._agent_metrics.values())
            total_successful = sum(m.successful_calls for m in self._agent_metrics.values())
            total_failed = sum(m.failed_calls for m in self._agent_metrics.values())
            total_latency = sum(m.total_latency_ms for m in self._agent_metrics.values())
            total_input_tokens = sum(m.total_input_tokens for m in self._agent_metrics.values())
            total_output_tokens = sum(m.total_output_tokens for m in self._agent_metrics.values())
            total_cost = sum(m.total_cost_usd for m in self._agent_metrics.values())
            total_fallbacks = sum(m.fallbacks_triggered for m in self._agent_metrics.values())
            total_retries = sum(m.retries for m in self._agent_metrics.values())
            
            return {
                "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
                "total_agents": len(self._agent_metrics),
                "total_calls": total_calls,
                "successful_calls": total_successful,
                "failed_calls": total_failed,
                "overall_success_rate": total_successful / total_calls if total_calls > 0 else 0,
                "avg_latency_ms": total_latency / total_calls if total_calls > 0 else 0,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "total_cost_usd": total_cost,
                "total_fallbacks": total_fallbacks,
                "total_retries": total_retries,
                "total_tasks_completed": len(self._task_metrics),
                "agent_metrics": {k: v.to_dict() for k, v in self._agent_metrics.items()},
            }
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._agent_metrics.clear()
            self._task_metrics.clear()
            self._custom_metrics.clear()
            self._start_time = datetime.utcnow()


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    global _metrics_collector
    with _metrics_lock:
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector()
        return _metrics_collector