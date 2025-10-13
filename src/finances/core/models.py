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
    date: date | str
    amount: int  # In milliunits (YNAB standard) - LEGACY
    description: str
    account_name: str

    # New type-safe fields
    amount_money: Money | None = None
    date_obj: FinancialDate | None = None

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

    def __post_init__(self) -> None:
        """Normalize data and sync legacy/modern fields."""
        # Convert string dates to date objects (legacy behavior)
        if isinstance(self.date, str):
            date_str = self.date
            try:
                object.__setattr__(self, "date", datetime.strptime(date_str, "%Y-%m-%d").date())
            except ValueError:
                # Try other common formats
                for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        object.__setattr__(self, "date", datetime.strptime(date_str, fmt).date())
                        break
                    except ValueError:
                        continue

        # Sync amount_money with legacy amount field
        if self.amount_money is not None and self.amount == 0:
            object.__setattr__(self, "amount", self.amount_money.to_milliunits())
        elif self.amount_money is None and self.amount != 0:
            # Create Money from legacy milliunits
            object.__setattr__(self, "amount_money", Money.from_milliunits(self.amount))

        # Sync date_obj with legacy date field
        if self.date_obj is not None and isinstance(self.date, str):
            object.__setattr__(self, "date", self.date_obj.date)
        elif self.date_obj is None and isinstance(self.date, date):
            object.__setattr__(self, "date_obj", FinancialDate(date=self.date))

    @property
    def transaction_type(self) -> TransactionType:
        """Determine transaction type based on amount."""
        amount_val = self.amount_money.to_cents() if self.amount_money else self.amount
        if amount_val < 0:
            return TransactionType.EXPENSE
        elif amount_val > 0:
            return TransactionType.INCOME
        else:
            return TransactionType.TRANSFER

    @property
    def amount_cents(self) -> int:
        """Get amount in cents."""
        # amount_money is always set by __post_init__
        if self.amount_money is None:
            raise ValueError("amount_money not initialized")
        return self.amount_money.to_cents()

    @property
    def amount_dollars(self) -> str:
        """Get formatted amount as dollar string."""
        # amount_money is always set by __post_init__
        if self.amount_money is None:
            raise ValueError("amount_money not initialized")
        return str(self.amount_money)


@dataclass
class Receipt:
    """
    Universal receipt model for purchase records.

    Represents a receipt from any vendor (Amazon, Apple, etc.)
    with standardized fields for consistent processing.
    """

    id: str
    date: date | str
    vendor: str
    total_amount: int  # In cents - LEGACY

    # New type-safe fields
    total_money: Money | None = None
    date_obj: FinancialDate | None = None

    # Optional fields
    subtotal: int | None = None  # In cents - LEGACY
    tax_amount: int | None = None  # In cents - LEGACY
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

    def __post_init__(self) -> None:
        """Normalize data and sync legacy/modern fields."""
        # Date conversion (legacy)
        if isinstance(self.date, str):
            date_str = self.date
            try:
                object.__setattr__(self, "date", datetime.strptime(date_str, "%Y-%m-%d").date())
            except ValueError:
                # Try other common formats
                for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        object.__setattr__(self, "date", datetime.strptime(date_str, fmt).date())
                        break
                    except ValueError:
                        continue

        # Sync total_money with legacy total_amount
        if self.total_money is not None and self.total_amount == 0:
            object.__setattr__(self, "total_amount", self.total_money.to_cents())
        elif self.total_money is None and self.total_amount != 0:
            object.__setattr__(self, "total_money", Money.from_cents(self.total_amount))

        # Sync date_obj
        if self.date_obj is None and isinstance(self.date, date):
            object.__setattr__(self, "date_obj", FinancialDate(date=self.date))

        # Sync subtotal and tax
        if self.subtotal_money is None and self.subtotal is not None:
            object.__setattr__(self, "subtotal_money", Money.from_cents(self.subtotal))
        if self.tax_money is None and self.tax_amount is not None:
            object.__setattr__(self, "tax_money", Money.from_cents(self.tax_amount))

    @property
    def item_count(self) -> int:
        """Get total number of items."""
        return len(self.items)

    @property
    def total_dollars(self) -> str:
        """Get formatted total as dollar string."""
        if self.total_money:
            return str(self.total_money)
        from .currency import format_cents

        return format_cents(self.total_amount)


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
        and transaction.date
        and transaction.description
        and transaction.account_name
        and isinstance(transaction.amount, int)
    )


def validate_receipt(receipt: Receipt) -> bool:
    """Validate a receipt has required fields."""
    return bool(
        receipt.id
        and receipt.date
        and receipt.vendor
        and isinstance(receipt.total_amount, int)
        and receipt.total_amount >= 0
    )


def validate_match_result(match_result: MatchResult) -> bool:
    """Validate a match result has required fields."""
    return bool(
        validate_transaction(match_result.transaction)
        and all(validate_receipt(r) for r in match_result.receipts)
        and 0.0 <= match_result.confidence <= 1.0
        and match_result.match_method
    )
