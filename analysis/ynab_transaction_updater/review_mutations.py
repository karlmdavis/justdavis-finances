#!/usr/bin/env python3
"""
Mutation Review Interface for YNAB Transaction Updater.

Provides interactive review of generated mutations with approval/rejection workflow.
Implements the Phase 2 logic from the specification.

Usage:
    python review_mutations.py \\
        --mutations mutations.yaml \\
        --interactive \\
        --output approved_mutations.yaml
"""

import yaml
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from .currency_utils import cents_to_dollars_str, milliunits_to_cents
except ImportError:
    from currency_utils import cents_to_dollars_str, milliunits_to_cents


class MutationReviewer:
    """Interactive review interface for mutation approval."""

    def __init__(self):
        """Initialize mutation reviewer."""
        self.approved = []
        self.rejected = []
        self.total_reviewed = 0

    def load_mutations(self, mutations_path: str) -> Dict[str, Any]:
        """
        Load mutations from YAML file.

        Args:
            mutations_path: Path to mutations YAML file

        Returns:
            Mutations data structure
        """
        try:
            with open(mutations_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load mutations: {e}")

    def review_mutations_interactive(self, mutations_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Review mutations interactively with user approval.

        Args:
            mutations_data: Loaded mutations data

        Returns:
            List of approved mutations
        """
        mutations = mutations_data.get('mutations', [])
        metadata = mutations_data.get('metadata', {})

        print("="*80)
        print("YNAB Transaction Mutation Review")
        print("="*80)
        print(f"Source: {metadata.get('source_file', 'Unknown')}")
        print(f"Generated: {metadata.get('generated_at', 'Unknown')}")
        print(f"Total mutations: {len(mutations)}")
        print(f"Confidence threshold: {metadata.get('confidence_threshold', 'Unknown')}")
        print("="*80)
        print()

        for i, mutation in enumerate(mutations, 1):
            print(f"Mutation {i}/{len(mutations)}")
            print("-" * 40)

            self._display_mutation(mutation)

            # Get user decision
            while True:
                choice = input("\n[a]pprove, [r]eject, [s]kip, [q]uit: ").lower().strip()

                if choice in ['a', 'approve']:
                    self._approve_mutation(mutation)
                    break
                elif choice in ['r', 'reject']:
                    reason = input("Rejection reason (optional): ").strip()
                    self._reject_mutation(mutation, reason)
                    break
                elif choice in ['s', 'skip']:
                    print("Skipped.")
                    break
                elif choice in ['q', 'quit']:
                    if input("Really quit? [y/N]: ").lower().startswith('y'):
                        print("Exiting review session.")
                        return self._get_approved_mutations()
                else:
                    print("Invalid choice. Please enter 'a', 'r', 's', or 'q'.")

            print()

        return self._get_approved_mutations()

    def review_mutations_batch(
        self,
        mutations_data: Dict[str, Any],
        auto_approve_confidence: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Review mutations in batch mode with automatic approval above threshold.

        Args:
            mutations_data: Loaded mutations data
            auto_approve_confidence: Auto-approve if confidence >= this value

        Returns:
            List of approved mutations
        """
        mutations = mutations_data.get('mutations', [])

        for mutation in mutations:
            confidence = mutation.get('confidence', 0.0)

            if confidence >= auto_approve_confidence:
                self._approve_mutation(mutation, "auto-approved (high confidence)")
            else:
                self._reject_mutation(mutation, f"below auto-approval threshold ({auto_approve_confidence})")

        return self._get_approved_mutations()

    def _display_mutation(self, mutation: Dict[str, Any]):
        """
        Display mutation details for review.

        Args:
            mutation: Mutation dictionary
        """
        # Reordered header (confidence moved to Match Details section)
        print(f"Transaction ID: {mutation['transaction_id']}")
        print(f"Date: {mutation['date']}")
        print(f"Account: {mutation['account']}")
        print(f"Source: {mutation['source']}")
        print(f"Action: {mutation['action']}")
        print()

        # New Match Details section
        self._display_match_details(mutation)
        print()

        # Original transaction
        original = mutation['original']
        amount_str = self._format_amount(original['amount'])
        print("BEFORE:")
        print(f"  Amount: {amount_str}")
        print(f"  Memo: '{original['memo']}'")
        print(f"  Payee: '{original['payee']}'")
        print()

        # Show what will change
        if mutation['action'] == 'split':
            self._display_split_changes(mutation)
        elif mutation['action'] == 'update_memo':
            self._display_memo_change(mutation)

        # Show matched order/receipt info
        self._display_match_info(mutation)

    def _display_split_changes(self, mutation: Dict[str, Any]):
        """Display split transaction changes."""
        splits = mutation.get('splits', [])
        print("AFTER (Split Transaction):")

        total_amount = 0
        for i, split in enumerate(splits, 1):
            amount_str = self._format_amount(split['amount'])
            print(f"  Split {i}: {amount_str} - {split['memo']}")
            total_amount += split['amount']

        print(f"  Total: {self._format_amount(total_amount)}")
        print()

    def _display_memo_change(self, mutation: Dict[str, Any]):
        """Display memo-only changes."""
        new_memo = mutation.get('new_memo', '')
        print("AFTER:")
        print(f"  Memo: '{new_memo}' (memo updated)")
        print()

    def _display_match_info(self, mutation: Dict[str, Any]):
        """Display matched order/receipt information."""
        source = mutation['source']

        if source == 'amazon':
            order = mutation.get('matched_order', {})
            print("Matched Amazon Order:")
            print(f"  Order ID: {order.get('order_id', 'N/A')}")
            print(f"  Order Date: {order.get('order_date', 'N/A')}")
            print(f"  Account: {order.get('account', 'N/A')}")
            order_total = order.get('total', 0)
            if order_total > 0:
                print(f"  Order Total: ${order_total/100:.2f}")

            # Show item breakdown with shipping/tax details
            items = mutation.get('item_breakdown', [])
            if items:
                print("  Item Details:")
                for item in items:
                    name = item.get('name', 'Unknown Item')
                    unit_price = item.get('unit_price', 0)
                    total_amount = item.get('amount', 0)
                    quantity = item.get('quantity', 1)

                    # Calculate shipping/tax
                    shipping_tax = total_amount - (unit_price * quantity)

                    # Truncate long names
                    display_name = name[:60] + "..." if len(name) > 60 else name

                    print(f"    • {display_name}")
                    print(f"      Base: ${unit_price/100:.2f} x {quantity} = ${(unit_price * quantity)/100:.2f}")
                    if shipping_tax > 0:
                        print(f"      +Shipping/Tax: ${shipping_tax/100:.2f}")
                    print(f"      Total: ${total_amount/100:.2f}")

        elif source == 'apple':
            receipt = mutation.get('matched_receipt', {})
            print("Matched Apple Receipt:")
            print(f"  Order ID: {receipt.get('order_id', 'N/A')}")
            print(f"  Receipt Date: {receipt.get('receipt_date', 'N/A')}")
            print(f"  Apple ID: {receipt.get('apple_id', 'N/A')}")
            print(f"  Subtotal: ${receipt.get('subtotal', 0):.2f}")
            print(f"  Tax: ${receipt.get('tax', 0):.2f}")

    def _display_match_details(self, mutation: Dict[str, Any]):
        """Display match quality details."""
        source = mutation['source']
        confidence = mutation['confidence']

        print("Match Details:")

        # Match Type
        match_type = self._get_match_type_description(mutation)
        print(f"  Match Type: {match_type}")

        # Confidence with level description
        confidence_level = self._get_confidence_level(confidence)
        print(f"  Confidence: {confidence:.3f} ({confidence_level})")

        # Date Delta
        date_delta = self._calculate_date_delta(mutation)
        print(f"  Date Delta: {date_delta}")

        # Amount Delta
        amount_delta = self._calculate_amount_delta(mutation)
        print(f"  Amount Delta: {amount_delta}")

    def _get_match_type_description(self, mutation: Dict[str, Any]) -> str:
        """Get human-readable match type description."""
        source = mutation['source']
        match_method = mutation.get('match_method')

        # Fallback: infer from action and item count if match_method not available
        if not match_method and 'item_breakdown' in mutation and mutation['item_breakdown']:
            items = mutation.get('item_breakdown', [])
            if len(items) == 1:
                match_method = 'complete_single_order'
            else:
                match_method = 'complete_multi_day_order'

        if source == 'amazon':
            amazon_descriptions = {
                'complete_single_order': 'Complete Single Order',
                'complete_multi_day_order': 'Complete Multi-Day Order',
                'complete_shipment': 'Complete Shipment',
                'complete_daily_shipment': 'Complete Daily Shipment',
                'split_payment': 'Partial Payment',
                'fuzzy_shipment_match': 'Approximate Shipment Match',
                'fuzzy_order_match': 'Approximate Order Match'
            }
            return amazon_descriptions.get(match_method, f'Unknown Match Type ({match_method})')

        elif source == 'apple':
            apple_descriptions = {
                'exact_date_amount': 'Exact Match',
                'date_window_match': 'Date Window Match'
            }
            return apple_descriptions.get(match_method, f'Unknown Match Type ({match_method})')

        return f'Unknown Match Type ({match_method})'

    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level description."""
        if confidence >= 0.95:
            return 'High'
        elif confidence >= 0.85:
            return 'Medium'
        elif confidence >= 0.80:
            return 'Acceptable'
        else:
            return 'Low'

    def _calculate_date_delta(self, mutation: Dict[str, Any]) -> str:
        """Calculate and format date delta between YNAB transaction and order/receipt."""
        from datetime import datetime

        try:
            ynab_date_str = mutation['date']
            ynab_date = datetime.strptime(ynab_date_str, '%Y-%m-%d').date()

            source = mutation['source']
            reference_date = None

            if source == 'amazon':
                # Prefer ship_date from items, fall back to order_date
                items = mutation.get('item_breakdown', [])
                if items and 'ship_date' in items[0]:
                    # Use first item's ship_date
                    ship_date_str = items[0]['ship_date']
                    # Parse ISO datetime: "2025-03-10 14:10:32.580000+00:00"
                    reference_date = datetime.fromisoformat(ship_date_str.replace('+00:00', '')).date()
                else:
                    # Fall back to order_date from matched_order
                    order_date_str = mutation.get('matched_order', {}).get('order_date', '')
                    if order_date_str:
                        reference_date = datetime.fromisoformat(order_date_str.replace('+00:00', '')).date()

            elif source == 'apple':
                # Use receipt_date
                receipt_date_str = mutation.get('matched_receipt', {}).get('receipt_date', '')
                if receipt_date_str:
                    reference_date = datetime.strptime(receipt_date_str, '%Y-%m-%d').date()

            if reference_date:
                delta_days = (ynab_date - reference_date).days
                if delta_days == 0:
                    return "Same day"
                elif delta_days > 0:
                    return f"+{delta_days} day{'s' if delta_days != 1 else ''} (YNAB after order/ship)"
                else:
                    return f"{delta_days} day{'s' if delta_days != -1 else ''} (YNAB before order/ship)"

            return "Date comparison unavailable"

        except Exception as e:
            return f"Date calculation error: {str(e)}"

    def _calculate_amount_delta(self, mutation: Dict[str, Any]) -> str:
        """Calculate and format amount delta between YNAB transaction and matched total."""
        try:
            ynab_amount_milliunits = abs(mutation['original']['amount'])  # milliunits

            # Convert YNAB milliunits to cents using integer arithmetic
            ynab_cents = ynab_amount_milliunits // 10

            # Calculate matched total from splits (if available) or item_breakdown
            if 'splits' in mutation:
                # Use actual split amounts (already accounts for remainder allocation)
                matched_total_milliunits = 0
                for split in mutation['splits']:
                    matched_total_milliunits += abs(split.get('amount', 0))
                matched_total_cents = matched_total_milliunits // 10
            else:
                # Fallback to item_breakdown for memo-only updates
                matched_total_cents = 0
                items = mutation.get('item_breakdown', [])
                for item in items:
                    matched_total_cents += item.get('amount', 0)

            # Calculate delta in cents (integer arithmetic)
            delta_cents = abs(ynab_cents - matched_total_cents)

            if delta_cents == 0:
                return "Perfect match"
            else:
                # Convert to dollars only for display
                delta_dollars = delta_cents / 100.0
                ynab_dollars = ynab_cents / 100.0
                delta_percent = (delta_cents / ynab_cents) * 100 if ynab_cents > 0 else 0
                # Use appropriate precision for small percentages
                if delta_percent < 0.1:
                    return f"${delta_dollars:.2f} ({delta_percent:.2f}%)"
                else:
                    return f"${delta_dollars:.2f} ({delta_percent:.1f}%)"

        except Exception as e:
            return f"Amount calculation error: {str(e)}"

    def _format_amount(self, amount_milliunits: int) -> str:
        """Format amount for display."""
        amount_cents = milliunits_to_cents(amount_milliunits)
        amount_str = cents_to_dollars_str(amount_cents)
        sign = "-" if amount_milliunits < 0 else ""
        return f"{sign}${amount_str}"

    def _approve_mutation(self, mutation: Dict[str, Any], notes: str = ""):
        """
        Approve a mutation.

        Args:
            mutation: Mutation to approve
            notes: Optional approval notes
        """
        self.approved.append({
            'transaction_id': mutation['transaction_id'],
            'approved': True,
            'notes': notes or "Approved by user"
        })
        self.total_reviewed += 1
        print("✓ Approved")

    def _reject_mutation(self, mutation: Dict[str, Any], reason: str = ""):
        """
        Reject a mutation.

        Args:
            mutation: Mutation to reject
            reason: Rejection reason
        """
        self.rejected.append({
            'transaction_id': mutation['transaction_id'],
            'approved': False,
            'reason': reason or "Rejected by user"
        })
        self.total_reviewed += 1
        print("✗ Rejected")

    def _get_approved_mutations(self) -> List[Dict[str, Any]]:
        """Get list of approved transaction IDs."""
        return [entry['transaction_id'] for entry in self.approved if entry['approved']]

    def save_approval_file(
        self,
        mutations_data: Dict[str, Any],
        approved_ids: List[str],
        output_path: str,
        source_mutations_path: str
    ):
        """
        Save approval results to YAML file.

        Args:
            mutations_data: Original mutations data
            approved_ids: List of approved transaction IDs
            output_path: Path to output approval file
            source_mutations_path: Path to source mutations file
        """
        # Filter mutations to only approved ones
        all_mutations = mutations_data.get('mutations', [])
        approved_mutations = [
            mutation for mutation in all_mutations
            if mutation['transaction_id'] in approved_ids
        ]

        # Calculate stats
        approved_count = len(self.approved)
        rejected_count = len(self.rejected)
        approved_amount = sum(
            mutation['original']['amount']
            for mutation in approved_mutations
        )

        approval_data = {
            'metadata': {
                'reviewed_at': datetime.now().isoformat() + 'Z',
                'reviewer': 'user',
                'source_mutations': source_mutations_path
            },
            'approved': self.approved,
            'rejected': self.rejected,
            'summary': {
                'total_reviewed': self.total_reviewed,
                'approved': approved_count,
                'rejected': rejected_count,
                'approved_amount': approved_amount
            },
            'mutations': approved_mutations
        }

        # Create output directory if needed
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(approval_data, f, default_flow_style=False, indent=2, sort_keys=False)

        print(f"\nReview Summary:")
        print(f"  Reviewed: {self.total_reviewed}")
        print(f"  Approved: {approved_count}")
        print(f"  Rejected: {rejected_count}")
        print(f"  Approved amount: {self._format_amount(approved_amount)}")
        print(f"\nSaved to: {output_path}")


def main():
    """Command-line interface for mutation review."""
    parser = argparse.ArgumentParser(description='Review YNAB transaction mutations')
    parser.add_argument('--mutations', required=True, help='Path to mutations YAML file')
    parser.add_argument('--output', required=True, help='Output approved mutations YAML file')
    parser.add_argument('--interactive', action='store_true', help='Interactive review mode')
    parser.add_argument('--auto-approve-confidence', type=float, default=1.0,
                        help='Auto-approve mutations with confidence >= this value')

    args = parser.parse_args()

    # Validate input file
    if not Path(args.mutations).exists():
        print(f"Error: File not found: {args.mutations}")
        return 1

    try:
        reviewer = MutationReviewer()

        # Load mutations
        print("Loading mutations...")
        mutations_data = reviewer.load_mutations(args.mutations)
        mutation_count = len(mutations_data.get('mutations', []))
        print(f"Loaded {mutation_count} mutations")

        # Review mutations
        if args.interactive:
            approved_ids = reviewer.review_mutations_interactive(mutations_data)
        else:
            approved_ids = reviewer.review_mutations_batch(mutations_data, args.auto_approve_confidence)

        # Save results
        reviewer.save_approval_file(mutations_data, approved_ids, args.output, args.mutations)

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())