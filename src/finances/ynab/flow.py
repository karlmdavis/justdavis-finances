#!/usr/bin/env python3
"""
YNAB Flow Nodes

Flow node implementations for YNAB integration.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo


class YnabSyncOutputInfo(OutputInfo):
    """Output information for YNAB sync node."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def is_data_ready(self) -> bool:
        """Ready if all three cache files exist (transactions, accounts, categories)."""
        if not self.cache_dir.exists():
            return False

        transactions_file = self.cache_dir / "transactions.json"
        accounts_file = self.cache_dir / "accounts.json"
        categories_file = self.cache_dir / "categories.json"

        return all([
            transactions_file.exists(),
            accounts_file.exists(),
            categories_file.exists(),
        ])

    def get_output_files(self) -> list[OutputFile]:
        """Return all cache files with record counts."""
        if not self.cache_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []

        # transactions.json - direct array
        transactions_file = self.cache_dir / "transactions.json"
        if transactions_file.exists():
            data = read_json(transactions_file)
            count = len(data) if isinstance(data, list) else 0
            files.append(OutputFile(path=transactions_file, record_count=count))

        # accounts.json - nested in "accounts" key
        accounts_file = self.cache_dir / "accounts.json"
        if accounts_file.exists():
            data = read_json(accounts_file)
            count = len(data.get("accounts", [])) if isinstance(data, dict) else 0
            files.append(OutputFile(path=accounts_file, record_count=count))

        # categories.json - nested in "category_groups" key
        categories_file = self.cache_dir / "categories.json"
        if categories_file.exists():
            data = read_json(categories_file)
            count = len(data.get("category_groups", [])) if isinstance(data, dict) else 0
            files.append(OutputFile(path=categories_file, record_count=count))

        return files


class YnabSyncFlowNode(FlowNode):
    """Sync YNAB data to local cache."""

    def __init__(self, data_dir: Path):
        super().__init__("ynab_sync")
        self.data_dir = data_dir

        # Initialize DataStore
        from .datastore import YnabCacheStore

        self.store = YnabCacheStore(data_dir / "ynab" / "cache")

    def get_output_info(self) -> OutputInfo:
        """Get output information for YNAB sync node."""
        return YnabSyncOutputInfo(self.data_dir / "ynab" / "cache")

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


class RetirementUpdateOutputInfo(OutputInfo):
    """Output information for retirement update node."""

    def __init__(self, edits_dir: Path):
        self.edits_dir = edits_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 retirement edit file exists."""
        if not self.edits_dir.exists():
            return False
        return len(list(self.edits_dir.glob("*retirement*.json"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return all retirement edit files with counts."""
        if not self.edits_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for edit_file in self.edits_dir.glob("*retirement*.json"):
            data = read_json(edit_file)
            # Handle both array and dict with "edits" key
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict) and "edits" in data:
                count = len(data["edits"])
            else:
                count = 0
            files.append(OutputFile(path=edit_file, record_count=count))

        return files


class RetirementUpdateFlowNode(FlowNode):
    """Update retirement account balances (manual step)."""

    def __init__(self, data_dir: Path):
        super().__init__("retirement_update")
        self.data_dir = data_dir
        self._dependencies = {"ynab_sync"}

        # Initialize DataStore
        from .datastore import YnabEditsStore

        self.store = YnabEditsStore(data_dir / "ynab" / "edits")

    def get_output_info(self) -> OutputInfo:
        """Get output information for retirement update node."""
        return RetirementUpdateOutputInfo(self.data_dir / "ynab" / "edits")

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
