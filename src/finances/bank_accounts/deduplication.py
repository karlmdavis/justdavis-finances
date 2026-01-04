"""Transaction de-duplication logic for bank account reconciliation."""

from pathlib import Path

from finances.bank_accounts.format_handlers.base import ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate


def deduplicate_transactions(parsed_files: list[tuple[Path, ParseResult, float]]) -> list[BankTransaction]:
    """
    Deduplicate transactions from multiple bank export files.

    Strategy: For each date, use transactions from the most recent file (by mtime).
    Within the same file, preserve ALL transactions (no intra-file deduplication).

    This handles the common scenario where monthly bank exports overlap
    (e.g., January export includes last few days of December).
    We assume newer exports have more accurate/complete data.

    Args:
        parsed_files: List of (file_path, parse_result, mtime) tuples

    Returns:
        List of deduplicated BankTransaction objects, sorted chronologically
        by posted_date
    """
    if not parsed_files:
        return []

    # Group transactions by (posted_date, file_path)
    # Key: (posted_date, file_path) -> Value: (transactions, mtime)
    transactions_by_date_file: dict[tuple[FinancialDate, Path], tuple[list[BankTransaction], float]] = {}

    for file_path, parse_result, mtime in parsed_files:
        for transaction in parse_result.transactions:
            key = (transaction.posted_date, file_path)
            if key not in transactions_by_date_file:
                transactions_by_date_file[key] = ([], mtime)
            transactions_by_date_file[key][0].append(transaction)

    # For each date, find the file with the latest mtime
    # Key: posted_date -> Value: (file_path, mtime)
    latest_file_by_date: dict[FinancialDate, tuple[Path, float]] = {}

    for (posted_date, file_path), (_txs, mtime) in transactions_by_date_file.items():
        if posted_date not in latest_file_by_date:
            latest_file_by_date[posted_date] = (file_path, mtime)
        else:
            _existing_path, existing_mtime = latest_file_by_date[posted_date]
            if mtime > existing_mtime:
                latest_file_by_date[posted_date] = (file_path, mtime)

    # Collect transactions from the selected files for each date
    result: list[BankTransaction] = []

    for (posted_date, file_path), (txs, _mtime) in transactions_by_date_file.items():
        latest_path, _latest_mtime = latest_file_by_date[posted_date]
        if file_path == latest_path:
            # This file is the latest for this date, include all transactions
            result.extend(txs)

    # Sort by posted_date (chronological order)
    result.sort(key=lambda tx: tx.posted_date)

    return result
