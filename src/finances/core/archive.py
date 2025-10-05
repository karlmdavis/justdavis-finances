#!/usr/bin/env python3
"""
Archive Management System

Provides transactional archiving of financial data before flow execution
to ensure data consistency and enable rollback capabilities.
"""

import logging
import tarfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .json_utils import read_json, write_json

logger = logging.getLogger(__name__)


@dataclass
class ArchiveManifest:
    """Manifest describing the contents and metadata of an archive."""

    archive_path: str
    creation_time: str
    trigger_reason: str
    domains: list[str]
    files_archived: int
    archive_size_bytes: int
    sequence_number: int
    flow_context: dict[str, Any]


@dataclass
class ArchiveSession:
    """Represents a complete archive session across all domains."""

    session_id: str
    creation_time: str
    trigger_reason: str
    archives: dict[str, ArchiveManifest]
    total_files: int
    total_size_bytes: int


class DomainArchiver:
    """
    Handles archiving for a specific data domain (amazon, apple, ynab, etc.).

    Creates compressed archives of current data before flow execution begins
    to ensure transactional consistency and enable rollback.
    """

    def __init__(self, domain_name: str, data_dir: Path):
        """
        Initialize domain archiver.

        Args:
            domain_name: Name of the domain (amazon, apple, ynab, etc.)
            data_dir: Base data directory
        """
        self.domain_name = domain_name
        self.data_dir = data_dir
        self.domain_dir = data_dir / domain_name
        self.archive_dir = self.domain_dir / "archive"

        # Ensure archive directory exists
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def get_archivable_files(self) -> list[Path]:
        """
        Get list of files that should be archived for this domain.

        Returns:
            List of file paths to include in archive
        """
        if not self.domain_dir.exists():
            return []

        archivable_files = []

        # Common patterns to archive (exclude archive directory itself)
        patterns_to_include = ["*.json", "*.yaml", "*.yml", "*.csv", "*.png", "*.jpg", "*.jpeg"]

        patterns_to_exclude = ["archive/**", "*.tmp", "*.log", "**/.DS_Store"]

        try:
            for pattern in patterns_to_include:
                for file_path in self.domain_dir.rglob(pattern):
                    if file_path.is_file():
                        # Check if file should be excluded
                        relative_path = file_path.relative_to(self.domain_dir)
                        should_exclude = any(
                            relative_path.match(exclude_pattern) for exclude_pattern in patterns_to_exclude
                        )

                        if not should_exclude:
                            archivable_files.append(file_path)

        except Exception as e:
            logger.warning(f"Error scanning {self.domain_name} files: {e}")

        return sorted(archivable_files)

    def get_next_sequence_number(self, date_prefix: str) -> int:
        """
        Get the next sequence number for archives created on a specific date.

        Args:
            date_prefix: Date prefix in YYYY-MM-DD format

        Returns:
            Next available sequence number
        """
        existing_archives = list(self.archive_dir.glob(f"{date_prefix}-*.tar.gz"))
        sequence_numbers = []

        for archive_path in existing_archives:
            try:
                # Extract sequence number from filename: YYYY-MM-DD-NNN.tar.gz
                name_parts = archive_path.stem.split("-")
                if len(name_parts) >= 4:
                    sequence_numbers.append(int(name_parts[3]))
            except (ValueError, IndexError):
                # PERF203: try-except in loop necessary for robust filename parsing
                continue

        return max(sequence_numbers, default=0) + 1

    def create_archive(
        self, trigger_reason: str, flow_context: dict[str, Any] | None = None
    ) -> ArchiveManifest | None:
        """
        Create compressed archive of current domain data.

        Args:
            trigger_reason: Reason for creating this archive
            flow_context: Optional flow context metadata

        Returns:
            ArchiveManifest if archive was created, None if no files to archive
        """
        files_to_archive = self.get_archivable_files()

        if not files_to_archive:
            logger.info(f"No files to archive for domain: {self.domain_name}")
            return None

        # Generate archive filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        sequence_num = self.get_next_sequence_number(date_str)
        archive_filename = f"{date_str}-{sequence_num:03d}.tar.gz"
        archive_path = self.archive_dir / archive_filename

        creation_time = datetime.now()

        try:
            # Create compressed archive
            with tarfile.open(archive_path, "w:gz") as tar:
                for file_path in files_to_archive:
                    # Use relative path within domain directory
                    arcname = file_path.relative_to(self.domain_dir)
                    tar.add(file_path, arcname=arcname)

            # Get archive size
            archive_size = archive_path.stat().st_size

            # Create manifest
            manifest = ArchiveManifest(
                archive_path=str(archive_path),
                creation_time=creation_time.isoformat(),
                trigger_reason=trigger_reason,
                domains=[self.domain_name],
                files_archived=len(files_to_archive),
                archive_size_bytes=archive_size,
                sequence_number=sequence_num,
                flow_context=flow_context or {},
            )

            # Save manifest alongside archive
            manifest_path = archive_path.with_suffix(".json")
            write_json(manifest_path, asdict(manifest))

            logger.info(
                f"Created archive: {archive_path} ({len(files_to_archive)} files, {archive_size:,} bytes)"
            )

            return manifest

        except Exception as e:
            logger.error(f"Failed to create archive for {self.domain_name}: {e}")
            # Clean up partial archive if it exists
            if archive_path.exists():
                archive_path.unlink()
            raise


class ArchiveManager:
    """
    Manages transactional archiving across all financial data domains.

    Coordinates archive creation before flow execution to ensure data
    consistency and provide rollback capabilities.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize archive manager.

        Args:
            data_dir: Base data directory containing all domains
        """
        self.data_dir = data_dir
        self.session_dir = data_dir / ".archive_sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize domain archivers
        self.domain_archivers = {
            "amazon": DomainArchiver("amazon", data_dir),
            "apple": DomainArchiver("apple", data_dir),
            "ynab": DomainArchiver("ynab", data_dir),
            "retirement": DomainArchiver("retirement", data_dir),
            "cash_flow": DomainArchiver("cash_flow", data_dir),
        }

    def get_domains_with_data(self) -> list[str]:
        """
        Get list of domains that have data to archive.

        Returns:
            List of domain names with archivable data
        """
        domains_with_data = []

        for domain_name, archiver in self.domain_archivers.items():
            files_to_archive = archiver.get_archivable_files()
            if files_to_archive:
                domains_with_data.append(domain_name)

        return domains_with_data

    def create_transaction_archive(
        self,
        trigger_reason: str,
        domains: list[str] | None = None,
        flow_context: dict[str, Any] | None = None,
    ) -> ArchiveSession:
        """
        Create transactional archive across specified domains.

        Args:
            trigger_reason: Reason for creating archives (e.g., "flow_execution")
            domains: List of domains to archive (defaults to all with data)
            flow_context: Optional flow context metadata

        Returns:
            ArchiveSession with details of all created archives
        """
        if domains is None:
            domains = self.get_domains_with_data()

        session_id = f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        creation_time = datetime.now()
        archives = {}
        total_files = 0
        total_size = 0

        logger.info(f"Creating transaction archive for domains: {domains}")

        for domain_name in domains:
            if domain_name not in self.domain_archivers:
                logger.warning(f"Unknown domain: {domain_name}")
                continue

            archiver = self.domain_archivers[domain_name]

            try:
                manifest = archiver.create_archive(trigger_reason, flow_context)
                if manifest:
                    archives[domain_name] = manifest
                    total_files += manifest.files_archived
                    total_size += manifest.archive_size_bytes

            except Exception as e:
                logger.error(f"Failed to archive domain {domain_name}: {e}")
                # Continue with other domains rather than failing completely
                continue

        # Create archive session record
        archive_session = ArchiveSession(
            session_id=session_id,
            creation_time=creation_time.isoformat(),
            trigger_reason=trigger_reason,
            archives=archives,
            total_files=total_files,
            total_size_bytes=total_size,
        )

        # Save session manifest
        session_file = self.session_dir / f"{session_id}.json"
        session_data = asdict(archive_session)
        # Convert ArchiveManifest objects to dicts
        session_data["archives"] = {domain: asdict(manifest) for domain, manifest in archives.items()}
        write_json(session_file, session_data)

        logger.info(
            f"Archive session complete: {len(archives)} domains, {total_files} files, {total_size:,} bytes"
        )

        return archive_session

    def list_recent_archives(self, domain: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """
        List recent archives for a domain or all domains.

        Args:
            domain: Optional domain filter
            limit: Maximum number of archives to return

        Returns:
            List of archive information dictionaries
        """
        archives = []

        if domain and domain in self.domain_archivers:
            # List archives for specific domain
            archiver = self.domain_archivers[domain]
            archive_files = sorted(
                archiver.archive_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:limit]

            for archive_path in archive_files:
                manifest_path = archive_path.with_suffix(".json")
                if manifest_path.exists():
                    try:
                        manifest_data = read_json(manifest_path)
                        archives.append(manifest_data)
                    except Exception as e:
                        logger.warning(f"Failed to read manifest {manifest_path}: {e}")

        else:
            # List recent archive sessions
            session_files = sorted(
                self.session_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:limit]

            for session_file in session_files:
                try:
                    session_data = read_json(session_file)
                    archives.append(session_data)
                except Exception as e:
                    # PERF203: try-except in loop necessary for robust JSON file reading
                    logger.warning(f"Failed to read session {session_file}: {e}")

        return archives

    def calculate_storage_usage(self) -> dict[str, Any]:
        """
        Calculate storage usage statistics for all archives.

        Returns:
            Dictionary with storage usage information
        """
        usage = {"domains": {}, "total_archives": 0, "total_size_bytes": 0}

        for domain_name, archiver in self.domain_archivers.items():
            archive_files = list(archiver.archive_dir.glob("*.tar.gz"))
            domain_size = sum(f.stat().st_size for f in archive_files)

            usage["domains"][domain_name] = {  # type: ignore[index]
                "archive_count": len(archive_files),
                "total_size_bytes": domain_size,
            }

            usage["total_archives"] += len(archive_files)  # type: ignore[operator]
            usage["total_size_bytes"] += domain_size  # type: ignore[operator]

        return usage

    def cleanup_old_archives(self, domain: str, keep_count: int = 10) -> int:
        """
        Clean up old archives for a domain, keeping the most recent ones.

        Args:
            domain: Domain name to clean up
            keep_count: Number of most recent archives to keep

        Returns:
            Number of archives deleted
        """
        if domain not in self.domain_archivers:
            raise ValueError(f"Unknown domain: {domain}")

        archiver = self.domain_archivers[domain]
        archive_files = sorted(
            archiver.archive_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True
        )

        if len(archive_files) <= keep_count:
            return 0

        files_to_delete = archive_files[keep_count:]
        deleted_count = 0

        for archive_path in files_to_delete:
            try:
                # Delete archive and its manifest
                archive_path.unlink()
                manifest_path = archive_path.with_suffix(".json")
                if manifest_path.exists():
                    manifest_path.unlink()

                deleted_count += 1
                logger.info(f"Deleted old archive: {archive_path}")

            except Exception as e:
                # PERF203: try-except in loop necessary for robust file deletion
                logger.error(f"Failed to delete {archive_path}: {e}")

        return deleted_count


def create_flow_archive(
    data_dir: Path, trigger_reason: str, flow_context: dict[str, Any] | None = None
) -> ArchiveSession:
    """
    Convenience function for creating archives before flow execution.

    Args:
        data_dir: Base data directory
        trigger_reason: Reason for creating archive
        flow_context: Optional flow context metadata

    Returns:
        ArchiveSession with archive details
    """
    archive_manager = ArchiveManager(data_dir)
    return archive_manager.create_transaction_archive(trigger_reason, flow_context=flow_context)
