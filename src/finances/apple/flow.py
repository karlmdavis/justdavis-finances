#!/usr/bin/env python3
"""
Apple Flow Nodes

Flow node implementations for Apple receipt processing and transaction matching.
"""

from datetime import datetime
from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary
from ..core.json_utils import read_json


class AppleEmailFetchFlowNode(FlowNode):
    """Fetch Apple receipt emails from IMAP."""

    def __init__(self, data_dir: Path):
        super().__init__("apple_email_fetch")
        self.data_dir = data_dir

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new Apple receipt emails should be fetched."""
        emails_dir = self.data_dir / "apple" / "emails"

        if not emails_dir.exists() or not list(emails_dir.glob("*.eml")):
            return True, ["No Apple emails found"]

        # Check age of most recent email
        email_files = list(emails_dir.glob("*.eml"))
        latest = max(email_files, key=lambda p: p.stat().st_mtime)
        age_days = (datetime.now().timestamp() - latest.stat().st_mtime) / 86400

        if age_days > 7:
            return True, [f"Latest email is {age_days:.0f} days old"]

        return False, ["Apple emails are recent"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Apple emails summary."""
        emails_dir = self.data_dir / "apple" / "emails"

        if not emails_dir.exists() or not list(emails_dir.glob("*.eml")):
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="No Apple emails found",
            )

        email_files = list(emails_dir.glob("*.eml"))
        latest_file = max(email_files, key=lambda p: p.stat().st_mtime)
        mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
        age = (datetime.now() - mtime).days

        return NodeDataSummary(
            exists=True,
            last_updated=mtime,
            age_days=age,
            item_count=len(email_files),
            size_bytes=sum(f.stat().st_size for f in email_files),
            summary_text=f"Apple emails: {len(email_files)} receipts",
        )

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

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new emails need parsing."""
        emails_dir = self.data_dir / "apple" / "emails"
        exports_dir = self.data_dir / "apple" / "exports"

        if not emails_dir.exists() or not list(emails_dir.glob("*.eml")):
            return False, ["No Apple emails to parse"]

        if not exports_dir.exists() or not list(exports_dir.glob("*.json")):
            return True, ["No parsed receipts found"]

        # Check timestamps
        latest_email = max(emails_dir.glob("*.eml"), key=lambda p: p.stat().st_mtime)
        latest_export = max(exports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

        if latest_email.stat().st_mtime > latest_export.stat().st_mtime:
            return True, ["New emails detected"]

        return False, ["Parsed receipts are up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get parsed Apple receipts summary."""
        exports_dir = self.data_dir / "apple" / "exports"

        if not exports_dir.exists() or not list(exports_dir.glob("*.json")):
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="No parsed Apple receipts found",
            )

        json_files = list(exports_dir.glob("*.json"))
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
        age = (datetime.now() - mtime).days

        return NodeDataSummary(
            exists=True,
            last_updated=mtime,
            age_days=age,
            item_count=len(json_files),
            size_bytes=sum(f.stat().st_size for f in json_files),
            summary_text=f"Parsed receipts: {len(json_files)} files",
        )

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

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new Apple receipts or YNAB data requires matching."""
        # Check if parsed receipts exist
        exports_dir = self.data_dir / "apple" / "exports"
        if not exports_dir.exists() or not list(exports_dir.glob("*.json")):
            return False, ["No parsed Apple receipts available"]

        # Check if YNAB cache exists
        ynab_cache = self.data_dir / "ynab" / "cache" / "transactions.json"
        if not ynab_cache.exists():
            return False, ["No YNAB cache available"]

        # Check if matching results exist
        matches_dir = self.data_dir / "apple" / "transaction_matches"
        if not matches_dir.exists() or not list(matches_dir.glob("*.json")):
            return True, ["No previous matching results"]

        # Compare timestamps
        latest_match = max(matches_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        ynab_mtime = ynab_cache.stat().st_mtime

        if ynab_mtime > latest_match.stat().st_mtime:
            return True, ["YNAB data updated since last match"]

        return False, ["Matching results are up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get Apple matching results summary."""
        matches_dir = self.data_dir / "apple" / "transaction_matches"

        if not matches_dir.exists() or not list(matches_dir.glob("*.json")):
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="No Apple matches found",
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
            summary_text=f"Apple matches: {count} transactions",
        )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute Apple transaction matching."""
        import pandas as pd

        from ..core.json_utils import write_json
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

            # Write results
            output_dir = self.data_dir / "apple" / "transaction_matches"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_file = output_dir / f"{timestamp}_apple_matching_results.json"

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

            write_json(output_file, result_data)

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
