#!/usr/bin/env python3
"""
YNAB-Based Retirement Account Management

Provides retirement account discovery and balance adjustment generation
using YNAB as the single source of truth for account data.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..core.currency import format_cents
from ..core.json_utils import read_json, write_json

logger = logging.getLogger(__name__)


@dataclass
class RetirementAccount:
    """Represents a discovered retirement account from YNAB."""

    id: str
    name: str
    balance_milliunits: int
    cleared_balance_milliunits: int
    last_reconciled_at: str | None

    @property
    def balance_cents(self) -> int:
        """Get current balance in cents."""
        return abs(self.balance_milliunits) // 10

    @property
    def cleared_balance_cents(self) -> int:
        """Get cleared balance in cents."""
        return abs(self.cleared_balance_milliunits) // 10

    @property
    def provider(self) -> str:
        """Extract provider from account name if available."""
        # Parse provider from patterns like "Karl's Fidelity: ..." or "Erica's Vanguard: ..."
        if ":" in self.name:
            parts = self.name.split(":")
            # Extract provider from first part (e.g., "Karl's Fidelity" -> "Fidelity")
            provider_part = parts[0].strip()
            # Remove possessive prefix if present
            if "'s " in provider_part:
                return provider_part.split("'s ", 1)[1]
            return provider_part
        return "Unknown"

    @property
    def account_type(self) -> str:
        """Guess account type from name."""
        name_lower = self.name.lower()
        if "401k" in name_lower or "401(k)" in name_lower:
            return "401(k)"
        elif "403b" in name_lower or "403(b)" in name_lower:
            return "403(b)"
        elif "roth" in name_lower:
            return "Roth IRA"
        elif "ira" in name_lower:
            return "IRA"
        elif "tsp" in name_lower or "thrift" in name_lower:
            return "TSP"
        else:
            return "Investment"


class YnabRetirementService:
    """
    Service for managing retirement accounts using YNAB data.

    Auto-discovers retirement accounts from YNAB cache and generates
    balance adjustment transactions following the standard edit workflow.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize retirement service.

        Args:
            data_dir: Base data directory containing YNAB cache
        """
        self.data_dir = data_dir
        self.ynab_cache_dir = data_dir / "ynab" / "cache"
        self.edits_dir = data_dir / "ynab" / "edits"
        self.edits_dir.mkdir(parents=True, exist_ok=True)

    def discover_retirement_accounts(self) -> list[RetirementAccount]:
        """
        Discover retirement accounts from YNAB cache.

        Filters for accounts that are:
        - type: "otherAsset"
        - on_budget: false
        - not closed

        Returns:
            List of discovered retirement accounts
        """
        accounts_file = self.ynab_cache_dir / "accounts.json"

        if not accounts_file.exists():
            logger.error(f"YNAB accounts cache not found: {accounts_file}")
            return []

        try:
            data = read_json(accounts_file)
            accounts = data.get("accounts", [])

            # Filter for retirement accounts (off-budget assets)
            retirement_accounts = [
                RetirementAccount(
                    id=account["id"],
                    name=account["name"],
                    balance_milliunits=account.get("balance", 0),
                    cleared_balance_milliunits=account.get("cleared_balance", 0),
                    last_reconciled_at=account.get("last_reconciled_at"),
                )
                for account in accounts
                if (
                    account.get("type") == "otherAsset"
                    and not account.get("on_budget", True)
                    and not account.get("closed", False)
                )
            ]

            # Sort by name for consistent ordering
            retirement_accounts.sort(key=lambda a: a.name)

            logger.info(f"Discovered {len(retirement_accounts)} retirement accounts")
            return retirement_accounts

        except Exception as e:
            logger.error(f"Failed to load retirement accounts: {e}")
            return []

    def generate_balance_adjustment(
        self, account: RetirementAccount, new_balance_cents: int, adjustment_date: date | None = None
    ) -> dict[str, Any]:
        """
        Generate a YNAB balance adjustment transaction.

        Args:
            account: The retirement account to adjust
            new_balance_cents: New balance in cents
            adjustment_date: Date for the adjustment (default: today)

        Returns:
            YNAB edit mutation for the balance adjustment
        """
        if adjustment_date is None:
            adjustment_date = date.today()

        # Calculate adjustment amount
        current_balance_cents = account.balance_cents
        adjustment_cents = new_balance_cents - current_balance_cents

        if adjustment_cents == 0:
            logger.info(f"No adjustment needed for {account.name}")
            return {}  # Return empty dict instead of None for consistency

        # Create reconciliation transaction
        mutation = {
            "account_id": account.id,
            "account_name": account.name,
            "action": "create_reconciliation",
            "date": adjustment_date.strftime("%Y-%m-%d"),
            "payee": f"{account.provider} Balance Adjustment",
            "category": "Investment Gains/Losses",  # This may need to be mapped to actual category ID
            "amount_milliunits": adjustment_cents * 10,  # Convert cents to milliunits
            "memo": f"Balance update: {format_cents(current_balance_cents)} → {format_cents(new_balance_cents)}",
            "cleared": "cleared",
            "approved": True,
            "flag_color": None,
            "source": "retirement",
            "confidence": 1.0,  # Balance adjustments are always high confidence
            "metadata": {
                "provider": account.provider,
                "account_type": account.account_type,
                "previous_balance_cents": current_balance_cents,
                "new_balance_cents": new_balance_cents,
                "adjustment_cents": adjustment_cents,
            },
        }

        logger.info(f"Generated adjustment for {account.name}: {format_cents(adjustment_cents)}")
        return mutation

    def create_retirement_edits(self, adjustments: list[dict[str, Any]]) -> Path:
        """
        Create a YNAB edits file for retirement balance adjustments.

        Args:
            adjustments: List of balance adjustment mutations

        Returns:
            Path to the created edits file
        """
        if not adjustments:
            logger.info("No retirement adjustments to save")
            return Path()  # Return empty Path instead of None

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.edits_dir / f"{timestamp}_retirement_edits.yaml"

        # Create edit file structure
        edit_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "source": "retirement_balance_update",
                "total_mutations": len(adjustments),
                "total_adjustment": sum(m["metadata"]["adjustment_cents"] for m in adjustments),
                "confidence_threshold": 1.0,
                "auto_approved": len(adjustments),  # All retirement adjustments are auto-approved
            },
            "mutations": adjustments,
        }

        # Write to file
        write_json(output_file, edit_data)

        logger.info(f"Created retirement edits file: {output_file}")
        logger.info(f"  Total adjustments: {len(adjustments)}")
        metadata_dict: dict[str, Any] = edit_data["metadata"]  # type: ignore[assignment]
        total_adj: int = metadata_dict["total_adjustment"]
        logger.info(f"  Net adjustment: {format_cents(total_adj)}")

        return output_file


def discover_retirement_accounts(data_dir: Path) -> list[RetirementAccount]:
    """
    Convenience function to discover retirement accounts.

    Args:
        data_dir: Base data directory

    Returns:
        List of discovered retirement accounts
    """
    service = YnabRetirementService(data_dir)
    return service.discover_retirement_accounts()


def generate_retirement_edits(data_dir: Path, balance_updates: dict[str, int]) -> Path | None:
    """
    Generate YNAB edits for retirement balance updates.

    Args:
        data_dir: Base data directory
        balance_updates: Dict mapping account IDs to new balances in cents

    Returns:
        Path to generated edits file, or None if no adjustments needed
    """
    service = YnabRetirementService(data_dir)

    # Discover accounts
    accounts = service.discover_retirement_accounts()
    accounts_by_id = {acc.id: acc for acc in accounts}

    # Generate adjustments
    adjustments = []
    for account_id, new_balance_cents in balance_updates.items():
        if account_id in accounts_by_id:
            account = accounts_by_id[account_id]
            mutation = service.generate_balance_adjustment(account, new_balance_cents)
            if mutation:
                adjustments.append(mutation)

    # Create edits file
    if adjustments:
        return service.create_retirement_edits(adjustments)

    return None
