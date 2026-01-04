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
