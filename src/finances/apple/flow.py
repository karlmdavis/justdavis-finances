#!/usr/bin/env python3
"""
Apple Flow Nodes

Flow node implementations for Apple receipt processing and transaction matching.
"""

from datetime import datetime
from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary


class AppleEmailFetchFlowNode(FlowNode):
    """Fetch Apple receipt emails from IMAP."""

    def __init__(self, data_dir: Path):
        super().__init__("apple_email_fetch")
        self.data_dir = data_dir

        # Initialize DataStore
        from .datastore import AppleEmailStore

        self.store = AppleEmailStore(data_dir / "apple" / "emails")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new Apple receipt emails should be fetched."""
        if not self.store.exists():
            return True, ["No Apple emails found"]

        # Check age of most recent email
        age_days = self.store.age_days()
        if age_days and age_days > 7:
            return True, [f"Latest email is {age_days} days old"]

        return False, ["Apple emails are recent"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Apple emails summary."""
        return self.store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Fetch Apple receipt emails."""
        from .email_fetcher import AppleEmailFetcher

        try:
            # Initialize fetcher (loads config from environment automatically)
            fetcher = AppleEmailFetcher()

            # Fetch emails from IMAP
            emails = fetcher.fetch_apple_receipts()

            if not emails:
                fetcher.disconnect()
                return FlowResult(
                    success=True,
                    items_processed=0,
                    metadata={"message": "No Apple receipt emails found"},
                )

            # Save emails to disk
            output_dir = self.data_dir / "apple" / "emails"
            output_dir.mkdir(parents=True, exist_ok=True)

            stats = fetcher.save_emails_to_disk(emails, output_dir)
            fetcher.disconnect()

            return FlowResult(
                success=True,
                items_processed=len(emails),
                new_items=len(emails),
                outputs=[output_dir / f for f in stats.get("files_created", [])],
                metadata={
                    "emails_fetched": len(emails),
                    "files_created": len(stats.get("files_created", [])),
                    "output_dir": str(output_dir),
                },
            )

        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Apple email fetching failed: {e}",
            )


class AppleReceiptParsingFlowNode(FlowNode):
    """Parse Apple receipt emails to extract transaction data."""

    def __init__(self, data_dir: Path):
        super().__init__("apple_receipt_parsing")
        self.data_dir = data_dir
        self._dependencies = {"apple_email_fetch"}

        # Initialize DataStores
        from .datastore import AppleEmailStore, AppleReceiptStore

        self.email_store = AppleEmailStore(data_dir / "apple" / "emails")
        self.receipt_store = AppleReceiptStore(data_dir / "apple" / "exports")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new emails need parsing."""
        if not self.email_store.exists():
            return False, ["No Apple emails to parse"]

        if not self.receipt_store.exists():
            return True, ["No parsed receipts found"]

        # Check timestamps
        email_time = self.email_store.last_modified()
        receipt_time = self.receipt_store.last_modified()

        if email_time and receipt_time and email_time > receipt_time:
            return True, ["New emails detected"]

        return False, ["Parsed receipts are up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get parsed Apple receipts summary."""
        return self.receipt_store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Parse Apple receipt emails."""
        from ..core.json_utils import write_json
        from .parser import AppleReceiptParser

        try:
            emails_dir = self.data_dir / "apple" / "emails"
            exports_dir = self.data_dir / "apple" / "exports"
            exports_dir.mkdir(parents=True, exist_ok=True)

            # Find all HTML files
            html_files = list(emails_dir.glob("*.html"))
            if not html_files:
                return FlowResult(
                    success=True,
                    items_processed=0,
                    metadata={"message": "No HTML files to parse"},
                )

            parser = AppleReceiptParser()
            parsed_count = 0
            failed_count = 0
            output_files = []

            for html_file in html_files:
                try:
                    # Read HTML content
                    html_content = html_file.read_text(encoding="utf-8")

                    # Parse using receipt_id from filename
                    receipt_id = html_file.stem
                    parsed_receipt = parser.parse_html_content(html_content, receipt_id)

                    # Use order_id as filename if available, otherwise use email filename
                    receipt_dict = parsed_receipt.to_dict()
                    output_filename = receipt_dict.get("order_id") or receipt_id
                    if not output_filename:
                        output_filename = receipt_id

                    # Write parsed receipt as JSON
                    output_file = exports_dir / f"{output_filename}.json"
                    write_json(output_file, receipt_dict)
                    output_files.append(output_file)
                    parsed_count += 1

                except Exception as e:
                    failed_count += 1
                    print(f"Failed to parse {html_file.name}: {e}")

            return FlowResult(
                success=True,
                items_processed=len(html_files),
                new_items=parsed_count,
                outputs=output_files,
                metadata={
                    "parsed_count": parsed_count,
                    "failed_count": failed_count,
                    "output_dir": str(exports_dir),
                },
            )

        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Apple receipt parsing failed: {e}",
            )


class AppleMatchingFlowNode(FlowNode):
    """Match YNAB transactions to Apple receipts."""

    def __init__(self, data_dir: Path):
        super().__init__("apple_matching")
        self.data_dir = data_dir
        self._dependencies = {"ynab_sync", "apple_receipt_parsing"}

        # Initialize DataStores
        from .datastore import AppleMatchResultsStore, AppleReceiptStore

        self.receipt_store = AppleReceiptStore(data_dir / "apple" / "exports")
        self.match_store = AppleMatchResultsStore(data_dir / "apple" / "transaction_matches")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new Apple receipts or YNAB data requires matching."""
        # Check if parsed receipts exist
        if not self.receipt_store.exists():
            return False, ["No parsed Apple receipts available"]

        # Check if YNAB cache exists
        ynab_cache = self.data_dir / "ynab" / "cache" / "transactions.json"
        if not ynab_cache.exists():
            return False, ["No YNAB cache available"]

        # Check if matching results exist
        if not self.match_store.exists():
            return True, ["No previous matching results"]

        # Compare timestamps
        latest_match_time = self.match_store.last_modified()
        ynab_mtime = ynab_cache.stat().st_mtime

        if latest_match_time and ynab_mtime > latest_match_time.timestamp():
            return True, ["YNAB data updated since last match"]

        return False, ["Matching results are up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Apple matching results summary."""
        return self.match_store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute Apple transaction matching."""
        import pandas as pd

        from ..core.json_utils import read_json
        from ..ynab import filter_transactions, load_ynab_transactions
        from .loader import normalize_apple_receipt_data
        from .matcher import batch_match_transactions

        try:
            # Load YNAB transactions
            ynab_cache_dir = self.data_dir / "ynab" / "cache"
            all_transactions = load_ynab_transactions(ynab_cache_dir)

            # Filter for Apple transactions
            transactions = filter_transactions(all_transactions, payee="Apple")

            if not transactions:
                return FlowResult(
                    success=True,
                    items_processed=0,
                    metadata={"message": "No Apple transactions to match"},
                )

            # Convert YNAB transactions to DataFrame
            ynab_df = pd.DataFrame(transactions)

            # Load Apple receipts from JSON files
            exports_dir = self.data_dir / "apple" / "exports"
            receipt_files = list(exports_dir.glob("*.json"))

            if not receipt_files:
                return FlowResult(
                    success=False,
                    error_message="No parsed Apple receipts found",
                )

            receipts = []
            for receipt_file in receipt_files:
                receipt_data = read_json(receipt_file)
                receipts.append(receipt_data)

            # Normalize Apple receipts to DataFrame
            apple_df = normalize_apple_receipt_data(receipts)

            # Match transactions
            match_results = batch_match_transactions(ynab_df, apple_df)

            # Calculate statistics
            matched_count = sum(1 for result in match_results if result.receipts)
            match_rate = matched_count / len(transactions) if transactions else 0.0
            total_confidence = sum(result.confidence for result in match_results if result.receipts)
            avg_confidence = total_confidence / matched_count if matched_count > 0 else 0.0

            # Write results using DataStore
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            result_data = {
                "metadata": {
                    "timestamp": timestamp,
                    "receipts_count": len(receipts),
                },
                "summary": {
                    "total_transactions": len(transactions),
                    "matched_transactions": matched_count,
                    "match_rate": match_rate,
                    "average_confidence": avg_confidence,
                },
                "matches": [
                    {
                        "transaction_id": result.transaction.id if result.transaction else None,
                        "transaction_amount": result.transaction.amount_cents if result.transaction else None,
                        "receipt_ids": [r.id for r in result.receipts] if result.receipts else [],
                        "matched": bool(result.receipts),
                        "confidence": result.confidence,
                        "match_method": result.match_method,
                        "date_difference": result.date_difference,
                        "amount_difference": result.amount_difference,
                    }
                    for result in match_results
                ],
            }

            self.match_store.save(result_data)

            # Get output file path for FlowResult
            output_dir = self.data_dir / "apple" / "transaction_matches"
            output_file = output_dir / f"{timestamp}_apple_matching_results.json"

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
            return FlowResult(
                success=False,
                error_message=f"Apple matching failed: {e}",
            )
