#!/usr/bin/env python3
"""
Tests for cash flow analysis integration with the flow system.

Tests the specific integration issue where the flow system calls CLI functions
without required parameters.
"""

import inspect

import pytest

from finances.cli.cashflow import analyze as cashflow_analyze_cmd


class TestCashFlowFlowIntegration:
    """Test cash flow analysis integration with flow system."""

    def test_analyze_function_signature_requires_start_and_end(self):
        """
        Test that demonstrates the actual issue: the analyze function requires
        start and end parameters, but the flow system doesn't provide them.

        This test verifies the function signature to show that start and end
        are required parameters without defaults.
        """
        # Get the actual callback function from the Click command
        actual_function = cashflow_analyze_cmd.callback

        # Inspect the function signature
        sig = inspect.signature(actual_function)

        # Verify that start and end are required parameters (no defaults)
        assert "start" in sig.parameters
        assert "end" in sig.parameters

        # Verify they don't have default values
        start_param = sig.parameters["start"]
        end_param = sig.parameters["end"]

        assert start_param.default == inspect.Parameter.empty, "start parameter has no default value"
        assert end_param.default == inspect.Parameter.empty, "end parameter has no default value"

        # This demonstrates the problem: the flow system calls this function
        # without providing start and end, which will cause a TypeError

    def test_flow_issue_demonstration(self):
        """
        This test demonstrates what the flow system is trying to do and why it fails.
        """
        from unittest.mock import MagicMock

        # Get the actual callback function from the Click command
        actual_function = cashflow_analyze_cmd.callback

        # This is what the flow system does when no date range is provided:
        # It calls the function with the default_kwargs but no start/end
        default_kwargs = {
            "ctx": MagicMock(),  # Flow system provides a mock context
            "accounts": (),
            "exclude_before": None,
            "output_dir": None,
            "format": "png",
        }

        # Add the parameters the flow system adds
        flow_kwargs = default_kwargs.copy()
        flow_kwargs["verbose"] = False

        # Try to create a bound call - this will fail because start/end are missing
        sig = inspect.signature(actual_function)

        with pytest.raises(TypeError) as exc_info:
            # This simulates the flow system trying to bind parameters
            sig.bind(**flow_kwargs)

        # Verify this is the exact error we see in the flow system
        error_message = str(exc_info.value)
        assert (
            "missing a required argument: 'start'" in error_message
            or "missing a required argument: 'end'" in error_message
        )

    def test_solution_works_with_default_values(self):
        """
        Test that shows the solution: if we provide start=None and end=None
        as defaults, the function signature binding will work.
        """
        from unittest.mock import MagicMock

        # Get the actual callback function from the Click command
        actual_function = cashflow_analyze_cmd.callback
        sig = inspect.signature(actual_function)

        # This is what the flow system should do: provide default values
        flow_kwargs_with_defaults = {
            "ctx": MagicMock(),  # Flow system provides a mock context
            "accounts": (),
            "exclude_before": None,
            "output_dir": None,
            "format": "png",
            "verbose": False,
            "start": None,  # Provide default value
            "end": None,  # Provide default value
        }

        # This should work without TypeError
        bound_args = sig.bind(**flow_kwargs_with_defaults)
        assert bound_args is not None

        # The bound arguments should include start and end
        assert "start" in bound_args.arguments
        assert "end" in bound_args.arguments
        assert bound_args.arguments["start"] is None
        assert bound_args.arguments["end"] is None
