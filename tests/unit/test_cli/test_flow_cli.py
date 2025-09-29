#!/usr/bin/env python3
"""
Unit tests for flow CLI command handling.

Tests the interaction between Click commands and the flow system,
particularly handling of Command objects in flow executors.
"""

import pytest
import click
from datetime import datetime
from unittest.mock import Mock, patch

from finances.core.flow import FlowContext, FlowResult, FunctionFlowNode, safe_get_callable_name as core_safe_get_callable_name
from finances.cli.flow import safe_get_callable_name


class TestFlowCliIntegration:
    """Test integration between CLI commands and flow system."""

    def test_safe_get_callable_name_with_click_command(self):
        """Test safe_get_callable_name handles Click Command objects."""
        # Create a mock Click command that mimics real CLI functions
        @click.command()
        @click.option('--test-param', default='default')
        @click.pass_context
        def mock_command(ctx, test_param):
            """Mock CLI command for testing."""
            return {"executed": True, "param": test_param}

        # Verify Click command doesn't have __name__
        assert not hasattr(mock_command, '__name__')
        assert hasattr(mock_command, 'name')

        # safe_get_callable_name should handle this gracefully
        name = safe_get_callable_name(mock_command)
        assert name == 'mock'  # Click removes the '_command' suffix

        # Both implementations should work the same
        core_name = core_safe_get_callable_name(mock_command)
        assert core_name == 'mock'

    def test_function_flow_node_with_command_object(self):
        """Test FunctionFlowNode handles objects without __name__."""
        # Create a callable object without __name__ attribute
        class MockCallable:
            def __call__(self, context):
                return FlowResult(success=True, items_processed=1)

        mock_callable = MockCallable()

        # Ensure it doesn't have __name__ (like Click Command objects)
        assert not hasattr(mock_callable, '__name__')

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
        assert not hasattr(test_command, '__name__')
        assert hasattr(test_command, 'name')
        assert test_command.name == 'test'  # Click removes '_command' suffix


class TestSafeNameExtraction:
    """Test safe name extraction utilities."""

    def test_extract_name_from_function(self):
        """Test name extraction from regular functions."""
        def test_function():
            pass

        # Should use function __name__
        assert hasattr(test_function, '__name__')
        assert test_function.__name__ == 'test_function'

    def test_extract_name_from_click_command(self):
        """Test name extraction from Click commands."""
        @click.command()
        def test_command():
            pass

        # Click Command objects don't have __name__ but have .name
        assert not hasattr(test_command, '__name__')
        assert hasattr(test_command, 'name')
        assert test_command.name == 'test'  # Click removes '_command' suffix

    def test_extract_name_from_callable_class(self):
        """Test name extraction from callable classes."""
        class TestCallable:
            def __call__(self):
                pass

        callable_obj = TestCallable()

        # Should fall back to class name
        assert not hasattr(callable_obj, '__name__')
        assert callable_obj.__class__.__name__ == 'TestCallable'

    def test_safe_name_extraction_helper(self):
        """Test a safe name extraction helper function."""
        def safe_get_name(obj):
            """Helper to safely extract name from any callable."""
            if hasattr(obj, '__name__'):
                return obj.__name__
            elif hasattr(obj, 'name'):
                return obj.name
            else:
                return obj.__class__.__name__

        # Test with function
        def test_func():
            pass
        assert safe_get_name(test_func) == 'test_func'

        # Test with Click command
        @click.command()
        def test_cmd():
            pass
        assert safe_get_name(test_cmd) == 'test'  # Click removes '_cmd' suffix

        # Test with callable class
        class TestCallable:
            def __call__(self):
                pass
        assert safe_get_name(TestCallable()) == 'TestCallable'