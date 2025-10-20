#!/usr/bin/env python3
"""
Unit tests for topological sort with alphabetical tie-breaking.

Tests the DependencyGraph.topological_sort method to ensure it:
1. Returns nodes in dependency order (dependencies before dependents)
2. Uses alphabetical ordering as tie-breaker for nodes at same level
3. Handles diamond dependencies correctly
"""

from finances.core.flow import FlowContext, FlowNode, FlowNodeRegistry, FlowResult, NoOutputInfo, OutputInfo
from finances.core.flow_engine import DependencyGraph


class MockNode(FlowNode):
    """Mock flow node for testing."""

    def __init__(self, name: str, dependencies: list[str] | None = None):
        super().__init__(name)
        if dependencies:
            self._dependencies = set(dependencies)

    def execute(self, context: FlowContext) -> FlowResult:
        return FlowResult(success=True)

    def get_output_info(self) -> OutputInfo:
        return NoOutputInfo()


class TestTopologicalSortAlphabetical:
    """Test topological sort with alphabetical tie-breaking."""

    def test_topological_sort_returns_nodes_in_dependency_order(self):
        """Test that nodes are sorted in dependency order (dependencies first)."""
        # Create registry with chain: A -> B -> C
        registry = FlowNodeRegistry()

        # Store original registry state
        original_nodes = registry.get_all_nodes().copy()

        try:
            # Register nodes in reverse alphabetical order to test sorting
            node_c = MockNode("C", dependencies=["B"])
            node_b = MockNode("B", dependencies=["A"])
            node_a = MockNode("A", dependencies=[])

            registry.register_node(node_c)
            registry.register_node(node_b)
            registry.register_node(node_a)

            # Create dependency graph and sort
            graph = DependencyGraph(registry)
            sorted_nodes = graph.topological_sort()

            # Verify dependency order: A must come before B, B must come before C
            assert sorted_nodes.index("A") < sorted_nodes.index("B")
            assert sorted_nodes.index("B") < sorted_nodes.index("C")
            assert sorted_nodes == ["A", "B", "C"]

        finally:
            # Restore original registry state
            registry._nodes = original_nodes

    def test_topological_sort_alphabetical_tie_breaking(self):
        """Test that nodes at same dependency level are sorted alphabetically."""
        # Create registry with 3 independent nodes (same level)
        registry = FlowNodeRegistry()

        # Store original registry state
        original_nodes = registry.get_all_nodes().copy()

        try:
            # Register nodes in random order to test alphabetical sorting
            node_zebra = MockNode("zebra", dependencies=[])
            node_apple = MockNode("apple", dependencies=[])
            node_banana = MockNode("banana", dependencies=[])

            registry.register_node(node_zebra)
            registry.register_node(node_apple)
            registry.register_node(node_banana)

            # Create dependency graph and sort
            graph = DependencyGraph(registry)
            sorted_nodes = graph.topological_sort()

            # Verify alphabetical order for nodes at same level
            assert sorted_nodes == ["apple", "banana", "zebra"]

        finally:
            # Restore original registry state
            registry._nodes = original_nodes

    def test_topological_sort_diamond_dependency(self):
        """Test alphabetical tie-breaking with diamond dependency pattern."""
        # Diamond pattern: A -> B, A -> C, B -> D, C -> D
        # Level 0: A
        # Level 1: B, C (alphabetical: B, C)
        # Level 2: D
        registry = FlowNodeRegistry()

        # Store original registry state
        original_nodes = registry.get_all_nodes().copy()

        try:
            # Register nodes in random order
            node_d = MockNode("D", dependencies=["B", "C"])
            node_a = MockNode("A", dependencies=[])
            node_c = MockNode("C", dependencies=["A"])
            node_b = MockNode("B", dependencies=["A"])

            registry.register_node(node_d)
            registry.register_node(node_a)
            registry.register_node(node_c)
            registry.register_node(node_b)

            # Create dependency graph and sort
            graph = DependencyGraph(registry)
            sorted_nodes = graph.topological_sort()

            # Verify dependency constraints
            assert sorted_nodes.index("A") < sorted_nodes.index("B")
            assert sorted_nodes.index("A") < sorted_nodes.index("C")
            assert sorted_nodes.index("B") < sorted_nodes.index("D")
            assert sorted_nodes.index("C") < sorted_nodes.index("D")

            # Verify alphabetical tie-breaking at level 1 (B before C)
            assert sorted_nodes.index("B") < sorted_nodes.index("C")

            # Verify exact order
            assert sorted_nodes == ["A", "B", "C", "D"]

        finally:
            # Restore original registry state
            registry._nodes = original_nodes
