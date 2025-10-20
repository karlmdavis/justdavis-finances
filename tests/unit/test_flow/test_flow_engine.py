#!/usr/bin/env python3
"""
Unit tests for flow execution engine.

Tests dependency resolution, execution orchestration, and change detection integration.
"""

from datetime import datetime
from unittest.mock import patch

from finances.core.flow import (
    FlowContext,
    FlowNode,
    FlowNodeRegistry,
    FlowResult,
    NodeExecution,
    NodeStatus,
    NoOutputInfo,
    OutputInfo,
)
from finances.core.flow_engine import DependencyGraph, FlowExecutionEngine


class MockFlowNode(FlowNode):
    """Mock flow node for testing."""

    def __init__(
        self,
        name: str,
        dependencies: list[str] | None = None,
        check_changes_result: tuple[bool, list[str]] = (False, []),
        execute_result: FlowResult = None,
        execution_callback=None,
    ):
        super().__init__(name)
        if dependencies:
            self._dependencies = set(dependencies)
        self.check_changes_result = check_changes_result
        self.execute_result = execute_result or FlowResult(success=True)
        self.execution_callback = execution_callback
        self.execution_count = 0

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        return self.check_changes_result

    def execute(self, context: FlowContext) -> FlowResult:
        self.execution_count += 1
        if self.execution_callback:
            self.execution_callback(self, context)
        return self.execute_result

    def get_output_info(self) -> OutputInfo:
        return NoOutputInfo()


class TestDependencyGraph:
    """Test DependencyGraph functionality."""

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

    def test_node_depends_on_direct_dependency(self):
        """Test _node_depends_on with direct dependency."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])

        registry.register_node(node1)
        registry.register_node(node2)

        graph = DependencyGraph(registry)

        # node2 directly depends on node1
        assert graph._node_depends_on("node2", "node1") is True
        # node1 does not depend on node2
        assert graph._node_depends_on("node1", "node2") is False

    def test_node_depends_on_transitive_dependency(self):
        """Test _node_depends_on with transitive dependency."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node2"])

        registry.register_node(node1)
        registry.register_node(node2)
        registry.register_node(node3)

        graph = DependencyGraph(registry)

        # node3 transitively depends on node1 (through node2)
        assert graph._node_depends_on("node3", "node1") is True
        # node3 directly depends on node2
        assert graph._node_depends_on("node3", "node2") is True
        # node1 does not depend on node3
        assert graph._node_depends_on("node1", "node3") is False

    def test_node_depends_on_no_dependency(self):
        """Test _node_depends_on with no dependency relationship."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2")

        registry.register_node(node1)
        registry.register_node(node2)

        graph = DependencyGraph(registry)

        # No dependency relationship
        assert graph._node_depends_on("node1", "node2") is False
        assert graph._node_depends_on("node2", "node1") is False

    def test_node_depends_on_missing_node(self):
        """Test _node_depends_on with missing node."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        registry.register_node(node1)

        graph = DependencyGraph(registry)

        # Missing nodes should return False
        assert graph._node_depends_on("node1", "missing") is False
        assert graph._node_depends_on("missing", "node1") is False


class TestFlowExecutionEngine:
    """Test FlowExecutionEngine functionality."""

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

    @patch("builtins.input", return_value="y")
    def test_execute_flow_simple(self, mock_input):
        """Test executing a simple flow."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", check_changes_result=(True, ["Changed"]))
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, []))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)

        result = engine.execute_flow()

        # Verify return format (executed_nodes, skipped_nodes, total_nodes)
        assert "executed_nodes" in result
        assert "skipped_nodes" in result
        assert "total_nodes" in result
        assert len(result["executed_nodes"]) == 2
        assert result["total_nodes"] == 2
        assert node1.execution_count == 1
        assert node2.execution_count == 1

    @patch("builtins.input", return_value="y")
    def test_execute_flow_stop_on_failure(self, mock_input):
        """Test flow execution stops on failure with sys.exit."""
        import pytest

        registry = FlowNodeRegistry()

        node1 = MockFlowNode(
            "node1",
            check_changes_result=(True, ["Changed"]),
            execute_result=FlowResult(success=False, error_message="Failed"),
        )
        node2 = MockFlowNode("node2", dependencies=["node1"], check_changes_result=(False, []))

        registry.register_node(node1)
        registry.register_node(node2)

        engine = FlowExecutionEngine(registry)

        # Node failure causes sys.exit(1)
        with pytest.raises(SystemExit) as exc_info:
            engine.execute_flow()

        assert exc_info.value.code == 1
        assert node1.execution_count == 1
        assert node2.execution_count == 0  # Should not execute due to node1 failure

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

        executions = {"node1": execution1, "node2": execution2, "node3": execution3}

        summary = engine.get_execution_summary(executions)

        assert summary["total_nodes"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["success_rate"] == 1 / 3
        assert summary["total_items_processed"] == 10
        assert summary["total_execution_time_seconds"] == 1.5
