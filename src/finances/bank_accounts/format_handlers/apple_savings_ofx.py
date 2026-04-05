import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import Money


class AppleSavingsOfxHandler(BankExportFormatHandler):
    """
    Apple Savings OFX format handler.

    Sign Convention: Accounting standard (withdrawals negative, deposits positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Ledger balance from LEDGERBAL tag (no available balance)
    """

    @property
    def format_name(self) -> str:
        return "apple_savings_ofx"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Savings OFX file."""
        root = ET.parse(file_path).getroot()

        transactions = self._parse_transactions(root)
        balance_points = self._parse_balances(root)

        banktranlist = root.find(".//BANKTRANLIST")
        dtstart_el = banktranlist.find("DTSTART") if banktranlist is not None else None
        dtend_el = banktranlist.find("DTEND") if banktranlist is not None else None
        statement_start_date = (
            self._parse_ofx_date(dtstart_el.text) if dtstart_el is not None and dtstart_el.text else None
        )
        statement_date = (
            self._parse_ofx_date(dtend_el.text)
            if dtend_el is not None and dtend_el.text
            else (balance_points[0].date if balance_points else None)
        )

        return ParseResult.create(
            transactions=transactions,
            balance_points=balance_points,
            statement_date=statement_date,
            statement_start_date=statement_start_date,
        )

    def _parse_transactions(self, root: ET.Element) -> list[BankTransaction]:
        """Extract transactions from OFX element tree."""
        transactions = []

        for trn in root.findall(".//STMTTRN"):
            posted_date_el = trn.find("DTPOSTED")
            amount_el = trn.find("TRNAMT")
            name_el = trn.find("NAME")

            missing_fields = []
            if posted_date_el is None or not posted_date_el.text:
                missing_fields.append("DTPOSTED")
            if amount_el is None or not amount_el.text:
                missing_fields.append("TRNAMT")
            if name_el is None or not name_el.text:
                missing_fields.append("NAME")

            if missing_fields:
                raise ValueError(
                    f"Missing required transaction fields in OFX: "
                    f"{', '.join(missing_fields)}. Expected DTPOSTED, TRNAMT, and NAME tags."
                )

            # Type narrowing after runtime validation
            posted_date_str = cast(str, posted_date_el.text)  # type: ignore[union-attr]
            amount_str = cast(str, amount_el.text)  # type: ignore[union-attr]
            name_str = cast(str, name_el.text)  # type: ignore[union-attr]

            tx = BankTransaction(
                posted_date=self._parse_ofx_date(posted_date_str),
                description=name_str,
                amount=Money.from_dollars(amount_str),
            )

            transactions.append(tx)

        return transactions

    def _parse_balances(self, root: ET.Element) -> list[BalancePoint]:
        """Extract balance from OFX element tree."""
        ledgerbal = root.find(".//LEDGERBAL")
        if ledgerbal is None:
            return []

        balamt_el = ledgerbal.find("BALAMT")
        dtasof_el = ledgerbal.find("DTASOF")

        if balamt_el is None or not balamt_el.text or dtasof_el is None or not dtasof_el.text:
            missing = []
            if balamt_el is None or not balamt_el.text:
                missing.append("BALAMT")
            if dtasof_el is None or not dtasof_el.text:
                missing.append("DTASOF")
            raise ValueError(f"LEDGERBAL tag found but missing required sub-elements: {', '.join(missing)}")

        # Savings accounts don't have available balance (unlike credit cards)
        return [
            BalancePoint(
                date=self._parse_ofx_date(dtasof_el.text),
                amount=Money.from_dollars(balamt_el.text),
                available=None,
            )
        ]
