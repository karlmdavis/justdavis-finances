#!/usr/bin/env python3
"""
Split Generation Flow Node

Flow node for generating YNAB splits from Amazon and Apple transaction matches.
"""

from datetime import datetime
from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary


def transform_apple_receipt_data(
    receipt_data: dict,
) -> tuple[list[dict], int | None, int | None]:
    """
    Transform Apple receipt data from parser format to calculator format.

    Parser format uses float dollars and 'cost' field:
        {"title": "Item", "cost": 10.99, ...}
        {"subtotal": 13.98, "tax": 1.12, ...}

    Calculator format uses int cents and 'price' field:
        {"name": "Item", "price": 1099}
        subtotal: 1398, tax: 112

    Args:
        receipt_data: Raw receipt data from parser

    Returns:
        Tuple of (items, subtotal_cents, tax_cents)
    """
    # Transform items: float dollars + 'cost' → int cents + 'price'
    raw_items = receipt_data.get("items", [])
    transformed_items = []

    for item in raw_items:
        # Get cost as float (parser stores dollars as float)
        cost_dollars = item.get("cost", 0.0)
        if not isinstance(cost_dollars, (int, float)):
            cost_dollars = 0.0

        # Convert dollars to cents
        cost_cents = int(cost_dollars * 100)

        # Create transformed item with 'price' field (not 'cost')
        transformed_item = {
            "name": item.get("title", "Unknown Item"),
            "price": cost_cents,  # Calculator expects 'price' not 'cost'
        }
        transformed_items.append(transformed_item)

    # Transform subtotal: float dollars → int cents
    subtotal_dollars = receipt_data.get("subtotal")
    subtotal_cents = None
    if subtotal_dollars is not None and isinstance(subtotal_dollars, (int, float)):
        subtotal_cents = int(subtotal_dollars * 100)

    # Transform tax: float dollars → int cents
    tax_dollars = receipt_data.get("tax")
    tax_cents = None
    if tax_dollars is not None and isinstance(tax_dollars, (int, float)):
        tax_cents = int(tax_dollars * 100)

    return transformed_items, subtotal_cents, tax_cents


class SplitGenerationFlowNode(FlowNode):
    """Generate YNAB splits from transaction matches (manual step)."""

    def __init__(self, data_dir: Path):
        super().__init__("split_generation")
        self.data_dir = data_dir
        self._dependencies = {"amazon_matching", "apple_matching"}

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if new matches require split generation."""
        reasons = []

        # Check for Amazon matches
        amazon_matches_dir = self.data_dir / "amazon" / "transaction_matches"
        amazon_matches = []
        if amazon_matches_dir.exists():
            amazon_matches = list(amazon_matches_dir.glob("*.json"))

        # Check for Apple matches
        apple_matches_dir = self.data_dir / "apple" / "transaction_matches"
        apple_matches = []
        if apple_matches_dir.exists():
            apple_matches = list(apple_matches_dir.glob("*.json"))

        if not amazon_matches and not apple_matches:
            return False, ["No match results available"]

        # Check for existing split edits
        edits_dir = self.data_dir / "ynab" / "edits"
        split_edits = []
        if edits_dir.exists():
            split_edits = list(edits_dir.glob("*split*.json"))

        if not split_edits:
            reasons.append("No split edits found")
            return True, reasons

        # Check if match files are newer than edits
        all_matches = amazon_matches + apple_matches
        if all_matches:
            latest_match = max(all_matches, key=lambda p: p.stat().st_mtime)
            latest_edit = max(split_edits, key=lambda p: p.stat().st_mtime)

            if latest_match.stat().st_mtime > latest_edit.stat().st_mtime:
                reasons.append("New matches since last split generation")
                return True, reasons

        return False, ["Split edits are up to date"]

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
        from ..core.json_utils import read_json, write_json
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

                        # Extract transaction info
                        ynab_tx = match.get("ynab_transaction", {})
                        tx_id = ynab_tx.get("id")
                        tx_amount_cents = ynab_tx.get("amount")

                        if not tx_id or tx_amount_cents is None:
                            continue

                        # Convert cents to milliunits (YNAB format)
                        from ..core.currency import cents_to_milliunits

                        tx_amount_milliunits = -cents_to_milliunits(tx_amount_cents)  # Negative for expenses

                        # Extract items from first order
                        amazon_order = best_match["amazon_orders"][0]
                        items = amazon_order.get("items", [])

                        if not items:
                            continue

                        # Generate splits
                        try:
                            splits = calculate_amazon_splits(tx_amount_milliunits, items)
                            all_edits.append(
                                {
                                    "transaction_id": tx_id,
                                    "splits": splits,
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

                            # Transform receipt data from parser format to calculator format
                            # Parser uses float dollars and 'cost' field
                            # Calculator expects int cents and 'price' field
                            items, subtotal, tax = transform_apple_receipt_data(receipt_data)

                            if not items:
                                continue

                            # Convert transaction amount to milliunits (negative for expenses)
                            from ..core.currency import cents_to_milliunits

                            tx_amount_milliunits = -cents_to_milliunits(tx_amount)

                            # Generate splits
                            splits = calculate_apple_splits(tx_amount_milliunits, items, subtotal, tax)

                            all_edits.append(
                                {
                                    "transaction_id": tx_id,
                                    "splits": splits,
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
