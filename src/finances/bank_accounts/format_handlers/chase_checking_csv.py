"""Chase Checking CSV format handler."""

import csv
from pathlib import Path

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import Money


class ChaseCheckingCsvHandler(BankExportFormatHandler):
    """
    Chase Checking CSV format handler.

    Sign Convention: Accounting standard (debits negative, credits positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Running balance for each transaction
    """

    @property
    def format_name(self) -> str:
        return "chase_checking_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    EXPECTED_COLUMNS = (
        "Posting Date",
        "Description",
        "Amount",
        "Type",
        "Balance",
        "Check or Slip #",
    )

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase Checking CSV file."""
        transactions = []
        # Chase CSVs are newest-first. For dates with multiple transactions, the first
        # row seen for a date is the last transaction of that day — its running balance
        # is the end-of-day balance. Use setdefault so subsequent (earlier) transactions
        # on the same date don't overwrite the end-of-day value.
        balance_by_date: dict = {}

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            actual = set(reader.fieldnames or [])
            missing = set(self.EXPECTED_COLUMNS) - actual
            if missing:
                raise ValueError(f"CSV file missing expected columns: {sorted(missing)}")

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

                    # Keep only end-of-day balance (first occurrence per date in newest-first file).
                    balance_by_date.setdefault(posted_date, balance_money)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}") from e

        balance_points = [
            BalancePoint(date=date, amount=balance, available=None)
            for date, balance in balance_by_date.items()
        ]

        return ParseResult.create(transactions=transactions, balance_points=balance_points)
