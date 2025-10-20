#!/usr/bin/env python3
"""
Unit tests for core flow system components.

Tests the fundamental flow infrastructure including nodes, contexts, and registries.
"""

from datetime import datetime

from finances.core.flow import (
    FlowContext,
    FlowNode,
    FlowNodeRegistry,
    FlowResult,
    FunctionFlowNode,
    OutputInfo,
    flow_node,
)


class MockFlowNode(FlowNode):
    """Mock flow node for testing."""

    def __init__(
        self,
        name: str,
        dependencies: list[str] | None = None,
        check_changes_result: tuple[bool, list[str]] = (False, []),
        execute_result: FlowResult = None,
    ):
        super().__init__(name)
        if dependencies:
            self._dependencies = set(dependencies)
        self.check_changes_result = check_changes_result
        self.execute_result = execute_result or FlowResult(success=True)

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        return self.check_changes_result

    def execute(self, context: FlowContext) -> FlowResult:
        return self.execute_result

    def get_output_info(self) -> OutputInfo:
        from finances.core.flow import NoOutputInfo

        return NoOutputInfo()


class TestFlowNode:
    """Test FlowNode base class functionality."""

    def test_execution(self):
        """Test node execution."""
        context = FlowContext(start_time=datetime.now())
        result = FlowResult(success=True, items_processed=42)

        node = MockFlowNode("test_node", execute_result=result)
        execution_result = node.execute(context)

        assert execution_result == result
        assert execution_result.success is True
        assert execution_result.items_processed == 42


class TestFunctionFlowNode:
    """Test FunctionFlowNode implementation."""

    def test_function_node_execution(self):
        """Test executing a function node."""

        def test_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=10, metadata={"test": True})

        node = FunctionFlowNode("test_func", test_func, [])
        context = FlowContext(start_time=datetime.now())

        result = node.execute(context)

        assert result.success is True
        assert result.items_processed == 10
        assert result.metadata["test"] is True

    def test_function_node_error_handling(self):
        """Test function node error handling."""

        def failing_func(context: FlowContext) -> FlowResult:
            raise ValueError("Test error")

        node = FunctionFlowNode("failing_func", failing_func, [])
        context = FlowContext(start_time=datetime.now())

        result = node.execute(context)

        assert result.success is False
        assert result.error_message == "Test error"

    def test_function_node_invalid_return(self):
        """Test function node with invalid return type."""

        def invalid_func(context: FlowContext) -> str:  # Wrong return type
            return "not a FlowResult"

        node = FunctionFlowNode("invalid_func", invalid_func, [])
        context = FlowContext(start_time=datetime.now())

        result = node.execute(context)

        assert result.success is False
        assert "must return FlowResult" in result.error_message


class TestFlowNodeRegistry:
    """Test FlowNodeRegistry functionality."""

    def test_validate_dependencies_success(self):
        """Test dependency validation with valid dependencies."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node1", "node2"])

        registry.register_node(node1)
        registry.register_node(node2)
        registry.register_node(node3)

        errors = registry.validate_dependencies()
        assert errors == []

    def test_validate_dependencies_missing(self):
        """Test dependency validation with missing dependencies."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", dependencies=["missing_node"])
        registry.register_node(node1)

        errors = registry.validate_dependencies()
        assert len(errors) == 1
        assert "depends on unknown node 'missing_node'" in errors[0]

    def test_detect_cycles_no_cycles(self):
        """Test cycle detection with no cycles."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1")
        node2 = MockFlowNode("node2", dependencies=["node1"])
        node3 = MockFlowNode("node3", dependencies=["node2"])

        registry.register_node(node1)
        registry.register_node(node2)
        registry.register_node(node3)

        cycles = registry.detect_cycles()
        assert cycles == []

    def test_detect_cycles_simple_cycle(self):
        """Test cycle detection with a simple cycle."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("node1", dependencies=["node2"])
        node2 = MockFlowNode("node2", dependencies=["node1"])

        registry.register_node(node1)
        registry.register_node(node2)

        cycles = registry.detect_cycles()
        assert len(cycles) == 1
        # Should detect the cycle node1 -> node2 -> node1
        cycle = cycles[0]
        assert "node1" in cycle and "node2" in cycle

    def test_overwrite_node_warning(self, caplog):
        """Test that overwriting a node logs a warning."""
        registry = FlowNodeRegistry()

        node1 = MockFlowNode("test_node")
        node2 = MockFlowNode("test_node")

        registry.register_node(node1)

        with caplog.at_level("WARNING"):
            registry.register_node(node2)

        assert "Overwriting existing node: test_node" in caplog.text


class TestFlowNodeDecorator:
    """Test the @flow_node decorator."""

    def test_decorator_execution(self):
        """Test executing a decorated function."""

        @flow_node("decorated_node")
        def test_function(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=42, metadata={"decorated": True})

        context = FlowContext(start_time=datetime.now())
        result = test_function.execute(context)

        assert result.success is True
        assert result.items_processed == 42
        assert result.metadata["decorated"] is True
