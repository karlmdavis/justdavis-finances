#!/usr/bin/env python3
"""
Core Data Models for Davis Family Finances

Common data structures used across all financial domains.
These models provide type safety and consistent interfaces for financial data.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from .dates import FinancialDate
from .money import Money


class TransactionType(Enum):
    """Types of financial transactions."""

    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class MatchConfidence(Enum):
    """Confidence levels for transaction matching."""

    HIGH = "high"  # > 0.90
    MEDIUM = "medium"  # 0.75 - 0.90
    LOW = "low"  # 0.50 - 0.75
    NONE = "none"  # < 0.50


@dataclass
class Transaction:
    """
    Universal transaction model used across all financial systems.

    Represents a financial transaction from any source (YNAB, bank, etc.)
    with standardized fields for consistent processing.
    """

    id: str
    date_obj: FinancialDate
    amount_money: Money
    description: str
    account_name: str

    # Optional fields
    payee_name: str | None = None
    category_name: str | None = None
    memo: str | None = None
    cleared: bool = True
    approved: bool = True

    # Metadata
    source: str = "unknown"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transaction":
        """
        Create Transaction from dict with flexible field names.

        Supports both old (amount, date) and new (amount_money, date_obj) field names.
        """
        # Handle date field
        if "date_obj" in data:
            date_obj = data["date_obj"]
        elif "date" in data:
            date_value = data["date"]
            if isinstance(date_value, FinancialDate):
                date_obj = date_value
            elif isinstance(date_value, str):
                date_obj = FinancialDate.from_string(date_value)
            else:
                date_obj = FinancialDate(date=date_value)
        else:
            raise ValueError("Transaction requires either 'date' or 'date_obj'")

        # Handle amount field
        if "amount_money" in data:
            amount_money = data["amount_money"]
        elif "amount" in data:
            amount_value = data["amount"]
            if isinstance(amount_value, Money):
                amount_money = amount_value
            else:
                # Assume milliunits
                amount_money = Money.from_milliunits(amount_value)
        else:
            raise ValueError("Transaction requires either 'amount' or 'amount_money'")

        return cls(
            id=data["id"],
            date_obj=date_obj,
            amount_money=amount_money,
            description=data["description"],
            account_name=data["account_name"],
            payee_name=data.get("payee_name"),
            category_name=data.get("category_name"),
            memo=data.get("memo"),
            cleared=data.get("cleared", True),
            approved=data.get("approved", True),
            source=data.get("source", "unknown"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @property
    def date(self) -> date:
        """Get date as Python date object for backward compatibility."""
        return self.date_obj.date

    @property
    def amount(self) -> int:
        """Get amount in milliunits for backward compatibility."""
        return self.amount_money.to_milliunits()

    @property
    def transaction_type(self) -> TransactionType:
        """Determine transaction type based on amount."""
        amount_val = self.amount_money.to_cents()
        if amount_val < 0:
            return TransactionType.EXPENSE
        elif amount_val > 0:
            return TransactionType.INCOME
        else:
            return TransactionType.TRANSFER

    @property
    def amount_cents(self) -> int:
        """Get amount in cents."""
        return self.amount_money.to_cents()

    @property
    def amount_dollars(self) -> str:
        """Get formatted amount as dollar string."""
        return str(self.amount_money)


@dataclass
class Receipt:
    """
    Universal receipt model for purchase records.

    Represents a receipt from any vendor (Amazon, Apple, etc.)
    with standardized fields for consistent processing.
    """

    id: str
    date_obj: FinancialDate
    vendor: str
    total_money: Money

    # Optional fields
    subtotal_money: Money | None = None
    tax_money: Money | None = None
    customer_id: str | None = None
    order_number: str | None = None

    # Items
    items: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    source: str = "unknown"
    created_at: datetime | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Receipt":
        """
        Create Receipt from dict with flexible field names.

        Supports both old (date, total_amount, subtotal, tax_amount) and
        new (date_obj, total_money, subtotal_money, tax_money) field names.
        """
        # Handle date field
        if "date_obj" in data:
            date_obj = data["date_obj"]
        elif "date" in data:
            date_value = data["date"]
            if isinstance(date_value, FinancialDate):
                date_obj = date_value
            elif isinstance(date_value, str):
                date_obj = FinancialDate.from_string(date_value)
            else:
                date_obj = FinancialDate(date=date_value)
        else:
            raise ValueError("Receipt requires either 'date' or 'date_obj'")

        # Handle total_money field
        if "total_money" in data:
            total_money = data["total_money"]
        elif "total_amount" in data:
            total_value = data["total_amount"]
            if isinstance(total_value, Money):
                total_money = total_value
            else:
                # Assume cents
                total_money = Money.from_cents(total_value)
        else:
            raise ValueError("Receipt requires either 'total_amount' or 'total_money'")

        # Handle optional subtotal/tax
        subtotal_money = None
        if "subtotal_money" in data:
            subtotal_money = data["subtotal_money"]
        elif "subtotal" in data and data["subtotal"] is not None:
            subtotal_money = Money.from_cents(data["subtotal"])

        tax_money = None
        if "tax_money" in data:
            tax_money = data["tax_money"]
        elif "tax_amount" in data and data["tax_amount"] is not None:
            tax_money = Money.from_cents(data["tax_amount"])

        return cls(
            id=data["id"],
            date_obj=date_obj,
            vendor=data["vendor"],
            total_money=total_money,
            subtotal_money=subtotal_money,
            tax_money=tax_money,
            customer_id=data.get("customer_id"),
            order_number=data.get("order_number"),
            items=data.get("items", []),
            source=data.get("source", "unknown"),
            created_at=data.get("created_at"),
            raw_data=data.get("raw_data"),
        )

    @property
    def date(self) -> date:
        """Get date as Python date object for backward compatibility."""
        return self.date_obj.date

    @property
    def total_amount(self) -> int:
        """Get total in cents for backward compatibility."""
        return self.total_money.to_cents()

    @property
    def subtotal(self) -> int | None:
        """Get subtotal in cents for backward compatibility."""
        return self.subtotal_money.to_cents() if self.subtotal_money else None

    @property
    def tax_amount(self) -> int | None:
        """Get tax in cents for backward compatibility."""
        return self.tax_money.to_cents() if self.tax_money else None

    @property
    def item_count(self) -> int:
        """Get total number of items."""
        return len(self.items)

    @property
    def total_dollars(self) -> str:
        """Get formatted total as dollar string."""
        return str(self.total_money)


@dataclass
class MatchResult:
    """
    Result of matching a transaction to receipt(s).

    Contains the matched transaction, receipts, and metadata about
    the matching process and confidence level.
    """

    transaction: Transaction
    receipts: list[Receipt]
    confidence: float
    match_method: str

    # Optional fields
    date_difference: int | None = None  # Days between transaction and receipt
    amount_difference: int | None = None  # Difference in cents
    unmatched_amount: int = 0  # Amount not covered by receipts

    # Processing metadata
    processing_time: float | None = None
    strategy_used: str | None = None
    notes: str | None = None
    created_at: datetime | None = field(default_factory=datetime.now)

    @property
    def confidence_level(self) -> MatchConfidence:
        """Get confidence level enum based on numeric confidence."""
        if self.confidence >= 0.90:
            return MatchConfidence.HIGH
        elif self.confidence >= 0.75:
            return MatchConfidence.MEDIUM
        elif self.confidence >= 0.50:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.NONE

    @property
    def is_exact_match(self) -> bool:
        """Check if this is an exact amount and date match."""
        return (
            self.confidence >= 0.95
            and (self.date_difference or 0) <= 1
            and (self.amount_difference or 0) == 0
        )

    @property
    def total_receipt_amount(self) -> int:
        """Get total amount of all matched receipts in cents."""
        return sum(receipt.total_amount for receipt in self.receipts)


@dataclass
class Account:
    """
    Financial account information.

    Represents a bank account, credit card, or other financial account
    with standardized fields for consistent processing.
    """

    id: str
    name: str
    type: str

    # Optional fields
    institution: str | None = None
    balance: int | None = None  # In milliunits
    currency: str = "USD"
    active: bool = True

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def balance_dollars(self) -> str:
        """Get formatted balance as dollar string."""
        if self.balance is None:
            return "Unknown"
        from .currency import format_milliunits

        return format_milliunits(self.balance)


@dataclass
class Category:
    """
    Transaction category information.

    Represents a category or subcategory for transaction classification
    with hierarchical support.
    """

    id: str
    name: str

    # Optional fields
    parent_id: str | None = None
    parent_name: str | None = None
    group_name: str | None = None
    budgeted: int | None = None  # In milliunits
    activity: int | None = None  # In milliunits

    # Metadata
    active: bool = True
    created_at: datetime | None = None

    @property
    def full_name(self) -> str:
        """Get full category name including parent."""
        if self.parent_name:
            return f"{self.parent_name}: {self.name}"
        return self.name


@dataclass
class ProcessingResult:
    """
    Result of processing a batch of transactions or receipts.

    Contains summary statistics and details about the processing operation.
    """

    total_processed: int
    successful: int
    failed: int
    errors: list[str] = field(default_factory=list)

    # Timing information
    start_time: datetime | None = None
    end_time: datetime | None = None
    processing_time: float | None = None

    # Results
    results: list[Any] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.successful / self.total_processed) * 100

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.failed / self.total_processed) * 100


# Type aliases for common data structures
TransactionList = list[Transaction]
ReceiptList = list[Receipt]
MatchResultList = list[MatchResult]
AccountList = list[Account]
CategoryList = list[Category]


# Common data validation functions
def validate_transaction(transaction: Transaction) -> bool:
    """Validate a transaction has required fields."""
    return bool(
        transaction.id
        and transaction.date_obj
        and transaction.description
        and transaction.account_name
        and transaction.amount_money
    )


def validate_receipt(receipt: Receipt) -> bool:
    """Validate a receipt has required fields."""
    return bool(
        receipt.id
        and receipt.date_obj
        and receipt.vendor
        and receipt.total_money
        and receipt.total_money.to_cents() >= 0
    )


def validate_match_result(match_result: MatchResult) -> bool:
    """Validate a match result has required fields."""
    return bool(
        validate_transaction(match_result.transaction)
        and all(validate_receipt(r) for r in match_result.receipts)
        and 0.0 <= match_result.confidence <= 1.0
        and match_result.match_method
    )
