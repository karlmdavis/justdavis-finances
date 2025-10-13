#!/usr/bin/env python3
"""
Integration Tests for Archive Management System

Tests the archive management functionality with real file system operations
using temporary directories. No mocking required - tests verify actual
archive creation, manifest generation, and cleanup operations.
"""

import json
import tarfile
import tempfile
from pathlib import Path

import pytest

from finances.core.archive import (
    ArchiveManager,
    ArchiveManifest,
    DomainArchiver,
    create_flow_archive,
)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_domain_data(temp_data_dir):
    """Create sample domain data for archiving."""
    domain_dir = temp_data_dir / "amazon"
    domain_dir.mkdir(parents=True)

    # Create sample files
    (domain_dir / "orders.json").write_text(json.dumps({"orders": [{"id": 1}]}))
    (domain_dir / "transactions.json").write_text(json.dumps({"transactions": [{"id": 1}]}))

    # Create subdirectory with data
    subdir = domain_dir / "raw"
    subdir.mkdir()
    (subdir / "data.csv").write_text("order_id,date\n123,2024-01-01\n")

    # Create a file that should be excluded
    (domain_dir / "temp.tmp").write_text("temporary file")
    (domain_dir / "debug.log").write_text("log file")

    return domain_dir


class TestDomainArchiver:
    """Tests for DomainArchiver class."""

    def test_init_creates_archive_directory(self, temp_data_dir):
        """Test that initializing archiver creates archive directory."""
        archiver = DomainArchiver("amazon", temp_data_dir)

        assert archiver.archive_dir.exists()
        assert archiver.archive_dir == temp_data_dir / "amazon" / "archive"

    def test_get_archivable_files_empty_domain(self, temp_data_dir):
        """Test getting archivable files from non-existent domain."""
        archiver = DomainArchiver("nonexistent", temp_data_dir)

        files = archiver.get_archivable_files()

        assert files == []

    def test_get_archivable_files_includes_correct_patterns(self, sample_domain_data, temp_data_dir):
        """Test that archivable files includes correct file patterns."""
        archiver = DomainArchiver("amazon", temp_data_dir)

        files = archiver.get_archivable_files()

        # Should include JSON and CSV files
        file_names = [f.name for f in files]
        assert "orders.json" in file_names
        assert "transactions.json" in file_names
        assert "data.csv" in file_names

        # Should exclude temp and log files
        assert "temp.tmp" not in file_names
        assert "debug.log" not in file_names

    def test_get_archivable_files_excludes_archive_directory(self, sample_domain_data, temp_data_dir):
        """Test that archivable files excludes the archive directory itself."""
        archiver = DomainArchiver("amazon", temp_data_dir)

        # Create a file in the archive directory
        (archiver.archive_dir / "old_archive.json").write_text("{}")

        files = archiver.get_archivable_files()

        # Should not include files from archive directory
        file_paths = [str(f) for f in files]
        assert not any("archive" in path for path in file_paths)

    def test_get_next_sequence_number_no_existing_archives(self, temp_data_dir):
        """Test getting next sequence number when no archives exist."""
        archiver = DomainArchiver("amazon", temp_data_dir)

        seq_num = archiver.get_next_sequence_number("2024-01-01")

        assert seq_num == 1

    def test_get_next_sequence_number_with_existing_archives(self, temp_data_dir):
        """Test getting next sequence number with existing archives."""
        from datetime import datetime
        import tarfile

        archiver = DomainArchiver("amazon", temp_data_dir)

        # Use today's date to match what create_archive will use
        today = datetime.now().strftime("%Y-%m-%d")

        # Create existing archives with today's date (must be valid tar files)
        for seq in [1, 2]:
            archive_path = archiver.archive_dir / f"{today}-{seq:03d}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                pass  # Empty but valid tar.gz file

        # Also create one with different date
        with tarfile.open(archiver.archive_dir / "2024-01-02-001.tar.gz", "w:gz") as tar:
            pass

        seq_num = archiver.get_next_sequence_number(today)

        assert seq_num == 3

    def test_get_next_sequence_number_ignores_malformed_names(self, temp_data_dir):
        """Test that malformed archive names are ignored in sequence numbering."""
        from datetime import datetime
        import tarfile

        archiver = DomainArchiver("amazon", temp_data_dir)

        # Use today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Create archives with malformed names
        with tarfile.open(archiver.archive_dir / f"{today}-001.tar.gz", "w:gz") as tar:
            pass
        (archiver.archive_dir / "invalid-name.tar.gz").write_bytes(b"")
        (archiver.archive_dir / f"{today}-xyz.tar.gz").write_bytes(b"")  # Malformed sequence

        seq_num = archiver.get_next_sequence_number(today)

        assert seq_num == 2

    def test_create_archive_no_files(self, temp_data_dir):
        """Test creating archive when domain has no files."""
        archiver = DomainArchiver("empty_domain", temp_data_dir)

        manifest = archiver.create_archive("test_trigger")

        assert manifest is None

    def test_create_archive_success(self, sample_domain_data, temp_data_dir):
        """Test successful archive creation."""
        archiver = DomainArchiver("amazon", temp_data_dir)

        manifest = archiver.create_archive("test_trigger", {"test": "context"})

        # Verify manifest
        assert manifest is not None
        assert manifest.trigger_reason == "test_trigger"
        assert manifest.domains == ["amazon"]
        assert manifest.files_archived == 3  # orders.json, transactions.json, data.csv
        assert manifest.archive_size_bytes > 0
        assert manifest.sequence_number == 1
        assert manifest.flow_context == {"test": "context"}

        # Verify archive file exists
        archive_path = Path(manifest.archive_path)
        assert archive_path.exists()
        assert archive_path.suffix == ".gz"

        # Verify manifest file exists
        manifest_path = archive_path.with_suffix(".json")
        assert manifest_path.exists()

    def test_create_archive_contents(self, sample_domain_data, temp_data_dir):
        """Test that archive contains correct files with correct structure."""
        archiver = DomainArchiver("amazon", temp_data_dir)

        manifest = archiver.create_archive("test_trigger")
        archive_path = Path(manifest.archive_path)

        # Extract and verify contents
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getmembers()
            member_names = [m.name for m in members]

            # Should contain files with relative paths (not absolute)
            assert "orders.json" in member_names
            assert "transactions.json" in member_names
            assert "raw/data.csv" in member_names

            # Should not contain excluded files
            assert "temp.tmp" not in member_names
            assert "debug.log" not in member_names

    def test_create_archive_sequence_numbering(self, sample_domain_data, temp_data_dir):
        """Test that sequence numbers increment based on existing archives."""
        from datetime import datetime
        import tarfile

        archiver = DomainArchiver("amazon", temp_data_dir)

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Pre-create some archives to establish a sequence
        with tarfile.open(archiver.archive_dir / f"{today}-001.tar.gz", "w:gz") as tar:
            pass
        with tarfile.open(archiver.archive_dir / f"{today}-002.tar.gz", "w:gz") as tar:
            pass

        # Now create a new archive - it should get sequence number 3
        manifest = archiver.create_archive("trigger_1")
        assert manifest.sequence_number == 3

        # Verify the archive was created with correct filename
        assert f"{today}-003.tar.gz" in manifest.archive_path


class TestArchiveManager:
    """Tests for ArchiveManager class."""

    def test_init_creates_session_directory(self, temp_data_dir):
        """Test that initializing manager creates session directory."""
        manager = ArchiveManager(temp_data_dir)

        assert manager.session_dir.exists()
        assert manager.session_dir == temp_data_dir / ".archive_sessions"

    def test_init_creates_domain_archivers(self, temp_data_dir):
        """Test that manager creates archivers for all domains."""
        manager = ArchiveManager(temp_data_dir)

        expected_domains = ["amazon", "apple", "ynab", "retirement", "cash_flow"]
        assert set(manager.domain_archivers.keys()) == set(expected_domains)

        for domain_name, archiver in manager.domain_archivers.items():
            assert isinstance(archiver, DomainArchiver)
            assert archiver.domain_name == domain_name

    def test_get_domains_with_data_empty(self, temp_data_dir):
        """Test getting domains with data when all domains are empty."""
        manager = ArchiveManager(temp_data_dir)

        domains = manager.get_domains_with_data()

        assert domains == []

    def test_get_domains_with_data_mixed(self, temp_data_dir):
        """Test getting domains with data when some have data."""
        # Create data in some domains
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text("{}")

        ynab_dir = temp_data_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "transactions.json").write_text("{}")

        manager = ArchiveManager(temp_data_dir)

        domains = manager.get_domains_with_data()

        assert set(domains) == {"amazon", "ynab"}

    def test_create_transaction_archive_empty(self, temp_data_dir):
        """Test creating transaction archive with no data."""
        manager = ArchiveManager(temp_data_dir)

        session = manager.create_transaction_archive("test_trigger")

        assert session.trigger_reason == "test_trigger"
        assert session.archives == {}
        assert session.total_files == 0
        assert session.total_size_bytes == 0

    def test_create_transaction_archive_all_domains(self, temp_data_dir):
        """Test creating transaction archive across multiple domains."""
        # Create data in multiple domains (using supported file types)
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        # Apple: Use JSON files since HTML is not in the archivable patterns
        apple_dir = temp_data_dir / "apple" / "exports"
        apple_dir.mkdir(parents=True)
        (apple_dir / "receipt.json").write_text('{"order_id": "123"}')

        ynab_dir = temp_data_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "transactions.json").write_text('{"transactions": []}')

        manager = ArchiveManager(temp_data_dir)

        session = manager.create_transaction_archive("flow_execution")

        # Verify session
        assert session.trigger_reason == "flow_execution"
        assert set(session.archives.keys()) == {"amazon", "apple", "ynab"}
        assert session.total_files == 3
        assert session.total_size_bytes > 0

        # Verify session file was created
        session_file = manager.session_dir / f"{session.session_id}.json"
        assert session_file.exists()

    def test_create_transaction_archive_specific_domains(self, temp_data_dir):
        """Test creating archive for specific domains only."""
        # Create data in multiple domains
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        ynab_dir = temp_data_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "transactions.json").write_text('{"transactions": []}')

        manager = ArchiveManager(temp_data_dir)

        session = manager.create_transaction_archive("test_trigger", domains=["amazon"])

        # Should only archive amazon
        assert set(session.archives.keys()) == {"amazon"}

    def test_create_transaction_archive_with_flow_context(self, temp_data_dir):
        """Test that flow context is included in archive manifests."""
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        manager = ArchiveManager(temp_data_dir)
        flow_context = {"execution_order": ["node1", "node2"], "timestamp": "2024-01-01"}

        session = manager.create_transaction_archive("test", flow_context=flow_context)

        # Verify context in manifest
        manifest = session.archives["amazon"]
        assert manifest.flow_context == flow_context

    def test_list_recent_archives_all_domains(self, temp_data_dir):
        """Test listing recent archives across all domains."""
        import time

        # Create some archives
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        manager = ArchiveManager(temp_data_dir)

        session1 = manager.create_transaction_archive("trigger_1")
        time.sleep(1)  # Ensure different session IDs (based on timestamp)
        session2 = manager.create_transaction_archive("trigger_2")

        archives = manager.list_recent_archives(limit=10)

        # Should return session data
        assert len(archives) == 2
        assert all("session_id" in archive for archive in archives)

    def test_list_recent_archives_specific_domain(self, temp_data_dir):
        """Test listing recent archives for a specific domain."""
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        manager = ArchiveManager(temp_data_dir)

        # Create archives - they will get sequential numbers
        session = manager.create_transaction_archive("trigger_1")

        archives = manager.list_recent_archives(domain="amazon", limit=10)

        # Should return manifest data for amazon domain
        assert len(archives) >= 1
        assert all("archive_path" in archive for archive in archives)
        assert all("amazon" in archive["domains"] for archive in archives)

    def test_list_recent_archives_respects_limit(self, temp_data_dir):
        """Test that archive listing respects the limit parameter."""
        import time

        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        manager = ArchiveManager(temp_data_dir)

        # Create 5 archives with different timestamps
        for i in range(5):
            manager.create_transaction_archive(f"trigger_{i}")
            time.sleep(1)  # Ensure different session IDs

        archives = manager.list_recent_archives(limit=3)

        assert len(archives) == 3

    def test_calculate_storage_usage_empty(self, temp_data_dir):
        """Test calculating storage usage with no archives."""
        manager = ArchiveManager(temp_data_dir)

        usage = manager.calculate_storage_usage()

        assert usage["total_archives"] == 0
        assert usage["total_size_bytes"] == 0
        assert len(usage["domains"]) == 5  # 5 domain archivers

    def test_calculate_storage_usage_with_archives(self, temp_data_dir):
        """Test calculating storage usage with archives."""
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}' * 100)  # Make it bigger

        manager = ArchiveManager(temp_data_dir)

        # Create one archive
        manager.create_transaction_archive("trigger_1")

        usage = manager.calculate_storage_usage()

        # Should have at least one archive
        assert usage["total_archives"] >= 1
        assert usage["total_size_bytes"] > 0
        assert usage["domains"]["amazon"]["archive_count"] >= 1
        assert usage["domains"]["amazon"]["total_size_bytes"] > 0

    def test_cleanup_old_archives_keeps_recent(self, temp_data_dir):
        """Test that cleanup keeps the most recent archives."""
        from datetime import datetime, timedelta
        import tarfile
        import time

        archiver = DomainArchiver("amazon", temp_data_dir)

        # Create 5 archives with different modification times by manually creating them
        for i in range(5):
            archive_path = archiver.archive_dir / f"2025-10-{13+i:02d}-001.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                pass
            # Set different modification times
            mtime = time.time() - (5 - i) * 60  # Each one minute apart, oldest first
            archive_path.touch()
            import os
            os.utime(archive_path, (mtime, mtime))

        manager = ArchiveManager(temp_data_dir)

        # Cleanup, keeping only 3
        deleted_count = manager.cleanup_old_archives("amazon", keep_count=3)

        assert deleted_count == 2

        # Verify only 3 archives remain
        remaining_archives = list(archiver.archive_dir.glob("*.tar.gz"))
        assert len(remaining_archives) == 3

    def test_cleanup_old_archives_deletes_manifests_too(self, temp_data_dir):
        """Test that cleanup also deletes manifest files."""
        import tarfile
        import time

        archiver = DomainArchiver("amazon", temp_data_dir)

        # Create 5 archives with manifest files, each with different modification times
        for i in range(5):
            archive_path = archiver.archive_dir / f"2025-10-{13+i:02d}-001.tar.gz"
            manifest_path = archive_path.with_suffix(".json")

            with tarfile.open(archive_path, "w:gz") as tar:
                pass
            manifest_path.write_text("{}")

            # Set different modification times
            mtime = time.time() - (5 - i) * 60
            import os
            os.utime(archive_path, (mtime, mtime))
            os.utime(manifest_path, (mtime, mtime))

        manager = ArchiveManager(temp_data_dir)

        deleted_count = manager.cleanup_old_archives("amazon", keep_count=2)

        assert deleted_count == 3

        # Verify manifest files were also deleted
        remaining_manifests = list(archiver.archive_dir.glob("*.json"))
        assert len(remaining_manifests) == 2

    def test_cleanup_old_archives_unknown_domain(self, temp_data_dir):
        """Test that cleanup raises error for unknown domain."""
        manager = ArchiveManager(temp_data_dir)

        with pytest.raises(ValueError, match="Unknown domain"):
            manager.cleanup_old_archives("nonexistent_domain", keep_count=5)


class TestCreateFlowArchive:
    """Tests for create_flow_archive convenience function."""

    def test_create_flow_archive(self, temp_data_dir):
        """Test create_flow_archive convenience function."""
        # Create some data
        amazon_dir = temp_data_dir / "amazon"
        amazon_dir.mkdir(parents=True)
        (amazon_dir / "orders.json").write_text('{"orders": []}')

        session = create_flow_archive(
            temp_data_dir, "test_trigger", flow_context={"test": "data"}
        )

        assert session is not None
        assert session.trigger_reason == "test_trigger"
        assert "amazon" in session.archives

    def test_create_flow_archive_empty(self, temp_data_dir):
        """Test create_flow_archive with no data."""
        session = create_flow_archive(temp_data_dir, "test_trigger")

        assert session is not None
        assert session.archives == {}
        assert session.total_files == 0
