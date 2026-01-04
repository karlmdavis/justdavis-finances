"""Apple Savings CSV format handler."""

import csv
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


class AppleSavingsCsvHandler(BankExportFormatHandler):
    """
    Apple Savings CSV format handler.

    Sign Convention: Consumer perspective (deposits positive, withdrawals negative)
    Normalization: Flip all signs (consumer → accounting)
    Balance Data: None (balance column exists but is unreliable - ignore it)
    """

    EXPECTED_HEADERS: ClassVar[list[str]] = [
        "Transaction Date",
        "Clearing Date",
        "Description",
        "Amount (USD)",
        "Transaction Type",
        "Balance (USD)",
    ]

    @property
    def format_name(self) -> str:
        return "apple_savings_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is an Apple Savings CSV."""
        if file_path.suffix.lower() != ".csv":
            return False

        try:
            with open(file_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                return headers == self.EXPECTED_HEADERS
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Savings CSV file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Apple Savings CSV file: {file_path}")

        transactions = []

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Parse amount and flip sign (consumer → accounting)
                    amount_str = row["Amount (USD)"].strip()
                    if not amount_str or amount_str == "---":
                        raise ValueError(f"Invalid amount format at line {row_num}: '{amount_str}'")

                    amount_decimal = Decimal(amount_str)
                    # Flip sign: consumer perspective → accounting standard
                    amount_cents = int(amount_decimal * -100)

                    tx = BankTransaction(
                        posted_date=self._parse_date(row["Clearing Date"]),
                        transaction_date=self._parse_date(row["Transaction Date"]),
                        description=row["Description"],
                        amount=Money.from_cents(amount_cents),
                        type=row["Transaction Type"],
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}") from e

        # No balance points - balance column is unreliable
        return ParseResult.create(transactions=transactions)

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        # Apple Savings CSV uses MM/DD/YYYY format
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
