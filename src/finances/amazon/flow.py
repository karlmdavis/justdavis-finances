#!/usr/bin/env python3
"""
Amazon Flow Nodes

Flow node implementations for Amazon transaction matching.
"""

from datetime import datetime
from pathlib import Path

import click

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary
from ..core.json_utils import read_json, write_json_with_defaults
from . import SimplifiedMatcher, load_amazon_data
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
        if not list(raw_dir.glob("**/Retail.OrderHistory.*.csv")):
            return True, [f"Found {len(zip_files)} ZIP file(s) to extract"]

        # Check if ZIPs are newer than extracted data
        latest_zip = max(zip_files, key=lambda p: p.stat().st_mtime)
        csv_files = list(raw_dir.glob("**/Retail.OrderHistory.*.csv"))
        latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)

        if latest_zip.stat().st_mtime > latest_csv.stat().st_mtime:
            return True, ["New ZIP files detected"]

        return False, ["No new Amazon data to extract"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Amazon raw data summary."""
        raw_dir = self.data_dir / "amazon" / "raw"

        if not raw_dir.exists() or not list(raw_dir.glob("**/Retail.OrderHistory.*.csv")):
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="No Amazon raw data found",
            )

        csv_files = list(raw_dir.glob("**/Retail.OrderHistory.*.csv"))
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
        age = (datetime.now() - mtime).days

        return NodeDataSummary(
            exists=True,
            last_updated=mtime,
            age_days=age,
            item_count=len(csv_files),
            size_bytes=sum(f.stat().st_size for f in csv_files),
            summary_text=f"Amazon data: {len(csv_files)} account(s)",
        )

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

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new Amazon data or YNAB data requires matching."""
        reasons = []

        # Check if Amazon raw data exists
        raw_dir = self.data_dir / "amazon" / "raw"
        if not raw_dir.exists() or not list(raw_dir.glob("**/Retail.OrderHistory.*.csv")):
            return False, ["No Amazon raw data available"]

        # Check if YNAB cache exists
        ynab_cache = self.data_dir / "ynab" / "cache" / "transactions.json"
        if not ynab_cache.exists():
            return False, ["No YNAB cache available"]

        # Check if matching results exist
        matches_dir = self.data_dir / "amazon" / "transaction_matches"
        if not matches_dir.exists() or not list(matches_dir.glob("*.json")):
            reasons.append("No previous matching results")
            return True, reasons

        # Compare timestamps
        latest_match = max(matches_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        ynab_mtime = ynab_cache.stat().st_mtime

        if ynab_mtime > latest_match.stat().st_mtime:
            reasons.append("YNAB data updated since last match")
            return True, reasons

        return False, ["Matching results are up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Amazon matching results summary."""
        matches_dir = self.data_dir / "amazon" / "transaction_matches"

        if not matches_dir.exists() or not list(matches_dir.glob("*.json")):
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="No Amazon matches found",
            )

        latest_file = max(matches_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
        age = (datetime.now() - mtime).days

        try:
            data = read_json(latest_file)
            count = len(data.get("matches", [])) if isinstance(data, dict) else 0
        except Exception:
            count = 0

        return NodeDataSummary(
            exists=True,
            last_updated=mtime,
            age_days=age,
            item_count=count,
            size_bytes=latest_file.stat().st_size,
            summary_text=f"Amazon matches: {count} transactions",
        )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute Amazon transaction matching."""
        from ..ynab import filter_transactions, load_ynab_transactions

        try:
            # Initialize matcher
            matcher = SimplifiedMatcher()

            # Load data
            amazon_data_dir = self.data_dir / "amazon" / "raw"
            ynab_cache_dir = self.data_dir / "ynab" / "cache"

            account_data = load_amazon_data(amazon_data_dir)
            all_transactions = load_ynab_transactions(ynab_cache_dir)

            # Filter transactions for Amazon
            transactions = filter_transactions(all_transactions, payee="Amazon")

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

            # Write results
            output_dir = self.data_dir / "amazon" / "transaction_matches"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_file = output_dir / f"{timestamp}_amazon_matching_results.json"

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

            # Use write_json_with_defaults to handle pandas Timestamps from CSV parsing
            write_json_with_defaults(output_file, result_data, default=str)

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
