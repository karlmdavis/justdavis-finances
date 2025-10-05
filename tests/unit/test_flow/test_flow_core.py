#!/usr/bin/env python3
"""
Unit tests for core flow system components.

Tests the fundamental flow infrastructure including nodes, contexts, and registries.
"""

import tempfile
from datetime import date, datetime
from pathlib import Path

from finances.core.flow import (
    FlowContext,
    FlowNode,
    FlowNodeRegistry,
    FlowResult,
    FunctionFlowNode,
    flow_node,
)


class TestFlowResult:
    """Test FlowResult dataclass functionality."""

    def test_basic_result_creation(self):
        """Test creating a basic FlowResult."""
        result = FlowResult(success=True, items_processed=10)

        assert result.success is True
        assert result.items_processed == 10
        assert result.new_items == 0
        assert result.updated_items == 0
        assert result.outputs == []
        assert result.requires_review is False
        assert result.review_instructions is None
        assert result.execution_time_seconds is None
        assert result.metadata == {}
        assert result.error_message is None

    def test_complete_result_creation(self):
        """Test creating a complete FlowResult with all fields."""
        temp_dir = Path(tempfile.gettempdir())
        outputs = [temp_dir / "test1.json", temp_dir / "test2.json"]
        metadata = {"test_key": "test_value"}

        result = FlowResult(
            success=True,
            items_processed=100,
            new_items=25,
            updated_items=75,
            outputs=outputs,
            requires_review=True,
            review_instructions="Review the generated splits",
            execution_time_seconds=15.5,
            metadata=metadata,
            error_message=None,
        )

        assert result.success is True
        assert result.items_processed == 100
        assert result.new_items == 25
        assert result.updated_items == 75
        assert result.outputs == outputs
        assert result.requires_review is True
        assert result.review_instructions == "Review the generated splits"
        assert result.execution_time_seconds == 15.5
        assert result.metadata == metadata
        assert result.error_message is None

    def test_failure_result(self):
        """Test creating a failure FlowResult."""
        result = FlowResult(success=False, error_message="Test error occurred")

        assert result.success is False
        assert result.error_message == "Test error occurred"


class TestFlowContext:
    """Test FlowContext dataclass functionality."""

    def test_basic_context_creation(self):
        """Test creating a basic FlowContext."""
        start_time = datetime.now()
        context = FlowContext(start_time=start_time)

        assert context.start_time == start_time
        assert context.interactive is True
        assert context.performance_tracking is False
        assert context.confidence_threshold == 10000
        assert context.date_range is None
        assert context.archive_manifest == {}
        assert context.execution_history == []
        assert context.dry_run is False
        assert context.force is False
        assert context.verbose is False

    def test_complete_context_creation(self):
        """Test creating a complete FlowContext with all fields."""
        start_time = datetime.now()
        date_range = (date(2024, 1, 1), date(2024, 12, 31))
        temp_dir = Path(tempfile.gettempdir())
        archive_manifest = {"domain1": temp_dir / "archive1.tar.gz"}

        context = FlowContext(
            start_time=start_time,
            interactive=False,
            performance_tracking=True,
            confidence_threshold=8000,
            date_range=date_range,
            archive_manifest=archive_manifest,
            dry_run=True,
            force=True,
            verbose=True,
        )

        assert context.start_time == start_time
        assert context.interactive is False
        assert context.performance_tracking is True
        assert context.confidence_threshold == 8000
        assert context.date_range == date_range
        assert context.archive_manifest == archive_manifest
        assert context.dry_run is True
        assert context.force is True
        assert context.verbose is True


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


class TestFlowNode:
    """Test FlowNode base class functionality."""

    def test_node_creation(self):
        """Test creating a flow node."""
        node = MockFlowNode("test_node")

        assert node.name == "test_node"
        assert node.dependencies == set()
        assert node.get_display_name() == "Test Node"
        assert node.get_active_form() == "Processing Test Node"

    def test_node_with_dependencies(self):
        """Test creating a flow node with dependencies."""
        dependencies = ["node1", "node2"]
        node = MockFlowNode("test_node", dependencies=dependencies)

        assert node.dependencies == {"node1", "node2"}

    def test_display_name_transformations(self):
        """Test display name transformations."""
        sync_node = MockFlowNode("ynab_sync")
        match_node = MockFlowNode("amazon_match")
        analysis_node = MockFlowNode("cash_flow_analysis")

        assert sync_node.get_display_name() == "Ynab Sync"
        assert sync_node.get_active_form() == "Syncing Ynab"

        assert match_node.get_display_name() == "Amazon Match"
        assert match_node.get_active_form() == "Matching Amazon"

        assert analysis_node.get_display_name() == "Cash Flow Analysis"
        assert analysis_node.get_active_form() == "Analyzing Cash Flow"

    def test_change_detection(self):
        """Test change detection interface."""
        context = FlowContext(start_time=datetime.now())

        # Test no changes
        node1 = MockFlowNode("node1", check_changes_result=(False, ["No changes"]))
        has_changes, reasons = node1.check_changes(context)
        assert has_changes is False
        assert reasons == ["No changes"]

        # Test has changes
        node2 = MockFlowNode("node2", check_changes_result=(True, ["Data updated", "New files"]))
        has_changes, reasons = node2.check_changes(context)
        assert has_changes is True
        assert reasons == ["Data updated", "New files"]

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

    def test_function_node_creation(self):
        """Test creating a function-based flow node."""

        def test_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=5)

        node = FunctionFlowNode("test_func", test_func, ["dep1", "dep2"])

        assert node.name == "test_func"
        assert node.dependencies == {"dep1", "dep2"}
        assert node.func == test_func

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

    def test_function_node_with_performance_tracking(self):
        """Test function node with performance tracking enabled."""

        def test_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=1)

        node = FunctionFlowNode("test_func", test_func, [])
        context = FlowContext(start_time=datetime.now(), performance_tracking=True)

        result = node.execute(context)

        assert result.success is True
        assert result.execution_time_seconds is not None
        assert result.execution_time_seconds >= 0

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

    def test_custom_change_detector(self):
        """Test function node with custom change detector."""

        def test_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True)

        def change_detector(context: FlowContext) -> tuple[bool, list[str]]:
            return True, ["Custom change detected"]

        node = FunctionFlowNode("test_func", test_func, [])
        node.set_change_detector(change_detector)

        context = FlowContext(start_time=datetime.now())
        has_changes, reasons = node.check_changes(context)

        assert has_changes is True
        assert reasons == ["Custom change detected"]


class TestFlowNodeRegistry:
    """Test FlowNodeRegistry functionality."""

    def test_registry_creation(self):
        """Test creating an empty registry."""
        registry = FlowNodeRegistry()

        assert len(registry.get_all_nodes()) == 0

    def test_register_node(self):
        """Test registering a node."""
        registry = FlowNodeRegistry()
        node = MockFlowNode("test_node")

        registry.register_node(node)

        assert len(registry.get_all_nodes()) == 1
        assert registry.get_node("test_node") == node

    def test_register_function_node(self):
        """Test registering a function as a node."""
        registry = FlowNodeRegistry()

        def test_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True)

        registry.register_function_node("test_func", test_func, ["dep1"])

        node = registry.get_node("test_func")
        assert node is not None
        assert node.name == "test_func"
        assert node.dependencies == {"dep1"}

    def test_register_function_node_with_change_detector(self):
        """Test registering a function node with change detector."""
        registry = FlowNodeRegistry()

        def test_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True)

        def change_detector(context: FlowContext) -> tuple[bool, list[str]]:
            return True, ["Test change"]

        registry.register_function_node("test_func", test_func, change_detector=change_detector)

        node = registry.get_node("test_func")
        context = FlowContext(start_time=datetime.now())
        has_changes, reasons = node.check_changes(context)

        assert has_changes is True
        assert reasons == ["Test change"]

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

    def test_decorator_basic(self):
        """Test basic decorator usage."""

        @flow_node("decorated_node")
        def test_function(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=1)

        assert isinstance(test_function, FunctionFlowNode)
        assert test_function.name == "decorated_node"
        assert test_function.dependencies == set()

    def test_decorator_with_dependencies(self):
        """Test decorator with dependencies."""

        @flow_node("decorated_node", depends_on=["dep1", "dep2"])
        def test_function(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=1)

        assert isinstance(test_function, FunctionFlowNode)
        assert test_function.name == "decorated_node"
        assert test_function.dependencies == {"dep1", "dep2"}

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
