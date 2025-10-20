#!/usr/bin/env python3
"""
Financial Flow System - Core Infrastructure

Provides unified command abstraction, dependency management, and execution
orchestration for the Financial Flow System.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def safe_get_callable_name(obj: Any) -> str:
    """
    Safely extract a name from any callable object.

    Handles functions, Click Command objects, and other callables.

    Args:
        obj: Any callable object

    Returns:
        str: Best available name for the callable
    """
    if hasattr(obj, "__name__"):
        return str(obj.__name__)
    elif hasattr(obj, "name"):
        return str(obj.name)
    else:
        return str(obj.__class__.__name__)


class NodeStatus(Enum):
    """Execution status for flow nodes."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FlowResult:
    """Standardized result structure from flow node execution."""

    success: bool
    items_processed: int = 0
    new_items: int = 0
    updated_items: int = 0
    outputs: list[Path] = field(default_factory=list)
    requires_review: bool = False
    review_instructions: str | None = None
    execution_time_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class FlowContext:
    """Execution context shared across all flow nodes."""

    start_time: datetime
    archive_manifest: dict[str, Path] = field(default_factory=dict)
    execution_history: list["NodeExecution"] = field(default_factory=list)


@dataclass
class NodeExecution:
    """Record of a single node execution."""

    node_name: str
    status: NodeStatus
    start_time: datetime | None = None
    end_time: datetime | None = None
    result: FlowResult | None = None
    changes_detected: bool = False
    change_reasons: list[str] = field(default_factory=list)


@dataclass
class NodeDataSummary:
    """Summary of a node's current data state for interactive prompts."""

    exists: bool
    last_updated: datetime | None
    age_days: int | None
    item_count: int | None
    size_bytes: int | None
    summary_text: str


@dataclass(frozen=True)
class OutputFile:
    """Information about a single output file from a flow node."""

    path: Path
    record_count: int


class OutputInfo(ABC):
    """Information about a flow node's output data."""

    @abstractmethod
    def is_data_ready(self) -> bool:
        """Returns True if output data is complete enough for dependencies to use."""
        pass

    @abstractmethod
    def get_output_files(self) -> list[OutputFile]:
        """Returns list of output files with their record counts."""
        pass


class NoOutputInfo(OutputInfo):
    """Output info for nodes with no persistent output (manual steps)."""

    def is_data_ready(self) -> bool:
        """Manual nodes are always ready (no data required)."""
        return True

    def get_output_files(self) -> list[OutputFile]:
        """Manual nodes have no output files."""
        return []


class FlowNode(ABC):
    """
    Abstract base class for flow nodes.

    All financial commands that participate in the flow system must implement
    this interface to provide standardized execution, change detection, and
    dependency management.
    """

    def __init__(self, name: str):
        """
        Initialize flow node.

        Args:
            name: Unique identifier for this node in the flow graph
        """
        self.name = name
        self._dependencies: set[str] = set()

    @property
    def dependencies(self) -> set[str]:
        """Get the set of node names this node depends on."""
        return self._dependencies.copy()

    @abstractmethod
    def execute(self, context: FlowContext) -> FlowResult:
        """
        Execute this node's operation.

        Args:
            context: Flow execution context

        Returns:
            FlowResult with execution details and outputs
        """
        pass

    @abstractmethod
    def get_output_info(self) -> OutputInfo:
        """
        Get information about this node's output data.

        Returns OutputInfo with methods to check data readiness and list output files.
        Used by flow engine for dependency validation and status display.

        Returns:
            OutputInfo instance with node's current output state
        """
        pass

    def get_display_name(self) -> str:
        """Get human-readable display name for this node."""
        return self.name.replace("_", " ").title()

    def get_active_form(self) -> str:
        """Get present continuous form for progress display."""
        display = self.get_display_name()
        # Simple transformation to present continuous
        if display.endswith("Sync"):
            return f"Syncing {display[:-4].strip()}"
        elif display.endswith("Match"):
            return f"Matching {display[:-5].strip()}"
        elif display.endswith("Analysis"):
            return f"Analyzing {display[:-8].strip()}"
        else:
            return f"Processing {display}"

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """
        Get summary of current data for this node.

        Returns information about data presence, age, and size for
        display in interactive prompts.

        Returns:
            NodeDataSummary with current data state
        """
        # Default implementation: no data available
        return NodeDataSummary(
            exists=False,
            last_updated=None,
            age_days=None,
            item_count=None,
            size_bytes=None,
            summary_text="No data summary available",
        )

    def prompt_user(self, context: FlowContext) -> bool:
        """
        Prompt user whether to execute this node.

        Shows data summary and asks user for decision.
        Returns True to execute, False to skip.

        Args:
            context: Flow execution context

        Returns:
            True if node should execute, False to skip
        """
        summary = self.get_data_summary(context)

        # Import click here to avoid circular imports
        import click

        click.echo(f"\n{self.get_display_name()}")
        click.echo(f"  {summary.summary_text}")

        if summary.last_updated:
            age_str = f"{summary.age_days} days ago" if summary.age_days else "recently"
            click.echo(f"  Last updated: {age_str}")
        else:
            click.echo("  Status: No data found")

        return click.confirm("  Update this data?", default=False)


def flow_node(
    name: str, depends_on: list[str] | None = None
) -> Callable[[Callable[[FlowContext], FlowResult]], "FunctionFlowNode"]:
    """
    Decorator for registering flow nodes with dependency declarations.

    Args:
        name: Unique node name
        depends_on: List of node names this node depends on

    Example:
        @flow_node("amazon_matching", depends_on=["ynab_sync", "amazon_unzip"])
        def amazon_match_command(context: FlowContext, **kwargs) -> FlowResult:
            # Implementation
            return FlowResult(success=True, items_processed=150)
    """

    def decorator(func: Callable[[FlowContext], FlowResult]) -> "FunctionFlowNode":
        return FunctionFlowNode(name, func, depends_on or [])

    return decorator


class FunctionFlowNode(FlowNode):
    """
    Flow node implementation that wraps a function.

    Allows existing CLI commands to be easily adapted for flow execution
    through a functional interface.
    """

    def __init__(self, name: str, func: Callable[[FlowContext], FlowResult], dependencies: list[str]):
        """
        Initialize function-based flow node.

        Args:
            name: Node identifier
            func: Function to execute (must return FlowResult)
            dependencies: List of dependency node names
        """
        super().__init__(name)
        self._dependencies = set(dependencies)
        self.func = func
        self._data_summary_func: Callable[[FlowContext], NodeDataSummary] | None = None

    def set_data_summary_func(self, func: Callable[[FlowContext], NodeDataSummary]) -> None:
        """Set custom data summary function."""
        self._data_summary_func = func

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get data summary using registered function or default."""
        if self._data_summary_func:
            return self._data_summary_func(context)

        # Use default implementation from base class
        return super().get_data_summary(context)

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute the wrapped function."""
        try:
            result = self.func(context)

            # Runtime validation for type safety
            # This validates at runtime while mypy validates at compile time
            if not isinstance(result, FlowResult):
                raise TypeError(
                    f"Function {safe_get_callable_name(self.func)} must return FlowResult, "
                    f"got {type(result).__name__}"
                )

            return result

        except AssertionError as e:
            logger.error(f"Type validation failed for {self.name}: {e}")
            return FlowResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error(f"Error executing {self.name}: {e}")
            return FlowResult(success=False, error_message=str(e))

    def get_output_info(self) -> OutputInfo:
        """Get output info - defaults to NoOutputInfo for function nodes."""
        return NoOutputInfo()


class CLIAdapterNode(FlowNode):
    """
    Flow node that adapts existing CLI commands for flow execution.

    Bridges the gap between the existing CLI infrastructure and the new
    flow system by wrapping CLI command functions.
    """

    def __init__(
        self,
        name: str,
        cli_command: Callable,
        dependencies: list[str] | None = None,
    ):
        """
        Initialize CLI adapter node.

        Args:
            name: Node identifier
            cli_command: CLI command function to wrap
            dependencies: List of dependency node names
        """
        super().__init__(name)
        if dependencies:
            self._dependencies = set(dependencies)

        self.cli_command = cli_command

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute the CLI command with flow context adaptation."""
        try:
            # This would adapt the CLI command call to work with flow context
            # The actual implementation would depend on the specific CLI command structure
            logger.info(f"Executing CLI command for {self.name}")

            # Placeholder - actual implementation would call the CLI command
            # with appropriate parameter mapping from FlowContext
            result = FlowResult(
                success=True,
                items_processed=0,
                metadata={
                    "cli_command": (
                        self.cli_command.__name__
                        if hasattr(self.cli_command, "__name__")
                        else str(self.cli_command)
                    )
                },
            )

            return result

        except Exception as e:
            logger.error(f"Error executing CLI command {self.name}: {e}")
            return FlowResult(success=False, error_message=str(e))

    def get_output_info(self) -> OutputInfo:
        """Get output info - defaults to NoOutputInfo for CLI nodes."""
        return NoOutputInfo()


class FlowNodeRegistry:
    """
    Registry for managing flow nodes and their dependencies.

    Maintains a central registry of all available flow nodes and provides
    dependency resolution and graph construction capabilities.
    """

    def __init__(self) -> None:
        """Initialize empty node registry."""
        self._nodes: dict[str, FlowNode] = {}

    def register_node(self, node: FlowNode) -> None:
        """
        Register a flow node.

        Args:
            node: FlowNode instance to register
        """
        if node.name in self._nodes:
            logger.warning(f"Overwriting existing node: {node.name}")

        self._nodes[node.name] = node
        logger.debug(f"Registered flow node: {node.name}")

    def register_function_node(
        self,
        name: str,
        func: Callable[[FlowContext], FlowResult],
        dependencies: list[str] | None = None,
        data_summary_func: Callable[[FlowContext], NodeDataSummary] | None = None,
    ) -> None:
        """
        Register a function as a flow node.

        Args:
            name: Node identifier
            func: Function to execute
            dependencies: List of dependency node names
            data_summary_func: Optional data summary function for interactive prompts
        """
        node = FunctionFlowNode(name, func, dependencies or [])
        if data_summary_func:
            node.set_data_summary_func(data_summary_func)

        self.register_node(node)

    def get_node(self, name: str) -> FlowNode | None:
        """Get a registered node by name."""
        return self._nodes.get(name)

    def get_all_nodes(self) -> dict[str, FlowNode]:
        """Get all registered nodes."""
        return self._nodes.copy()

    def validate_dependencies(self) -> list[str]:
        """
        Validate that all node dependencies exist.

        Returns:
            List of validation error messages
        """
        errors = [
            f"Node '{node_name}' depends on unknown node '{dep_name}'"
            for node_name, node in self._nodes.items()
            for dep_name in node.dependencies
            if dep_name not in self._nodes
        ]

        return errors

    def detect_cycles(self) -> list[list[str]]:
        """
        Detect dependency cycles in the flow graph.

        Returns:
            List of cycles found, each cycle is a list of node names
        """

        def visit(node_name: str, path: list[str], visited: set[str], cycles: list[list[str]]) -> None:
            if node_name in path:
                # Found a cycle
                cycle_start = path.index(node_name)
                cycle = [*path[cycle_start:], node_name]
                cycles.append(cycle)
                return

            if node_name in visited:
                return

            visited.add(node_name)
            path.append(node_name)

            node = self._nodes.get(node_name)
            if node:
                for dep_name in node.dependencies:
                    visit(dep_name, path, visited, cycles)

            path.pop()

        cycles: list[list[str]] = []
        visited: set[str] = set()

        for node_name in self._nodes:
            if node_name not in visited:
                visit(node_name, [], visited, cycles)

        return cycles


# Global node registry instance
flow_registry = FlowNodeRegistry()
