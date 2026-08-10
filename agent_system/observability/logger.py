"""
Observability - Logger
Structured JSON logging for the agent system.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import structlog


class StructuredLogger:
    """Structured logger with JSON output."""
    
    def __init__(self, name: str):
        self.name = name
        self._logger = structlog.get_logger(name)
        self._context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> "StructuredLogger":
        """Bind context variables."""
        new_logger = StructuredLogger(self.name)
        new_logger._logger = self._logger.bind(**kwargs)
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def _log(self, level: str, event: str, **kwargs) -> None:
        """Log with structured data."""
        log_data = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "logger": self.name,
            **self._context,
            **kwargs,
        }
        getattr(self._logger, level)(**log_data)
    
    def debug(self, event: str, **kwargs) -> None:
        self._log("debug", event, **kwargs)
    
    def info(self, event: str, **kwargs) -> None:
        self._log("info", event, **kwargs)
    
    def warning(self, event: str, **kwargs) -> None:
        self._log("warning", event, **kwargs)
    
    def error(self, event: str, **kwargs) -> None:
        self._log("error", event, **kwargs)
    
    def critical(self, event: str, **kwargs) -> None:
        self._log("critical", event, **kwargs)
    
    def exception(self, event: str, **kwargs) -> None:
        self._log("error", event, exc_info=True, **kwargs)
    
    # Specialized logging methods
    def log_agent_call(
        self,
        agent: str,
        provider: str,
        model: str,
        task_id: str,
        latency_ms: int,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        **kwargs
    ) -> None:
        """Log an agent LLM call."""
        self.info(
            "agent_call",
            agent=agent,
            provider=provider,
            model=model,
            task_id=task_id,
            latency_ms=latency_ms,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            **kwargs,
        )
    
    def log_task_start(self, task_id: str, agent: str, description: str, **kwargs) -> None:
        """Log task start."""
        self.info(
            "task_start",
            task_id=task_id,
            agent=agent,
            description=description[:200],
            **kwargs,
        )
    
    def log_task_complete(
        self,
        task_id: str,
        agent: str,
        status: str,
        duration_ms: int,
        **kwargs
    ) -> None:
        """Log task completion."""
        self.info(
            "task_complete",
            task_id=task_id,
            agent=agent,
            status=status,
            duration_ms=duration_ms,
            **kwargs,
        )
    
    def log_tool_call(
        self,
        tool_name: str,
        agent: str,
        task_id: str,
        duration_ms: int,
        success: bool,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a tool call."""
        self.info(
            "tool_call",
            tool_name=tool_name,
            agent=agent,
            task_id=task_id,
            duration_ms=duration_ms,
            success=success,
            error=error,
            **kwargs,
        )
    
    def log_fallback(
        self,
        from_provider: str,
        from_model: str,
        to_provider: str,
        to_model: str,
        reason: str,
        **kwargs
    ) -> None:
        """Log a provider/model fallback."""
        self.warning(
            "fallback",
            from_provider=from_provider,
            from_model=from_model,
            to_provider=to_provider,
            to_model=to_model,
            reason=reason,
            **kwargs,
        )
    
    def log_conflict(
        self,
        task_id: str,
        agents: list,
        resolution_strategy: str,
        **kwargs
    ) -> None:
        """Log a conflict between agents."""
        self.warning(
            "conflict",
            task_id=task_id,
            agents=agents,
            resolution_strategy=resolution_strategy,
            **kwargs,
        )
    
    def log_approval_request(
        self,
        request_id: str,
        task_id: str,
        action_type: str,
        **kwargs
    ) -> None:
        """Log an approval request."""
        self.info(
            "approval_request",
            request_id=request_id,
            task_id=task_id,
            action_type=action_type,
            **kwargs,
        )


# Global logger cache
_loggers: Dict[str, StructuredLogger] = {}
_loggers_lock = threading.Lock()
_structlog_configured = False


def _configure_structlog_once(log_level: str, log_dir: Path) -> None:
    """Configure structlog globally once with rotating file handlers."""
    global _structlog_configured
    
    if _structlog_configured:
        return
    
    log_level = log_level.upper()
    
    # Create log directory
    log_dir.mkdir(exist_ok=True)
    
    # Create rotating file handler (10MB max, 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "agent_system.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.handlers = [file_handler, console_handler]
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    _structlog_configured = True


def get_logger(name: str) -> StructuredLogger:
    """Get or create a structured logger."""
    with _loggers_lock:
        if name not in _loggers:
            _loggers[name] = StructuredLogger(name)
        return _loggers[name]


def configure_logging(log_level: str = "INFO", log_dir: Optional[str] = None) -> None:
    """Configure global logging settings."""
    os.environ["LOG_LEVEL"] = log_level.upper()
    if log_dir:
        os.environ["LOG_DIR"] = log_dir
    
    # Determine log directory
    if log_dir:
        log_path = Path(log_dir)
    else:
        log_path = Path(os.getcwd()) / "logs"
    
    # Configure structlog with rotation
    _configure_structlog_once(log_level.upper(), log_path)
    
    # Clear existing loggers to force reconfiguration with new settings
    global _loggers
    with _loggers_lock:
        _loggers.clear()