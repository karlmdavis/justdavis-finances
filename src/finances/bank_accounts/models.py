"""Domain models for bank account reconciliation."""

from __future__ import annotations

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
    def from_dict(cls, data: dict[str, Any]) -> ImportPattern:
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
    source_directory: str  # Where to find statement files
    download_instructions: str  # User instructions for downloading

    # Import configuration
    import_patterns: tuple[ImportPattern, ...]  # Immutable sequence

    # Date offset configuration
    ynab_date_offset_days: int = 0  # Days to shift bank posted_date when searching YNAB

    # Manually-verified balance checkpoints (e.g. from iPhone Wallet app).
    # These supplement OFX balance points for accounts where OFX balances are unreliable.
    # Each entry: {"date": "YYYY-MM-DD", "amount_milliunits": int}
    # Sign convention matches YNAB: negative for credit card debt, positive for assets.
    manual_balance_points: tuple[BalancePoint, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        result: dict[str, Any] = {
            "ynab_account_id": self.ynab_account_id,
            "ynab_account_name": self.ynab_account_name,
            "slug": self.slug,
            "bank_name": self.bank_name,
            "source_directory": self.source_directory,
            "download_instructions": self.download_instructions,
            "import_patterns": [p.to_dict() for p in self.import_patterns],
            "ynab_date_offset_days": self.ynab_date_offset_days,
        }
        if self.manual_balance_points:
            result["manual_balance_points"] = [p.to_dict() for p in self.manual_balance_points]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountConfig:
        """Deserialize from dict."""
        return cls(
            ynab_account_id=data["ynab_account_id"],
            ynab_account_name=data["ynab_account_name"],
            slug=data["slug"],
            bank_name=data["bank_name"],
            source_directory=data["source_directory"],
            download_instructions=data["download_instructions"],
            import_patterns=tuple(ImportPattern.from_dict(p) for p in data["import_patterns"]),
            ynab_date_offset_days=data.get("ynab_date_offset_days", 0),
            manual_balance_points=tuple(
                BalancePoint.from_dict(bp) for bp in data.get("manual_balance_points", [])
            ),
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
    def from_dict(cls, data: dict[str, Any]) -> BankAccountsConfig:
        """Deserialize from dict."""
        return cls(
            accounts=tuple(AccountConfig.from_dict(a) for a in data["accounts"]),
        )

    @classmethod
    def empty(cls) -> BankAccountsConfig:
        """Create an empty configuration."""
        return cls(accounts=())

    @classmethod
    def load(cls, config_path: str | None = None) -> BankAccountsConfig:
        """
        Load bank accounts configuration from JSON file.

        If config doesn't exist and YNAB cache is available, creates a stub
        configuration file with TODO_REQUIRED placeholders for user to fill in.

        Args:
            config_path: Optional path to config file. If None, uses default location
                        from FINANCES_CONFIG_DIR or ./config/bank_accounts_config.json

        Returns:
            Loaded configuration, or empty config if file doesn't exist

        Raises:
            json.JSONDecodeError: If the YNAB accounts cache or config file contains
                invalid JSON
            KeyError: If the YNAB accounts cache is missing required fields (id, name, type)
            OSError: If the config directory cannot be created or the stub file cannot
                be written
        """
        import os
        from pathlib import Path

        from finances.bank_accounts.config import generate_config_stub
        from finances.core.json_utils import read_json, write_json

        if config_path is None:
            # Try environment variable first, then default location
            config_dir = os.getenv("FINANCES_CONFIG_DIR", "./config")
            config_path_obj = Path(config_dir) / "bank_accounts_config.json"
        else:
            config_path_obj = Path(config_path)

        if not config_path_obj.exists():
            # Try to create stub from YNAB accounts
            # Get data directory from environment or default
            data_dir = Path(os.getenv("FINANCES_DATA_DIR", "./data"))
            ynab_accounts_file = data_dir / "ynab" / "cache" / "accounts.json"

            if ynab_accounts_file.exists():
                # Load YNAB accounts
                accounts_data = read_json(ynab_accounts_file)

                # Handle both {"accounts": [...]} and [...] formats
                if isinstance(accounts_data, dict) and "accounts" in accounts_data:
                    accounts_list = accounts_data["accounts"]
                elif isinstance(accounts_data, list):
                    accounts_list = accounts_data
                else:
                    accounts_list = []

                # Convert to dict format expected by generate_config_stub
                ynab_accounts_dict = {
                    acct["id"]: {"name": acct["name"], "type": acct["type"]}
                    for acct in accounts_list
                    if not acct.get("closed", False) and acct.get("on_budget", True)
                }

                # Generate stub config
                stub_config = generate_config_stub(ynab_accounts_dict)

                # Create config directory if needed
                config_path_obj.parent.mkdir(parents=True, exist_ok=True)

                # Save stub to file
                write_json(config_path_obj, stub_config.to_dict())

                print(f"\n[OK] Created stub configuration at {config_path_obj}")
                print("  Please edit this file and replace all TODO_REQUIRED values.")
                print("  See docs/bank-accounts-reconciliation.md for details.\n")

            # Return empty config (don't load stub - user needs to edit it first)
            return cls.empty()

        data = read_json(config_path_obj)
        return cls.from_dict(data)


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
    def from_dict(cls, data: dict[str, Any]) -> BankTransaction:
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
    def from_dict(cls, data: dict[str, Any]) -> BalancePoint:
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
        """Serialize for output. All monetary fields are in milliunits."""
        return {
            "date": str(self.date),
            "bank_balance_milliunits": self.bank_balance.to_milliunits(),
            "ynab_balance_milliunits": self.ynab_balance.to_milliunits(),
            "bank_txs_not_in_ynab_milliunits": self.bank_txs_not_in_ynab.to_milliunits(),
            "ynab_txs_not_in_bank_milliunits": self.ynab_txs_not_in_bank.to_milliunits(),
            "adjusted_bank_balance_milliunits": self.adjusted_bank_balance.to_milliunits(),
            "adjusted_ynab_balance_milliunits": self.adjusted_ynab_balance.to_milliunits(),
            "is_reconciled": self.is_reconciled,
            "difference_milliunits": self.difference.to_milliunits(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceReconciliationPoint:
        """Deserialize from dict."""
        return cls(
            date=FinancialDate.from_string(data["date"]),
            bank_balance=Money.from_milliunits(data["bank_balance_milliunits"]),
            ynab_balance=Money.from_milliunits(data["ynab_balance_milliunits"]),
            bank_txs_not_in_ynab=Money.from_milliunits(data["bank_txs_not_in_ynab_milliunits"]),
            ynab_txs_not_in_bank=Money.from_milliunits(data["ynab_txs_not_in_bank_milliunits"]),
            adjusted_bank_balance=Money.from_milliunits(data["adjusted_bank_balance_milliunits"]),
            adjusted_ynab_balance=Money.from_milliunits(data["adjusted_ynab_balance_milliunits"]),
            is_reconciled=data["is_reconciled"],
            difference=Money.from_milliunits(data["difference_milliunits"]),
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
    def from_dict(cls, data: dict[str, Any]) -> BalanceReconciliation:
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
