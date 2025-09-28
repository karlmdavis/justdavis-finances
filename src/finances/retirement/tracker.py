#!/usr/bin/env python3
"""
Retirement Account Balance Tracker

Manages retirement account balance updates and generates YNAB adjustment transactions.
"""

import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

from ..core.currency import milliunits_to_cents, format_cents

logger = logging.getLogger(__name__)


@dataclass
class RetirementAccount:
    """Represents a tracked retirement account."""
    name: str
    account_type: str  # 401k, 403b, IRA, Roth IRA, etc.
    provider: str
    ynab_account_id: Optional[str] = None
    ynab_account_name: Optional[str] = None
    is_active: bool = True


@dataclass
class BalanceEntry:
    """Represents a balance update entry."""
    date: str  # YYYY-MM-DD format
    balance_cents: int  # Balance in cents
    previous_balance_cents: Optional[int] = None
    adjustment_cents: Optional[int] = None
    notes: Optional[str] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

        if self.previous_balance_cents is not None and self.adjustment_cents is None:
            self.adjustment_cents = self.balance_cents - self.previous_balance_cents


@dataclass
class RetirementUpdate:
    """Represents a complete retirement account update session."""
    date: str
    accounts_updated: List[str]
    total_adjustment_cents: int
    ynab_transactions_created: List[Dict[str, Any]]
    timestamp: str


class RetirementTracker:
    """
    Manages retirement account balance tracking and YNAB integration.

    Provides interactive balance updates, historical tracking, and generates
    YNAB adjustment transactions to keep retirement account balances in sync.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize retirement tracker.

        Args:
            data_dir: Base data directory for storing retirement data
        """
        self.data_dir = data_dir
        self.retirement_dir = data_dir / "retirement"
        self.retirement_dir.mkdir(parents=True, exist_ok=True)

        self.accounts_file = self.retirement_dir / "accounts.yaml"
        self.history_file = self.retirement_dir / "balance_history.yaml"

        # Load configuration
        self.accounts = self._load_accounts()
        self.balance_history = self._load_balance_history()

    def _load_accounts(self) -> Dict[str, RetirementAccount]:
        """Load retirement account configuration."""
        if not self.accounts_file.exists():
            # Create default accounts file
            default_accounts = {
                "karl_401k": RetirementAccount(
                    name="karl_401k",
                    account_type="401k",
                    provider="Fidelity",
                    ynab_account_name="Karl 401k"
                ),
                "erica_403b": RetirementAccount(
                    name="erica_403b",
                    account_type="403b",
                    provider="TIAA",
                    ynab_account_name="Erica 403b"
                ),
                "karl_ira": RetirementAccount(
                    name="karl_ira",
                    account_type="IRA",
                    provider="Vanguard",
                    ynab_account_name="Karl IRA"
                )
            }

            self._save_accounts(default_accounts)
            return default_accounts

        try:
            with open(self.accounts_file, 'r') as f:
                data = yaml.safe_load(f) or {}

            accounts = {}
            for account_name, account_data in data.items():
                accounts[account_name] = RetirementAccount(**account_data)

            return accounts

        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")
            return {}

    def _save_accounts(self, accounts: Dict[str, RetirementAccount]) -> None:
        """Save retirement account configuration."""
        data = {}
        for account_name, account in accounts.items():
            data[account_name] = asdict(account)

        with open(self.accounts_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=True)

    def _load_balance_history(self) -> Dict[str, List[BalanceEntry]]:
        """Load balance history for all accounts."""
        if not self.history_file.exists():
            return {}

        try:
            with open(self.history_file, 'r') as f:
                data = yaml.safe_load(f) or {}

            history = {}
            for account_name, entries in data.items():
                history[account_name] = []
                for entry_data in entries:
                    history[account_name].append(BalanceEntry(**entry_data))

            return history

        except Exception as e:
            logger.error(f"Failed to load balance history: {e}")
            return {}

    def _save_balance_history(self) -> None:
        """Save balance history to file."""
        data = {}
        for account_name, entries in self.balance_history.items():
            data[account_name] = [asdict(entry) for entry in entries]

        with open(self.history_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=True)

    def get_active_accounts(self) -> List[RetirementAccount]:
        """Get list of active retirement accounts."""
        return [account for account in self.accounts.values() if account.is_active]

    def get_last_balance(self, account_name: str) -> Optional[BalanceEntry]:
        """Get the most recent balance entry for an account."""
        if account_name not in self.balance_history:
            return None

        entries = self.balance_history[account_name]
        if not entries:
            return None

        # Sort by date and return most recent
        sorted_entries = sorted(entries, key=lambda x: x.date)
        return sorted_entries[-1]

    def add_balance_entry(self, account_name: str, balance_cents: int,
                         entry_date: Optional[date] = None, notes: Optional[str] = None) -> BalanceEntry:
        """
        Add a new balance entry for an account.

        Args:
            account_name: Name of the retirement account
            balance_cents: New balance in cents
            entry_date: Date of the balance (default: today)
            notes: Optional notes about the update

        Returns:
            The created balance entry
        """
        if account_name not in self.accounts:
            raise ValueError(f"Unknown retirement account: {account_name}")

        if entry_date is None:
            entry_date = date.today()

        date_str = entry_date.strftime("%Y-%m-%d")

        # Get previous balance
        previous_entry = self.get_last_balance(account_name)
        previous_balance_cents = previous_entry.balance_cents if previous_entry else None

        # Create new entry
        entry = BalanceEntry(
            date=date_str,
            balance_cents=balance_cents,
            previous_balance_cents=previous_balance_cents,
            notes=notes
        )

        # Add to history
        if account_name not in self.balance_history:
            self.balance_history[account_name] = []

        self.balance_history[account_name].append(entry)

        # Save to file
        self._save_balance_history()

        logger.info(f"Added balance entry for {account_name}: {format_cents(balance_cents)}")

        return entry

    def generate_ynab_adjustment_transaction(self, account_name: str,
                                           balance_entry: BalanceEntry) -> Optional[Dict[str, Any]]:
        """
        Generate YNAB adjustment transaction for a balance update.

        Args:
            account_name: Name of the retirement account
            balance_entry: The balance entry to create adjustment for

        Returns:
            YNAB transaction data or None if no adjustment needed
        """
        if balance_entry.adjustment_cents is None or balance_entry.adjustment_cents == 0:
            return None

        account = self.accounts[account_name]
        if not account.ynab_account_name:
            logger.warning(f"No YNAB account mapped for {account_name}")
            return None

        # Create transaction data structure
        # Note: This would integrate with the YNAB API in the actual implementation
        transaction = {
            "account_name": account.ynab_account_name,
            "payee_name": f"{account.provider} Adjustment",
            "category_name": "Investment Gains/Losses",
            "memo": f"Balance update: {format_cents(balance_entry.balance_cents)} (from {format_cents(balance_entry.previous_balance_cents or 0)})",
            "amount_milliunits": balance_entry.adjustment_cents * 10,  # Convert cents to milliunits
            "date": balance_entry.date,
            "cleared": "cleared"
        }

        return transaction

    def update_session(self, updates: Dict[str, Dict[str, Any]]) -> RetirementUpdate:
        """
        Process a batch of retirement account updates.

        Args:
            updates: Dictionary mapping account names to update data
                    Format: {account_name: {"balance_cents": int, "date": date, "notes": str}}

        Returns:
            RetirementUpdate summary object
        """
        session_date = date.today().strftime("%Y-%m-%d")
        accounts_updated = []
        total_adjustment_cents = 0
        ynab_transactions = []

        for account_name, update_data in updates.items():
            try:
                # Add balance entry
                entry = self.add_balance_entry(
                    account_name=account_name,
                    balance_cents=update_data["balance_cents"],
                    entry_date=update_data.get("date"),
                    notes=update_data.get("notes")
                )

                accounts_updated.append(account_name)

                if entry.adjustment_cents:
                    total_adjustment_cents += entry.adjustment_cents

                # Generate YNAB transaction
                ynab_transaction = self.generate_ynab_adjustment_transaction(account_name, entry)
                if ynab_transaction:
                    ynab_transactions.append(ynab_transaction)

            except Exception as e:
                logger.error(f"Failed to update {account_name}: {e}")
                continue

        return RetirementUpdate(
            date=session_date,
            accounts_updated=accounts_updated,
            total_adjustment_cents=total_adjustment_cents,
            ynab_transactions_created=ynab_transactions,
            timestamp=datetime.now().isoformat()
        )


def update_retirement_balances(data_dir: Path, updates: Dict[str, Dict[str, Any]]) -> RetirementUpdate:
    """
    Convenience function for updating retirement balances.

    Args:
        data_dir: Base data directory
        updates: Dictionary mapping account names to update data

    Returns:
        RetirementUpdate summary object
    """
    tracker = RetirementTracker(data_dir)
    return tracker.update_session(updates)