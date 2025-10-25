#!/usr/bin/env python3
"""
Unit tests for flow engine archiving functionality.

Tests directory hash computation for change detection during archiving.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from finances.core.flow import FlowContext, FlowNode, FlowResult, NoOutputInfo, OutputInfo
from finances.core.flow_engine import FlowExecutionEngine


class TestDirectoryHashComputation:
    """Test compute_directory_hash method for change detection."""

    def setup_method(self):
        """Create temporary directory for tests."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_compute_directory_hash_returns_same_hash_for_identical_content(self):
        """Same directory contents should produce same hash."""
        # Create directory with sample files
        (self.temp_dir / "file1.txt").write_text("content1")
        (self.temp_dir / "file2.txt").write_text("content2")
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "subdir" / "file3.txt").write_text("content3")

        engine = FlowExecutionEngine()

        # Compute hash twice - should be identical
        hash1 = engine.compute_directory_hash(self.temp_dir)
        hash2 = engine.compute_directory_hash(self.temp_dir)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64-character hex digest

    def test_compute_directory_hash_returns_different_hash_for_different_content(self):
        """Different directory contents should produce different hashes."""
        # Create first version
        (self.temp_dir / "file1.txt").write_text("content1")

        engine = FlowExecutionEngine()
        hash1 = engine.compute_directory_hash(self.temp_dir)

        # Modify content
        (self.temp_dir / "file1.txt").write_text("modified content")
        hash2 = engine.compute_directory_hash(self.temp_dir)

        assert hash1 != hash2

        # Add new file
        (self.temp_dir / "file2.txt").write_text("new file")
        hash3 = engine.compute_directory_hash(self.temp_dir)

        assert hash2 != hash3
        assert hash1 != hash3

    def test_compute_directory_hash_ignores_archive_subdirectory(self):
        """Archive subdirectory should be ignored to avoid recursion."""
        # Create directory with archive subdirectory
        (self.temp_dir / "file1.txt").write_text("content1")
        archive_dir = self.temp_dir / "archive"
        archive_dir.mkdir()
        (archive_dir / "archived_file.txt").write_text("archived content")

        engine = FlowExecutionEngine()
        hash_with_archive = engine.compute_directory_hash(self.temp_dir)

        # Remove archive directory
        import shutil

        shutil.rmtree(archive_dir)
        hash_without_archive = engine.compute_directory_hash(self.temp_dir)

        # Hashes should be identical (archive was ignored)
        assert hash_with_archive == hash_without_archive

    def test_compute_directory_hash_returns_empty_string_for_nonexistent_directory(self):
        """Nonexistent directory should return empty string."""
        nonexistent_dir = self.temp_dir / "does_not_exist"

        engine = FlowExecutionEngine()
        hash_result = engine.compute_directory_hash(nonexistent_dir)

        assert hash_result == ""


class MockNodeWithOutput(FlowNode):
    """Mock node with output directory for archive testing."""

    def __init__(self, name: str, output_dir: Path):
        super().__init__(name)
        self.output_dir = output_dir

    def get_output_dir(self) -> Path:
        """Return the output directory."""
        return self.output_dir

    def get_output_info(self) -> OutputInfo:
        """Return no-op output info."""
        return NoOutputInfo()

    def execute(self, context: FlowContext) -> FlowResult:
        """Mock execution (not used in tests)."""
        return FlowResult(success=True)

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Mock change detection (not used in tests)."""
        return False, []

    def prompt_user(self, context: FlowContext) -> bool:
        """Mock prompt (not used in tests)."""
        return True


class TestArchiveCreation:
    """Test archive creation functions."""

    def setup_method(self):
        """Create temporary directory for tests."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_archive_existing_data_creates_pre_archive(self):
        """Archive existing data should create timestamped _pre archive."""
        # Create output directory with sample files
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        (output_dir / "file1.txt").write_text("content1")
        (output_dir / "file2.txt").write_text("content2")

        # Create mock node and context
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())

        # Create engine and archive existing data
        engine = FlowExecutionEngine()
        engine.archive_existing_data(node, output_dir, context)

        # Verify archive was created
        archive_dir = output_dir / "archive"
        assert archive_dir.exists()

        # Verify timestamped _pre archive exists
        pre_archives = list(archive_dir.glob("*_pre"))
        assert len(pre_archives) == 1
        pre_archive = pre_archives[0]

        # Verify archive contains files
        assert (pre_archive / "file1.txt").exists()
        assert (pre_archive / "file2.txt").exists()
        assert (pre_archive / "file1.txt").read_text() == "content1"
        assert (pre_archive / "file2.txt").read_text() == "content2"

        # Verify archive path stored in context
        assert "test_node_pre" in context.archive_manifest
        assert context.archive_manifest["test_node_pre"] == pre_archive

    def test_archive_existing_data_excludes_archive_subdirectory(self):
        """Archive should exclude archive/ subdirectory to prevent recursion."""
        # Create output directory with archive subdirectory
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        (output_dir / "file1.txt").write_text("content1")

        # Create archive directory with old archives
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()
        old_archive = archive_dir / "old_archive"
        old_archive.mkdir()
        (old_archive / "old_file.txt").write_text("old content")

        # Create mock node and context
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())

        # Create engine and archive existing data
        engine = FlowExecutionEngine()
        engine.archive_existing_data(node, output_dir, context)

        # Verify new _pre archive was created
        pre_archives = list(archive_dir.glob("*_pre"))
        assert len(pre_archives) == 1
        pre_archive = pre_archives[0]

        # Verify archive contains file1.txt but NOT archive subdirectory
        assert (pre_archive / "file1.txt").exists()
        assert not (pre_archive / "archive").exists()

    def test_archive_new_data_creates_post_archive(self):
        """Archive new data should create timestamped _post archive."""
        # Create output directory with sample files
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        (output_dir / "file1.txt").write_text("new content1")
        (output_dir / "file2.txt").write_text("new content2")

        # Create mock node and context
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())

        # Create archive directory (simulating pre-archive already exists)
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()

        # Create engine and archive new data
        engine = FlowExecutionEngine()
        engine.archive_new_data(node, output_dir, context)

        # Verify timestamped _post archive exists
        post_archives = list(archive_dir.glob("*_post"))
        assert len(post_archives) == 1
        post_archive = post_archives[0]

        # Verify archive contains files
        assert (post_archive / "file1.txt").exists()
        assert (post_archive / "file2.txt").exists()
        assert (post_archive / "file1.txt").read_text() == "new content1"
        assert (post_archive / "file2.txt").read_text() == "new content2"

        # Verify archive path stored in context
        assert "test_node_post" in context.archive_manifest
        assert context.archive_manifest["test_node_post"] == post_archive

    def test_archive_failure_raises_system_exit(self):
        """Archive failure should raise SystemExit (critical operation)."""
        # Create output directory
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        (output_dir / "file1.txt").write_text("content1")

        # Create mock node and context
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())

        # Create engine
        engine = FlowExecutionEngine()

        # Make output_dir unwritable (simulate permission error)

        output_dir.chmod(0o444)

        # Verify archive failure raises SystemExit
        try:
            with pytest.raises(SystemExit) as exc_info:
                engine.archive_existing_data(node, output_dir, context)
            assert exc_info.value.code == 1
        finally:
            # Restore permissions for cleanup
            output_dir.chmod(0o755)

    def test_archive_new_data_returns_archived_file_list(self):
        """Archive new data should return list of files that were archived."""
        # Create output directory with files
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        file1 = output_dir / "file1.txt"
        file2 = output_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        # Create subdirectory with file
        subdir = output_dir / "subdir"
        subdir.mkdir()
        file3 = subdir / "file3.txt"
        file3.write_text("content3")

        # Create mock node and context
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())

        # Create archive directory
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()

        # Create engine and archive new data
        engine = FlowExecutionEngine()
        archived_files = engine.archive_new_data(node, output_dir, context)

        # Verify returned list contains all files (excluding archive)
        assert len(archived_files) == 3
        assert file1 in archived_files
        assert file2 in archived_files
        assert file3 in archived_files

    def test_archive_new_data_excludes_archive_directory_from_returned_list(self):
        """Archived file list should not include files from archive/ subdirectory."""
        # Create output directory with files
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        file1 = output_dir / "file1.txt"
        file1.write_text("content1")

        # Create archive directory with old archive
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()
        old_archive = archive_dir / "2024-10-20_10-00-00_post"
        old_archive.mkdir()
        old_file = old_archive / "old_file.txt"
        old_file.write_text("old content")

        # Create mock node and context
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())

        # Create engine and archive new data
        engine = FlowExecutionEngine()
        archived_files = engine.archive_new_data(node, output_dir, context)

        # Verify returned list only contains file1, not archive contents
        assert len(archived_files) == 1
        assert file1 in archived_files
        assert old_file not in archived_files


class TestArchiveCleanup:
    """Test archive cleanup functionality."""

    def setup_method(self):
        """Create temporary directory for tests."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_old_files_deleted_after_archiving(self):
        """Old files should be deleted after being archived."""
        # Create output directory with old files
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        old_file1 = output_dir / "old_file1.txt"
        old_file2 = output_dir / "old_file2.txt"
        old_file1.write_text("old content 1")
        old_file2.write_text("old content 2")

        # Create archive directory
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()

        # Simulate archiving and cleanup
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())
        engine = FlowExecutionEngine()

        # Archive files (returns list of archived files)
        archived_files = engine.archive_new_data(node, output_dir, context)

        # Verify old files exist before cleanup
        assert old_file1.exists()
        assert old_file2.exists()

        # Simulate cleanup (no new files to keep)
        new_files = set()  # Empty - no newly created files
        for file_path in archived_files:
            if file_path.resolve() not in new_files:
                file_path.unlink()

        # Verify old files were deleted
        assert not old_file1.exists()
        assert not old_file2.exists()

    def test_newly_created_files_not_deleted(self):
        """Newly created files from result.outputs should not be deleted."""
        # Create output directory with old file and new file
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        old_file = output_dir / "old_file.txt"
        new_file = output_dir / "new_file.txt"
        old_file.write_text("old content")
        new_file.write_text("new content")

        # Create archive directory
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()

        # Simulate archiving
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())
        engine = FlowExecutionEngine()
        archived_files = engine.archive_new_data(node, output_dir, context)

        # Verify both files were archived
        assert len(archived_files) == 2

        # Simulate cleanup (new_file is newly created and should be kept)
        new_files = {new_file.resolve()}
        for file_path in archived_files:
            if file_path.resolve() not in new_files:
                file_path.unlink()

        # Verify old file deleted but new file preserved
        assert not old_file.exists()
        assert new_file.exists()

    def test_archive_directory_not_affected_by_cleanup(self):
        """Archive directory should not be affected by cleanup."""
        # Create output directory
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        old_file = output_dir / "old_file.txt"
        old_file.write_text("old content")

        # Create archive directory with existing archives
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()
        existing_archive = archive_dir / "2024-10-20_10-00-00_pre"
        existing_archive.mkdir()
        existing_file = existing_archive / "existing.txt"
        existing_file.write_text("existing archived content")

        # Simulate archiving
        node = MockNodeWithOutput("test_node", output_dir)
        context = FlowContext(start_time=datetime.now())
        engine = FlowExecutionEngine()
        archived_files = engine.archive_new_data(node, output_dir, context)

        # Verify archived_files doesn't include archive directory contents
        assert existing_file not in archived_files

        # Simulate cleanup
        new_files = set()
        for file_path in archived_files:
            if file_path.resolve() not in new_files:
                file_path.unlink()

        # Verify archive directory and its contents still exist
        assert archive_dir.exists()
        assert existing_archive.exists()
        assert existing_file.exists()
        assert existing_file.read_text() == "existing archived content"

        # Verify new post archive was created
        post_archives = list(archive_dir.glob("*_post"))
        assert len(post_archives) == 1
