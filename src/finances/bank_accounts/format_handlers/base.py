"""Base classes for bank export format handlers."""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, cast

from ofxtools.Parser import OFXTree

from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import FinancialDate, Money


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


def _ofx_date(date_str: str) -> FinancialDate:
    """Parse OFX YYYYMMDD format date (may have timestamp suffix)."""
    date_part = date_str[:8]
    return FinancialDate.from_string(f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}")


def _parse_ofx_transactions(root: ET.Element) -> list[BankTransaction]:
    """Extract transactions from an OFX element tree."""
    transactions = []

    for trn in root.findall(".//STMTTRN"):
        posted_date_el = trn.find("DTPOSTED")
        amount_el = trn.find("TRNAMT")
        name_el = trn.find("NAME")

        missing_fields = []
        if posted_date_el is None or not posted_date_el.text:
            missing_fields.append("DTPOSTED")
        if amount_el is None or not amount_el.text:
            missing_fields.append("TRNAMT")
        if name_el is None or not name_el.text:
            missing_fields.append("NAME")

        if missing_fields:
            raise ValueError(
                f"Missing required transaction fields in OFX: "
                f"{', '.join(missing_fields)}. Expected DTPOSTED, TRNAMT, and NAME tags."
            )

        # Type narrowing after runtime validation
        posted_date_str = cast(str, posted_date_el.text)  # type: ignore[union-attr]
        amount_str = cast(str, amount_el.text)  # type: ignore[union-attr]
        name_str = cast(str, name_el.text)  # type: ignore[union-attr]

        transactions.append(
            BankTransaction(
                posted_date=_ofx_date(posted_date_str),
                description=name_str,
                amount=Money.from_dollars(amount_str),
            )
        )

    return transactions


def _parse_ofx_balances(root: ET.Element, include_available: bool = False) -> list[BalancePoint]:
    """
    Extract balance points from an OFX element tree.

    Args:
        root: OFX element tree root
        include_available: If True, also parse AVAILBAL (for credit cards).
            Savings and checking accounts don't expose an available balance.
    """
    ledgerbal = root.find(".//LEDGERBAL")
    if ledgerbal is None:
        return []

    balamt_el = ledgerbal.find("BALAMT")
    dtasof_el = ledgerbal.find("DTASOF")

    if balamt_el is None or not balamt_el.text or dtasof_el is None or not dtasof_el.text:
        missing = []
        if balamt_el is None or not balamt_el.text:
            missing.append("BALAMT")
        if dtasof_el is None or not dtasof_el.text:
            missing.append("DTASOF")
        raise ValueError(f"LEDGERBAL tag found but missing required sub-elements: {', '.join(missing)}")

    ledger_money = Money.from_dollars(balamt_el.text)
    balance_date = _ofx_date(dtasof_el.text)

    available = None
    if include_available:
        availbal = root.find(".//AVAILBAL")
        if availbal is not None:
            avail_el = availbal.find("BALAMT")
            if avail_el is not None and avail_el.text:
                available = Money.from_dollars(avail_el.text)

    return [BalancePoint(date=balance_date, amount=ledger_money, available=available)]


def parse_ofx_file(file_path: Path, include_available: bool = False) -> ParseResult:
    """
    Parse any OFX file and return a ParseResult.

    Args:
        file_path: Path to the OFX file to parse.
        include_available: Set True for credit card accounts (reads AVAILBAL tag).
            Savings and checking accounts do not expose an available balance.

    Returns:
        ParseResult with transactions, balance points, and statement date range.

    Raises:
        ValueError: If the file is malformed or missing required fields.
    """
    parser = OFXTree()
    with open(file_path, "rb") as f:
        parser.parse(f)
    root = parser.getroot()
    if root is None:
        raise ValueError(f"OFX parser returned no root element from {file_path}")

    transactions = _parse_ofx_transactions(root)
    balance_points = _parse_ofx_balances(root, include_available=include_available)

    banktranlist = root.find(".//BANKTRANLIST")
    dtstart_el = banktranlist.find("DTSTART") if banktranlist is not None else None
    dtend_el = banktranlist.find("DTEND") if banktranlist is not None else None
    statement_start_date = _ofx_date(dtstart_el.text) if dtstart_el is not None and dtstart_el.text else None
    statement_date = (
        _ofx_date(dtend_el.text)
        if dtend_el is not None and dtend_el.text
        else (balance_points[0].date if balance_points else None)
    )

    return ParseResult.create(
        transactions=transactions,
        balance_points=balance_points,
        statement_date=statement_date,
        statement_start_date=statement_start_date,
    )


class BankExportFormatHandler(ABC):
    """Base class for all bank export format parsers."""

    # Class-level constant so the registry can read it without instantiating the handler.
    # Subclasses must define FORMAT_NAME = "..." and override format_name to return it.
    FORMAT_NAME: ClassVar[str]

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

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date (used by CSV and QIF handlers)."""
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")

    def _parse_ofx_date(self, date_str: str) -> FinancialDate:
        """Parse OFX YYYYMMDD format date (may have timestamp suffix)."""
        return _ofx_date(date_str)

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
