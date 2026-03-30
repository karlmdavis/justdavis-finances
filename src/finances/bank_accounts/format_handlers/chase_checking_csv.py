"""Chase Checking CSV format handler."""

import csv
from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import FinancialDate, Money


class ChaseCheckingCsvHandler(BankExportFormatHandler):
    """
    Chase Checking CSV format handler.

    Sign Convention: Accounting standard (debits negative, credits positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Running balance for each transaction
    """

    EXPECTED_HEADERS: ClassVar[list[str]] = [
        "Details",
        "Posting Date",
        "Description",
        "Amount",
        "Type",
        "Balance",
        "Check or Slip #",
    ]

    @property
    def format_name(self) -> str:
        return "chase_checking_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase Checking CSV file."""
        transactions = []
        balance_points = []

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

                    # Parse running balance
                    balance_str = row["Balance"].strip()
                    balance_money = Money.from_dollars(balance_str)

                    # Parse check number (may be empty)
                    check_number_str = row["Check or Slip #"].strip()
                    check_number = check_number_str if check_number_str else None

                    # Parse posted date
                    posted_date = self._parse_date(row["Posting Date"])

                    # Create transaction with running balance
                    tx = BankTransaction(
                        posted_date=posted_date,
                        description=row["Description"],
                        amount=amount,
                        type=row["Type"],
                        running_balance=balance_money,
                        check_number=check_number,
                    )

                    transactions.append(tx)

                    # Create balance point for this transaction
                    balance_point = BalancePoint(
                        date=posted_date,
                        amount=balance_money,
                        available=None,  # Checking accounts don't track available balance separately
                    )

                    balance_points.append(balance_point)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}") from e

        return ParseResult.create(transactions=transactions, balance_points=balance_points)

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        # Chase CSV uses MM/DD/YYYY format
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
