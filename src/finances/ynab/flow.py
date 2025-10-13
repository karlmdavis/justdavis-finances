#!/usr/bin/env python3
"""
YNAB Flow Nodes

Flow node implementations for YNAB integration.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary


class YnabSyncFlowNode(FlowNode):
    """Sync YNAB data to local cache."""

    def __init__(self, data_dir: Path):
        super().__init__("ynab_sync")
        self.data_dir = data_dir

        # Initialize DataStore
        from .datastore import YnabCacheStore

        self.store = YnabCacheStore(data_dir / "ynab" / "cache")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if YNAB cache needs updating."""
        if not self.store.exists():
            return True, ["YNAB cache does not exist"]

        # Check age of cache
        last_mod = self.store.last_modified()
        if last_mod:
            age_hours = (datetime.now() - last_mod).total_seconds() / 3600

            if age_hours > 24:
                return True, [f"YNAB cache is {age_hours:.1f} hours old"]

        return False, ["YNAB cache is up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get YNAB cache data summary."""
        return self.store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute YNAB sync using external ynab CLI tool."""
        try:
            # Call the external ynab CLI tool
            cmd = ["ynab", "sync", "--days", "30"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603

            return FlowResult(
                success=True,
                items_processed=1,
                metadata={"ynab_sync": "completed", "output": result.stdout},
            )
        except subprocess.CalledProcessError as e:
            return FlowResult(
                success=False,
                error_message=f"YNAB sync failed: {e.stderr}",
            )
        except FileNotFoundError:
            return FlowResult(
                success=False,
                error_message="ynab CLI tool not found. Please install it first.",
            )


class RetirementUpdateFlowNode(FlowNode):
    """Update retirement account balances (manual step)."""

    def __init__(self, data_dir: Path):
        super().__init__("retirement_update")
        self.data_dir = data_dir
        self._dependencies = {"ynab_sync"}

        # Initialize DataStore
        from .datastore import YnabEditsStore

        self.store = YnabEditsStore(data_dir / "ynab" / "edits")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if retirement accounts need updating."""
        # Check for retirement edit files specifically
        retirement_edits = self.store.get_retirement_edits()
        if not retirement_edits:
            return True, ["No retirement edits found"]

        # Check age of most recent retirement edit
        latest = max(retirement_edits, key=lambda p: p.stat().st_mtime)
        age_days = (datetime.now().timestamp() - latest.stat().st_mtime) / 86400

        if age_days > 30:
            return True, [f"Latest retirement update is {age_days:.0f} days old"]

        return False, ["Retirement accounts recently updated"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get retirement accounts summary."""
        from . import discover_retirement_accounts

        try:
            accounts = discover_retirement_accounts(self.data_dir)

            if not accounts:
                return NodeDataSummary(
                    exists=False,
                    last_updated=None,
                    age_days=None,
                    item_count=None,
                    size_bytes=None,
                    summary_text="No retirement accounts found",
                )

            # Check for last retirement edit file using DataStore
            retirement_edits = self.store.get_retirement_edits()

            last_updated = None
            age = None
            if retirement_edits:
                latest = max(retirement_edits, key=lambda p: p.stat().st_mtime)
                last_updated = datetime.fromtimestamp(latest.stat().st_mtime)
                age = (datetime.now() - last_updated).days

            total_balance = sum(acc.balance_cents for acc in accounts)
            from ..core.currency import format_cents

            return NodeDataSummary(
                exists=True,
                last_updated=last_updated,
                age_days=age,
                item_count=len(accounts),
                size_bytes=None,
                summary_text=f"Retirement accounts: {len(accounts)} accounts, {format_cents(total_balance)} total",
            )
        except Exception:
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="Error loading retirement accounts",
            )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute retirement account update (manual step with account discovery)."""
        from . import discover_retirement_accounts

        try:
            accounts = discover_retirement_accounts(self.data_dir)

            if not accounts:
                return FlowResult(
                    success=False,
                    error_message="No retirement accounts found in YNAB cache",
                )

            # Format account info for review instructions
            account_list = "\n".join(f"  - {acc.name}: {acc.balance_cents} cents" for acc in accounts)

            return FlowResult(
                success=True,
                items_processed=len(accounts),
                requires_review=True,
                review_instructions=f"Manually update retirement account balances:\n\n"
                f"Discovered accounts:\n{account_list}\n\n"
                f"Run `finances flow` to generate balance adjustments through the retirement update node",
            )
        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Retirement update failed: {e}",
            )
