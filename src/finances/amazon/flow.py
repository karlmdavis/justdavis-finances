#!/usr/bin/env python3
"""
Amazon Flow Nodes

Flow node implementations for Amazon transaction matching.
"""

from datetime import datetime
from pathlib import Path

import click

from ..core.flow import (
    FlowContext,
    FlowNode,
    FlowResult,
    NodeDataSummary,
    OutputFile,
    OutputInfo,
)
from . import SimplifiedMatcher, load_orders
from .unzipper import extract_amazon_zip_files


class AmazonOrderHistoryOutputInfo(OutputInfo):
    """Output information for Amazon order history request (manual step)."""

    def __init__(self, raw_dir: Path):
        self.raw_dir = raw_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .zip file exists."""
        if not self.raw_dir.exists():
            return False
        return len(list(self.raw_dir.glob("*.zip"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return .zip files (1 record per ZIP file to process)."""
        if not self.raw_dir.exists():
            return []
        return [OutputFile(path=zip_file, record_count=1) for zip_file in self.raw_dir.glob("*.zip")]


class AmazonOrderHistoryRequestFlowNode(FlowNode):
    """Manual step prompting user to download Amazon order history."""

    def __init__(self, data_dir: Path) -> None:
        super().__init__("amazon_order_history_request")
        self.data_dir = data_dir

    def get_output_info(self) -> OutputInfo:
        """Get output information for manual step - checks for ZIP files."""
        return AmazonOrderHistoryOutputInfo(self.data_dir / "amazon" / "raw")

    def get_output_dir(self) -> Path | None:
        """Return Amazon raw directory where ZIPs should be placed."""
        return self.data_dir / "amazon" / "raw"

    def execute(self, context: FlowContext) -> FlowResult:
        """Prompt user to download Amazon order history."""
        raw_dir = self.data_dir / "amazon" / "raw"
        click.echo("\n📋 Manual Step Required:")
        click.echo("1. Visit https://www.amazon.com/gp/privacycentral/dsar/preview.html")
        click.echo("2. Request 'Order Reports' for the desired date range")
        click.echo("3. Download the ZIP files when ready")
        click.echo(f"4. Place them in {raw_dir}")

        if not click.confirm("Have you completed this step?"):
            return FlowResult(success=False, error_message="User cancelled manual step")

        return FlowResult(
            success=True,
            items_processed=0,
            metadata={"manual_step": True, "description": "Amazon order history request"},
        )


class AmazonUnzipOutputInfo(OutputInfo):
    """Output information for Amazon unzip node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 order history CSV exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("**/Retail.OrderHistory.*.csv"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return order history CSV files with row counts."""
        if not self.output_dir.exists():
            return []

        files = []
        for csv_file in self.output_dir.glob("**/Retail.OrderHistory.*.csv"):
            try:
                lines = csv_file.read_text().strip().split("\n")
                # Count data rows (exclude header)
                row_count = max(0, len(lines) - 1)
                files.append(OutputFile(path=csv_file, record_count=row_count))
            except Exception:
                files.append(OutputFile(path=csv_file, record_count=0))

        return files


class AmazonUnzipFlowNode(FlowNode):
    """Extract Amazon order history ZIP files."""

    def __init__(self, data_dir: Path):
        super().__init__("amazon_unzip")
        self.data_dir = data_dir
        self._dependencies = {"amazon_order_history_request"}

        # Initialize DataStore
        from .datastore import AmazonRawDataStore

        self.store = AmazonRawDataStore(data_dir / "amazon" / "raw")

    def get_output_info(self) -> OutputInfo:
        """Get output information for unzip node."""
        return AmazonUnzipOutputInfo(self.data_dir / "amazon" / "raw")

    def get_output_dir(self) -> Path | None:
        """Return Amazon raw data output directory."""
        return self.data_dir / "amazon" / "raw"

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


class AmazonMatchingOutputInfo(OutputInfo):
    """Output information for Amazon matching node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .json match result file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return .json match result files with match counts."""
        if not self.output_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for json_file in self.output_dir.glob("*.json"):
            try:
                data = read_json(json_file)
                match_count = len(data.get("matches", []))
                files.append(OutputFile(path=json_file, record_count=match_count))
            except Exception:
                files.append(OutputFile(path=json_file, record_count=0))

        return files


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

    def get_output_info(self) -> OutputInfo:
        """Get output information for matching node."""
        return AmazonMatchingOutputInfo(self.data_dir / "amazon" / "transaction_matches")

    def get_output_dir(self) -> Path | None:
        """Return Amazon matching results output directory."""
        return self.data_dir / "amazon" / "transaction_matches"

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

            if not amazon_transactions:
                return FlowResult(
                    success=True,
                    items_processed=0,
                    metadata={"message": "No Amazon transactions to match"},
                )

            # Match transactions using domain model signature
            matches = []
            matched_count = 0
            total_confidence = 0.0

            for transaction in amazon_transactions:
                # Use new domain model signature: YnabTransaction, dict[str, list[AmazonOrderItem]]
                match_result = matcher.match_transaction(transaction, orders_by_account)

                # Convert AmazonMatchResult to dict for JSON storage
                match_dict = {
                    "ynab_transaction": {
                        "id": match_result.transaction.id,
                        "amount": match_result.transaction.amount.to_milliunits(),
                        "date": match_result.transaction.date.to_iso_string(),
                        "payee_name": match_result.transaction.payee_name,
                        "memo": match_result.transaction.memo,
                        "account_name": match_result.transaction.account_name,
                    },
                    "matches": [m.to_dict() for m in match_result.matches],
                    "best_match": match_result.best_match.to_dict() if match_result.best_match else None,
                    "message": match_result.message,
                }

                if match_result.best_match:
                    matched_count += 1
                    total_confidence += match_result.best_match.confidence
                matches.append(match_dict)

            # Calculate statistics
            match_rate = matched_count / len(amazon_transactions) if amazon_transactions else 0.0
            avg_confidence = total_confidence / matched_count if matched_count > 0 else 0.0

            # Write results using DataStore
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            result_data = {
                "metadata": {
                    "timestamp": timestamp,
                    "accounts": "all",
                },
                "summary": {
                    "total_transactions": len(amazon_transactions),
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
                items_processed=len(amazon_transactions),
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
