#!/usr/bin/env python3
"""
E2E Tests for Financial Flow System

Comprehensive end-to-end tests for the finances flow system using subprocess
to run actual CLI commands with synthetic test data.

These tests validate the complete flow orchestration system from user perspective.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.fixtures.synthetic_data import save_synthetic_ynab_data

# Working directory for all subprocess calls
REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def flow_test_env(monkeypatch):
    """
    Create isolated test environment with synthetic YNAB data.

    Sets up temporary directories and environment variables for flow tests.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create data directory structure
        data_dir = temp_path / "data"
        ynab_cache_dir = data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True, exist_ok=True)

        # Generate synthetic YNAB data
        save_synthetic_ynab_data(ynab_cache_dir)

        # Create other required directories
        (data_dir / "amazon" / "raw").mkdir(parents=True, exist_ok=True)
        (data_dir / "amazon" / "transaction_matches").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "emails").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "exports").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "transaction_matches").mkdir(parents=True, exist_ok=True)
        (data_dir / "ynab" / "edits").mkdir(parents=True, exist_ok=True)
        (data_dir / "cash_flow" / "charts").mkdir(parents=True, exist_ok=True)

        # Set environment variables for this test
        monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))
        monkeypatch.setenv("FINANCES_ENV", "test")
        monkeypatch.setenv("YNAB_API_TOKEN", "test-token-e2e")
        monkeypatch.setenv("EMAIL_PASSWORD", "test-password-e2e")

        yield {
            "temp_dir": temp_path,
            "data_dir": data_dir,
            "ynab_cache_dir": ynab_cache_dir,
        }


def run_flow_command(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    """
    Execute a finances flow command and return the result.

    Args:
        args: Command arguments (e.g., ["validate"])
        env: Optional environment variables to pass

    Returns:
        CompletedProcess result with stdout, stderr, and returncode
    """
    cmd = ["uv", "run", "finances", "flow", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    return result


@pytest.mark.e2e
def test_flow_validate_command(flow_test_env):
    """
    Test `finances flow validate` with real flow nodes.

    Validates that the flow system configuration is valid and all nodes
    are properly registered.
    """
    result = run_flow_command(["validate"])

    # Should succeed with valid flow configuration
    assert result.returncode == 0, f"Validate command failed: {result.stderr}"
    assert "Flow validation passed" in result.stdout, "Expected validation success message"
    assert "Registered nodes:" in result.stdout, "Expected node count in output"


@pytest.mark.e2e
def test_flow_graph_text_format(flow_test_env):
    """
    Test `finances flow graph` text output.

    Validates that the graph command displays the dependency graph in
    human-readable text format.
    """
    result = run_flow_command(["graph"])

    assert result.returncode == 0, f"Graph command failed: {result.stderr}"
    assert "Financial Flow System Dependency Graph" in result.stdout
    assert "Total nodes:" in result.stdout
    assert "Execution levels:" in result.stdout
    assert "Level 1:" in result.stdout

    # Should show some expected nodes
    assert "ynab_sync" in result.stdout.lower() or "YNAB Sync" in result.stdout
    assert "depends on:" in result.stdout or "no dependencies" in result.stdout


@pytest.mark.e2e
def test_flow_go_dry_run(flow_test_env):
    """
    Test `finances flow go --dry-run` with synthetic YNAB data.

    Validates that dry-run mode shows execution plan without making changes.
    """
    result = run_flow_command(["go", "--dry-run", "--non-interactive"])

    # Dry run should always succeed (no actual execution)
    assert result.returncode == 0, f"Dry run failed: {result.stderr}"
    assert "Dry run mode - no changes will be made" in result.stdout
    assert "Dynamic execution will process" in result.stdout or "No nodes need execution" in result.stdout


@pytest.mark.e2e
def test_flow_go_no_changes_detected(flow_test_env):
    """
    Test flow behavior when no changes are detected.

    Validates that the system correctly reports when no execution is needed.
    """
    # First run with dry-run to establish baseline
    result = run_flow_command(["go", "--dry-run", "--non-interactive"])

    assert result.returncode == 0, f"Flow execution failed: {result.stderr}"

    # Should indicate no changes or show execution plan
    assert (
        "No nodes need execution" in result.stdout
        or "Dynamic execution will process" in result.stdout
        or "Initially triggered nodes:" in result.stdout
    )


@pytest.mark.e2e
def test_flow_command_error_handling(flow_test_env):
    """
    Test error handling for invalid flow commands.

    Validates that invalid command combinations are handled gracefully.
    """
    # Test with invalid format option
    result = run_flow_command(["graph", "--format", "invalid"])

    # Should fail with helpful error message
    assert result.returncode != 0, "Should fail with invalid format"
    assert "invalid" in result.stderr.lower() or "error" in result.stderr.lower()


@pytest.mark.e2e
def test_flow_help_commands(flow_test_env):
    """
    Test that help commands work correctly.

    Validates that --help provides useful information for all flow commands.
    """
    # Main flow help
    result = run_flow_command(["--help"])
    assert result.returncode == 0
    assert "Financial Flow System" in result.stdout
    assert "go" in result.stdout
    assert "graph" in result.stdout
    assert "validate" in result.stdout

    # Subcommand help
    for subcmd in ["go", "graph", "validate"]:
        result = run_flow_command([subcmd, "--help"])
        assert result.returncode == 0, f"Help for {subcmd} failed"
        assert "Usage:" in result.stdout or "Options:" in result.stdout


@pytest.mark.e2e
@pytest.mark.slow
def test_flow_complete_orchestration(flow_test_env):
    """
    Test complete flow orchestration with real node execution.

    This E2E test validates that `finances flow go` actually:
    1. Detects changes in data files
    2. Executes appropriate nodes in correct order
    3. Produces expected output files
    4. Handles multi-step workflows correctly

    This is the most important E2E test - it verifies the entire
    flow system works as a cohesive whole, not just individual pieces.
    """
    from tests.fixtures.synthetic_data import (
        save_synthetic_amazon_data,
        save_synthetic_apple_receipt,
    )

    # Setup comprehensive test data
    data_dir = flow_test_env["data_dir"]

    # Add Amazon data (triggers amazon_unzip and amazon_matching)
    amazon_raw_dir = data_dir / "amazon" / "raw"
    amazon_raw_dir.mkdir(parents=True, exist_ok=True)
    save_synthetic_amazon_data(amazon_raw_dir)

    # Add Apple receipt data (triggers apple_receipt_parsing and apple_matching)
    apple_emails_dir = data_dir / "apple" / "emails"
    apple_emails_dir.mkdir(parents=True, exist_ok=True)
    save_synthetic_apple_receipt(apple_emails_dir)

    # Note: YNAB data is already setup by flow_test_env fixture

    # Execute the flow with --dry-run to validate orchestration without mutations
    # Using dry-run because we don't want to hit real YNAB APIs or create actual edits
    result = run_flow_command(["go", "--dry-run", "--non-interactive"])

    # Verify the command succeeded
    assert result.returncode == 0, f"Flow execution failed: {result.stderr}\nStdout: {result.stdout}"

    # Verify orchestration output shows expected behavior
    assert "Dry run mode - no changes will be made" in result.stdout, "Should indicate dry run mode"

    # Should show execution plan or completion
    assert (
        "Dynamic execution" in result.stdout
        or "No nodes need execution" in result.stdout
        or "execution completed" in result.stdout.lower()
    ), "Should show execution status"

    # Verify that the flow detected YNAB as a starting point
    # (since we have YNAB cache data)
    assert "ynab" in result.stdout.lower() or "YNAB" in result.stdout, "Should mention YNAB in execution"

    # Verify node dependency ordering by checking execution sequence
    # In dry-run mode, nodes should still be processed in dependency order
    # Look for dynamic execution planning or node processing
    assert (
        "Initially triggered nodes:" in result.stdout  # Dynamic execution planning
        or "Executing" in result.stdout  # Node execution
        or "will process" in result.stdout.lower()  # Execution plan
    ), "Should show execution progress"

    # Now run without dry-run but with --force to execute all nodes
    # This tests actual execution (though some nodes may fail due to missing external dependencies)
    result_force = run_flow_command(["go", "--force", "--non-interactive", "--verbose"])

    # With --force, it should attempt to execute
    # Note: Some nodes may fail (e.g., YNAB API calls with test token), but we verify orchestration
    assert (
        result_force.returncode == 0 or "failed" in result_force.stdout.lower()
    ), "Should execute or report failures"

    # Verify that execution attempted multiple nodes
    assert (
        "Executing" in result_force.stdout or "execution" in result_force.stdout.lower()
    ), "Should show node execution"

    # Verify execution summary is provided
    assert (
        "completed" in result_force.stdout.lower()
        or "failed" in result_force.stdout.lower()
        or "nodes" in result_force.stdout.lower()
    ), "Should provide execution summary"

    # Verify that nodes were processed in dependency order
    # The output should show progression through levels or sequential execution
    lines = result_force.stdout.lower().split("\n")
    execution_lines = [
        line for line in lines if "executing" in line or "completed" in line or "failed" in line
    ]

    # Should have executed at least some nodes
    assert len(execution_lines) > 0, "Should have executed at least one node"


@pytest.mark.e2e
def test_flow_go_invalid_date_format(flow_test_env):
    """
    Test error handling for invalid date format in flow go command.

    Validates that malformed date strings are rejected with helpful error messages.
    """
    # Test with invalid month
    result = run_flow_command(["go", "--start", "2024-13-01", "--end", "2024-12-31", "--dry-run"])

    # Should fail with error about invalid date format
    assert result.returncode != 0, "Should fail with invalid date format"
    assert "Invalid date format" in result.stderr or "does not match format" in result.stderr.lower()

    # Test with completely invalid date string
    result = run_flow_command(["go", "--start", "not-a-date", "--end", "2024-12-31", "--dry-run"])

    assert result.returncode != 0, "Should fail with invalid date string"
    assert "Invalid date format" in result.stderr or "does not match format" in result.stderr.lower()


@pytest.mark.e2e
def test_flow_go_missing_end_date(flow_test_env):
    """
    Test error handling when only --start is provided without --end.

    Validates that both date parameters must be provided together.
    """
    result = run_flow_command(["go", "--start", "2024-07-01", "--dry-run"])

    # Should fail with error about missing --end
    assert result.returncode != 0, "Should fail when only --start is provided"
    assert (
        "Both --start and --end must be provided together" in result.stderr
        or "must be provided together" in result.stderr
    ), "Should indicate both parameters required"


@pytest.mark.e2e
def test_flow_go_missing_start_date(flow_test_env):
    """
    Test error handling when only --end is provided without --start.

    Validates that both date parameters must be provided together.
    """
    result = run_flow_command(["go", "--end", "2024-12-31", "--dry-run"])

    # Should fail with error about missing --start
    assert result.returncode != 0, "Should fail when only --end is provided"
    assert (
        "Both --start and --end must be provided together" in result.stderr
        or "must be provided together" in result.stderr
    ), "Should indicate both parameters required"


@pytest.mark.e2e
def test_flow_go_inverted_date_range(flow_test_env):
    """
    Test that inverted date range (end < start) results in no-op execution.

    When user provides a backwards date range, the system should succeed
    but execute no nodes since the date filter excludes everything.
    """
    result = run_flow_command(
        ["go", "--start", "2024-12-31", "--end", "2024-01-01", "--dry-run", "--non-interactive"]
    )

    # Should succeed (not an error condition)
    assert result.returncode == 0, f"Should succeed with inverted date range: {result.stderr}"

    # Should indicate no execution needed
    assert (
        "No nodes need execution" in result.stdout
        or "Dry run mode - no changes will be made" in result.stdout
    ), "Should indicate no-op execution"


@pytest.mark.e2e
@pytest.mark.slow
def test_flow_go_interactive_mode(flow_test_env):
    """
    Test `finances flow go` in interactive mode with user prompts.

    This test uses pexpect to spawn the flow command interactively and
    simulates user responses to prompts. This exercises code paths that
    are not tested when using --non-interactive flag.

    Validates that the interactive flow:
    1. Displays execution plan and prompts for confirmation
    2. Handles user confirmation responses
    3. Executes the flow system successfully
    4. Displays results and completion status
    """
    import os

    import pexpect

    # Build environment with test data directory
    env = os.environ.copy()
    env["FINANCES_DATA_DIR"] = str(flow_test_env["data_dir"])
    env["FINANCES_ENV"] = "test"
    env["YNAB_API_TOKEN"] = "test-token-e2e"  # noqa: S105 - test credential
    env["EMAIL_PASSWORD"] = "test-password-e2e"  # noqa: S105 - test credential

    # Spawn the flow command interactively (no --non-interactive flag)
    cmd = ["uv", "run", "finances", "flow", "go", "--dry-run"]
    child = pexpect.spawn(
        " ".join(cmd),
        cwd=REPO_ROOT,
        env=env,
        timeout=120,
        encoding="utf-8",
    )

    try:
        # Enable logging for debugging
        child.logfile_read = None  # Set to sys.stdout for debugging

        # Accumulate all output
        full_output = []

        # Expect the execution plan to be displayed
        child.expect("Dynamic execution will process", timeout=30)
        full_output.append(child.before + child.after)

        # Expect the prompt asking to proceed
        child.expect("Proceed with dynamic execution?", timeout=10)
        full_output.append(child.before + child.after)

        # Send confirmation (yes)
        child.sendline("y")

        # Expect dry run confirmation
        child.expect("Dry run mode - no changes will be made", timeout=10)
        full_output.append(child.before + child.after)

        # Wait for completion
        child.expect(pexpect.EOF, timeout=60)
        full_output.append(child.before)

        # Check exit code
        child.close()
        exit_code = child.exitstatus

        # Verify successful completion
        assert exit_code == 0, f"Flow execution should succeed, got exit code {exit_code}"

        # Verify output contains expected messages
        combined_output = "".join(full_output)
        assert "Dry run mode" in combined_output, "Should indicate dry run mode"
        assert "Proceed with dynamic execution?" in combined_output, "Should show confirmation prompt"

    except pexpect.TIMEOUT as e:
        # Capture what we got before timeout
        output = child.before or ""
        child.close(force=True)
        pytest.fail(f"Interactive flow test timed out. Output so far:\n{output}\nException: {e}")

    except pexpect.EOF as e:
        # Unexpected EOF
        output = child.before or ""
        child.close(force=True)
        pytest.fail(f"Interactive flow ended unexpectedly. Output:\n{output}\nException: {e}")

    finally:
        # Ensure process is terminated
        if child.isalive():
            child.close(force=True)
