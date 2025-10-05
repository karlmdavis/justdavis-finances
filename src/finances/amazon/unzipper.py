#!/usr/bin/env python3
"""
Amazon Order History Unzipper

Extracts Amazon order history ZIP files to structured data directories.
"""

import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AmazonUnzipper:
    """
    Handles extraction of Amazon order history ZIP files.

    Processes downloaded ZIP files and extracts them to organized directory
    structure suitable for downstream processing.
    """

    def __init__(self, raw_data_dir: Path):
        """
        Initialize unzipper.

        Args:
            raw_data_dir: Base directory for raw Amazon data storage
        """
        self.raw_data_dir = raw_data_dir
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)

    def scan_for_zip_files(self, download_dir: Path) -> list[Path]:
        """
        Scan directory for Amazon order history ZIP files.

        Args:
            download_dir: Directory containing downloaded ZIP files

        Returns:
            List of ZIP file paths found
        """
        if not download_dir.exists():
            logger.warning(f"Download directory does not exist: {download_dir}")
            return []

        zip_files = list(download_dir.glob("*.zip"))
        logger.info(f"Found {len(zip_files)} ZIP files in {download_dir}")

        return sorted(zip_files)

    def extract_zip_file(self, zip_path: Path, account_name: Optional[str] = None) -> dict[str, Any]:
        """
        Extract a single ZIP file to organized directory structure.

        Args:
            zip_path: Path to ZIP file
            account_name: Optional account name for organization

        Returns:
            Dictionary with extraction results and metadata
        """
        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")

        # Determine account name from filename if not provided
        if account_name is None:
            # Try to extract account name from filename patterns
            # Common patterns: "amazon_orders_karl.zip", "orders_erica_2024.zip"
            stem = zip_path.stem.lower()
            if "karl" in stem:
                account_name = "karl"
            elif "erica" in stem:
                account_name = "erica"
            else:
                account_name = "unknown"

        # Generate output directory name with timestamp and account
        timestamp = datetime.now().strftime("%Y-%m-%d")
        output_dir_name = f"{timestamp}_{account_name}_amazon_data"
        output_dir = self.raw_data_dir / output_dir_name

        # Check if directory already exists
        if output_dir.exists():
            logger.warning(f"Output directory already exists: {output_dir}")
            # Add sequence number to avoid conflicts
            counter = 1
            while output_dir.exists():
                output_dir_name = f"{timestamp}_{account_name}_amazon_data_{counter:03d}"
                output_dir = self.raw_data_dir / output_dir_name
                counter += 1

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Get list of files in ZIP
                file_list = zip_ref.namelist()
                logger.info(f"Extracting {len(file_list)} files from {zip_path.name}")

                # Extract all files
                zip_ref.extractall(output_dir)

                # Categorize extracted files
                csv_files = [f for f in file_list if f.endswith(".csv")]
                json_files = [f for f in file_list if f.endswith(".json")]
                other_files = [f for f in file_list if not (f.endswith(".csv") or f.endswith(".json"))]

                result = {
                    "success": True,
                    "zip_file": str(zip_path),
                    "output_directory": str(output_dir),
                    "account_name": account_name,
                    "files_extracted": len(file_list),
                    "csv_files": csv_files,
                    "json_files": json_files,
                    "other_files": other_files,
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(f"Successfully extracted to: {output_dir}")
                logger.info(f"Files: {len(csv_files)} CSV, {len(json_files)} JSON, {len(other_files)} other")

                return result

        except zipfile.BadZipFile as e:
            error_msg = f"Invalid ZIP file: {zip_path} - {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

        except Exception as e:
            error_msg = f"Failed to extract {zip_path}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def batch_extract(self, download_dir: Path, account_filter: Optional[list[str]] = None) -> dict[str, Any]:
        """
        Extract all ZIP files found in download directory.

        Args:
            download_dir: Directory containing ZIP files
            account_filter: Optional list of account names to filter by

        Returns:
            Dictionary with batch extraction results
        """
        zip_files = self.scan_for_zip_files(download_dir)

        if not zip_files:
            return {
                "success": True,
                "message": "No ZIP files found to extract",
                "files_processed": 0,
                "extractions": [],
            }

        extractions = []
        errors = []

        for zip_path in zip_files:
            try:
                # Try to determine account from filename
                account_name = None
                if account_filter:
                    # Check if any filter account is in filename
                    filename_lower = zip_path.name.lower()
                    for account in account_filter:
                        if account.lower() in filename_lower:
                            account_name = account
                            break

                    # Skip if account filter specified but no match found
                    if account_name is None:
                        logger.info(f"Skipping {zip_path.name} - no matching account filter")
                        continue

                extraction_result = self.extract_zip_file(zip_path, account_name)
                extractions.append(extraction_result)

            except Exception as e:
                error_info = {
                    "zip_file": str(zip_path),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                errors.append(error_info)
                logger.error(f"Failed to extract {zip_path}: {e}")

        result = {
            "success": len(errors) == 0,
            "files_processed": len(extractions),
            "files_failed": len(errors),
            "extractions": extractions,
            "errors": errors,
        }

        if errors:
            result["success"] = False
            result["message"] = f"Completed with {len(errors)} errors"
        else:
            result["message"] = f"Successfully extracted {len(extractions)} files"

        return result


def extract_amazon_zip_files(
    download_dir: Path, raw_data_dir: Path, account_filter: Optional[list[str]] = None
) -> dict[str, Any]:
    """
    Convenience function for extracting Amazon ZIP files.

    Args:
        download_dir: Directory containing downloaded ZIP files
        raw_data_dir: Directory for storing extracted data
        account_filter: Optional list of account names to filter by

    Returns:
        Dictionary with extraction results
    """
    unzipper = AmazonUnzipper(raw_data_dir)
    return unzipper.batch_extract(download_dir, account_filter)
