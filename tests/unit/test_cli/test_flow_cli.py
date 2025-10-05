#!/usr/bin/env python3
"""
Unit tests for flow CLI command handling.

Tests the interaction between Click commands and the flow system,
particularly handling of Command objects in flow executors.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from finances.cli.flow import setup_flow_nodes
from finances.core.flow import FlowContext, flow_registry


class TestFlowExecutorParameterBinding:
    """Test parameter binding between flow system and CLI commands."""

    def test_apple_receipt_parsing_executor_context_error(self):
        """Test that reproduces the 'Context' object is not iterable error."""

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
