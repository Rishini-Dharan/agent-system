"""
CLI - Main Entry Point
Command-line interface for the agent system.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from agent_system.config import get_config, get_config_manager
from agent_system.router import ModelRouter, RoutingContext, TaskType, ComplexityLevel
from agent_system.schemas import (
    Task,
    TaskStatus,
    TaskType as SchemaTaskType,
    AgentName,
    ExecutionContext,
    ExecutionMode,
)
from agent_system.runtime import (
    ExecutionManager,
    ContextManager,
    ToolManager,
    BuiltinTools,
)
from agent_system.agents import create_all_agents
from agent_system.state import get_db_manager, close_db_manager
from agent_system.observability import configure_logging, get_logger, get_metrics
from agent_system.security import get_permission_manager, get_command_guard


console = Console()


class AgentSystemCLI:
    """Main CLI application."""
    
    def __init__(self):
        self.router = ModelRouter()
        self.execution_manager: Optional[ExecutionManager] = None
        self.context_manager: Optional[ContextManager] = None
        self.tool_manager: Optional[ToolManager] = None
        self.agents: Dict[str, Any] = {}
        self.logger = get_logger("cli")
        self.metrics = get_metrics()
    
    async def initialize(self) -> None:
        """Initialize the agent system."""
        console.print("[bold blue]Initializing Agent System...[/bold blue]")
        
        # Configure logging
        configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
        
        # Initialize database
        db = await get_db_manager()
        
        # Initialize components
        self.tool_manager = ToolManager()
        BuiltinTools.register_all(self.tool_manager)
        
        self.context_manager = ContextManager()
        
        # Create agents
        self.agents = create_all_agents(self.tool_manager)
        
        # Create execution manager
        self.execution_manager = ExecutionManager(
            agent_registry=None,  # Will use global registry
            context_manager=self.context_manager,
            max_parallel_agents=4,
        )
        await self.execution_manager.initialize()
        
        console.print("[bold green]Agent System initialized successfully![/bold green]")
    
    async def shutdown(self) -> None:
        """Shutdown the agent system."""
        if self.execution_manager:
            await self.execution_manager.shutdown()
        await close_db_manager()
        console.print("[bold yellow]Agent System shutdown complete.[/bold yellow]")
    
    async def run_task(
        self,
        objective: str,
        task_type: str = "custom",
        agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a single task."""
        task_id = f"task-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        # Determine task type
        try:
            tt = SchemaTaskType(task_type)
        except ValueError:
            tt = SchemaTaskType.CUSTOM
        
        # Determine agent
        assigned_agent = AgentName(agent) if agent else None
        if not assigned_agent:
            # Route to appropriate agent
            routing_context = RoutingContext(
                task_type=TaskType(task_type),
                complexity=ComplexityLevel.MEDIUM,
            )
            decision = self.router.route(routing_context)
            assigned_agent = AgentName(decision.agent_name)
        
        # Create task
        task = Task(
            task_id=task_id,
            task_type=tt,
            description=objective,
            objective=objective,
            assigned_agent=assigned_agent,
        )
        
        console.print(Panel(f"[bold]Task:[/bold] {objective}\n[bold]Agent:[/bold] {assigned_agent.value}", title=f"Task {task_id}"))
        
        # Execute task
        start_time = time.time()
        completed_task = await self.execution_manager.execute_task(task)
        
        duration = int((time.time() - start_time) * 1000)
        
        # Display result
        self._display_task_result(completed_task, duration)
        
        return completed_task.model_dump()
    
    def _display_task_result(self, task: Task, duration_ms: int) -> None:
        """Display task result."""
        status_color = {
            TaskStatus.SUCCESS: "green",
            TaskStatus.FAILED: "red",
            TaskStatus.PARTIAL: "yellow",
        }.get(task.status, "white")
        
        console.print(f"\n[bold]Result:[/bold] [{status_color}]{task.status.value}[/{status_color}]")
        console.print(f"[bold]Duration:[/bold] {duration_ms}ms")
        
        if task.output:
            console.print("\n[bold]Output:[/bold]")
            if isinstance(task.output, dict):
                # Try to display summary
                if "summary" in task.output:
                    console.print(task.output["summary"])
                else:
                    console.print(json.dumps(task.output, indent=2))
            else:
                console.print(str(task.output))
        
        if task.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in task.errors:
                console.print(f"  - {error}")
    
    async def run_workflow(
        self,
        name: str,
        objective: str,
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run a multi-step workflow."""
        workflow_id = f"workflow-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        console.print(Panel(f"[bold]Workflow:[/bold] {name}\n[bold]Objective:[/bold] {objective}", title=f"Workflow {workflow_id}"))
        
        exec_context = await self.execution_manager.execute_workflow(
            workflow_id=workflow_id,
            workflow_name=name,
            objective=objective,
            steps=steps,
        )
        
        # Display results
        console.print(f"\n[bold]Workflow Status:[/bold] {exec_context.status.value}")
        console.print(f"[bold]Completed Tasks:[/bold] {exec_context.metrics.completed_tasks}")
        console.print(f"[bold]Failed Tasks:[/bold] {exec_context.metrics.failed_tasks}")
        
        return {
            "workflow_id": workflow_id,
            "status": exec_context.status.value,
            "metrics": {
                "completed_tasks": exec_context.metrics.completed_tasks,
                "failed_tasks": exec_context.metrics.failed_tasks,
                "total_duration_ms": exec_context.metrics.total_duration_ms,
            },
        }
    
    def show_status(self) -> None:
        """Show system status."""
        # Get routing info
        routing_info = self.router.get_routing_info()
        
        # Get metrics
        metrics_summary = self.metrics.get_summary()
        
        # Display configuration
        console.print(Panel("[bold]Agent System Status[/bold]"))
        
        # Available providers
        table = Table(title="Available Providers")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        
        for provider in routing_info["available_providers"]:
            table.add_row(provider, "✓ Configured")
        
        console.print(table)
        
        # Configured models
        model_table = Table(title="Configured Models")
        model_table.add_column("Agent", style="cyan")
        model_table.add_column("Provider", style="green")
        model_table.add_column("Model", style="yellow")
        
        for agent_name, model_config in routing_info["configured_models"].items():
            model_table.add_row(
                agent_name,
                model_config.get("provider", ""),
                model_config.get("model", ""),
            )
        
        console.print(model_table)
        
        # Metrics summary
        console.print("\n[bold]Metrics Summary:[/bold]")
        console.print(f"  Total Calls: {metrics_summary['total_calls']}")
        console.print(f"  Success Rate: {metrics_summary['overall_success_rate']:.1%}")
        console.print(f"  Avg Latency: {metrics_summary['avg_latency_ms']:.0f}ms")
        console.print(f"  Total Cost: ${metrics_summary['total_cost_usd']:.4f}")
    
    def show_agents(self) -> None:
        """Show available agents."""
        table = Table(title="Available Agents")
        table.add_column("Agent", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Permissions", style="yellow")
        table.add_column("Default Model", style="green")
        
        agents_config = get_config("agents")
        models_config = get_config("models")
        
        for agent_name, agent_config in agents_config.items():
            model_config = models_config.get(agent_name, {})
            table.add_row(
                agent_name,
                agent_config.get("description", ""),
                agent_config.get("permissions", ""),
                model_config.get("model", ""),
            )
        
        console.print(table)
    
    def show_models(self) -> None:
        """Show configured models."""
        models_config = get_config("models")
        
        table = Table(title="Model Configuration")
        table.add_column("Role", style="cyan")
        table.add_column("Provider", style="green")
        table.add_column("Model", style="yellow")
        table.add_column("Temperature", style="blue")
        table.add_column("Max Tokens", style="magenta")
        
        for role, config in models_config.get("models", {}).items():
            table.add_row(
                role,
                config.get("provider", ""),
                config.get("model", ""),
                str(config.get("temperature", "")),
                str(config.get("max_tokens", "")),
            )
        
        console.print(table)
    
    def show_logs(self, lines: int = 50) -> None:
        """Show recent logs."""
        log_dir = Path(os.getcwd()) / "logs"
        
        if not log_dir.exists():
            console.print("[yellow]No logs directory found[/yellow]")
            return
        
        # Find most recent log file
        log_files = list(log_dir.glob("*.log"))
        if not log_files:
            console.print("[yellow]No log files found[/yellow]")
            return
        
        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
        
        console.print(f"[bold]Showing last {lines} lines from {latest_log.name}:[/bold]\n")
        
        with open(latest_log, "r") as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                try:
                    # Try to parse and pretty-print JSON
                    log_data = json.loads(line.strip())
                    console.print(json.dumps(log_data, indent=2))
                except json.JSONDecodeError:
                    console.print(line.rstrip())
    
    async def run_tests(self) -> None:
        """Run unit tests."""
        console.print("[bold]Running tests...[/bold]")
        
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            capture_output=True,
            text=True,
        )
        
        console.print(result.stdout)
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]")
        
        if result.returncode == 0:
            console.print("[bold green]All tests passed![/bold green]")
        else:
            console.print("[bold red]Some tests failed![/bold red]")
    
    async def doctor(self) -> None:
        """Run environment diagnostics."""
        console.print(Panel("[bold]Agent System Doctor[/bold]"))
        
        checks = []
        
        # Python version
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        checks.append(("Python Version", py_version, py_version >= "3.11"))
        
        # Required packages
        required_packages = [
            "pydantic", "pyyaml", "httpx", "openai", "google-generativeai",
            "aiosqlite", "sqlalchemy", "click", "rich", "gitpython",
            "playwright", "structlog", "tenacity", "orjson",
        ]
        
        for pkg in required_packages:
            try:
                __import__(pkg)
                checks.append((f"Package: {pkg}", "Installed", True))
            except ImportError:
                checks.append((f"Package: {pkg}", "Missing", False))
        
        # Environment variables
        env_vars = [
            "NVIDIA_API_KEY",
            "OPENROUTER_API_KEY",
            "ZAI_API_KEY",
            "GOOGLE_API_KEY",
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            checks.append((f"Env: {var}", "Set" if value else "Not Set", bool(value)))
        
        # External tools
        external_tools = [
            ("git", "git --version"),
            ("semgrep", "semgrep --version"),
            ("gitleaks", "gitleaks version"),
            ("trivy", "trivy version"),
        ]
        
        for name, cmd in external_tools:
            try:
                result = subprocess.run(cmd.split(), capture_output=True, timeout=5)
                checks.append((f"Tool: {name}", "Available" if result.returncode == 0 else "Error", result.returncode == 0))
            except (FileNotFoundError, subprocess.TimeoutExpired):
                checks.append((f"Tool: {name}", "Not Found", False))
        
        # Display results
        table = Table(title="Environment Checks")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Pass", style="green")
        
        for check_name, status, passed in checks:
            status_style = "green" if passed else "red"
            table.add_row(check_name, status, "[OK]" if passed else "[FAIL]")
        
        console.print(table)
        
        # Summary
        passed_count = sum(1 for _, _, p in checks if p)
        total_count = len(checks)
        console.print(f"\n[bold]Summary:[/bold] {passed_count}/{total_count} checks passed")
        
        if passed_count == total_count:
            console.print("[bold green]All checks passed![/bold green]")
        else:
            console.print("[bold yellow]Some checks failed. Review above.[/bold yellow]")
    
    def show_config(self) -> None:
        """Show current configuration."""
        config_manager = get_config_manager()
        all_configs = config_manager.load_all()
        
        for name, config in all_configs.items():
            console.print(Panel(
                Syntax(json.dumps(config, indent=2), "json", theme="monokai"),
                title=f"Config: {name}",
            ))


# CLI Commands
@click.group()
@click.option("--log-level", default="INFO", help="Log level")
@click.pass_context
def cli(ctx, log_level):
    """Agent System - Multi-model autonomous coding agent platform."""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level


@cli.command()
@click.argument("objective")
@click.option("--type", "task_type", default="custom", help="Task type")
@click.option("--agent", help="Specific agent to use")
@click.pass_context
def run(ctx, objective: str, task_type: str, agent: str):
    """Run a single task."""
    async def _run():
        system = AgentSystemCLI()
        await system.initialize()
        try:
            await system.run_task(objective, task_type, agent)
        finally:
            await system.shutdown()
    
    asyncio.run(_run())


@cli.command()
@click.argument("name")
@click.argument("objective")
@click.option("--steps", "steps_file", type=click.Path(exists=True), help="JSON file with workflow steps")
@click.pass_context
def workflow(ctx, name: str, objective: str, steps_file: str):
    """Run a multi-step workflow."""
    async def _workflow():
        # Load steps from file
        with open(steps_file, "r") as f:
            steps = json.load(f)
        
        system = AgentSystemCLI()
        await system.initialize()
        try:
            await system.run_workflow(name, objective, steps)
        finally:
            await system.shutdown()
    
    asyncio.run(_workflow())


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        system.show_status()
    finally:
        asyncio.run(system.shutdown())


@cli.command()
@click.pass_context
def agents(ctx):
    """Show available agents."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        system.show_agents()
    finally:
        asyncio.run(system.shutdown())


@cli.command()
@click.pass_context
def models(ctx):
    """Show configured models."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        system.show_models()
    finally:
        asyncio.run(system.shutdown())


@cli.command()
@click.option("--lines", "-n", default=50, help="Number of lines to show")
@click.pass_context
def logs(ctx, lines: int):
    """Show recent logs."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        system.show_logs(lines)
    finally:
        asyncio.run(system.shutdown())


@cli.command()
@click.pass_context
def test(ctx):
    """Run unit tests."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        asyncio.run(system.run_tests())
    finally:
        asyncio.run(system.shutdown())


@cli.command()
@click.pass_context
def doctor(ctx):
    """Run environment diagnostics."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        asyncio.run(system.doctor())
    finally:
        asyncio.run(system.shutdown())


@cli.command()
@click.pass_context
def config(ctx):
    """Show current configuration."""
    system = AgentSystemCLI()
    asyncio.run(system.initialize())
    try:
        system.show_config()
    finally:
        asyncio.run(system.shutdown())


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()