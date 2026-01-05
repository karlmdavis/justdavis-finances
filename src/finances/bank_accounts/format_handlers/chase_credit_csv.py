"""Chase Credit CSV format handler."""

import csv
from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


class ChaseCreditCsvHandler(BankExportFormatHandler):
    """
    Chase Credit Card CSV format handler.

    Sign Convention: Accounting standard (purchases negative, payments positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: None (CSV doesn't include balance data)
    """

    EXPECTED_HEADERS: ClassVar[list[str]] = [
        "Transaction Date",
        "Post Date",
        "Description",
        "Category",
        "Type",
        "Amount",
        "Memo",
    ]

    @property
    def format_name(self) -> str:
        return "chase_credit_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is a Chase Credit CSV."""
        if file_path.suffix.lower() != ".csv":
            return False

        try:
            with open(file_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                return headers == self.EXPECTED_HEADERS
        except (OSError, UnicodeDecodeError):
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase Credit CSV file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Chase Credit CSV file: {file_path}")

        transactions = []

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Parse amount (already accounting standard - use as-is)
                    amount_str = row["Amount"].strip()
                    if not amount_str or amount_str == "---":
                        raise ValueError(f"Invalid amount format at line {row_num}: '{amount_str}'")

                    # NO sign flip - already accounting standard
                    amount = Money.from_dollars(amount_str)

                    # Parse memo (may be empty)
                    memo_str = row["Memo"].strip()
                    memo = memo_str if memo_str else None

                    # Parse transaction date and posted date
                    transaction_date = self._parse_date(row["Transaction Date"])
                    posted_date = self._parse_date(row["Post Date"])

                    # Create transaction (NO running_balance for credit cards)
                    tx = BankTransaction(
                        transaction_date=transaction_date,
                        posted_date=posted_date,
                        description=row["Description"],
                        amount=amount,
                        type=row["Type"],
                        category=row["Category"],
                        memo=memo,
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}") from e

        # NO balance_points for credit card CSV (doesn't include balance data)
        return ParseResult.create(transactions=transactions, balance_points=[])

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        # Chase CSV uses MM/DD/YYYY format
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
