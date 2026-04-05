"""Apple Savings CSV format handler."""

import csv
from pathlib import Path

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import Money


class AppleSavingsCsvHandler(BankExportFormatHandler):
    """
    Apple Savings CSV format handler.

    Sign Convention: Amounts are absolute values; Transaction Type (Credit/Debit) determines sign.
    Normalization: Credit → positive (deposit/inflow), Debit → negative (withdrawal/outflow)
    Balance Data: None (no balance column in this format)
    """

    @property
    def format_name(self) -> str:
        return "apple_savings_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    EXPECTED_COLUMNS = (
        "Transaction Date",
        "Posted Date",
        "Description",
        "Activity Type",
        "Transaction Type",
        "Amount",
    )

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Savings CSV file."""
        transactions = []

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            actual = set(reader.fieldnames or [])
            missing = set(self.EXPECTED_COLUMNS) - actual
            if missing:
                raise ValueError(f"CSV file missing expected columns: {sorted(missing)}")

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Parse amount (always absolute) and apply sign from Transaction Type
                    amount_str = row["Amount"].strip()
                    if not amount_str or amount_str == "---":
                        raise ValueError(f"Invalid amount format at line {row_num}: '{amount_str}'")

                    # Credit = positive (deposit/inflow), Debit = negative (withdrawal/outflow)
                    amount = Money.from_dollars(amount_str)
                    if row["Transaction Type"].strip() != "Credit":
                        amount = amount * -1

                    tx = BankTransaction(
                        posted_date=self._parse_date(row["Posted Date"]),
                        transaction_date=self._parse_date(row["Transaction Date"]),
                        description=row["Description"],
                        amount=amount,
                        type=row["Activity Type"],
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}") from e

        # No balance points - balance column is unreliable
        return ParseResult.create(transactions=transactions)
