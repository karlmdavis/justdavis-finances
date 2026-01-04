"""Domain models for bank account reconciliation."""

from dataclasses import dataclass
from typing import Any

from finances.core import FinancialDate, Money


@dataclass(frozen=True)
class BankTransaction:
    """Immutable bank transaction from normalized format."""

    # Required fields
    posted_date: FinancialDate
    description: str
    amount: Money  # Negative for expenses, positive for income

    # Optional fields (account-specific)
    transaction_date: FinancialDate | None = None
    merchant: str | None = None
    type: str | None = None
    category: str | None = None
    memo: str | None = None
    purchased_by: str | None = None
    running_balance: Money | None = None
    cleared_status: str | None = None
    check_number: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        result = {
            "posted_date": str(self.posted_date),
            "description": self.description,
            "amount_milliunits": self.amount.to_milliunits(),
        }

        # Add optional fields if present
        if self.transaction_date is not None:
            result["transaction_date"] = str(self.transaction_date)
        if self.merchant is not None:
            result["merchant"] = self.merchant
        if self.type is not None:
            result["type"] = self.type
        if self.category is not None:
            result["category"] = self.category
        if self.memo is not None:
            result["memo"] = self.memo
        if self.purchased_by is not None:
            result["purchased_by"] = self.purchased_by
        if self.running_balance is not None:
            result["running_balance_milliunits"] = self.running_balance.to_milliunits()
        if self.cleared_status is not None:
            result["cleared_status"] = self.cleared_status
        if self.check_number is not None:
            result["check_number"] = self.check_number

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BankTransaction":
        """Deserialize from normalized format dict."""
        return cls(
            posted_date=FinancialDate.from_string(data["posted_date"]),
            description=data["description"],
            amount=Money.from_milliunits(data["amount_milliunits"]),
            transaction_date=(
                FinancialDate.from_string(data["transaction_date"]) if "transaction_date" in data else None
            ),
            merchant=data.get("merchant"),
            type=data.get("type"),
            category=data.get("category"),
            memo=data.get("memo"),
            purchased_by=data.get("purchased_by"),
            running_balance=(
                Money.from_milliunits(data["running_balance_milliunits"])
                if "running_balance_milliunits" in data
                else None
            ),
            cleared_status=data.get("cleared_status"),
            check_number=data.get("check_number"),
        )


@dataclass(frozen=True)
class BalancePoint:
    """Immutable balance snapshot from bank data."""

    date: FinancialDate
    amount: Money  # Ledger balance
    available: Money | None = None  # Available balance (credit accounts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        result: dict[str, Any] = {
            "date": str(self.date),
            "amount_milliunits": self.amount.to_milliunits(),
        }

        if self.available is not None:
            result["available_milliunits"] = self.available.to_milliunits()

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalancePoint":
        """Deserialize from normalized format dict."""
        return cls(
            date=FinancialDate.from_string(data["date"]),
            amount=Money.from_milliunits(data["amount_milliunits"]),
            available=(
                Money.from_milliunits(data["available_milliunits"])
                if "available_milliunits" in data
                else None
            ),
        )


@dataclass(frozen=True)
class BalanceReconciliationPoint:
    """Balance reconciliation at a single date."""

    date: FinancialDate
    bank_balance: Money
    ynab_balance: Money
    bank_txs_not_in_ynab: Money  # Sum of unmatched bank transactions
    ynab_txs_not_in_bank: Money  # Sum of unmatched YNAB transactions
    adjusted_bank_balance: Money
    adjusted_ynab_balance: Money
    is_reconciled: bool  # True if adjusted balances match exactly
    difference: Money  # adjusted_bank - adjusted_ynab

    def to_dict(self) -> dict[str, Any]:
        """Serialize for output."""
        return {
            "date": str(self.date),
            "bank_balance": self.bank_balance.to_milliunits(),
            "ynab_balance": self.ynab_balance.to_milliunits(),
            "bank_txs_not_in_ynab": self.bank_txs_not_in_ynab.to_milliunits(),
            "ynab_txs_not_in_bank": self.ynab_txs_not_in_bank.to_milliunits(),
            "adjusted_bank_balance": self.adjusted_bank_balance.to_milliunits(),
            "adjusted_ynab_balance": self.adjusted_ynab_balance.to_milliunits(),
            "is_reconciled": self.is_reconciled,
            "difference": self.difference.to_milliunits(),
        }
