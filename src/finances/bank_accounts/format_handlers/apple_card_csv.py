"""Apple Card CSV format handler."""

import csv
from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


class AppleCardCsvHandler(BankExportFormatHandler):
    """
    Apple Card CSV format handler.

    Sign Convention: Consumer perspective (purchases positive, payments negative)
    Normalization: Flip all signs (consumer → accounting)
    Balance Data: None (CSV doesn't include balance)
    """

    EXPECTED_HEADERS: ClassVar[list[str]] = [
        "Transaction Date",
        "Clearing Date",
        "Description",
        "Merchant",
        "Category",
        "Type",
        "Amount (USD)",
        "Purchased By",
    ]

    @property
    def format_name(self) -> str:
        return "apple_card_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Card CSV file."""
        transactions = []

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Parse amount and flip sign (consumer → accounting)
                    amount_str = row["Amount (USD)"].strip()
                    if not amount_str or amount_str == "---":
                        raise ValueError(f"Invalid amount format at line {row_num}: '{amount_str}'")

                    # Flip sign: consumer perspective → accounting standard
                    amount = Money.from_dollars(amount_str) * -1

                    tx = BankTransaction(
                        posted_date=self._parse_date(row["Clearing Date"]),
                        transaction_date=self._parse_date(row["Transaction Date"]),
                        description=row["Description"],
                        merchant=row["Merchant"],
                        amount=amount,
                        type=row["Type"],
                        category=row["Category"],
                        purchased_by=row["Purchased By"],
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}") from e

        return ParseResult.create(transactions=transactions)

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        # Apple Card CSV uses MM/DD/YYYY format
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
