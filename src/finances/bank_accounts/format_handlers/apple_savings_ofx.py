"""Apple Savings OFX format handler."""

from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult, parse_ofx_file


class AppleSavingsOfxHandler(BankExportFormatHandler):
    """
    Apple Savings OFX format handler.

    Sign Convention: Accounting standard (withdrawals negative, deposits positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Ledger balance from LEDGERBAL tag (no available balance)
    """

    FORMAT_NAME: ClassVar[str] = "apple_savings_ofx"

    @property
    def format_name(self) -> str:
        return self.FORMAT_NAME

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Savings OFX file (handles OFX 1.x SGML and OFX 2.x XML formats)."""
        # include_available=False: savings accounts don't have a credit limit / available balance.
        return parse_ofx_file(file_path, include_available=False)
