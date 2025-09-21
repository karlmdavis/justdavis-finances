#!/usr/bin/env python3
"""
Mutation Generator for YNAB Transaction Updater.

Reads Amazon and Apple transaction matching results and generates YAML mutation plans
for review and application. Implements the Phase 1 logic from the specification.

Usage:
    python generate_mutations.py \\
        --matches-file results/2025-09-01_amazon_matching_results.json \\
        --ynab-cache ynab-data/transactions.json \\
        --confidence-threshold 0.8 \\
        --output mutations.yaml
"""

import json
import yaml
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from .split_calculator import (
        calculate_amazon_splits, calculate_apple_splits, should_split_transaction,
        SplitCalculationError, validate_split_calculation
    )
    from .currency_utils import milliunits_to_cents, cents_to_dollars_str
except ImportError:
    from split_calculator import (
        calculate_amazon_splits, calculate_apple_splits, should_split_transaction,
        SplitCalculationError, validate_split_calculation
    )
    from currency_utils import milliunits_to_cents, cents_to_dollars_str


class MutationGenerator:
    """Generates YAML mutation plans from transaction matching results."""

    def __init__(self, confidence_threshold: float = 0.8):
        """
        Initialize mutation generator.

        Args:
            confidence_threshold: Minimum confidence score for processing matches
        """
        self.confidence_threshold = confidence_threshold
        self.mutations = []
        self.skipped_count = 0
        self.error_count = 0

    def load_ynab_transactions(self, ynab_cache_path: str, unapproved_only: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Load YNAB transactions from cache file with optional filtering.

        Args:
            ynab_cache_path: Path to cached transactions.json
            unapproved_only: If True, only load transactions with approved=false

        Returns:
            Dictionary mapping transaction ID to transaction data
        """
        try:
            with open(ynab_cache_path, 'r') as f:
                transactions = json.load(f)

            total_count = len(transactions)

            if unapproved_only:
                # Filter to only unapproved transactions (approved=false)
                # Default to approved=true if field is missing (conservative approach)
                transactions = [tx for tx in transactions if not tx.get('approved', True)]
                print(f"Filtered to {len(transactions)} unapproved transactions from {total_count} total")
            else:
                print(f"Loaded {total_count} transactions (no filtering)")

            return {tx['id']: tx for tx in transactions}
        except Exception as e:
            raise RuntimeError(f"Failed to load YNAB cache: {e}")

    def load_match_results(self, matches_file_path: str) -> Dict[str, Any]:
        """
        Load transaction matching results from JSON file.

        Args:
            matches_file_path: Path to matching results JSON

        Returns:
            Matching results data structure
        """
        try:
            with open(matches_file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load match results: {e}")

    def generate_mutations(
        self,
        matches_data: Dict[str, Any],
        ynab_transactions: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate mutations from matching results.

        Args:
            matches_data: Loaded matching results
            ynab_transactions: Dictionary of YNAB transactions by ID

        Returns:
            List of mutation dictionaries
        """
        mutations = []
        results = matches_data.get('results', [])

        for result in results:
            try:
                mutation = self._process_match_result(result, ynab_transactions)
                if mutation:
                    mutations.append(mutation)
                else:
                    self.skipped_count += 1
            except Exception as e:
                print(f"Error processing match result: {e}")
                self.error_count += 1

        return mutations

    def _process_match_result(
        self,
        result: Dict[str, Any],
        ynab_transactions: Dict[str, Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single match result into a mutation.

        Args:
            result: Single match result from Amazon/Apple matcher
            ynab_transactions: Dictionary of YNAB transactions by ID

        Returns:
            Mutation dictionary or None if should be skipped
        """
        ynab_tx = result.get('ynab_transaction', {})
        transaction_id = ynab_tx.get('id')

        if not transaction_id:
            print("Warning: Match result missing transaction ID")
            return None

        # Get full transaction data from cache
        full_transaction = ynab_transactions.get(transaction_id)
        if not full_transaction:
            print(f"Warning: Transaction {transaction_id} not found in YNAB cache")
            return None

        # Determine source and confidence
        source, confidence, matched_data = self._extract_match_info(result)
        if not source:
            print(f"Warning: Could not determine source for transaction {transaction_id}")
            return None

        # Check confidence threshold
        if confidence < self.confidence_threshold:
            print(f"Skipping transaction {transaction_id}: confidence {confidence} below threshold {self.confidence_threshold}")
            return None

        # Check if already split
        if full_transaction.get('subtransactions'):
            print(f"Skipping transaction {transaction_id}: already has subtransactions")
            return None

        # Generate mutation based on source
        if source == 'amazon':
            return self._generate_amazon_mutation(full_transaction, matched_data, confidence)
        elif source == 'apple':
            return self._generate_apple_mutation(full_transaction, matched_data, confidence)
        else:
            print(f"Warning: Unknown source '{source}' for transaction {transaction_id}")
            return None

    def _extract_match_info(self, result: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[Dict[str, Any]]]:
        """
        Extract source, confidence, and matched data from result.

        Args:
            result: Match result dictionary

        Returns:
            Tuple of (source, confidence, matched_data)
        """
        # Amazon format
        if 'matches' in result and result['matches']:
            best_match = max(result['matches'], key=lambda m: m.get('confidence', 0))
            return 'amazon', best_match.get('confidence', 0), best_match

        # Apple format
        if 'matched' in result and result['matched']:
            confidence = result.get('match_confidence', 0)
            return 'apple', confidence, result

        return None, 0.0, None

    def _generate_amazon_mutation(
        self,
        transaction: Dict[str, Any],
        match_data: Dict[str, Any],
        confidence: float
    ) -> Optional[Dict[str, Any]]:
        """
        Generate mutation for Amazon transaction.

        Args:
            transaction: Full YNAB transaction data
            match_data: Amazon match data
            confidence: Match confidence score

        Returns:
            Mutation dictionary or None if error
        """
        amazon_orders = match_data.get('amazon_orders', [])
        if not amazon_orders:
            return None

        # Extract all items from all matched orders
        all_items = []
        for order in amazon_orders:
            items = order.get('items', [])
            all_items.extend(items)

        if not all_items:
            return None

        try:
            # Calculate splits
            transaction_amount = transaction['amount']
            splits = calculate_amazon_splits(
                transaction_amount,
                all_items,
                transaction.get('category_id')
            )

            # Determine action type
            action = 'split' if should_split_transaction(all_items) else 'update_memo'

            mutation = {
                'transaction_id': transaction['id'],
                'action': action,
                'confidence': confidence,
                'source': 'amazon',
                'account': transaction['account_name'],
                'date': transaction['date'],
                'original': {
                    'amount': transaction['amount'],
                    'memo': transaction.get('memo') or '',
                    'payee': transaction.get('payee_name') or ''
                },
                'matched_order': {
                    'order_id': amazon_orders[0].get('order_id', ''),
                    'order_date': amazon_orders[0].get('order_date', ''),
                    'account': match_data.get('account', ''),
                    'total': amazon_orders[0].get('total', 0)
                },
                'item_breakdown': all_items,  # Include original item data for review
                'match_method': match_data.get('match_method')  # Include match method for display
            }

            if action == 'split':
                mutation['splits'] = [
                    {
                        'amount': split['amount'],
                        'memo': split['memo']
                    }
                    for split in splits
                ]
            else:
                mutation['new_memo'] = splits[0]['memo']

            return mutation

        except SplitCalculationError as e:
            print(f"Split calculation error for transaction {transaction['id']}: {e}")
            return None

    def _generate_apple_mutation(
        self,
        transaction: Dict[str, Any],
        match_data: Dict[str, Any],
        confidence: float
    ) -> Optional[Dict[str, Any]]:
        """
        Generate mutation for Apple transaction.

        Args:
            transaction: Full YNAB transaction data
            match_data: Apple match data
            confidence: Match confidence score

        Returns:
            Mutation dictionary or None if error
        """
        apple_receipts = match_data.get('apple_receipts', [])
        if not apple_receipts:
            return None

        receipt = apple_receipts[0]  # Apple is 1:1 transaction model
        items = receipt.get('items', [])
        if not items:
            return None

        try:
            # Calculate splits
            transaction_amount = transaction['amount']
            # Handle None values in Apple receipts (subtotal/tax often null)
            subtotal = receipt.get('subtotal') or 0.0
            tax = receipt.get('tax') or 0.0

            splits = calculate_apple_splits(
                transaction_amount,
                items,
                subtotal,
                tax,
                transaction.get('category_id')
            )

            # Determine action type
            action = 'split' if should_split_transaction(items) else 'update_memo'

            mutation = {
                'transaction_id': transaction['id'],
                'action': action,
                'confidence': confidence,
                'source': 'apple',
                'account': transaction['account_name'],
                'date': transaction['date'],
                'original': {
                    'amount': transaction['amount'],
                    'memo': transaction.get('memo') or '',
                    'payee': transaction.get('payee_name') or ''
                },
                'matched_receipt': {
                    'order_id': receipt.get('order_id', ''),
                    'receipt_date': receipt.get('date', ''),
                    'apple_id': receipt.get('apple_id', ''),
                    'subtotal': subtotal,
                    'tax': tax
                },
                'match_method': match_data.get('match_strategy')  # Apple uses match_strategy field
            }

            if action == 'split':
                mutation['splits'] = [
                    {
                        'amount': split['amount'],
                        'memo': split['memo']
                    }
                    for split in splits
                ]
            else:
                mutation['new_memo'] = splits[0]['memo']

            return mutation

        except SplitCalculationError as e:
            print(f"Split calculation error for transaction {transaction['id']}: {e}")
            return None

    def save_mutations_yaml(self, mutations: List[Dict[str, Any]], output_path: str, source_file: str):
        """
        Save mutations to YAML file with metadata.

        Args:
            mutations: List of mutation dictionaries
            output_path: Path to output YAML file
            source_file: Path to source matching results file
        """
        total_amount = sum(mutation['original']['amount'] for mutation in mutations)

        yaml_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat() + 'Z',
                'source_file': source_file,
                'total_mutations': len(mutations),
                'total_amount': total_amount,
                'confidence_threshold': self.confidence_threshold,
                'skipped_count': self.skipped_count,
                'error_count': self.error_count
            },
            'mutations': mutations
        }

        # Create output directory if needed
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, indent=2, sort_keys=False)

        print(f"Generated {len(mutations)} mutations")
        print(f"Skipped: {self.skipped_count}, Errors: {self.error_count}")
        print(f"Saved to: {output_path}")


def main():
    """Command-line interface for mutation generation."""
    parser = argparse.ArgumentParser(description='Generate YNAB transaction mutations from matching results')
    parser.add_argument('--matches-file', required=True, help='Path to matching results JSON file')
    parser.add_argument('--ynab-cache', required=True, help='Path to cached YNAB transactions.json')
    parser.add_argument('--confidence-threshold', type=float, default=0.8, help='Minimum confidence threshold')
    parser.add_argument('--unapproved-only', action='store_true', help='Only process unapproved YNAB transactions (approved=false)')
    parser.add_argument('--output', required=True, help='Output YAML file path')

    args = parser.parse_args()

    # Validate input files
    for file_path in [args.matches_file, args.ynab_cache]:
        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}")
            return 1

    try:
        generator = MutationGenerator(args.confidence_threshold)

        # Load data
        print("Loading YNAB transactions...")
        ynab_transactions = generator.load_ynab_transactions(args.ynab_cache, args.unapproved_only)

        print("Loading match results...")
        matches_data = generator.load_match_results(args.matches_file)
        result_count = len(matches_data.get('results', []))
        print(f"Loaded {result_count} match results")

        # Generate mutations
        print("Generating mutations...")
        mutations = generator.generate_mutations(matches_data, ynab_transactions)

        # Save output
        generator.save_mutations_yaml(mutations, args.output, args.matches_file)

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())