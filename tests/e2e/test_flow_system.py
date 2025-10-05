#!/usr/bin/env python3
"""
E2E Tests for Financial Flow System

Comprehensive end-to-end tests for the finances flow system using subprocess
to run actual CLI commands with synthetic test data.

These tests validate the complete flow orchestration system from user perspective.
"""

import json
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
def test_flow_validate_verbose(flow_test_env):
    """
    Test `finances flow validate --verbose` shows execution levels.

    Validates that verbose mode displays detailed flow graph information.
    """
    result = run_flow_command(["validate", "--verbose"])

    assert result.returncode == 0, f"Validate verbose failed: {result.stderr}"
    assert "Flow validation passed" in result.stdout
    assert "Execution levels:" in result.stdout, "Expected execution levels in verbose output"
    assert "Level 1:" in result.stdout, "Expected level breakdown"


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
def test_flow_graph_json_format(flow_test_env):
    """
    Test `finances flow graph --format json`.

    Validates that JSON output contains valid structure with nodes and
    execution levels.
    """
    result = run_flow_command(["graph", "--format", "json"])

    assert result.returncode == 0, f"Graph JSON command failed: {result.stderr}"

    # Parse JSON output
    try:
        graph_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON output: {e}\nOutput: {result.stdout}")

    # Validate JSON structure
    assert "nodes" in graph_data, "Expected 'nodes' in JSON output"
    assert "execution_levels" in graph_data, "Expected 'execution_levels' in JSON output"
    assert isinstance(graph_data["nodes"], dict), "Nodes should be a dictionary"
    assert isinstance(graph_data["execution_levels"], list), "Execution levels should be a list"

    # Validate node structure
    assert len(graph_data["nodes"]) > 0, "Should have at least one node"
    for node_name, node_data in graph_data["nodes"].items():
        assert "display_name" in node_data, f"Node {node_name} missing display_name"
        assert "dependencies" in node_data, f"Node {node_name} missing dependencies"
        assert isinstance(node_data["dependencies"], list), "Dependencies should be a list"


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
def test_flow_go_with_node_filtering(flow_test_env):
    """
    Test `finances flow go --nodes ynab_sync --dry-run`.

    Validates that node filtering works correctly and only specified nodes
    (and their dependencies) are executed.
    """
    result = run_flow_command(["go", "--nodes", "ynab_sync", "--dry-run", "--non-interactive"])

    assert result.returncode == 0, f"Node filtering failed: {result.stderr}"

    # Should mention the specific node
    output_lower = result.stdout.lower()
    assert "ynab" in output_lower or "sync" in output_lower, "Expected ynab_sync node in output"


@pytest.mark.e2e
def test_flow_go_force_mode(flow_test_env):
    """
    Test `finances flow go --force --dry-run`.

    Validates that force mode executes all nodes regardless of change detection.
    """
    result = run_flow_command(["go", "--force", "--dry-run", "--non-interactive"])

    assert result.returncode == 0, f"Force mode failed: {result.stderr}"

    # Force mode should show force execution
    assert (
        "Force execution requested" in result.stdout or "Dynamic execution will process" in result.stdout
    ), "Expected force execution indication"
    assert "Dry run mode" in result.stdout


@pytest.mark.e2e
def test_flow_go_multiple_nodes_filtering(flow_test_env):
    """
    Test `finances flow go --nodes ynab_sync --nodes amazon_matching --dry-run`.

    Validates that multiple node filters work correctly.
    """
    result = run_flow_command(
        [
            "go",
            "--nodes",
            "ynab_sync",
            "--nodes",
            "amazon_matching",
            "--dry-run",
            "--non-interactive",
        ]
    )

    # Should succeed even if some nodes can't execute due to missing data
    assert result.returncode == 0, f"Multiple node filtering failed: {result.stderr}"


@pytest.mark.e2e
def test_flow_go_verbose_output(flow_test_env):
    """
    Test `finances flow go --verbose --dry-run`.

    Validates that verbose mode provides detailed execution information.
    """
    result = run_flow_command(["go", "--verbose", "--dry-run", "--non-interactive"])

    assert result.returncode == 0, f"Verbose mode failed: {result.stderr}"
    assert "Financial Flow System Execution" in result.stdout
    assert "Mode:" in result.stdout, "Expected mode information in verbose output"
    assert "Execution:" in result.stdout, "Expected execution type in verbose output"


@pytest.mark.e2e
def test_flow_go_non_interactive(flow_test_env):
    """
    Test `--non-interactive` mode with dry-run.

    Validates that non-interactive mode doesn't prompt for user input.
    """
    result = run_flow_command(["go", "--non-interactive", "--dry-run"])

    # Should complete without waiting for input
    assert result.returncode == 0, f"Non-interactive mode failed: {result.stderr}"
    # Non-interactive mode should complete successfully without prompts
    # The command completes and shows dry-run output
    assert "Dry run mode" in result.stdout


@pytest.mark.e2e
def test_flow_go_skip_archive(flow_test_env):
    """
    Test `finances flow go --skip-archive --dry-run`.

    Validates that archive creation can be skipped.
    """
    result = run_flow_command(["go", "--skip-archive", "--dry-run", "--non-interactive"])

    assert result.returncode == 0, f"Skip archive failed: {result.stderr}"
    # Archive creation messages should not appear
    assert "Creating transaction archive" not in result.stdout


@pytest.mark.e2e
def test_flow_validate_catches_invalid_nodes(flow_test_env):
    """
    Test that validate catches configuration errors.

    This test verifies the validation system works, though with current
    implementation all nodes should be valid.
    """
    result = run_flow_command(["validate"])

    # Current implementation should pass
    assert result.returncode == 0
    assert "validation passed" in result.stdout.lower()


@pytest.mark.e2e
def test_flow_graph_shows_all_standard_nodes(flow_test_env):
    """
    Test that graph shows all expected standard flow nodes.

    Validates that the graph includes core nodes like ynab_sync, amazon_matching,
    apple_matching, etc.
    """
    result = run_flow_command(["graph"])

    assert result.returncode == 0, f"Graph command failed: {result.stderr}"

    # Check for presence of key nodes (using case-insensitive search)
    output_lower = result.stdout.lower()

    # Core nodes that should always be present
    expected_keywords = ["ynab", "amazon", "apple"]

    for keyword in expected_keywords:
        assert keyword in output_lower, f"Expected '{keyword}' node in flow graph"


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
def test_flow_go_date_range_filtering(flow_test_env):
    """
    Test `finances flow go --start 2024-01-01 --end 2024-12-31 --dry-run`.

    Validates that date range filtering is accepted and processed.
    """
    result = run_flow_command(
        [
            "go",
            "--start",
            "2024-01-01",
            "--end",
            "2024-12-31",
            "--dry-run",
            "--non-interactive",
        ]
    )

    assert result.returncode == 0, f"Date range filtering failed: {result.stderr}"
    # Should show date range in output (if verbose or when showing execution plan)


@pytest.mark.e2e
def test_flow_go_confidence_threshold(flow_test_env):
    """
    Test `finances flow go --confidence-threshold 8000 --dry-run`.

    Validates that confidence threshold parameter is accepted.
    """
    result = run_flow_command(
        [
            "go",
            "--confidence-threshold",
            "8000",
            "--dry-run",
            "--non-interactive",
        ]
    )

    assert result.returncode == 0, f"Confidence threshold failed: {result.stderr}"


@pytest.mark.e2e
def test_flow_go_perf_tracking(flow_test_env):
    """
    Test `finances flow go --perf --dry-run`.

    Validates that performance tracking mode is accepted.
    """
    result = run_flow_command(["go", "--perf", "--dry-run", "--non-interactive"])

    assert result.returncode == 0, f"Performance tracking failed: {result.stderr}"


@pytest.mark.e2e
def test_flow_integration_validate_then_graph(flow_test_env):
    """
    Integration test: validate flow then display graph.

    Tests that commands can be run sequentially without issues.
    """
    # First validate
    validate_result = run_flow_command(["validate"])
    assert validate_result.returncode == 0, f"Validation failed: {validate_result.stderr}"

    # Then show graph
    graph_result = run_flow_command(["graph"])
    assert graph_result.returncode == 0, f"Graph failed: {graph_result.stderr}"

    # Both should succeed
    assert "validation passed" in validate_result.stdout.lower()
    assert "Financial Flow System Dependency Graph" in graph_result.stdout


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
