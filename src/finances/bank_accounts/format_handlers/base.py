"""Base classes for bank export format handlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import FinancialDate


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing a bank export file."""

    transactions: tuple[BankTransaction, ...]  # Immutable sequence
    balance_points: tuple[BalancePoint, ...]  # Immutable sequence
    statement_date: FinancialDate | None = None  # For statement-based exports (OFX/QIF)
    statement_start_date: FinancialDate | None = None  # Start of statement period (per-file)
    coverage_intervals: tuple[tuple[FinancialDate, FinancialDate], ...] = ()  # Authoritative date ranges

    @classmethod
    def create(
        cls,
        transactions: list[BankTransaction],
        balance_points: list[BalancePoint] | None = None,
        statement_date: FinancialDate | None = None,
        statement_start_date: FinancialDate | None = None,
        coverage_intervals: tuple[tuple[FinancialDate, FinancialDate], ...] = (),
    ) -> "ParseResult":
        """Create ParseResult from lists (converts to immutable tuples)."""
        return cls(
            transactions=tuple(transactions),
            balance_points=tuple(balance_points or []),
            statement_date=statement_date,
            statement_start_date=statement_start_date,
            coverage_intervals=coverage_intervals,
        )


class BankExportFormatHandler(ABC):
    """Base class for all bank export format parsers."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Unique identifier for this format (e.g., 'apple_card_csv')."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this handler can process (e.g., ('.csv',))."""
        pass

    @abstractmethod
    def validate_file(self, file_path: Path) -> bool:
        """
        Quick validation that file matches expected format.

        Check:
        - File extension
        - Header structure (for CSV)
        - Root elements (for XML/OFX)
        - Required fields present

        Returns:
            True if file appears to match this handler's format, False otherwise.
        """
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse bank export file and return transactions and balance data.

        Responsibilities:
        1. Read format-specific file structure
        2. Normalize signs to accounting standard:
           - Expenses (purchases, debits) → NEGATIVE
           - Income (payments, credits) → POSITIVE
        3. Extract all available fields
        4. Extract balance data if available
        5. Return immutable ParseResult

        Args:
            file_path: Path to the bank export file to parse

        Returns:
            ParseResult containing parsed transactions and balance points

        Raises:
            ValueError: If file is malformed or missing required fields
        """
        pass
