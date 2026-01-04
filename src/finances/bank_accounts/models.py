"""Domain models for bank account reconciliation."""

from dataclasses import dataclass
from typing import Any

from finances.core import FinancialDate, Money


@dataclass(frozen=True)
class ImportPattern:
    """Immutable file import pattern configuration."""

    pattern: str  # Glob pattern (e.g., "*_transactions.csv")
    format_handler: str  # Handler name (e.g., "chase_checking_csv")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "pattern": self.pattern,
            "format_handler": self.format_handler,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportPattern":
        """Deserialize from dict."""
        return cls(
            pattern=data["pattern"],
            format_handler=data["format_handler"],
        )


@dataclass(frozen=True)
class AccountConfig:
    """Immutable bank account configuration."""

    # YNAB-sourced fields (auto-filled)
    ynab_account_id: str
    ynab_account_name: str

    # User-provided fields
    slug: str  # URL-safe identifier (e.g., "chase-checking")
    bank_name: str  # Display name (e.g., "Chase")
    account_type: str  # "checking", "credit", "savings", etc.
    statement_frequency: str  # "monthly", "weekly", etc.
    source_directory: str  # Where to find statement files
    download_instructions: str  # User instructions for downloading

    # Import configuration
    import_patterns: tuple[ImportPattern, ...]  # Immutable sequence

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "ynab_account_id": self.ynab_account_id,
            "ynab_account_name": self.ynab_account_name,
            "slug": self.slug,
            "bank_name": self.bank_name,
            "account_type": self.account_type,
            "statement_frequency": self.statement_frequency,
            "source_directory": self.source_directory,
            "download_instructions": self.download_instructions,
            "import_patterns": [p.to_dict() for p in self.import_patterns],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccountConfig":
        """Deserialize from dict."""
        return cls(
            ynab_account_id=data["ynab_account_id"],
            ynab_account_name=data["ynab_account_name"],
            slug=data["slug"],
            bank_name=data["bank_name"],
            account_type=data["account_type"],
            statement_frequency=data["statement_frequency"],
            source_directory=data["source_directory"],
            download_instructions=data["download_instructions"],
            import_patterns=tuple(ImportPattern.from_dict(p) for p in data["import_patterns"]),
        )


@dataclass(frozen=True)
class BankAccountsConfig:
    """Immutable bank accounts configuration."""

    accounts: tuple[AccountConfig, ...]  # Immutable sequence

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "accounts": [a.to_dict() for a in self.accounts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BankAccountsConfig":
        """Deserialize from dict."""
        return cls(
            accounts=tuple(AccountConfig.from_dict(a) for a in data["accounts"]),
        )

    @classmethod
    def empty(cls) -> "BankAccountsConfig":
        """Create an empty configuration."""
        return cls(accounts=())


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceReconciliationPoint":
        """Deserialize from dict."""
        return cls(
            date=FinancialDate.from_string(data["date"]),
            bank_balance=Money.from_milliunits(data["bank_balance"]),
            ynab_balance=Money.from_milliunits(data["ynab_balance"]),
            bank_txs_not_in_ynab=Money.from_milliunits(data["bank_txs_not_in_ynab"]),
            ynab_txs_not_in_bank=Money.from_milliunits(data["ynab_txs_not_in_bank"]),
            adjusted_bank_balance=Money.from_milliunits(data["adjusted_bank_balance"]),
            adjusted_ynab_balance=Money.from_milliunits(data["adjusted_ynab_balance"]),
            is_reconciled=data["is_reconciled"],
            difference=Money.from_milliunits(data["difference"]),
        )


@dataclass(frozen=True)
class BalanceReconciliation:
    """Complete balance reconciliation history for an account."""

    account_id: str
    points: tuple[BalanceReconciliationPoint, ...]
    last_reconciled_date: FinancialDate | None
    first_diverged_date: FinancialDate | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "account_id": self.account_id,
            "points": [p.to_dict() for p in self.points],
            "last_reconciled_date": str(self.last_reconciled_date) if self.last_reconciled_date else None,
            "first_diverged_date": str(self.first_diverged_date) if self.first_diverged_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceReconciliation":
        """Deserialize from dict."""
        return cls(
            account_id=data["account_id"],
            points=tuple(BalanceReconciliationPoint.from_dict(p) for p in data["points"]),
            last_reconciled_date=(
                FinancialDate.from_string(data["last_reconciled_date"])
                if data["last_reconciled_date"]
                else None
            ),
            first_diverged_date=(
                FinancialDate.from_string(data["first_diverged_date"])
                if data["first_diverged_date"]
                else None
            ),
        )
