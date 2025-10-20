#!/usr/bin/env python3
"""
Flow Execution Engine

Provides dependency resolution, change detection, and orchestrated execution
of the Financial Flow System.
"""

import logging
import shutil
import sys
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

from .flow import (
    FlowContext,
    FlowNode,
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

        # Initialize queue with nodes that have no dependencies (sorted alphabetically)
        initial_nodes = sorted([node for node in nodes_to_execute if in_degree[node] == 0])
        queue = deque(initial_nodes)
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            # Process dependents and collect newly ready nodes
            next_batch = []
            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_batch.append(dependent)

            # Sort newly ready nodes alphabetically before adding to queue
            next_batch.sort()
            queue.extend(next_batch)

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

    def compute_directory_hash(self, directory: Path) -> str:
        """
        Compute SHA-256 hash of all files in directory using CLI tool.

        Uses sha256sum (Linux) or shasum (macOS) for performance.
        Ignores 'archive/' subdirectory to avoid recursion.

        Args:
            directory: Path to directory to hash

        Returns:
            SHA-256 hex digest string, or empty string if directory doesn't exist
        """
        import hashlib
        import platform
        import subprocess

        if not directory.exists():
            return ""

        # Get all files recursively and sort for deterministic ordering
        files_to_hash = []
        for file_path in sorted(directory.rglob("*")):
            # Skip directories and archive subdirectory
            if not file_path.is_file():
                continue
            if "archive" in file_path.parts:
                continue
            files_to_hash.append(file_path)

        if not files_to_hash:
            return hashlib.sha256().hexdigest()

        # Determine which CLI tool to use based on platform
        system = platform.system()
        hash_cmd = ["shasum", "-a", "256"] if system == "Darwin" else ["sha256sum"]

        try:
            # Process files in batches to avoid "Argument list too long" error
            # System limit is typically ~256KB for command line arguments
            # Use batch size of 100 files to stay well under limit
            batch_size = 100
            combined_hash = hashlib.sha256()

            for i in range(0, len(files_to_hash), batch_size):
                batch = files_to_hash[i : i + batch_size]

                # Run hash command on batch (file paths are from trusted directory walk)
                result = subprocess.run(  # noqa: S603
                    hash_cmd + [str(f) for f in batch],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=directory,
                )

                # Process batch results
                for line in result.stdout.strip().split("\n"):
                    if line:
                        # Extract hash (first field) and filename
                        parts = line.split(maxsplit=1)
                        if len(parts) == 2:
                            file_hash, filename = parts
                            # Hash both filename and file hash for complete coverage
                            combined_hash.update(filename.encode())
                            combined_hash.update(file_hash.encode())

            return combined_hash.hexdigest()

        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            # Fallback to Python implementation if CLI tool not available
            logger.warning(f"CLI hashing tool not available, using Python fallback for {directory}")
            hash_obj = hashlib.sha256()

            for file_path in files_to_hash:
                # Hash file path (relative to base directory)
                relative_path = file_path.relative_to(directory)
                hash_obj.update(str(relative_path).encode())

                # Hash file contents
                hash_obj.update(file_path.read_bytes())

            return hash_obj.hexdigest()

    def archive_existing_data(self, node: FlowNode, output_dir: Path, context: FlowContext) -> None:
        """
        Archive existing data before execution.

        Creates timestamped _pre archive in output_dir/archive/ subdirectory.

        Args:
            node: Flow node being executed
            output_dir: Path to node's output directory
            context: Flow execution context

        Raises:
            SystemExit: If archive operation fails (critical for financial data)
        """
        try:
            archive_dir = output_dir / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Add count suffix to avoid collisions if multiple archives in same second
            base_name = f"{timestamp}_pre"
            archive_path = archive_dir / base_name
            count = 1
            while archive_path.exists():
                archive_path = archive_dir / f"{base_name}_{count}"
                count += 1

            # Copy entire output directory, excluding archive subdirectory
            shutil.copytree(output_dir, archive_path, ignore=shutil.ignore_patterns("archive"))

            # Store archive path in context for audit trail
            context.archive_manifest[f"{node.name}_pre"] = archive_path

        except Exception as e:
            print(f"\nERROR: Failed to archive existing data for '{node.name}'")
            print(f"  Reason: {e}")
            print("  Cannot proceed without backup - flow stopped")
            sys.exit(1)

    def archive_new_data(self, node: FlowNode, output_dir: Path, context: FlowContext) -> None:
        """
        Archive new data after execution if changed.

        Creates timestamped _post archive in output_dir/archive/ subdirectory.

        Args:
            node: Flow node that was executed
            output_dir: Path to node's output directory
            context: Flow execution context

        Raises:
            SystemExit: If archive operation fails (critical for financial data)
        """
        try:
            archive_dir = output_dir / "archive"
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Add count suffix to avoid collisions if multiple archives in same second
            base_name = f"{timestamp}_post"
            archive_path = archive_dir / base_name
            count = 1
            while archive_path.exists():
                archive_path = archive_dir / f"{base_name}_{count}"
                count += 1

            # Copy entire output directory, excluding archive subdirectory
            shutil.copytree(output_dir, archive_path, ignore=shutil.ignore_patterns("archive"))

            # Store archive path in context for audit trail
            context.archive_manifest[f"{node.name}_post"] = archive_path

        except Exception as e:
            print(f"\nERROR: Failed to archive new data for '{node.name}'")
            print(f"  Reason: {e}")
            print("  Data was produced but not archived - flow stopped")
            sys.exit(1)

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

    def topological_sort_nodes(self) -> list[str]:
        """
        Sort all nodes by dependencies with alphabetical tie-breaking.

        Returns:
            Ordered list of node names (dependencies first, alphabetically within levels)
        """
        all_nodes = set(self.registry.get_all_nodes().keys())
        return self.dependency_graph.topological_sort(all_nodes)

    def execute_flow(self) -> dict[str, Any]:
        """
        Execute the complete flow with sequential prompt-validate-execute pattern.

        For each node in topological order:
        1. Display status and prompt user
        2. Validate dependencies have usable data
        3. Archive existing data (if any)
        4. Execute node
        5. Archive new data if changed

        Returns:
            Dictionary with execution summary and results
        """
        # Validate flow before execution
        validation_errors = self.validate_flow()
        if validation_errors:
            print("\nERROR: Flow validation failed")
            for error in validation_errors:
                print(f"  - {error}")
            sys.exit(1)

        # Create flow context
        context = FlowContext(start_time=datetime.now())

        # Get nodes in topological order with alphabetical tie-breaking
        sorted_nodes = self.topological_sort_nodes()

        executed_nodes = []
        skipped_nodes = []

        # Sequential execution loop
        for node_name in sorted_nodes:
            node = self.registry.get_node(node_name)
            if not node:
                print(f"\nERROR: Node '{node_name}' not found in registry")
                sys.exit(1)

            # Get output info for status display
            output_info = node.get_output_info()
            files = output_info.get_output_files()

            # Format status display
            if not files:
                status = "No data"
            else:
                file_count = len(files)
                total_records = sum(f.record_count for f in files)
                try:
                    latest_file = max(files, key=lambda f: f.path.stat().st_mtime)
                    age_days = (
                        datetime.now() - datetime.fromtimestamp(latest_file.path.stat().st_mtime)
                    ).days
                    status = f"{file_count} files with {total_records} total records, {age_days} days old"
                except (FileNotFoundError, OSError):
                    # File deleted between get_output_files() and stat() call
                    status = f"{file_count} files with {total_records} total records (age unknown)"

            # Display and prompt
            print(f"\n[{node_name}]")
            print(f"  Status: {status}")
            response = input("  Run this node? [y/N] ")

            if response.lower() != "y":
                skipped_nodes.append(node_name)
                continue

            # Validate dependencies have usable data
            for dep_name in node.dependencies:
                dep_node = self.registry.get_node(dep_name)
                if not dep_node:
                    print(f"\nERROR: Cannot run '{node_name}'")
                    print(f"  Dependency '{dep_name}' not found in registry")
                    sys.exit(1)

                dep_info = dep_node.get_output_info()
                if not dep_info.is_data_ready():
                    print(f"\nERROR: Cannot run '{node_name}'")
                    print(f"  Dependency '{dep_name}' has no usable data")
                    print(f"  Run the flow again and say 'yes' to '{dep_name}'")
                    sys.exit(1)

            # Get output directory (returns None if node has no persistent output)
            output_dir = node.get_output_dir()

            # Archive existing data (if exists)
            pre_hash = None
            if output_dir and output_dir.exists() and any(output_dir.iterdir()):
                pre_hash = self.compute_directory_hash(output_dir)
                self.archive_existing_data(node, output_dir, context)

            # Execute node
            result = node.execute(context)

            if not result.success:
                print("\nERROR: Node execution failed")
                print(f"  Node: {node_name}")
                print(f"  Error: {result.error_message}")
                sys.exit(1)

            executed_nodes.append(node_name)

            # Display updated status after successful execution
            updated_output_info = node.get_output_info()
            updated_files = updated_output_info.get_output_files()
            if updated_files:
                file_count = len(updated_files)
                total_records = sum(f.record_count for f in updated_files)
                try:
                    latest_file = max(updated_files, key=lambda f: f.path.stat().st_mtime)
                    age_days = (
                        datetime.now() - datetime.fromtimestamp(latest_file.path.stat().st_mtime)
                    ).days
                    updated_status = (
                        f"{file_count} files with {total_records} total records, {age_days} days old"
                    )
                except (FileNotFoundError, OSError):
                    updated_status = f"{file_count} files with {total_records} total records (age unknown)"
                print(f"\n✓ Updated status: {updated_status}")

            # Archive new data if changed
            if output_dir and output_dir.exists():
                post_hash = self.compute_directory_hash(output_dir)
                if post_hash != pre_hash:
                    self.archive_new_data(node, output_dir, context)

        # Print execution summary
        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Executed: {len(executed_nodes)} nodes")
        print(f"Skipped:  {len(skipped_nodes)} nodes")
        if executed_nodes:
            print("\nExecuted nodes:")
            for node_name in executed_nodes:
                print(f"  - {node_name}")
        if skipped_nodes:
            print("\nSkipped nodes:")
            for node_name in skipped_nodes:
                print(f"  - {node_name}")

        return {
            "executed_nodes": executed_nodes,
            "skipped_nodes": skipped_nodes,
            "total_nodes": len(sorted_nodes),
        }

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
