"""Chase Credit QIF format handler."""

from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


class ChaseCreditQifHandler(BankExportFormatHandler):
    """
    Chase Credit Card QIF (Quicken Interchange Format) handler.

    Sign Convention: Accounting standard (purchases negative, payments positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: None (QIF doesn't include balance data for Chase credit)

    QIF Format:
    - Text format with field codes (one field per line)
    - Header: !Type:CCard or !Type:Bank
    - Field codes:
      - D = Date (MM/DD/YYYY)
      - T = Amount (already accounting standard)
      - P = Payee/Description
      - M = Memo (optional)
      - C = Cleared status (optional)
      - N = Check number (optional)
      - ^ = End of transaction marker
    """

    VALID_HEADERS: ClassVar[list[str]] = ["!Type:CCard", "!Type:Bank"]

    @property
    def format_name(self) -> str:
        return "chase_credit_qif"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".qif",)

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase Credit QIF file."""
        transactions = []

        with open(file_path, encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]

        # Validate and skip header line
        if not lines or lines[0] not in self.VALID_HEADERS:
            raise ValueError(
                f"Invalid QIF header. Expected one of {self.VALID_HEADERS}, "
                f"got: {repr(lines[0]) if lines else 'empty file'}"
            )
        i = 1
        current_tx: dict[str, str] = {}
        line_num = 2  # Start at 2 (header is line 1)

        while i < len(lines):
            line = lines[i]

            if not line:  # Skip empty lines
                i += 1
                line_num += 1
                continue

            # Transaction field codes
            if line.startswith("D"):
                current_tx["date"] = line[1:]
            elif line.startswith("T"):
                current_tx["amount"] = line[1:]
            elif line.startswith("P"):
                current_tx["payee"] = line[1:]
            elif line.startswith("M"):
                current_tx["memo"] = line[1:]
            elif line.startswith("C"):
                current_tx["cleared"] = line[1:]
            elif line.startswith("N"):
                current_tx["check_number"] = line[1:]
            elif line == "^":
                # End of transaction - parse and create BankTransaction
                try:
                    tx = self._parse_transaction(current_tx, line_num)
                    transactions.append(tx)
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error near line {line_num}: {e}") from e

                # Reset for next transaction
                current_tx = {}

            i += 1
            line_num += 1

        # NO balance_points for QIF (doesn't include balance data)
        return ParseResult.create(transactions=transactions, balance_points=[])

    def _parse_transaction(self, tx_data: dict[str, str], line_num: int) -> BankTransaction:
        """Parse transaction data from QIF field dictionary."""
        # Parse amount (already accounting standard - use as-is)
        amount_str = tx_data.get("amount", "").strip()
        if not amount_str or amount_str == "---":
            raise ValueError(f"Invalid amount format at line {line_num}: '{amount_str}'")

        # NO sign flip - already accounting standard
        amount = Money.from_dollars(amount_str)

        # Parse date (MM/DD/YYYY format)
        date_str = tx_data.get("date", "").strip()
        if not date_str:
            raise ValueError(f"Missing date at line {line_num}")
        posted_date = self._parse_date(date_str)

        # Get payee/description (default to "Unknown" if missing)
        description = tx_data.get("payee", "Unknown").strip() or "Unknown"

        # Get cleared status (optional)
        cleared_status = tx_data.get("cleared")

        # Get memo (optional)
        memo = tx_data.get("memo")

        # Get check number (optional)
        check_number = tx_data.get("check_number")

        # Create transaction (NO running_balance for credit cards)
        return BankTransaction(
            posted_date=posted_date,
            description=description,
            amount=amount,
            memo=memo,
            cleared_status=cleared_status,
            check_number=check_number,
        )

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        # QIF uses MM/DD/YYYY format
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
