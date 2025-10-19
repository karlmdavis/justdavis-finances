#!/usr/bin/env python3
"""
Unit tests for flow engine archiving functionality.

Tests directory hash computation for change detection during archiving.
"""

import tempfile
from pathlib import Path

import pytest

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
