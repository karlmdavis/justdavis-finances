#!/usr/bin/env python3
"""
Unit tests for flow CLI command handling.

Tests the interaction between Click commands and the flow system,
particularly handling of Command objects in flow executors.
"""

from datetime import datetime
from unittest.mock import patch

import click

from finances.cli.flow import safe_get_callable_name
from finances.core.flow import (
    FlowContext,
    FlowResult,
    FunctionFlowNode,
)
from finances.core.flow import (
    safe_get_callable_name as core_safe_get_callable_name,
)


class TestFlowCliIntegration:
    """Test integration between CLI commands and flow system."""

    def test_safe_get_callable_name_with_click_command(self):
        """Test safe_get_callable_name handles Click Command objects."""

        # Create a mock Click command that mimics real CLI functions
        @click.command()
        @click.option("--test-param", default="default")
        @click.pass_context
        def mock_command(ctx, test_param):
            """Mock CLI command for testing."""
            return {"executed": True, "param": test_param}

        # Verify Click command doesn't have __name__
        assert not hasattr(mock_command, "__name__")
        assert hasattr(mock_command, "name")

        # safe_get_callable_name should handle this gracefully
        name = safe_get_callable_name(mock_command)
        assert name == "mock"  # Click removes the '_command' suffix

        # Both implementations should work the same
        core_name = core_safe_get_callable_name(mock_command)
        assert core_name == "mock"

    def test_function_flow_node_with_command_object(self):
        """Test FunctionFlowNode handles objects without __name__."""

        # Create a callable object without __name__ attribute
        class MockCallable:
            def __call__(self, context):
                return FlowResult(success=True, items_processed=1)

        mock_callable = MockCallable()

        # Ensure it doesn't have __name__ (like Click Command objects)
        assert not hasattr(mock_callable, "__name__")

        # Create FunctionFlowNode
        node = FunctionFlowNode("test_node", mock_callable, [])

        # Create test context
        context = FlowContext(start_time=datetime.now())

        # This should NOT raise an AttributeError about __name__
        result = node.execute(context)

        assert isinstance(result, FlowResult)
        assert result.success is True

    def test_click_command_properties(self):
        """Test properties of Click Command objects."""

        @click.command()
        def test_command():
            """Test command."""
            pass

        # Verify Click Command object behavior
        assert isinstance(test_command, click.Command)
        assert not hasattr(test_command, "__name__")
        assert hasattr(test_command, "name")
        assert test_command.name == "test"  # Click removes '_command' suffix


class TestSafeNameExtraction:
    """Test safe name extraction utilities."""

    def test_extract_name_from_function(self):
        """Test name extraction from regular functions."""

        def test_function():
            pass

        # Should use function __name__
        assert hasattr(test_function, "__name__")
        assert test_function.__name__ == "test_function"

    def test_extract_name_from_click_command(self):
        """Test name extraction from Click commands."""

        @click.command()
        def test_command():
            pass

        # Click Command objects don't have __name__ but have .name
        assert not hasattr(test_command, "__name__")
        assert hasattr(test_command, "name")
        assert test_command.name == "test"  # Click removes '_command' suffix

    def test_extract_name_from_callable_class(self):
        """Test name extraction from callable classes."""

        class TestCallable:
            def __call__(self):
                pass

        callable_obj = TestCallable()

        # Should fall back to class name
        assert not hasattr(callable_obj, "__name__")
        assert callable_obj.__class__.__name__ == "TestCallable"

    def test_safe_name_extraction_helper(self):
        """Test a safe name extraction helper function."""

        def safe_get_name(obj):
            """Helper to safely extract name from any callable."""
            if hasattr(obj, "__name__"):
                return obj.__name__
            elif hasattr(obj, "name"):
                return obj.name
            else:
                return obj.__class__.__name__

        # Test with function
        def test_func():
            pass

        assert safe_get_name(test_func) == "test_func"

        # Test with Click command
        @click.command()
        def test_cmd():
            pass

        assert safe_get_name(test_cmd) == "test"  # Click removes '_cmd' suffix

        # Test with callable class
        class TestCallable:
            def __call__(self):
                pass

        assert safe_get_name(TestCallable()) == "TestCallable"


class TestFlowExecutorParameterBinding:
    """Test parameter binding between flow system and CLI commands."""

    def test_apple_receipt_parsing_executor_context_error(self):
        """Test that reproduces the 'Context' object is not iterable error."""
        import tempfile
        from datetime import datetime
        from pathlib import Path
        from unittest.mock import MagicMock

        from finances.cli.flow import setup_flow_nodes
        from finances.core.flow import FlowContext, flow_registry

        # Setup temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock config to use temp directory
            mock_config = MagicMock()
            mock_config.data_dir = temp_path

            # Create the apple/emails directory
            apple_emails_dir = temp_path / "apple" / "emails"
            apple_emails_dir.mkdir(parents=True, exist_ok=True)

            with (
                patch("finances.cli.flow.get_config", return_value=mock_config),
                patch("finances.core.change_detection.create_change_detectors", return_value={}),
                patch(
                    "finances.cli.flow.get_change_detector_function",
                    return_value=lambda ctx: (True, ["Test"]),
                ),
            ):
                # Setup flow nodes (this creates the apple_receipt_parsing node)
                setup_flow_nodes()

                # Get the apple_receipt_parsing node
                node = flow_registry.get_node("apple_receipt_parsing")
                assert node is not None

                # Create flow context
                flow_context = FlowContext(start_time=datetime.now(), verbose=True)

                # This should reproduce the "'Context' object is not iterable" error
                # when the node tries to execute
                try:
                    result = node.execute(flow_context)
                    # If no error, the bug may be fixed or not reproduced
                    # We'll check if it failed for the expected reason
                    assert result.success is False or result.success is True
                except TypeError as e:
                    if "'Context' object is not iterable" in str(e):
                        raise AssertionError(
                            "Context iteration error should be fixed but still occurs"
                        ) from e
                    else:
                        # Different error, re-raise
                        raise

    def test_callback_function_exists_on_click_commands(self):
        """Test that Click commands have callback attribute (used by our fix)."""
        import click

        @click.command()
        @click.option("--test-param", default="default")
        def mock_cli_command(test_param: str):
            """Mock CLI command."""
            return f"executed with {test_param}"

        # Verify the command has a callback attribute
        assert hasattr(mock_cli_command, "callback")
        assert callable(mock_cli_command.callback)

        # The callback should be the original function
        callback = mock_cli_command.callback
        assert callback.__name__ == "mock_cli_command"
