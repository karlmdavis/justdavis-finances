#!/usr/bin/env python3
"""
Flow Execution Engine

Provides dependency resolution, change detection, and orchestrated execution
of the Financial Flow System.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from .flow import (
    FlowContext,
    FlowNodeRegistry,
    FlowResult,
    NodeExecution,
    NodeStatus,
    flow_registry,
)

logger = logging.getLogger(__name__)


class DependencyGraph:
    """
    Manages dependency relationships and execution ordering for flow nodes.

    Constructs a directed acyclic graph (DAG) from node dependencies and
    provides topological sorting for execution order.
    """

    def __init__(self, registry: FlowNodeRegistry):
        """
        Initialize dependency graph from node registry.

        Args:
            registry: FlowNodeRegistry containing all available nodes
        """
        self.registry = registry
        self.nodes = registry.get_all_nodes()

        # Build adjacency lists
        self.dependents: dict[str, set[str]] = defaultdict(set)  # nodes that depend on this node
        self.dependencies: dict[str, set[str]] = defaultdict(set)  # nodes this node depends on

        self._build_graph()

    def _build_graph(self) -> None:
        """Build the dependency graph from registered nodes."""
        for node_name, node in self.nodes.items():
            self.dependencies[node_name] = node.dependencies.copy()

            # Build reverse mapping (dependents)
            for dep_name in node.dependencies:
                self.dependents[dep_name].add(node_name)

    def validate(self) -> list[str]:
        """
        Validate the dependency graph for errors.

        Returns:
            List of validation error messages
        """
        errors = []

        # Check for missing dependencies
        registry_errors = self.registry.validate_dependencies()
        errors.extend(registry_errors)

        # Check for cycles
        cycles = self.registry.detect_cycles()
        for cycle in cycles:
            cycle_str = " -> ".join(cycle)
            errors.append(f"Dependency cycle detected: {cycle_str}")

        return errors

    def topological_sort(self, nodes_to_execute: set[str] | None = None) -> list[str]:
        """
        Get topologically sorted execution order for nodes.

        Args:
            nodes_to_execute: Optional set of nodes to include in sort.
                             If None, includes all nodes.

        Returns:
            List of node names in execution order
        """
        if nodes_to_execute is None:
            nodes_to_execute = set(self.nodes.keys())

        # Kahn's algorithm for topological sorting
        in_degree: dict[str, int] = defaultdict(int)
        graph: dict[str, set[str]] = defaultdict(set)

        # Build subgraph for nodes to execute
        for node_name in nodes_to_execute:
            for dep_name in self.dependencies[node_name]:
                if dep_name in nodes_to_execute:
                    graph[dep_name].add(node_name)
                    in_degree[node_name] += 1

        # Initialize queue with nodes that have no dependencies
        queue = deque([node for node in nodes_to_execute if in_degree[node] == 0])
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            # Process dependents
            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check if all nodes were processed (no cycles)
        if len(result) != len(nodes_to_execute):
            remaining = nodes_to_execute - set(result)
            raise ValueError(f"Cyclic dependency detected among nodes: {remaining}")

        return result

    def get_execution_levels(self, nodes_to_execute: set[str] | None = None) -> list[list[str]]:
        """
        Get nodes grouped by execution level for potential parallel execution.

        Args:
            nodes_to_execute: Optional set of nodes to include

        Returns:
            List of lists, where each inner list contains nodes that can
            execute in parallel at that level
        """
        if nodes_to_execute is None:
            nodes_to_execute = set(self.nodes.keys())

        levels = []
        remaining_nodes = nodes_to_execute.copy()
        processed: set[str] = set()

        while remaining_nodes:
            # Find nodes with no unprocessed dependencies
            current_level = []
            for node_name in remaining_nodes:
                node_deps = self.dependencies[node_name] & nodes_to_execute
                if node_deps.issubset(processed):
                    current_level.append(node_name)

            if not current_level:
                # Should not happen if graph is valid
                raise ValueError(f"Unable to find next execution level. Remaining: {remaining_nodes}")

            levels.append(sorted(current_level))
            remaining_nodes -= set(current_level)
            processed.update(current_level)

        return levels

    def find_changed_subgraph(self, changed_nodes: set[str]) -> set[str]:
        """
        Find all nodes that need execution due to upstream changes.

        Args:
            changed_nodes: Set of nodes that have detected changes

        Returns:
            Set of all nodes that need to execute (including downstream dependents)
        """
        needs_execution = set(changed_nodes)
        queue = deque(changed_nodes)

        while queue:
            current = queue.popleft()

            # Add all dependents to execution set
            for dependent in self.dependents[current]:
                if dependent not in needs_execution:
                    needs_execution.add(dependent)
                    queue.append(dependent)

        return needs_execution

    def _node_depends_on(self, node_name: str, dependency_name: str) -> bool:
        """
        Check if a node transitively depends on another node.

        Args:
            node_name: Name of the node to check
            dependency_name: Name of the potential dependency

        Returns:
            True if node_name depends on dependency_name (directly or transitively)
        """
        if node_name not in self.nodes or dependency_name not in self.nodes:
            return False

        # BFS to find if dependency_name is reachable from node_name's dependencies
        visited = set()
        queue = deque([node_name])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            # Check direct dependencies
            for dep in self.dependencies.get(current, set()):
                if dep == dependency_name:
                    return True
                if dep not in visited:
                    queue.append(dep)

        return False


class FlowExecutionEngine:
    """
    Orchestrates execution of the Financial Flow System.

    Manages dependency resolution, change detection, progress reporting,
    and coordinated execution of all flow nodes.
    """

    def __init__(self, registry: FlowNodeRegistry | None = None):
        """
        Initialize flow execution engine.

        Args:
            registry: FlowNodeRegistry to use (defaults to global registry)
        """
        self.registry = registry or flow_registry
        self.dependency_graph = DependencyGraph(self.registry)

    def validate_flow(self) -> list[str]:
        """
        Validate the entire flow for errors.

        Returns:
            List of validation error messages
        """
        return self.dependency_graph.validate()

    def detect_changes(
        self, context: FlowContext, nodes_to_check: set[str] | None = None
    ) -> dict[str, tuple[bool, list[str]]]:
        """
        Detect changes across all specified nodes.

        Args:
            context: Flow execution context
            nodes_to_check: Optional set of nodes to check (defaults to all)

        Returns:
            Dictionary mapping node names to (has_changes, change_reasons)
        """
        if nodes_to_check is None:
            nodes_to_check = set(self.registry.get_all_nodes().keys())

        changes = {}

        for node_name in nodes_to_check:
            node = self.registry.get_node(node_name)
            if node:
                try:
                    has_changes, reasons = node.check_changes(context)
                    changes[node_name] = (has_changes, reasons)
                    logger.debug(f"Change detection for {node_name}: {has_changes}, reasons: {reasons}")
                except Exception as e:
                    logger.error(f"Error detecting changes for {node_name}: {e}")
                    changes[node_name] = (True, [f"Error in change detection: {e}"])

        return changes

    def plan_execution(
        self, context: FlowContext, target_nodes: set[str] | None = None
    ) -> tuple[list[str], dict[str, list[str]]]:
        """
        Plan the execution order and determine which nodes need to run.

        Args:
            context: Flow execution context
            target_nodes: Optional set of target nodes to execute

        Returns:
            Tuple of (execution_order, change_summary)
        """
        # Determine nodes to consider
        all_nodes = set(self.registry.get_all_nodes().keys()) if target_nodes is None else target_nodes

        # Detect changes
        changes = self.detect_changes(context, all_nodes)

        # Find nodes that have changes or are forced
        changed_nodes = set()
        change_summary = {}

        for node_name, (has_changes, reasons) in changes.items():
            if has_changes or context.force:
                changed_nodes.add(node_name)
                if context.force:
                    # In force mode, prepend force reason
                    change_summary[node_name] = ["Force execution requested", *reasons]
                else:
                    change_summary[node_name] = reasons

        # If force mode, add all target nodes
        if context.force:
            changed_nodes.update(all_nodes)
            for node_name in all_nodes:
                if node_name not in change_summary:
                    change_summary[node_name] = ["Force execution requested"]

        # Find all nodes that need execution (including downstream)
        execution_nodes = self.dependency_graph.find_changed_subgraph(changed_nodes)

        # Get execution order
        execution_order = self.dependency_graph.topological_sort(execution_nodes) if execution_nodes else []

        return execution_order, change_summary

    def execute_node(self, node_name: str, context: FlowContext) -> NodeExecution:
        """
        Execute a single node.

        Args:
            node_name: Name of the node to execute
            context: Flow execution context

        Returns:
            NodeExecution record
        """
        node = self.registry.get_node(node_name)
        if not node:
            raise ValueError(f"Unknown node: {node_name}")

        execution = NodeExecution(node_name=node_name, status=NodeStatus.RUNNING, start_time=datetime.now())

        try:
            logger.info(f"Executing node: {node_name}")

            # Execute the node
            result = node.execute(context)
            execution.result = result

            if result.success:
                execution.status = NodeStatus.COMPLETED
                logger.info(f"Node {node_name} completed successfully")
            else:
                execution.status = NodeStatus.FAILED
                logger.error(f"Node {node_name} failed: {result.error_message}")

        except Exception as e:
            execution.status = NodeStatus.FAILED
            execution.result = FlowResult(success=False, error_message=str(e))
            logger.error(f"Exception executing node {node_name}: {e}")

        finally:
            execution.end_time = datetime.now()

        return execution

    def find_ready_nodes(self, remaining_nodes: set[str], completed_nodes: set[str]) -> set[str]:
        """
        Find nodes that are ready to execute (all dependencies satisfied).

        Args:
            remaining_nodes: Set of nodes that haven't been executed yet
            completed_nodes: Set of nodes that have been successfully completed

        Returns:
            Set of nodes that are ready to execute
        """
        ready_nodes = set()

        for node_name in remaining_nodes:
            node = self.registry.get_node(node_name)
            if not node:
                continue

            # Check if all dependencies are satisfied
            dependencies_satisfied = all(
                dep_name in completed_nodes or dep_name not in remaining_nodes
                for dep_name in node.dependencies
            )

            if dependencies_satisfied:
                ready_nodes.add(node_name)

        return ready_nodes

    def execute_flow(
        self, context: FlowContext, target_nodes: set[str] | None = None
    ) -> dict[str, NodeExecution]:
        """
        Execute the complete flow with dynamic dependency resolution.

        Uses dynamic execution planning where nodes are executed as their
        dependencies become satisfied, allowing for adaptive workflow execution.

        Args:
            context: Flow execution context
            target_nodes: Optional set of target nodes to execute

        Returns:
            Dictionary mapping node names to their execution records
        """
        # Validate flow before execution
        validation_errors = self.validate_flow()
        if validation_errors:
            raise ValueError(f"Flow validation failed: {validation_errors}")

        # Determine initial nodes to consider
        all_nodes = set(self.registry.get_all_nodes().keys()) if target_nodes is None else target_nodes

        # Initial change detection to find starting nodes
        changes = self.detect_changes(context, all_nodes)
        initially_changed = set()
        change_summary = {}

        for node_name, (has_changes, reasons) in changes.items():
            if has_changes or context.force:
                initially_changed.add(node_name)
                if context.force:
                    change_summary[node_name] = ["Force execution requested", *reasons]
                else:
                    change_summary[node_name] = reasons

        if context.force:
            initially_changed.update(all_nodes)
            for node_name in all_nodes:
                if node_name not in change_summary:
                    change_summary[node_name] = ["Force execution requested"]

        # Find all nodes that need execution due to changes (including downstream)
        nodes_needing_execution = self.dependency_graph.find_changed_subgraph(initially_changed)

        # Filter nodes_needing_execution by target_nodes (respects exclusions)
        nodes_needing_execution = nodes_needing_execution & all_nodes

        logger.info(f"Dynamic execution starting with {len(nodes_needing_execution)} potential nodes")
        if context.verbose:
            logger.info(f"Initially changed: {initially_changed}")
            logger.info(f"Nodes needing execution: {nodes_needing_execution}")

        # Dynamic execution state
        executions = {}
        completed_nodes: set[str] = set()
        failed_nodes: set[str] = set()
        remaining_nodes = nodes_needing_execution.copy()
        execution_count = 0

        # Dynamic execution loop
        while remaining_nodes:
            # Find nodes that are ready to execute
            ready_nodes = self.find_ready_nodes(remaining_nodes, completed_nodes)

            if not ready_nodes:
                # No nodes are ready - either dependency cycle or all remaining nodes failed
                logger.error(f"No ready nodes found with {len(remaining_nodes)} remaining")
                logger.error(f"Remaining nodes: {remaining_nodes}")
                logger.error(f"Failed nodes: {failed_nodes}")
                break

            # Execute ready nodes (in deterministic order for consistency)
            for node_name in sorted(ready_nodes):
                execution_count += 1
                logger.info(f"[{execution_count}] Executing: {node_name}")

                # Check if we should skip due to dry run
                if context.dry_run:
                    execution = NodeExecution(
                        node_name=node_name,
                        status=NodeStatus.SKIPPED,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        result=FlowResult(success=True, metadata={"dry_run": True}),
                    )
                    logger.info(f"Skipped {node_name} (dry run mode)")
                    completed_nodes.add(node_name)
                else:
                    execution = self.execute_node(node_name, context)

                    if execution.status == NodeStatus.COMPLETED:
                        completed_nodes.add(node_name)
                        logger.info(f"Node {node_name} completed successfully")
                    elif execution.status == NodeStatus.FAILED:
                        failed_nodes.add(node_name)
                        logger.error(f"Node {node_name} failed")

                executions[node_name] = execution
                context.execution_history.append(execution)
                remaining_nodes.discard(node_name)

                # Stop on failure unless we're in force mode
                if execution.status == NodeStatus.FAILED and not context.force:
                    logger.error(f"Flow execution stopped due to failure in {node_name}")
                    # Mark remaining dependent nodes as skipped
                    for remaining_node in remaining_nodes:
                        skip_execution = NodeExecution(
                            node_name=remaining_node,
                            status=NodeStatus.SKIPPED,
                            start_time=datetime.now(),
                            end_time=datetime.now(),
                            result=FlowResult(success=True, metadata={"skipped_due_to_failure": node_name}),
                        )
                        executions[remaining_node] = skip_execution
                        context.execution_history.append(skip_execution)
                    remaining_nodes.clear()
                    break

        logger.info(
            f"Dynamic execution completed: {len(completed_nodes)} completed, {len(failed_nodes)} failed"
        )
        return executions

    def get_execution_summary(self, executions: dict[str, NodeExecution]) -> dict[str, Any]:
        """
        Generate summary statistics for a flow execution.

        Args:
            executions: Dictionary of node executions

        Returns:
            Summary statistics dictionary
        """
        total_nodes = len(executions)
        completed = sum(1 for e in executions.values() if e.status == NodeStatus.COMPLETED)
        failed = sum(1 for e in executions.values() if e.status == NodeStatus.FAILED)
        skipped = sum(1 for e in executions.values() if e.status == NodeStatus.SKIPPED)

        total_items_processed = sum(
            e.result.items_processed for e in executions.values() if e.result and e.result.success
        )

        total_execution_time = sum(
            e.result.execution_time_seconds
            for e in executions.values()
            if e.result and e.result.execution_time_seconds
        )

        return {
            "total_nodes": total_nodes,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": completed / total_nodes if total_nodes > 0 else 0,
            "total_items_processed": total_items_processed,
            "total_execution_time_seconds": total_execution_time,
        }
