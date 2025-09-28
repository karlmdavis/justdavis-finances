#!/usr/bin/env python3
"""
Change Detection System

Provides intelligent change detection for all Financial Flow System nodes
to determine when execution is required based on upstream data changes.
"""

import imaplib
import email
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging

from .flow import FlowContext
from .config import get_config
from .json_utils import write_json_with_defaults, read_json

logger = logging.getLogger(__name__)


class ChangeDetector:
    """
    Base class for node-specific change detection.

    Provides common utilities and interface for detecting when a flow node
    needs to execute based on upstream data changes.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize change detector.

        Args:
            data_dir: Base data directory for the system
        """
        self.data_dir = data_dir
        self.cache_dir = data_dir / "cache" / "flow"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_file(self, node_name: str) -> Path:
        """Get cache file path for a specific node."""
        return self.cache_dir / f"{node_name}_last_check.json"

    def load_last_check_state(self, node_name: str) -> Dict[str, Any]:
        """Load the last check state for a node."""
        cache_file = self.get_cache_file(node_name)
        if cache_file.exists():
            try:
                return read_json(cache_file)
            except Exception as e:
                logger.warning(f"Failed to load cache for {node_name}: {e}")

        return {}

    def save_last_check_state(self, node_name: str, state: Dict[str, Any]) -> None:
        """Save the last check state for a node."""
        cache_file = self.get_cache_file(node_name)
        try:
            write_json_with_defaults(cache_file, state)
        except Exception as e:
            logger.warning(f"Failed to save cache for {node_name}: {e}")

    def get_file_modification_times(self, directory: Path, pattern: str = "*") -> Dict[str, float]:
        """Get modification times for files in a directory."""
        mod_times = {}

        if not directory.exists():
            return mod_times

        try:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    mod_times[str(file_path.relative_to(directory))] = file_path.stat().st_mtime
        except Exception as e:
            logger.warning(f"Error getting modification times from {directory}: {e}")

        return mod_times

    def get_directory_listing(self, directory: Path) -> List[str]:
        """Get sorted list of items in a directory."""
        if not directory.exists():
            return []

        try:
            return sorted([item.name for item in directory.iterdir()])
        except Exception as e:
            logger.warning(f"Error listing directory {directory}: {e}")
            return []


class YnabSyncChangeDetector(ChangeDetector):
    """Change detection for YNAB sync operations."""

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        """
        Check if YNAB sync needs to run based on server_knowledge changes.

        Args:
            context: Flow execution context

        Returns:
            Tuple of (needs_sync, change_reasons)
        """
        node_name = "ynab_sync"
        ynab_cache_dir = self.data_dir / "ynab" / "cache"

        # Load last check state
        last_state = self.load_last_check_state(node_name)
        current_time = datetime.now()

        # Check if cache files exist
        cache_files = ["accounts.json", "categories.json", "transactions.json"]
        missing_files = []

        for cache_file in cache_files:
            cache_path = ynab_cache_dir / cache_file
            if not cache_path.exists():
                missing_files.append(cache_file)

        if missing_files:
            return True, [f"Missing cache files: {', '.join(missing_files)}"]

        # Check server_knowledge changes
        try:
            server_knowledge_changes = []

            # Check accounts server_knowledge
            accounts_file = ynab_cache_dir / "accounts.json"
            if accounts_file.exists():
                accounts_data = read_json(accounts_file)
                current_accounts_knowledge = accounts_data.get('server_knowledge')

                last_accounts_knowledge = last_state.get('accounts_server_knowledge')
                if current_accounts_knowledge != last_accounts_knowledge:
                    server_knowledge_changes.append("accounts server_knowledge changed")

            # Check categories server_knowledge
            categories_file = ynab_cache_dir / "categories.json"
            if categories_file.exists():
                categories_data = read_json(categories_file)
                current_categories_knowledge = categories_data.get('server_knowledge')

                last_categories_knowledge = last_state.get('categories_server_knowledge')
                if current_categories_knowledge != last_categories_knowledge:
                    server_knowledge_changes.append("categories server_knowledge changed")

            # Check time-based refresh (e.g., every 24 hours)
            last_sync_time = last_state.get('last_sync_time')
            if last_sync_time:
                last_sync = datetime.fromisoformat(last_sync_time)
                if current_time - last_sync > timedelta(hours=24):
                    server_knowledge_changes.append("24-hour refresh interval reached")
            else:
                server_knowledge_changes.append("No previous sync time recorded")

            if server_knowledge_changes:
                # Update state for next check
                new_state = {
                    'last_sync_time': current_time.isoformat(),
                    'accounts_server_knowledge': current_accounts_knowledge if 'current_accounts_knowledge' in locals() else None,
                    'categories_server_knowledge': current_categories_knowledge if 'current_categories_knowledge' in locals() else None
                }
                self.save_last_check_state(node_name, new_state)

                return True, server_knowledge_changes

            return False, ["No changes detected in YNAB data"]

        except Exception as e:
            logger.error(f"Error checking YNAB changes: {e}")
            return True, [f"Error in change detection: {e}"]


class AmazonUnzipChangeDetector(ChangeDetector):
    """Change detection for Amazon order history unzip operations."""

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        """
        Check if new ZIP files are available for extraction.

        Note: This detector needs to be configured with a download directory
        path. For now, it checks the default Downloads directory.
        """
        node_name = "amazon_unzip"

        # Check common download locations for ZIP files
        download_locations = [
            Path.home() / "Downloads",
            self.data_dir / "amazon" / "downloads"
        ]

        last_state = self.load_last_check_state(node_name)
        last_zip_files = set(last_state.get('zip_files', []))

        current_zip_files = set()
        new_files = []

        for download_dir in download_locations:
            if download_dir.exists():
                for zip_file in download_dir.glob("*.zip"):
                    # Look for Amazon-related ZIP files
                    if any(keyword in zip_file.name.lower() for keyword in ['amazon', 'order', 'purchase']):
                        relative_path = str(zip_file)
                        current_zip_files.add(relative_path)

                        if relative_path not in last_zip_files:
                            new_files.append(zip_file.name)

        if new_files:
            # Update state
            new_state = {
                'zip_files': list(current_zip_files),
                'last_check_time': datetime.now().isoformat()
            }
            self.save_last_check_state(node_name, new_state)

            return True, [f"New Amazon ZIP files detected: {', '.join(new_files)}"]

        return False, ["No new Amazon ZIP files detected"]


class AmazonMatchingChangeDetector(ChangeDetector):
    """Change detection for Amazon transaction matching."""

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        """Check if Amazon matching needs to run based on upstream changes."""
        node_name = "amazon_matching"
        amazon_raw_dir = self.data_dir / "amazon" / "raw"
        ynab_cache_dir = self.data_dir / "ynab" / "cache"

        last_state = self.load_last_check_state(node_name)
        changes = []

        # Check for new Amazon data directories
        current_amazon_dirs = self.get_directory_listing(amazon_raw_dir)
        last_amazon_dirs = last_state.get('amazon_directories', [])

        if current_amazon_dirs != last_amazon_dirs:
            new_dirs = set(current_amazon_dirs) - set(last_amazon_dirs)
            if new_dirs:
                changes.append(f"New Amazon data directories: {', '.join(new_dirs)}")

        # Check YNAB transactions file modification time
        transactions_file = ynab_cache_dir / "transactions.json"
        if transactions_file.exists():
            current_mod_time = transactions_file.stat().st_mtime
            last_mod_time = last_state.get('ynab_transactions_mod_time')

            if last_mod_time is None or current_mod_time > last_mod_time:
                changes.append("YNAB transactions cache updated")

        if changes:
            # Update state
            new_state = {
                'amazon_directories': current_amazon_dirs,
                'ynab_transactions_mod_time': current_mod_time if 'current_mod_time' in locals() else None,
                'last_check_time': datetime.now().isoformat()
            }
            self.save_last_check_state(node_name, new_state)

            return True, changes

        return False, ["No changes in Amazon data or YNAB transactions"]


class AppleEmailChangeDetector(ChangeDetector):
    """Change detection for Apple receipt email fetching."""

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        """
        Check if new Apple receipt emails are available.

        Note: This would integrate with IMAP to check for new emails.
        For now, it provides a time-based check.
        """
        node_name = "apple_email_fetch"
        last_state = self.load_last_check_state(node_name)

        # Time-based check (e.g., every 12 hours)
        current_time = datetime.now()
        last_fetch_time = last_state.get('last_fetch_time')

        if last_fetch_time:
            last_fetch = datetime.fromisoformat(last_fetch_time)
            if current_time - last_fetch > timedelta(hours=12):
                # Update state
                new_state = {
                    'last_fetch_time': current_time.isoformat()
                }
                self.save_last_check_state(node_name, new_state)

                return True, ["12-hour email fetch interval reached"]
            else:
                time_remaining = timedelta(hours=12) - (current_time - last_fetch)
                hours_remaining = int(time_remaining.total_seconds() / 3600)
                return False, [f"Next fetch in {hours_remaining} hours"]
        else:
            # First run
            new_state = {
                'last_fetch_time': current_time.isoformat()
            }
            self.save_last_check_state(node_name, new_state)

            return True, ["No previous fetch time recorded"]


class AppleMatchingChangeDetector(ChangeDetector):
    """Change detection for Apple transaction matching."""

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        """Check if Apple matching needs to run based on upstream changes."""
        node_name = "apple_matching"
        apple_exports_dir = self.data_dir / "apple" / "exports"
        ynab_cache_dir = self.data_dir / "ynab" / "cache"

        last_state = self.load_last_check_state(node_name)
        changes = []

        # Check for new Apple export directories
        current_export_dirs = self.get_directory_listing(apple_exports_dir)
        last_export_dirs = last_state.get('apple_export_directories', [])

        if current_export_dirs != last_export_dirs:
            new_dirs = set(current_export_dirs) - set(last_export_dirs)
            if new_dirs:
                changes.append(f"New Apple export directories: {', '.join(new_dirs)}")

        # Check YNAB transactions file modification time
        transactions_file = ynab_cache_dir / "transactions.json"
        if transactions_file.exists():
            current_mod_time = transactions_file.stat().st_mtime
            last_mod_time = last_state.get('ynab_transactions_mod_time')

            if last_mod_time is None or current_mod_time > last_mod_time:
                changes.append("YNAB transactions cache updated")

        if changes:
            # Update state
            new_state = {
                'apple_export_directories': current_export_dirs,
                'ynab_transactions_mod_time': current_mod_time if 'current_mod_time' in locals() else None,
                'last_check_time': datetime.now().isoformat()
            }
            self.save_last_check_state(node_name, new_state)

            return True, changes

        return False, ["No changes in Apple exports or YNAB transactions"]


class RetirementUpdateChangeDetector(ChangeDetector):
    """Change detection for retirement account updates."""

    def check_changes(self, context: FlowContext) -> Tuple[bool, List[str]]:
        """
        Check if retirement accounts need balance updates.

        Uses configurable threshold (e.g., monthly updates).
        """
        node_name = "retirement_update"
        last_state = self.load_last_check_state(node_name)

        # Check for monthly update cycle
        current_time = datetime.now()
        last_update_time = last_state.get('last_update_time')

        if last_update_time:
            last_update = datetime.fromisoformat(last_update_time)
            # Check if it's been more than 30 days
            if current_time - last_update > timedelta(days=30):
                return True, ["Monthly retirement update cycle reached"]
            else:
                days_remaining = 30 - (current_time - last_update).days
                return False, [f"Next update in {days_remaining} days"]
        else:
            return True, ["No previous retirement update recorded"]


def create_change_detectors(data_dir: Path) -> Dict[str, ChangeDetector]:
    """
    Create and configure all change detectors for the flow system.

    Args:
        data_dir: Base data directory

    Returns:
        Dictionary mapping node names to their change detectors
    """
    return {
        "ynab_sync": YnabSyncChangeDetector(data_dir),
        "amazon_unzip": AmazonUnzipChangeDetector(data_dir),
        "amazon_matching": AmazonMatchingChangeDetector(data_dir),
        "apple_email_fetch": AppleEmailChangeDetector(data_dir),
        "apple_matching": AppleMatchingChangeDetector(data_dir),
        "retirement_update": RetirementUpdateChangeDetector(data_dir)
    }


def get_change_detector_function(detector: ChangeDetector):
    """
    Create a change detector function compatible with FlowNode.

    Args:
        detector: ChangeDetector instance

    Returns:
        Function that takes FlowContext and returns (bool, List[str])
    """
    def change_detector_func(context: FlowContext) -> Tuple[bool, List[str]]:
        return detector.check_changes(context)

    return change_detector_func