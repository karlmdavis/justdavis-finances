"""Account data retrieval flow node."""

import shutil
from pathlib import Path

from finances.bank_accounts.models import BankAccountsConfig


def retrieve_account_data(config: BankAccountsConfig, base_dir: Path) -> dict[str, dict[str, int]]:
    """
    Copy bank export files from source to raw directory.

    For each account in config:
    - Expands ~ in source_directory path
    - Creates destination directory at base_dir/raw/{slug}
    - For each import_pattern, finds matching files using glob
    - Copies files that don't already exist with same name and size
    - Tracks files copied and skipped per account

    Args:
        config: Bank accounts configuration
        base_dir: Base directory for data storage

    Returns:
        Summary dict mapping account slug to {"copied": N, "skipped": M}

    Raises:
        FileNotFoundError: If source_directory does not exist for any account
    """
    summary: dict[str, dict[str, int]] = {}

    for account in config.accounts:
        # Expand ~ in source path
        source_dir = Path(account.source_directory).expanduser()

        # Validate source directory exists
        if not source_dir.exists():
            raise FileNotFoundError(
                f"Source directory does not exist for account '{account.slug}': {source_dir}"
            )

        # Create destination directory
        dest_dir = base_dir / "raw" / account.slug
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Track files for this account
        files_copied = 0
        files_skipped = 0

        # Collect matching files across all patterns, deduplicating files matched by multiple patterns
        matched_files: set[Path] = set()
        for pattern in account.import_patterns:
            matched_files.update(source_dir.glob(pattern.pattern))

        for source_file in sorted(matched_files):
            # Skip directories (glob might match them)
            if not source_file.is_file():
                continue

            dest_file = dest_dir / source_file.name

            # Check if file already exists with same size
            if dest_file.exists() and dest_file.stat().st_size == source_file.stat().st_size:
                files_skipped += 1
            else:
                # Copy file with metadata preservation
                shutil.copy2(source_file, dest_file)
                files_copied += 1

        # Store summary for this account
        summary[account.slug] = {"copied": files_copied, "skipped": files_skipped}

    return summary
