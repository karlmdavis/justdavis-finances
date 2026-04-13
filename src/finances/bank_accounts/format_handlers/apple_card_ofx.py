"""Apple Card OFX format handler."""

from pathlib import Path
from typing import ClassVar

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult, parse_ofx_file


class AppleCardOfxHandler(BankExportFormatHandler):
    """
    Apple Card OFX format handler.

    Sign Convention: Accounting standard (purchases negative, balance negative)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Statement balance (LEDGERBAL) and available credit (AVAILBAL)
    """

    FORMAT_NAME: ClassVar[str] = "apple_card_ofx"

    @property
    def format_name(self) -> str:
        return self.FORMAT_NAME

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Card OFX file (handles OFX 1.x SGML and OFX 2.x XML formats)."""
        # include_available=True: Apple Card is a credit card and exposes AVAILBAL (remaining credit).
        return parse_ofx_file(file_path, include_available=True)
