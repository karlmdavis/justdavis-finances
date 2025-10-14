#!/usr/bin/env python3
"""
YNAB Domain Models

Type-safe models representing YNAB API data structures.
These models are true to the YNAB API format and use Money/FinancialDate primitives.
"""

from dataclasses import dataclass
from typing import Any

from ..core.dates import FinancialDate
from ..core.money import Money


@dataclass
class YnabAccount:
    """
    YNAB account from API.

    Represents a financial account in YNAB with all API fields.
    """

    id: str
    name: str
    type: str  # "checking", "savings", "creditCard", etc.
    on_budget: bool
    closed: bool
    balance: Money  # Current account balance
    cleared_balance: Money  # Balance of cleared transactions
    uncleared_balance: Money  # Balance of uncleared transactions
    transfer_payee_id: str | None = None
    deleted: bool = False
    # Note field added for additional account information
    note: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YnabAccount":
        """
        Create YnabAccount from API dict.

        Args:
            data: Dictionary from YNAB API (accounts.json)

        Returns:
            YnabAccount instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            on_budget=data["on_budget"],
            closed=data["closed"],
            balance=Money.from_milliunits(data["balance"]),
            cleared_balance=Money.from_milliunits(data["cleared_balance"]),
            uncleared_balance=Money.from_milliunits(data["uncleared_balance"]),
            transfer_payee_id=data.get("transfer_payee_id"),
            deleted=data.get("deleted", False),
            note=data.get("note"),
        )


@dataclass
class YnabCategoryGroup:
    """
    YNAB category group from API.

    Represents a top-level category group containing categories.
    """

    id: str
    name: str
    hidden: bool
    deleted: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YnabCategoryGroup":
        """
        Create YnabCategoryGroup from API dict.

        Args:
            data: Dictionary from YNAB API (categories.json)

        Returns:
            YnabCategoryGroup instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            hidden=data["hidden"],
            deleted=data.get("deleted", False),
        )


@dataclass
class YnabCategory:
    """
    YNAB category from API.

    Represents a budget category within a category group.
    """

    id: str
    category_group_id: str
    category_group_name: str | None
    name: str
    hidden: bool
    deleted: bool = False
    # Budgeting fields (optional - may not be present in all responses)
    budgeted: Money | None = None
    activity: Money | None = None
    balance: Money | None = None
    goal_type: str | None = None
    goal_creation_month: str | None = None
    goal_target: Money | None = None
    goal_target_month: str | None = None
    goal_percentage_complete: int | None = None
    goal_months_to_budget: int | None = None
    goal_under_funded: Money | None = None
    goal_overall_funded: Money | None = None
    goal_overall_left: Money | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], category_group_name: str | None = None) -> "YnabCategory":
        """
        Create YnabCategory from API dict.

        Args:
            data: Dictionary from YNAB API (categories.json)
            category_group_name: Name of parent category group

        Returns:
            YnabCategory instance
        """
        return cls(
            id=data["id"],
            category_group_id=data["category_group_id"],
            category_group_name=category_group_name,
            name=data["name"],
            hidden=data["hidden"],
            deleted=data.get("deleted", False),
            budgeted=Money.from_milliunits(data["budgeted"]) if "budgeted" in data else None,
            activity=Money.from_milliunits(data["activity"]) if "activity" in data else None,
            balance=Money.from_milliunits(data["balance"]) if "balance" in data else None,
            goal_type=data.get("goal_type"),
            goal_creation_month=data.get("goal_creation_month"),
            goal_target=Money.from_milliunits(data["goal_target"]) if data.get("goal_target") else None,
            goal_target_month=data.get("goal_target_month"),
            goal_percentage_complete=data.get("goal_percentage_complete"),
            goal_months_to_budget=data.get("goal_months_to_budget"),
            goal_under_funded=(
                Money.from_milliunits(data["goal_under_funded"]) if data.get("goal_under_funded") else None
            ),
            goal_overall_funded=(
                Money.from_milliunits(data["goal_overall_funded"])
                if data.get("goal_overall_funded")
                else None
            ),
            goal_overall_left=(
                Money.from_milliunits(data["goal_overall_left"]) if data.get("goal_overall_left") else None
            ),
        )

    @property
    def full_name(self) -> str:
        """Get full category name including group."""
        if self.category_group_name:
            return f"{self.category_group_name}: {self.name}"
        return self.name


@dataclass
class YnabSubtransaction:
    """
    YNAB subtransaction (split) from API.

    Represents a split transaction within a parent transaction.
    """

    id: str
    transaction_id: str
    amount: Money
    memo: str | None
    payee_id: str | None
    payee_name: str | None
    category_id: str | None
    category_name: str | None
    transfer_account_id: str | None
    transfer_transaction_id: str | None
    deleted: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YnabSubtransaction":
        """
        Create YnabSubtransaction from API dict.

        Args:
            data: Dictionary from YNAB API (subtransaction object)

        Returns:
            YnabSubtransaction instance
        """
        return cls(
            id=data["id"],
            transaction_id=data["transaction_id"],
            amount=Money.from_milliunits(data["amount"]),
            memo=data.get("memo"),
            payee_id=data.get("payee_id"),
            payee_name=data.get("payee_name"),
            category_id=data.get("category_id"),
            category_name=data.get("category_name"),
            transfer_account_id=data.get("transfer_account_id"),
            transfer_transaction_id=data.get("transfer_transaction_id"),
            deleted=data.get("deleted", False),
        )


@dataclass
class YnabTransaction:
    """
    YNAB transaction from API.

    Represents a financial transaction in YNAB with all API fields.
    """

    id: str
    date: FinancialDate
    amount: Money
    memo: str | None
    cleared: str  # "cleared", "uncleared", "reconciled"
    approved: bool
    account_id: str
    account_name: str | None
    payee_id: str | None
    payee_name: str | None
    category_id: str | None
    category_name: str | None
    transfer_account_id: str | None
    transfer_transaction_id: str | None
    matched_transaction_id: str | None
    import_id: str | None
    import_payee_name: str | None
    import_payee_name_original: str | None
    debt_transaction_type: str | None
    deleted: bool = False
    # Subtransactions (splits)
    subtransactions: list[YnabSubtransaction] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YnabTransaction":
        """
        Create YnabTransaction from API dict.

        Args:
            data: Dictionary from YNAB API (transactions.json)

        Returns:
            YnabTransaction instance
        """
        subtransactions = None
        if data.get("subtransactions"):
            subtransactions = [YnabSubtransaction.from_dict(sub) for sub in data["subtransactions"]]

        return cls(
            id=data["id"],
            date=FinancialDate.from_string(data["date"]),
            amount=Money.from_milliunits(data["amount"]),
            memo=data.get("memo"),
            cleared=data.get("cleared", "uncleared"),  # Default to uncleared if not present
            approved=data.get("approved", True),  # Default to approved if not present
            account_id=data.get("account_id", "unknown"),  # Default to unknown if not present
            account_name=data.get("account_name"),
            payee_id=data.get("payee_id"),
            payee_name=data.get("payee_name"),
            category_id=data.get("category_id"),
            category_name=data.get("category_name"),
            transfer_account_id=data.get("transfer_account_id"),
            transfer_transaction_id=data.get("transfer_transaction_id"),
            matched_transaction_id=data.get("matched_transaction_id"),
            import_id=data.get("import_id"),
            import_payee_name=data.get("import_payee_name"),
            import_payee_name_original=data.get("import_payee_name_original"),
            debt_transaction_type=data.get("debt_transaction_type"),
            deleted=data.get("deleted", False),
            subtransactions=subtransactions,
        )

    @property
    def is_split(self) -> bool:
        """Check if this transaction has subtransactions."""
        return self.subtransactions is not None and len(self.subtransactions) > 0

    @property
    def is_transfer(self) -> bool:
        """Check if this is a transfer transaction."""
        return self.transfer_account_id is not None
