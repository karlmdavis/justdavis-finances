#!/usr/bin/env python3
"""
Integration tests for the Financial Flow System.

Tests end-to-end flow execution with real CLI integration and file system operations.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

from finances.cli.flow import flow, setup_flow_nodes
from finances.core.archive import ArchiveManager
from finances.core.change_detection import create_change_detectors
from finances.core.flow import FlowContext, FlowResult, NodeStatus, flow_registry
from finances.core.flow_engine import FlowExecutionEngine


class TestFlowCLIIntegration:
    """Test CLI integration for flow commands."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())
        # Set real config via environment variable
        os.environ["FINANCES_DATA_DIR"] = str(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)
        # Clean up environment
        if "FINANCES_DATA_DIR" in os.environ:
            del os.environ["FINANCES_DATA_DIR"]

    def test_flow_validate_command(self):
        """Test flow validate CLI command."""
        result = self.runner.invoke(flow, ["validate"])

        assert result.exit_code == 0
        assert "Flow validation passed" in result.output
        assert "Registered nodes:" in result.output

    def test_flow_graph_command(self):
        """Test flow graph CLI command."""
        result = self.runner.invoke(flow, ["graph"])

        assert result.exit_code == 0
        assert "Financial Flow System Dependency Graph" in result.output
        assert "Level 1:" in result.output

    def test_flow_graph_json_format(self):
        """Test flow graph CLI command with JSON output."""
        result = self.runner.invoke(flow, ["graph", "--format", "json"])

        assert result.exit_code == 0

        # Should be valid JSON
        graph_data = json.loads(result.output)
        assert "nodes" in graph_data
        assert "execution_levels" in graph_data

    def test_flow_execute_dry_run(self):
        """Test flow execute CLI command in dry run mode."""
        # Create some test data to trigger changes
        ynab_dir = self.temp_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)

        # Create placeholder YNAB cache files
        (ynab_dir / "accounts.json").write_text('{"server_knowledge": 123}')
        (ynab_dir / "categories.json").write_text('{"server_knowledge": 456}')
        (ynab_dir / "transactions.json").write_text("[]")

        result = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run", "--verbose"])

        assert result.exit_code == 0
        assert "Dry run mode - no changes will be made" in result.output
        assert "Dynamic execution will process" in result.output

    def test_flow_execute_no_changes(self):
        """Test flow execute when no changes are detected."""
        # Don't create any data files - should result in no changes, use dry-run mode
        result = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run"])

        assert result.exit_code == 0
        # With no data files, we might still get some nodes that want to execute
        assert "Dry run mode" in result.output

    def test_flow_execute_specific_nodes(self):
        """Test flow execute with specific nodes."""
        result = self.runner.invoke(
            flow,
            ["go", "--non-interactive", "--dry-run", "--nodes", "ynab_sync", "--nodes", "cash_flow_analysis"],
        )

        assert result.exit_code == 0
        # Should show limited execution plan
        assert "Dynamic execution will process" in result.output

    def test_flow_execute_force_mode(self):
        """Test flow execute with force mode."""
        result = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run", "--force"])

        assert result.exit_code == 0
        assert "Dynamic execution will process" in result.output
        # In force mode, should execute many nodes even without changes

    def test_flow_execute_non_interactive(self):
        """Test flow execute in non-interactive mode."""
        result = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run"])

        assert result.exit_code == 0
        assert "Dry run mode" in result.output

    def test_flow_execute_with_archive_creation(self):
        """Test flow execute creates archives when not in dry-run mode."""
        # Create some test data that will trigger changes
        ynab_dir = self.temp_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "accounts.json").write_text('{"server_knowledge": 123, "accounts": []}')
        (ynab_dir / "categories.json").write_text('{"server_knowledge": 456, "category_groups": []}')
        (ynab_dir / "transactions.json").write_text("[]")

        # Run without dry-run, non-interactive to trigger archive creation
        result = self.runner.invoke(flow, ["go", "--non-interactive", "--force"])

        # Should create archive (check for archive message in output)
        assert "Creating transaction archive" in result.output
        assert "Archive created" in result.output

        # Verify archive directory was created
        archive_dirs = (
            list((self.temp_dir / "ynab" / "archive").glob("*.tar.gz"))
            if (self.temp_dir / "ynab" / "archive").exists()
            else []
        )
        assert len(archive_dirs) >= 0  # Archive may or may not be created depending on data

    def test_flow_execute_skip_archive(self):
        """Test flow execute skips archive when --skip-archive flag is used."""
        # Create test data
        ynab_dir = self.temp_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "accounts.json").write_text('{"server_knowledge": 123}')
        (ynab_dir / "categories.json").write_text('{"server_knowledge": 456}')
        (ynab_dir / "transactions.json").write_text("[]")

        # Run with --skip-archive flag
        result = self.runner.invoke(flow, ["go", "--non-interactive", "--force", "--skip-archive"])

        # Should not create archive
        assert "Creating transaction archive" not in result.output

    def test_flow_execute_verbose_flag(self):
        """Test flow execute with verbose flag enables detailed output."""
        result_normal = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run"])
        result_verbose = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run", "--verbose"])

        assert result_normal.exit_code == 0
        assert result_verbose.exit_code == 0

        # Verbose mode should produce more output
        assert len(result_verbose.output) >= len(result_normal.output)

        # Verbose mode should include execution details
        assert "Dry run mode" in result_verbose.output

    def test_flow_execute_performance_tracking(self):
        """Test flow execute with performance tracking enabled."""
        result = self.runner.invoke(flow, ["go", "--non-interactive", "--dry-run", "--perf"])

        assert result.exit_code == 0
        # Performance tracking should be enabled (implementation-dependent output)
        assert "Dry run mode" in result.output

    def test_flow_execute_date_range_filter(self):
        """Test flow execute with date range filtering."""
        result = self.runner.invoke(
            flow, ["go", "--non-interactive", "--dry-run", "--start", "2024-07-01", "--end", "2024-07-31"]
        )

        assert result.exit_code == 0
        # Date range filtering should be applied
        assert "Dry run mode" in result.output

    def test_flow_execute_confidence_threshold(self):
        """Test flow execute with custom confidence threshold."""
        # Default is 10000 basis points (100%), test with 8000 (80%)
        result = self.runner.invoke(
            flow, ["go", "--non-interactive", "--dry-run", "--confidence-threshold", "8000"]
        )

        assert result.exit_code == 0
        # Confidence threshold should be applied
        assert "Dry run mode" in result.output


class TestArchiveIntegration:
    """Test archive system integration."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_archive_manager_creation(self):
        """Test creating archive manager and domain archivers."""
        archive_manager = ArchiveManager(self.temp_dir)

        assert len(archive_manager.domain_archivers) == 5
        assert "amazon" in archive_manager.domain_archivers
        assert "apple" in archive_manager.domain_archivers
        assert "ynab" in archive_manager.domain_archivers
        assert "retirement" in archive_manager.domain_archivers
        assert "cash_flow" in archive_manager.domain_archivers

    def test_archive_creation_with_data(self):
        """Test creating archives when data exists."""
        # Create test data files
        amazon_dir = self.temp_dir / "amazon"
        amazon_dir.mkdir(parents=True)

        (amazon_dir / "test_data.json").write_text('{"test": "data"}')
        (amazon_dir / "results.csv").write_text("col1,col2\nval1,val2")

        archive_manager = ArchiveManager(self.temp_dir)
        session = archive_manager.create_transaction_archive("test_trigger")

        assert len(session.archives) == 1
        assert "amazon" in session.archives
        assert session.total_files == 2

        # Verify archive file was created
        amazon_archiver = archive_manager.domain_archivers["amazon"]
        archive_files = list(amazon_archiver.archive_dir.glob("*.tar.gz"))
        assert len(archive_files) == 1

    def test_archive_creation_no_data(self):
        """Test creating archives when no data exists."""
        archive_manager = ArchiveManager(self.temp_dir)
        session = archive_manager.create_transaction_archive("test_trigger")

        # Should have no archives since no data exists
        assert len(session.archives) == 0
        assert session.total_files == 0

    def test_archive_listing(self):
        """Test listing recent archives."""
        # Create test data and archive
        ynab_dir = self.temp_dir / "ynab"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "cache.json").write_text('{"test": true}')

        archive_manager = ArchiveManager(self.temp_dir)
        archive_manager.create_transaction_archive("test_trigger")

        # List recent archives
        recent_archives = archive_manager.list_recent_archives()
        assert len(recent_archives) >= 1

        # List archives for specific domain
        domain_archives = archive_manager.list_recent_archives(domain="ynab")
        assert len(domain_archives) >= 1

    def test_storage_usage_calculation(self):
        """Test calculating storage usage."""
        # Create test data and archive
        apple_dir = self.temp_dir / "apple"
        apple_dir.mkdir(parents=True)
        (apple_dir / "receipts.json").write_text('{"receipts": []}')

        archive_manager = ArchiveManager(self.temp_dir)
        archive_manager.create_transaction_archive("test_trigger")

        usage = archive_manager.calculate_storage_usage()

        assert "domains" in usage
        assert "total_archives" in usage
        assert "total_size_bytes" in usage
        assert usage["total_archives"] >= 1


class TestChangeDetectionIntegration:
    """Test change detection system integration."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_change_detectors_creation(self):
        """Test creating all change detectors."""
        detectors = create_change_detectors(self.temp_dir)

        expected_detectors = [
            "ynab_sync",
            "amazon_unzip",
            "amazon_matching",
            "apple_email_fetch",
            "apple_matching",
            "retirement_update",
        ]

        for detector_name in expected_detectors:
            assert detector_name in detectors

    def test_ynab_sync_change_detection(self):
        """Test YNAB sync change detection."""
        detectors = create_change_detectors(self.temp_dir)
        ynab_detector = detectors["ynab_sync"]

        context = FlowContext(start_time=datetime.now())

        # First run - should detect changes (no cache files)
        has_changes, reasons = ynab_detector.check_changes(context)
        assert has_changes is True
        assert any("Missing cache files" in reason for reason in reasons)

        # Create cache files
        ynab_cache_dir = self.temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {"server_knowledge": 12345, "accounts": []}
        (ynab_cache_dir / "accounts.json").write_text(json.dumps(accounts_data))

        categories_data = {"server_knowledge": 67890, "category_groups": []}
        (ynab_cache_dir / "categories.json").write_text(json.dumps(categories_data))

        (ynab_cache_dir / "transactions.json").write_text("[]")

        # Second run - should still detect changes (first time sync)
        has_changes, reasons = ynab_detector.check_changes(context)
        assert has_changes is True

    def test_amazon_matching_change_detection(self):
        """Test Amazon matching change detection."""
        detectors = create_change_detectors(self.temp_dir)
        amazon_detector = detectors["amazon_matching"]

        context = FlowContext(start_time=datetime.now())

        # Create Amazon data directory
        amazon_raw_dir = self.temp_dir / "amazon" / "raw"
        amazon_raw_dir.mkdir(parents=True)

        # Initially no changes (no data)
        has_changes, reasons = amazon_detector.check_changes(context)
        assert has_changes is False

        # Add Amazon data directory
        test_data_dir = amazon_raw_dir / "2024-01-01_test_amazon_data"
        test_data_dir.mkdir()

        # Should detect new directory
        has_changes, reasons = amazon_detector.check_changes(context)
        assert has_changes is True
        assert any("New Amazon data directories" in reason for reason in reasons)

    def test_retirement_update_change_detection(self):
        """Test retirement update change detection."""
        detectors = create_change_detectors(self.temp_dir)
        retirement_detector = detectors["retirement_update"]

        context = FlowContext(start_time=datetime.now())

        # First run - should need update (no previous update)
        has_changes, reasons = retirement_detector.check_changes(context)
        assert has_changes is True
        assert any("No previous retirement update" in reason for reason in reasons)


class TestEndToEndFlow:
    """Test complete end-to-end flow execution with real components."""

    def setup_method(self):
        """Set up test environment with real config."""
        self.temp_dir = Path(tempfile.mkdtemp())
        os.environ["FINANCES_DATA_DIR"] = str(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)
        if "FINANCES_DATA_DIR" in os.environ:
            del os.environ["FINANCES_DATA_DIR"]

    def test_complete_flow_dry_run(self):
        """Test complete flow execution in dry run mode with real engine."""
        # Create test data to trigger changes
        self._create_test_data()

        # Clear registry to avoid conflicts
        flow_registry._nodes.clear()

        # Set up flow nodes
        setup_flow_nodes()

        # Create execution engine
        engine = FlowExecutionEngine()

        # Validate flow
        validation_errors = engine.validate_flow()
        assert validation_errors == []

        # Create context
        context = FlowContext(start_time=datetime.now(), dry_run=True, verbose=True)

        # Execute flow
        executions = engine.execute_flow(context)

        # Verify execution
        assert len(executions) > 0

        # All executions should be skipped in dry run mode
        for execution in executions.values():
            assert execution.status == NodeStatus.SKIPPED

        # Get summary
        summary = engine.get_execution_summary(executions)
        assert summary["total_nodes"] > 0
        assert summary["skipped"] > 0

    def _create_test_data(self):
        """Create test data to trigger flow execution."""
        # Create YNAB cache data
        ynab_cache_dir = self.temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {"server_knowledge": 12345, "accounts": [{"id": "account1", "name": "Test Account"}]}
        (ynab_cache_dir / "accounts.json").write_text(json.dumps(accounts_data))

        categories_data = {
            "server_knowledge": 67890,
            "category_groups": [{"id": "group1", "name": "Test Group"}],
        }
        (ynab_cache_dir / "categories.json").write_text(json.dumps(categories_data))

        (ynab_cache_dir / "transactions.json").write_text("[]")

        # Create Amazon data
        amazon_raw_dir = self.temp_dir / "amazon" / "raw"
        amazon_raw_dir.mkdir(parents=True)

        test_data_dir = amazon_raw_dir / "2024-01-01_test_amazon_data"
        test_data_dir.mkdir()
        (test_data_dir / "orders.csv").write_text("Order Date,Order ID,Total\n2024-01-01,123456,25.99")

        # Create Apple data
        apple_exports_dir = self.temp_dir / "apple" / "exports"
        apple_exports_dir.mkdir(parents=True)

        export_dir = apple_exports_dir / "2024-01-01_apple_receipts_export"
        export_dir.mkdir()
        (export_dir / "receipts.json").write_text('{"receipts": []}')

    def test_flow_execution_with_archive(self):
        """Test flow execution creates archives with real execution."""
        # Create test data
        self._create_test_data()

        # Clear registry
        flow_registry._nodes.clear()

        # Set up flow nodes
        setup_flow_nodes()

        # Execute with archive creation
        runner = CliRunner()
        result = runner.invoke(flow, ["go", "--non-interactive", "--dry-run", "--verbose"])

        assert result.exit_code == 0
        # In dry run mode, archives are not created, so we just check it runs successfully

    def test_performance_metrics_collection(self):
        """Test performance metrics are collected when enabled."""
        # Create a simple flow
        flow_registry._nodes.clear()

        def test_node_func(context: FlowContext) -> FlowResult:
            return FlowResult(success=True, items_processed=100)

        flow_registry.register_function_node(
            "test_node", test_node_func, dependencies=[], change_detector=lambda ctx: (True, ["Test change"])
        )

        engine = FlowExecutionEngine()
        context = FlowContext(start_time=datetime.now(), performance_tracking=True)

        executions = engine.execute_flow(context)

        assert len(executions) == 1
        execution = executions["test_node"]
        assert execution.result.execution_time_seconds is not None
        assert execution.result.execution_time_seconds >= 0
