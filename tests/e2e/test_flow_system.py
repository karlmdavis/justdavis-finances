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
REPO_ROOT = "/Users/karl/workspaces/justdavis/personal/justdavis-finances"


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
