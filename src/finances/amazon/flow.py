#!/usr/bin/env python3
"""
Amazon Flow Nodes

Flow node implementations for Amazon transaction matching.
"""

from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary
from . import SimplifiedMatcher, load_orders, orders_to_dataframe
from .unzipper import extract_amazon_zip_files


class AmazonOrderHistoryRequestFlowNode(FlowNode):
    """Manual step prompting user to download Amazon order history."""

    def __init__(self) -> None:
        super().__init__("amazon_order_history_request")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Manual step - always returns False (user initiates)."""
        return False, ["Manual step - user prompt required"]

    def execute(self, context: FlowContext) -> FlowResult:
        """Prompt user to download Amazon order history."""
        click.echo("\n📋 Manual Step Required:")
        click.echo("1. Visit https://www.amazon.com/gp/privacycentral/dsar/preview.html")
        click.echo("2. Request 'Order Reports' for the desired date range")
        click.echo("3. Download the ZIP files when ready")
        click.echo("4. Place them in your download directory")

        if not click.confirm("Have you completed this step?"):
            return FlowResult(success=False, error_message="User cancelled manual step")

        return FlowResult(
            success=True,
            items_processed=0,
            metadata={"manual_step": True, "description": "Amazon order history request"},
        )


class AmazonUnzipFlowNode(FlowNode):
    """Extract Amazon order history ZIP files."""

    def __init__(self, data_dir: Path):
        super().__init__("amazon_unzip")
        self.data_dir = data_dir
        self._dependencies = {"amazon_order_history_request"}

        # Initialize DataStore
        from .datastore import AmazonRawDataStore

        self.store = AmazonRawDataStore(data_dir / "amazon" / "raw")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new ZIP files are available in amazon/raw."""
        raw_dir = self.data_dir / "amazon" / "raw"

        if not raw_dir.exists():
            return False, ["Amazon raw directory not found"]

        # Look for Amazon ZIP files in raw directory
        zip_files = list(raw_dir.glob("*.zip"))
        if not zip_files:
            return False, ["No Amazon ZIP files to extract"]

        # Check if we have any extracted data
        if not self.store.exists():
            return True, [f"Found {len(zip_files)} ZIP file(s) to extract"]

        # Check if ZIPs are newer than extracted data
        latest_zip = max(zip_files, key=lambda p: p.stat().st_mtime)
        latest_csv_mtime = self.store.last_modified()

        if latest_csv_mtime and latest_zip.stat().st_mtime > latest_csv_mtime.timestamp():
            return True, ["New ZIP files detected"]

        return False, ["No new Amazon data to extract"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Amazon raw data summary."""
        return self.store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Extract Amazon ZIP files from amazon/raw directory."""
        raw_dir = self.data_dir / "amazon" / "raw"

        if not raw_dir.exists():
            return FlowResult(success=False, error_message="Amazon raw directory not found")

        try:
            # Extract ZIP files in place (source and destination are the same)
            result = extract_amazon_zip_files(raw_dir, raw_dir)

            if result["success"]:
                return FlowResult(
                    success=True,
                    items_processed=result["files_processed"],
                    new_items=result["files_processed"],
                    metadata=result,
                )
            else:
                return FlowResult(
                    success=False,
                    error_message=result["message"],
                    metadata=result,
                )
        except Exception as e:
            return FlowResult(success=False, error_message=f"Unzip failed: {e}")


class AmazonMatchingFlowNode(FlowNode):
    """Match YNAB transactions to Amazon orders."""

    def __init__(self, data_dir: Path):
        super().__init__("amazon_matching")
        self.data_dir = data_dir
        self._dependencies = {"ynab_sync", "amazon_unzip"}

        # Initialize DataStores
        from .datastore import AmazonMatchResultsStore, AmazonRawDataStore

        self.raw_store = AmazonRawDataStore(data_dir / "amazon" / "raw")
        self.match_store = AmazonMatchResultsStore(data_dir / "amazon" / "transaction_matches")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new Amazon data or YNAB data requires matching."""
        reasons = []

        # Check if Amazon raw data exists
        if not self.raw_store.exists():
            return False, ["No Amazon raw data available"]

        # Check if YNAB cache exists
        ynab_cache = self.data_dir / "ynab" / "cache" / "transactions.json"
        if not ynab_cache.exists():
            return False, ["No YNAB cache available"]

        # Check if matching results exist
        if not self.match_store.exists():
            reasons.append("No previous matching results")
            return True, reasons

        # Compare timestamps
        latest_match_time = self.match_store.last_modified()
        ynab_mtime = ynab_cache.stat().st_mtime

        if latest_match_time and ynab_mtime > latest_match_time.timestamp():
            reasons.append("YNAB data updated since last match")
            return True, reasons

        return False, ["Matching results are up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Amazon matching results summary."""
        return self.match_store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute Amazon transaction matching."""
        from ..ynab import filter_transactions_by_payee, load_transactions

        try:
            # Initialize matcher
            matcher = SimplifiedMatcher()

            # Load data using new domain model functions
            amazon_data_dir = self.data_dir / "amazon" / "raw"
            ynab_cache_dir = self.data_dir / "ynab" / "cache"

            # Load domain models
            orders_by_account = load_orders(amazon_data_dir)
            all_transactions = load_transactions(ynab_cache_dir)

            # Filter for Amazon transactions using domain model function
            amazon_transactions = filter_transactions_by_payee(all_transactions, payee="Amazon")

            # Convert domain models to DataFrames for matcher (temporary adapter)
            account_data = {
                account: (orders_to_dataframe(orders), pd.DataFrame())  # (retail_df, digital_df)
                for account, orders in orders_by_account.items()
            }

            # Convert YnabTransaction models to dicts for matcher (temporary adapter)
            transactions = [
                {
                    "id": tx.id,
                    "amount": tx.amount.to_milliunits(),
                    "date": tx.date.to_iso_string(),
                    "payee_name": tx.payee_name,
                    "memo": tx.memo,
                    "account_name": tx.account_name,
                    "cleared": tx.cleared,
                    "approved": tx.approved,
                    "account_id": tx.account_id,
                    "category_name": tx.category_name,
                }
                for tx in amazon_transactions
            ]

            if not transactions:
                return FlowResult(
                    success=True,
                    items_processed=0,
                    metadata={"message": "No Amazon transactions to match"},
                )

            # Match transactions
            matches = []
            matched_count = 0
            total_confidence = 0.0

            for tx in transactions:
                match_result = matcher.match_transaction(tx, account_data)
                if match_result.get("best_match"):
                    matched_count += 1
                    total_confidence += match_result["best_match"].get("confidence", 0.0)
                matches.append(match_result)

            # Calculate statistics
            match_rate = matched_count / len(transactions) if transactions else 0.0
            avg_confidence = total_confidence / matched_count if matched_count > 0 else 0.0

            # Write results using DataStore
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            result_data = {
                "metadata": {
                    "timestamp": timestamp,
                    "accounts": "all",
                },
                "summary": {
                    "total_transactions": len(transactions),
                    "matched_transactions": matched_count,
                    "match_rate": match_rate,
                    "average_confidence": avg_confidence,
                },
                "matches": matches,
            }

            self.match_store.save(result_data)

            # Get output file path for FlowResult
            output_dir = self.data_dir / "amazon" / "transaction_matches"
            output_file = output_dir / f"{timestamp}_amazon_matching_results.json"

            return FlowResult(
                success=True,
                items_processed=len(transactions),
                new_items=matched_count,
                outputs=[output_file],
                metadata={
                    "matched_count": matched_count,
                    "match_rate": match_rate,
                    "avg_confidence": avg_confidence,
                },
            )

        except Exception as e:
            return FlowResult(success=False, error_message=f"Matching failed: {e}")
