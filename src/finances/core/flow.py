#!/usr/bin/env python3
"""
Financial Flow System - Core Infrastructure

Provides unified command abstraction, dependency management, and execution
orchestration for the Financial Flow System.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def safe_get_callable_name(obj):
    """
    Safely extract a name from any callable object.

    Handles functions, Click Command objects, and other callables.

    Args:
        obj: Any callable object

    Returns:
        str: Best available name for the callable
    """
    if hasattr(obj, "__name__"):
        return obj.__name__
    elif hasattr(obj, "name"):
        return obj.name
    else:
        return obj.__class__.__name__


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
    review_instructions: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class FlowContext:
    """Execution context shared across all flow nodes."""

    start_time: datetime
    interactive: bool = True
    performance_tracking: bool = False
    confidence_threshold: int = 10000  # 100.00% in basis points
    date_range: Optional[tuple[date, date]] = None
    archive_manifest: dict[str, Path] = field(default_factory=dict)
    execution_history: list["NodeExecution"] = field(default_factory=list)
    dry_run: bool = False
    force: bool = False
    verbose: bool = False


@dataclass
class NodeExecution:
    """Record of a single node execution."""

    node_name: str
    status: NodeStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[FlowResult] = None
    changes_detected: bool = False
    change_reasons: list[str] = field(default_factory=list)


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
    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """
        Check if this node needs to execute based on upstream changes.

        Args:
            context: Flow execution context

        Returns:
            Tuple of (needs_execution, list_of_change_reasons)
        """
        pass

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


def flow_node(name: str, depends_on: Optional[list[str]] = None):
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
        self._change_detector: Optional[Callable[[FlowContext], tuple[bool, list[str]]]] = None

    def set_change_detector(self, detector: Callable[[FlowContext], tuple[bool, list[str]]]) -> None:
        """Set custom change detection function."""
        self._change_detector = detector

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check for changes using registered detector or default logic."""
        if self._change_detector:
            return self._change_detector(context)

        # Default: always execute if no custom detector
        return True, ["No change detector configured"]

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute the wrapped function."""
        try:
            start_time = datetime.now()
            result = self.func(context)

            # Ensure result is valid
            if not isinstance(result, FlowResult):
                func_name = safe_get_callable_name(self.func)
                raise ValueError(f"Function {func_name} must return FlowResult")

            # Add timing information
            if context.performance_tracking:
                end_time = datetime.now()
                result.execution_time_seconds = (end_time - start_time).total_seconds()

            return result

        except Exception as e:
            logger.error(f"Error executing {self.name}: {e}")
            return FlowResult(success=False, error_message=str(e))


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
        dependencies: Optional[list[str]] = None,
        change_detector: Optional[Callable[[FlowContext], tuple[bool, list[str]]]] = None,
    ):
        """
        Initialize CLI adapter node.

        Args:
            name: Node identifier
            cli_command: CLI command function to wrap
            dependencies: List of dependency node names
            change_detector: Function to detect if execution is needed
        """
        super().__init__(name)
        if dependencies:
            self._dependencies = set(dependencies)

        self.cli_command = cli_command
        self._change_detector = change_detector

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check for changes using provided detector or default."""
        if self._change_detector:
            return self._change_detector(context)

        # Default: execute on any upstream change or if forced
        if context.force:
            return True, ["Force execution requested"]

        # For now, assume changes if no detector provided
        return True, ["No change detector available"]

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute the CLI command with flow context adaptation."""
        try:
            start_time = datetime.now()

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

            if context.performance_tracking:
                end_time = datetime.now()
                result.execution_time_seconds = (end_time - start_time).total_seconds()

            return result

        except Exception as e:
            logger.error(f"Error executing CLI command {self.name}: {e}")
            return FlowResult(success=False, error_message=str(e))


class FlowNodeRegistry:
    """
    Registry for managing flow nodes and their dependencies.

    Maintains a central registry of all available flow nodes and provides
    dependency resolution and graph construction capabilities.
    """

    def __init__(self):
        """Initialize empty node registry."""
        self._nodes: dict[str, FlowNode] = {}
        self._change_detectors: dict[str, Callable[[FlowContext], tuple[bool, list[str]]]] = {}

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
        dependencies: Optional[list[str]] = None,
        change_detector: Optional[Callable[[FlowContext], tuple[bool, list[str]]]] = None,
    ) -> None:
        """
        Register a function as a flow node.

        Args:
            name: Node identifier
            func: Function to execute
            dependencies: List of dependency node names
            change_detector: Optional change detection function
        """
        node = FunctionFlowNode(name, func, dependencies or [])
        if change_detector:
            node.set_change_detector(change_detector)

        self.register_node(node)

    def get_node(self, name: str) -> Optional[FlowNode]:
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
        errors = []

        for node_name, node in self._nodes.items():
            for dep_name in node.dependencies:
                if dep_name not in self._nodes:
                    errors.append(f"Node '{node_name}' depends on unknown node '{dep_name}'")

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

        cycles = []
        visited = set()

        for node_name in self._nodes:
            if node_name not in visited:
                visit(node_name, [], visited, cycles)

        return cycles


# Global node registry instance
flow_registry = FlowNodeRegistry()
