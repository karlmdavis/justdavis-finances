import re
from pathlib import Path
from typing import cast

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import FinancialDate, Money


class AppleCardOfxHandler(BankExportFormatHandler):
    """
    Apple Card OFX format handler.

    Sign Convention: Accounting standard (purchases negative, balance negative)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Statement balance from LEDGERBAL tag
    """

    @property
    def format_name(self) -> str:
        return "apple_card_ofx"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is an OFX file."""
        if file_path.suffix.lower() != ".ofx":
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
            return "<OFX>" in content and "<STMTTRN>" in content
        except (OSError, UnicodeDecodeError):
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Card OFX file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Apple Card OFX file: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        transactions = self._parse_transactions(content)
        balance_points = self._parse_balances(content)
        statement_date = balance_points[0].date if balance_points else None

        return ParseResult.create(
            transactions=transactions, balance_points=balance_points, statement_date=statement_date
        )

    def _parse_transactions(self, content: str) -> list[BankTransaction]:
        """Extract transactions from OFX content."""
        transactions = []

        # Find all STMTTRN blocks
        stmttrn_pattern = r"<STMTTRN>(.*?)</STMTTRN>"
        for match in re.finditer(stmttrn_pattern, content, re.DOTALL):
            trn_block = match.group(1)

            # Extract fields
            posted_date = self._extract_tag(trn_block, "DTPOSTED")
            amount = self._extract_tag(trn_block, "TRNAMT")
            name = self._extract_tag(trn_block, "NAME")

            if not all([posted_date, amount, name]):
                missing_fields = []
                if not posted_date:
                    missing_fields.append("DTPOSTED")
                if not amount:
                    missing_fields.append("TRNAMT")
                if not name:
                    missing_fields.append("NAME")
                raise ValueError(
                    f"Missing required transaction fields in OFX: "
                    f"{', '.join(missing_fields)}. Expected DTPOSTED, TRNAMT, and NAME tags."
                )

            # Type narrowing after runtime validation
            posted_date = cast(str, posted_date)
            amount = cast(str, amount)
            name = cast(str, name)

            # Parse amount (already accounting standard - use as-is)
            amount_money = Money.from_dollars(amount)

            tx = BankTransaction(
                posted_date=self._parse_ofx_date(posted_date),
                description=name,
                amount=amount_money,
            )

            transactions.append(tx)

        return transactions

    def _parse_balances(self, content: str) -> list[BalancePoint]:
        """Extract balance from OFX content."""
        # Extract LEDGERBAL
        ledger_bal = self._extract_tag(content, "BALAMT", parent="LEDGERBAL")
        ledger_date = self._extract_tag(content, "DTASOF", parent="LEDGERBAL")

        if not ledger_bal or not ledger_date:
            return []  # No balance data

        # Extract AVAILBAL (optional)
        avail_bal = self._extract_tag(content, "BALAMT", parent="AVAILBAL")

        # Parse amounts
        ledger_money = Money.from_dollars(ledger_bal)

        available = None
        if avail_bal:
            available = Money.from_dollars(avail_bal)

        balance = BalancePoint(
            date=self._parse_ofx_date(ledger_date), amount=ledger_money, available=available
        )

        return [balance]

    def _extract_tag(self, content: str, tag: str, parent: str | None = None) -> str | None:
        """Extract value from OFX tag."""
        if parent:
            # Find parent block first
            parent_pattern = f"<{parent}>(.*?)</{parent}>"
            parent_match = re.search(parent_pattern, content, re.DOTALL)
            if not parent_match:
                return None
            content = parent_match.group(1)

        # Extract tag value
        pattern = f"<{tag}>(.*?)<"
        match = re.search(pattern, content)
        return match.group(1).strip() if match else None

    def _parse_ofx_date(self, date_str: str) -> FinancialDate:
        """Parse OFX date format (YYYYMMDD)."""
        # OFX date format: YYYYMMDD (may have timestamp suffix)
        date_part = date_str[:8]  # Take first 8 characters
        year = date_part[:4]
        month = date_part[4:6]
        day = date_part[6:8]
        return FinancialDate.from_string(f"{year}-{month}-{day}")
