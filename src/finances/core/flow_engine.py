#!/usr/bin/env python3
"""
Flow Execution Engine

Provides dependency resolution, change detection, and orchestrated execution
of the Financial Flow System.
"""

from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
import logging

from .flow import (
    FlowNode, FlowContext, FlowResult, NodeExecution, NodeStatus,
    FlowNodeRegistry, flow_registry
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
        self.dependents: Dict[str, Set[str]] = defaultdict(set)  # nodes that depend on this node
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)  # nodes this node depends on

        self._build_graph()

    def _build_graph(self) -> None:
        """Build the dependency graph from registered nodes."""
        for node_name, node in self.nodes.items():
            self.dependencies[node_name] = node.dependencies.copy()

            # Build reverse mapping (dependents)
            for dep_name in node.dependencies:
                self.dependents[dep_name].add(node_name)

    def validate(self) -> List[str]:
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

    def topological_sort(self, nodes_to_execute: Optional[Set[str]] = None) -> List[str]:
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
        in_degree = defaultdict(int)
        graph = defaultdict(set)

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

    def get_execution_levels(self, nodes_to_execute: Optional[Set[str]] = None) -> List[List[str]]:
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
        processed = set()

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

    def find_changed_subgraph(self, changed_nodes: Set[str]) -> Set[str]:
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


class FlowExecutionEngine:
    """
    Orchestrates execution of the Financial Flow System.

    Manages dependency resolution, change detection, progress reporting,
    and coordinated execution of all flow nodes.
    """

    def __init__(self, registry: Optional[FlowNodeRegistry] = None):
        """
        Initialize flow execution engine.

        Args:
            registry: FlowNodeRegistry to use (defaults to global registry)
        """
        self.registry = registry or flow_registry
        self.dependency_graph = DependencyGraph(self.registry)

    def validate_flow(self) -> List[str]:
        """
        Validate the entire flow for errors.

        Returns:
            List of validation error messages
        """
        return self.dependency_graph.validate()

    def detect_changes(self, context: FlowContext,
                      nodes_to_check: Optional[Set[str]] = None) -> Dict[str, Tuple[bool, List[str]]]:
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

    def plan_execution(self, context: FlowContext,
                      target_nodes: Optional[Set[str]] = None) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Plan the execution order and determine which nodes need to run.

        Args:
            context: Flow execution context
            target_nodes: Optional set of target nodes to execute

        Returns:
            Tuple of (execution_order, change_summary)
        """
        # Determine nodes to consider
        if target_nodes is None:
            all_nodes = set(self.registry.get_all_nodes().keys())
        else:
            all_nodes = target_nodes

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
                    change_summary[node_name] = ["Force execution requested"] + reasons
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
        if execution_nodes:
            execution_order = self.dependency_graph.topological_sort(execution_nodes)
        else:
            execution_order = []

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

        execution = NodeExecution(
            node_name=node_name,
            status=NodeStatus.RUNNING,
            start_time=datetime.now()
        )

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
            execution.result = FlowResult(
                success=False,
                error_message=str(e)
            )
            logger.error(f"Exception executing node {node_name}: {e}")

        finally:
            execution.end_time = datetime.now()

        return execution

    def execute_flow(self, context: FlowContext,
                    target_nodes: Optional[Set[str]] = None) -> Dict[str, NodeExecution]:
        """
        Execute the complete flow with dependency resolution.

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

        # Plan execution
        execution_order, change_summary = self.plan_execution(context, target_nodes)

        logger.info(f"Planned execution for {len(execution_order)} nodes")
        if context.verbose:
            logger.info(f"Execution order: {execution_order}")
            logger.info(f"Changes detected: {change_summary}")

        # Execute nodes in order
        executions = {}

        for i, node_name in enumerate(execution_order, 1):
            logger.info(f"[{i}/{len(execution_order)}] Executing: {node_name}")

            # Check if we should skip due to dry run
            if context.dry_run:
                execution = NodeExecution(
                    node_name=node_name,
                    status=NodeStatus.SKIPPED,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    result=FlowResult(success=True, metadata={"dry_run": True})
                )
                logger.info(f"Skipped {node_name} (dry run mode)")
            else:
                execution = self.execute_node(node_name, context)

            executions[node_name] = execution
            context.execution_history.append(execution)

            # Stop on failure unless we're in continue-on-error mode
            if execution.status == NodeStatus.FAILED and not context.force:
                logger.error(f"Flow execution stopped due to failure in {node_name}")
                break

        return executions

    def get_execution_summary(self, executions: Dict[str, NodeExecution]) -> Dict[str, Any]:
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
            e.result.items_processed for e in executions.values()
            if e.result and e.result.success
        )

        total_execution_time = sum(
            e.result.execution_time_seconds for e in executions.values()
            if e.result and e.result.execution_time_seconds
        )

        return {
            "total_nodes": total_nodes,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": completed / total_nodes if total_nodes > 0 else 0,
            "total_items_processed": total_items_processed,
            "total_execution_time_seconds": total_execution_time
        }