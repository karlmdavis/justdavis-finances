#!/usr/bin/env python3
"""
Split Generation Flow Node

Flow node for generating YNAB splits from Amazon and Apple transaction matches.
"""

from datetime import datetime
from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo


class SplitGenerationOutputInfo(OutputInfo):
    """Output information for split generation node."""

    def __init__(self, edits_dir: Path):
        self.edits_dir = edits_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 file with 'edits' key exists."""
        if not self.edits_dir.exists():
            return False

        from ..core.json_utils import read_json

        # Check all JSON files for "edits" key
        for json_file in self.edits_dir.glob("*.json"):
            try:
                data = read_json(json_file)
                if isinstance(data, dict) and "edits" in data:
                    return True
            except Exception:
                continue

        return False

    def get_output_files(self) -> list[OutputFile]:
        """Return only files with 'edits' key and their counts."""
        if not self.edits_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for json_file in self.edits_dir.glob("*.json"):
            try:
                data = read_json(json_file)
                # Only include files with "edits" key
                if isinstance(data, dict) and "edits" in data:
                    count = len(data["edits"])
                    files.append(OutputFile(path=json_file, record_count=count))
            except Exception:
                continue

        return files


class SplitGenerationFlowNode(FlowNode):
    """Generate YNAB splits from transaction matches (manual step)."""

    def __init__(self, data_dir: Path):
        super().__init__("split_generation")
        self.data_dir = data_dir
        self._dependencies = {"amazon_matching", "apple_matching"}

    def get_output_info(self) -> OutputInfo:
        """Get output information for split generation node."""
        return SplitGenerationOutputInfo(self.data_dir / "ynab" / "edits")

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get split generation summary."""
        # Count available match files
        amazon_matches_dir = self.data_dir / "amazon" / "transaction_matches"
        apple_matches_dir = self.data_dir / "apple" / "transaction_matches"

        amazon_count = len(list(amazon_matches_dir.glob("*.json"))) if amazon_matches_dir.exists() else 0
        apple_count = len(list(apple_matches_dir.glob("*.json"))) if apple_matches_dir.exists() else 0

        if amazon_count == 0 and apple_count == 0:
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=None,
                size_bytes=None,
                summary_text="No match results available for split generation",
            )

        # Check last edit time
        edits_dir = self.data_dir / "ynab" / "edits"
        last_updated = None
        age = None
        if edits_dir.exists():
            split_edits = list(edits_dir.glob("*split*.json"))
            if split_edits:
                latest = max(split_edits, key=lambda p: p.stat().st_mtime)
                last_updated = datetime.fromtimestamp(latest.stat().st_mtime)
                age = (datetime.now() - last_updated).days

        return NodeDataSummary(
            exists=True,
            last_updated=last_updated,
            age_days=age,
            item_count=amazon_count + apple_count,
            size_bytes=None,
            summary_text=f"Match files available: {amazon_count} Amazon, {apple_count} Apple",
        )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute split generation from Amazon and Apple match results."""
        from ..amazon.models import MatchedOrderItem
        from ..apple.parser import ParsedReceipt
        from ..core.json_utils import read_json, write_json
        from .models import YnabTransaction
        from .split_calculator import calculate_amazon_splits, calculate_apple_splits

        try:
            amazon_matches_dir = self.data_dir / "amazon" / "transaction_matches"
            apple_matches_dir = self.data_dir / "apple" / "transaction_matches"

            all_edits = []
            amazon_processed = 0
            apple_processed = 0

            # Process Amazon matches
            if amazon_matches_dir.exists():
                for match_file in amazon_matches_dir.glob("*.json"):
                    match_data = read_json(match_file)

                    # Extract matches from file
                    matches = match_data.get("matches", [])

                    for match in matches:
                        best_match = match.get("best_match")
                        if not best_match or not best_match.get("amazon_orders"):
                            continue

                        # Extract transaction info and create domain model
                        ynab_tx_dict = match.get("ynab_transaction", {})
                        tx_id = ynab_tx_dict.get("id")
                        tx_amount_milliunits = ynab_tx_dict.get("amount")  # Already in milliunits

                        if not tx_id or tx_amount_milliunits is None:
                            continue

                        # Create YnabTransaction domain model
                        transaction = YnabTransaction.from_dict(ynab_tx_dict)

                        # Extract items from first order and convert to domain models
                        amazon_order = best_match["amazon_orders"][0]
                        item_dicts = amazon_order.get("items", [])

                        if not item_dicts:
                            continue

                        # Deserialize items from JSON using MatchedOrderItem (match-layer model)
                        matched_items = [MatchedOrderItem.from_dict(item_dict) for item_dict in item_dicts]

                        # Generate splits using domain model signature
                        try:
                            splits = calculate_amazon_splits(transaction, matched_items)
                            # Convert YnabSplit objects to dicts for JSON
                            split_dicts = [s.to_ynab_dict() for s in splits]
                            all_edits.append(
                                {
                                    "transaction_id": tx_id,
                                    "splits": split_dicts,
                                    "source": "amazon",
                                }
                            )
                            amazon_processed += 1
                        except Exception as e:
                            print(f"Failed to generate Amazon splits for {tx_id}: {e}")

            # Process Apple matches
            if apple_matches_dir.exists():
                for match_file in apple_matches_dir.glob("*.json"):
                    match_data = read_json(match_file)

                    # Extract matches from file
                    matches = match_data.get("matches", [])

                    for match in matches:
                        if not match.get("matched"):
                            continue

                        tx_id = match.get("transaction_id")
                        tx_amount = match.get("transaction_amount")
                        receipt_ids = match.get("receipt_ids", [])

                        if not tx_id or not receipt_ids or tx_amount is None:
                            continue

                        # For now, skip multi-receipt matches (1:1 model only)
                        if len(receipt_ids) != 1:
                            continue

                        # Load receipt data to get items
                        receipt_file = self.data_dir / "apple" / "exports" / f"{receipt_ids[0]}.json"
                        if not receipt_file.exists():
                            print(f"Receipt file not found: {receipt_file}")
                            continue

                        try:
                            receipt_data = read_json(receipt_file)

                            # Create ParsedReceipt domain model from dict
                            receipt = ParsedReceipt.from_dict(receipt_data)

                            if not receipt.items:
                                continue

                            # Create YnabTransaction domain model
                            # Note: tx_amount is already in milliunits (from Apple matcher)
                            transaction = YnabTransaction.from_dict(
                                {
                                    "id": tx_id,
                                    "date": match.get("transaction_date", ""),
                                    "amount": tx_amount,
                                }
                            )

                            # Generate splits using domain model signature
                            splits = calculate_apple_splits(transaction, receipt)

                            # Convert YnabSplit objects to dicts for JSON
                            split_dicts = [s.to_ynab_dict() for s in splits]

                            all_edits.append(
                                {
                                    "transaction_id": tx_id,
                                    "splits": split_dicts,
                                    "source": "apple",
                                }
                            )
                            apple_processed += 1

                        except Exception as e:
                            print(f"Failed to generate Apple splits for {tx_id}: {e}")

            if not all_edits:
                return FlowResult(
                    success=True,
                    items_processed=0,
                    metadata={"message": "No splits generated - no valid matches found"},
                )

            # Write combined edit file
            edits_dir = self.data_dir / "ynab" / "edits"
            edits_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_file = edits_dir / f"{timestamp}_split_edits.json"

            edit_data = {
                "metadata": {
                    "timestamp": timestamp,
                    "amazon_matches_processed": amazon_processed,
                    "apple_matches_processed": apple_processed,
                    "total_edits": len(all_edits),
                },
                "edits": all_edits,
            }

            write_json(output_file, edit_data)

            return FlowResult(
                success=True,
                items_processed=amazon_processed + apple_processed,
                new_items=len(all_edits),
                outputs=[output_file],
                metadata={
                    "amazon_edits": amazon_processed,
                    "apple_edits": apple_processed,
                    "total_edits": len(all_edits),
                    "output_file": str(output_file),
                },
            )

        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Split generation failed: {e}",
            )
