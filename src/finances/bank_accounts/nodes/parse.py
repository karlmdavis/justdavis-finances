"""Account data parsing flow node."""

from pathlib import Path

from finances.bank_accounts.deduplication import deduplicate_transactions
from finances.bank_accounts.format_handlers.base import ParseResult
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from finances.bank_accounts.models import BalancePoint, BankAccountsConfig, ImportPattern
from finances.core import FinancialDate


def _consolidate_intervals(
    intervals: list[tuple[FinancialDate, FinancialDate]],
) -> list[tuple[FinancialDate, FinancialDate]]:
    """Merge overlapping intervals using intersection (conservative).

    When two intervals overlap, shrink to their common area.
    Non-overlapping intervals are kept as independent entries.
    Intervals are sorted by start date before processing.
    """
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda x: x[0])
    result = []
    cur_start, cur_end = sorted_ivs[0]
    for start, end in sorted_ivs[1:]:
        if start <= cur_end:  # intervals overlap: intersect
            cur_start = max(cur_start, start)
            cur_end = min(cur_end, end)
            if cur_start > cur_end:  # intersection is empty (degenerate)
                cur_start, cur_end = start, end
        else:  # no overlap: emit current, advance
            result.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    result.append((cur_start, cur_end))
    return result


def deduplicate_balances(parsed_files: list[tuple[Path, ParseResult, float]]) -> list[BalancePoint]:
    """
    Deduplicate balance points from multiple bank export files.

    Strategy: For each date, use balance from the most recent file (by mtime).

    Args:
        parsed_files: List of (file_path, parse_result, mtime) tuples

    Returns:
        List of deduplicated BalancePoint objects, sorted chronologically by date
    """
    if not parsed_files:
        return []

    # Group balances by (date, file_path)
    # Key: (date, file_path) -> Value: (balance_points, mtime)
    balances_by_date_file: dict[tuple[FinancialDate, Path], tuple[list[BalancePoint], float]] = {}

    for file_path, parse_result, mtime in parsed_files:
        for balance in parse_result.balance_points:
            key = (balance.date, file_path)
            if key not in balances_by_date_file:
                balances_by_date_file[key] = ([], mtime)
            balances_by_date_file[key][0].append(balance)

    # For each date, find the file with the latest mtime
    # Key: date -> Value: (file_path, mtime)
    latest_file_by_date: dict[FinancialDate, tuple[Path, float]] = {}

    for (date, file_path), (_balances, mtime) in balances_by_date_file.items():
        if date not in latest_file_by_date:
            latest_file_by_date[date] = (file_path, mtime)
        else:
            _existing_path, existing_mtime = latest_file_by_date[date]
            if mtime > existing_mtime:
                latest_file_by_date[date] = (file_path, mtime)

    # Collect balances from the selected files for each date
    result: list[BalancePoint] = []

    for (date, file_path), (balances, _mtime) in balances_by_date_file.items():
        latest_path, _latest_mtime = latest_file_by_date[date]
        if file_path == latest_path:
            # This file is the latest for this date, include all balances
            result.extend(balances)

    # Sort by date (chronological order)
    result.sort(key=lambda b: b.date)

    return result


def find_format_handler(file_path: Path, import_patterns: tuple[ImportPattern, ...]) -> str | None:
    """
    Find the format handler for a file based on import patterns.

    Args:
        file_path: Path to the file to match
        import_patterns: Tuple of ImportPattern objects

    Returns:
        Format handler name if match found, None otherwise
    """
    for pattern in import_patterns:
        # Use Path.match() for glob-style matching on filename
        if file_path.match(pattern.pattern):
            return str(pattern.format_handler)
    return None


def parse_account_data(
    config: BankAccountsConfig, base_dir: Path, handler_registry: FormatHandlerRegistry
) -> dict[str, ParseResult]:
    """
    Parse raw bank files and return parsed data.

    For each account in config:
    - Reads files from base_dir/raw/{slug}
    - Matches files against import_patterns to find format handlers
    - Parses files using registered handlers
    - De-duplicates transactions and balances across overlapping files
    - Returns ParseResult with transactions, balance_points, and statement_date

    Note: This function does NOT write files. The caller is responsible for
    serialization and timestamping using DataStore.save() for Pattern C accumulation.

    Args:
        config: Bank accounts configuration
        base_dir: Base directory for data storage
        handler_registry: Registry of format handlers

    Returns:
        Dict mapping account slug to ParseResult objects
    """
    results: dict[str, ParseResult] = {}

    for account in config.accounts:
        # Get raw directory
        raw_dir = base_dir / "raw" / account.slug

        # If raw directory doesn't exist, create empty ParseResult
        if not raw_dir.exists():
            raw_dir.mkdir(parents=True)
            results[account.slug] = ParseResult.create(transactions=[])
            continue

        # Collect parsed files: (file_path, ParseResult, mtime)
        parsed_files: list[tuple[Path, ParseResult, float]] = []

        # Process each file in raw directory
        for file_path in raw_dir.iterdir():
            # Skip directories
            if not file_path.is_file():
                continue

            # Find matching format handler
            handler_name = find_format_handler(file_path, account.import_patterns)
            if handler_name is None:
                # No matching pattern, skip file
                continue

            # Get handler from registry
            try:
                handler = handler_registry.get(handler_name)
            except KeyError:
                # Handler not found, skip file
                # This should not happen if config validation ran, but be defensive
                continue

            # Parse file
            try:
                parse_result = handler.parse(file_path)
                mtime = file_path.stat().st_mtime
                parsed_files.append((file_path, parse_result, mtime))
            except Exception:  # noqa: S112
                # Parse failed, skip file
                # In production, we might want to log this
                continue

        # De-duplicate transactions and balances
        transactions = deduplicate_transactions(parsed_files)
        balances = deduplicate_balances(parsed_files)

        # Compute coverage intervals: one raw interval per file, then consolidate
        raw_intervals: list[tuple[FinancialDate, FinancialDate]] = []
        for _file_path, file_result, _mtime in parsed_files:
            start = file_result.statement_start_date or (
                min(tx.posted_date for tx in file_result.transactions) if file_result.transactions else None
            )
            end = file_result.statement_date or (
                max(tx.posted_date for tx in file_result.transactions) if file_result.transactions else None
            )
            if start and end:
                raw_intervals.append((start, end))

        coverage_intervals = tuple(_consolidate_intervals(raw_intervals))

        # Create ParseResult
        results[account.slug] = ParseResult.create(
            transactions=list(transactions),
            balance_points=list(balances),
            coverage_intervals=coverage_intervals,
        )

    return results
