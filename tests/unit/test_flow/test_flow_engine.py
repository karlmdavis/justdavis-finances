#!/usr/bin/env python3
"""
Unit tests for flow execution engine.

Tests dependency resolution, execution orchestration, and change detection integration.
"""

import pytest
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Set

from finances.core.flow import (
    FlowNode, FlowContext, FlowResult, NodeExecution, NodeStatus, FlowNodeRegistry
)
from finances.core.flow_engine import DependencyGraph, FlowExecutionEngine


class MockFlowNode(FlowNode):
    """Mock flow node for testing."""

    def __init__(self, name: str, dependencies: List[str] = None,
                 check_changes_result: Tuple[bool, List[str]] = (False, []),
                 execute_result: FlowResult = None,
                 execution_callback=None):
        super().__init__(name)
        if dependencies:
            self._dependencies = set(dependencies)
        self.check_changes_result = check_changes_result
        self.execute_result = execute_result or FlowResult(success=True)
        self.execution_callback = execution_callback
        self.execution_count = 0

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        return self.check_changes_result

    def execute(self, context: FlowContext) -> FlowResult:
        self.execution_count += 1
        if self.execution_callback:
            self.execution_callback(self, context)
        return self.execute_result


class TestDependencyGraph:
    """Test DependencyGraph functionality."""

    def test_graph_creation(self):
        """Test creating a dependency graph."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node1", "node2"])

        registry.register_node(node1)
        registry.register_node(node2)
        registry.register_node(node3)

        graph = DependencyGraph(registry)

        assert len(graph.nodes) == 3
        assert graph.dependencies["node1"] == set()
        assert graph.dependencies["node2"] == {"node1"}
        assert graph.dependencies["node3"] == {"node1", "node2"}

        assert graph.dependents["node1"] == {"node2", "node3"}
        assert graph.dependents["node2"] == {"node3"}
        assert graph.dependents["node3"] == set()

    def test_topological_sort_simple(self):
        """Test topological sorting with simple dependencies."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node2"])

        registry.register_node(node1)
        registry.register_node(node2)
        registry.register_node(node3)

        graph = DependencyGraph(registry)
        sorted_nodes = graph.topological_sort()

        # Should be in dependency order
        assert sorted_nodes.index("node1") < sorted_nodes.index("node2")
        assert sorted_nodes.index("node2") < sorted_nodes.index("node3")

    def test_topological_sort_complex(self):
        """Test topological sorting with complex dependencies."""
        registry = FlowNodeRegistry()

        node_a = MockFlowNode("a")
        node_b = MockFlowNode("b")
        node_c = MockFlowNode("c", dependencies=["a", "b"])
        node_d = MockFlowNode("d", dependencies=["b"])
        node_e = MockFlowNode("e", dependencies=["c", "d"])

        for node in [node_a, node_b, node_c, node_d, node_e]:
            registry.register_node(node)

        graph = DependencyGraph(registry)
        sorted_nodes = graph.topological_sort()

        # Verify dependencies are respected
        assert sorted_nodes.index("a") < sorted_nodes.index("c")
        assert sorted_nodes.index("b") < sorted_nodes.index("c")
        assert sorted_nodes.index("b") < sorted_nodes.index("d")
        assert sorted_nodes.index("c") < sorted_nodes.index("e")
        assert sorted_nodes.index("d") < sorted_nodes.index("e")

    def test_topological_sort_subset(self):
        """Test topological sorting with a subset of nodes."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node2"])
        node4 = MockFlowNode("node4")  # Independent node

        for node in [node1, node2, node3, node4]:
            registry.register_node(node)

        graph = DependencyGraph(registry)

        # Sort only subset
        subset = {"node1", "node2", "node4"}
        sorted_nodes = graph.topological_sort(subset)

        assert len(sorted_nodes) == 3
        assert "node3" not in sorted_nodes
        assert sorted_nodes.index("node1") < sorted_nodes.index("node2")

    def test_execution_levels(self):
        """Test getting execution levels for parallel execution."""
        registry = FlowNodeRegistry()

        # Create diamond dependency structure
        node_a = MockFlowNode("a")
        node_b = MockFlowNode("b", dependencies=["a"])
        node_c = MockFlowNode("c", dependencies=["a"])
        node_d = MockFlowNode("d", dependencies=["b", "c"])

        for node in [node_a, node_b, node_c, node_d]:
            registry.register_node(node)

        graph = DependencyGraph(registry)
        levels = graph.get_execution_levels()

        assert len(levels) == 3
        assert levels[0] == ["a"]  # Level 1: no dependencies
        assert set(levels[1]) == {"b", "c"}  # Level 2: depend on a
        assert levels[2] == ["d"]  # Level 3: depends on b and c

    def test_find_changed_subgraph(self):
        """Test finding nodes that need execution due to changes."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node2"])
        node4 = MockFlowNode("node4")  # Independent

        for node in [node1, node2, node3, node4]:
            registry.register_node(node)

        graph = DependencyGraph(registry)

        # If node1 changes, node2 and node3 should also execute
        changed_subgraph = graph.find_changed_subgraph({"node1"})
        assert changed_subgraph == {"node1", "node2", "node3"}

        # If node2 changes, only node3 should also execute
        changed_subgraph = graph.find_changed_subgraph({"node2"})
        assert changed_subgraph == {"node2", "node3"}

        # If node4 changes, only node4 executes
        changed_subgraph = graph.find_changed_subgraph({"node4"})
        assert changed_subgraph == {"node4"}

    def test_validate_success(self):
        """Test validation with valid graph."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])

        registry.register_node(node1)
        registry.register_node(node2)

        graph = DependencyGraph(registry)
        errors = graph.validate()

        assert errors == []

    def test_validate_missing_dependencies(self):
        """Test validation with missing dependencies."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", dependencies=["missing"])
        registry.register_node(node1)

        graph = DependencyGraph(registry)
        errors = graph.validate()

        assert len(errors) > 0
        assert any("missing" in error for error in errors)

    def test_validate_cycles(self):
        """Test validation with dependency cycles."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", dependencies=["node2"])
        node2 = MockFlowNode("node2", dependencies=["node1"])

        registry.register_node(node1)
        registry.register_node(node2)

        graph = DependencyGraph(registry)
        errors = graph.validate()

        assert len(errors) > 0
        assert any("cycle" in error.lower() for error in errors)


class TestFlowExecutionEngine:
    """Test FlowExecutionEngine functionality."""

    def test_engine_creation(self):
        """Test creating a flow execution engine."""
        registry = FlowNodeRegistry()
        engine = FlowExecutionEngine(registry)

        assert engine.registry == registry
        assert isinstance(engine.dependency_graph, DependencyGraph)

    def test_validate_flow_success(self):
        """Test flow validation with valid flow."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        errors = engine.validate_flow()

        assert errors == []

    def test_validate_flow_errors(self):
        """Test flow validation with errors."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", dependencies=["missing"])
        registry.register_node(node1)

        engine = FlowExecutionEngine(registry)
        errors = engine.validate_flow()

        assert len(errors) > 0

    def test_detect_changes(self):
        """Test change detection across nodes."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Data updated"]))
        node2 = MockFlowNode("node2", check_changes_result=(False, ["No changes"]))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        changes = engine.detect_changes(context)

        assert changes["node1"] == (True, ["Data updated"])
        assert changes["node2"] == (False, ["No changes"])

    def test_detect_changes_subset(self):
        """Test change detection on subset of nodes."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Changed"]))
        node2 = MockFlowNode("node2", check_changes_result=(False, ["No changes"]))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        # Check only node1
        changes = engine.detect_changes(context, {"node1"})

        assert len(changes) == 1
        assert "node1" in changes
        assert "node2" not in changes

    def test_plan_execution_no_changes(self):
        """Test execution planning when no changes detected."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(False, ["No changes"]))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, ["No changes"]))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        execution_order, change_summary = engine.plan_execution(context)

        assert execution_order == []
        assert change_summary == {}

    def test_plan_execution_with_changes(self):
        """Test execution planning with changes detected."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Data changed"]))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, ["No changes"]))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        execution_order, change_summary = engine.plan_execution(context)

        # Both nodes should execute (node2 because node1 changed)
        assert len(execution_order) == 2
        assert execution_order.index("node1") < execution_order.index("node2")
        assert "node1" in change_summary

    def test_plan_execution_force_mode(self):
        """Test execution planning with force mode."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(False, ["No changes"]))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, ["No changes"]))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now(), force=True)

        execution_order, change_summary = engine.plan_execution(context)

        # All nodes should execute in force mode
        assert len(execution_order) == 2
        assert execution_order.index("node1") < execution_order.index("node2")

        # Check that all nodes have force execution in their reasons
        for node_name, reasons in change_summary.items():
            assert any("Force execution" in reason for reason in reasons), f"Node {node_name} missing force reason: {reasons}"

    def test_execute_node_success(self):
        """Test successful node execution."""
        registry = FlowNodeRegistry()
        result = FlowResult(success=True, items_processed=10)
        node = MockFlowNode("test_node", execute_result=result)

        registry.register_node(node)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        execution = engine.execute_node("test_node", context)

        assert execution.node_name == "test_node"
        assert execution.status == NodeStatus.COMPLETED
        assert execution.result == result
        assert execution.start_time is not None
        assert execution.end_time is not None

    def test_execute_node_failure(self):
        """Test node execution failure."""
        registry = FlowNodeRegistry()
        result = FlowResult(success=False, error_message="Test error")
        node = MockFlowNode("test_node", execute_result=result)

        registry.register_node(node)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        execution = engine.execute_node("test_node", context)

        assert execution.node_name == "test_node"
        assert execution.status == NodeStatus.FAILED
        assert execution.result.success is False
        assert execution.result.error_message == "Test error"

    def test_execute_node_exception(self):
        """Test node execution with exception."""
        registry = FlowNodeRegistry()

        def failing_callback(node, context):
            raise RuntimeError("Execution failed")

        node = MockFlowNode("test_node", execution_callback=failing_callback)
        registry.register_node(node)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        execution = engine.execute_node("test_node", context)

        assert execution.node_name == "test_node"
        assert execution.status == NodeStatus.FAILED
        assert execution.result.success is False
        assert "Execution failed" in execution.result.error_message

    def test_execute_flow_simple(self):
        """Test executing a simple flow."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Changed"]))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, []))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        executions = engine.execute_flow(context)

        assert len(executions) == 2
        assert executions["node1"].status == NodeStatus.COMPLETED
        assert executions["node2"].status == NodeStatus.COMPLETED
        assert node1.execution_count == 1
        assert node2.execution_count == 1

    def test_execute_flow_dry_run(self):
        """Test executing flow in dry run mode."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Changed"]))
        registry.register_node(node1)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now(), dry_run=True)

        executions = engine.execute_flow(context)

        assert len(executions) == 1
        assert executions["node1"].status == NodeStatus.SKIPPED
        assert node1.execution_count == 0  # Should not have executed

    def test_execute_flow_stop_on_failure(self):
        """Test flow execution stops on failure."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Changed"]),
                           execute_result=FlowResult(success=False, error_message="Failed"))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, []))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now())

        executions = engine.execute_flow(context)

        assert len(executions) == 2  # node1 failed, node2 skipped due to failure
        assert executions["node1"].status == NodeStatus.FAILED
        assert executions["node2"].status == NodeStatus.SKIPPED
        assert node1.execution_count == 1
        assert node2.execution_count == 0  # Should not execute due to dependency failure

    def test_execute_flow_continue_on_error(self):
        """Test flow execution continues on error with force flag."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Changed"]),
                           execute_result=FlowResult(success=False, error_message="Failed"))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, []))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)
        context = FlowContext(start_time=datetime.now(), force=True)

        executions = engine.execute_flow(context)

        assert len(executions) == 2  # Should continue despite failure
        assert executions["node1"].status == NodeStatus.FAILED
        assert executions["node2"].status == NodeStatus.COMPLETED

    def test_get_execution_summary(self):
        """Test generation of execution summary."""
        registry = FlowNodeRegistry()
        engine = FlowExecutionEngine(registry)

        # Create mock executions
        execution1 = NodeExecution("node1", NodeStatus.COMPLETED)
        execution1.result = FlowResult(success=True, items_processed=10, execution_time_seconds=1.5)

        execution2 = NodeExecution("node2", NodeStatus.FAILED)
        execution2.result = FlowResult(success=False)

        execution3 = NodeExecution("node3", NodeStatus.SKIPPED)
        execution3.result = FlowResult(success=True, metadata={"dry_run": True})

        executions = {
            "node1": execution1,
            "node2": execution2,
            "node3": execution3
        }

        summary = engine.get_execution_summary(executions)

        assert summary["total_nodes"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["success_rate"] == 1/3
        assert summary["total_items_processed"] == 10
        assert summary["total_execution_time_seconds"] == 1.5