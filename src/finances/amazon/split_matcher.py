#!/usr/bin/env python3
"""
Split Payment Matcher for Amazon Orders

Handles cases where Amazon splits a single order into multiple credit card transactions.
Tracks which items have been matched to prevent double-counting.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import pandas as pd


class SplitPaymentMatcher:
    """
    Manages split payment matching across multiple YNAB transactions.
    Maintains state about which order items have already been matched.

    By default uses in-memory storage. Optionally can persist to file cache.
    """

    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize the matcher with optional persistent cache.

        Args:
            cache_file: Optional path to cache file for persistent matching state.
                       If None (default), uses in-memory storage only.
        """
        self.cache_file = cache_file
        self.matched_items = defaultdict(set)  # {order_id: set of matched item indices}
        self.transaction_matches = {}  # {transaction_id: match_details}

        # Only load cache if file is specified AND exists
        if self.cache_file and os.path.exists(self.cache_file):
            self.load_cache()

    def load_cache(self):
        """Load previous matching state from cache file."""
        if not self.cache_file:
            return

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                # Convert lists back to sets
                self.matched_items = {
                    order_id: set(items)
                    for order_id, items in data.get('matched_items', {}).items()
                }
                self.transaction_matches = data.get('transaction_matches', {})
        except Exception as e:
            print(f"Warning: Could not load cache: {e}")

    def save_cache(self):
        """Save current matching state to cache file (only if cache file specified)."""
        if not self.cache_file:
            return  # In-memory mode, no saving needed

        try:
            data = {
                'matched_items': {
                    order_id: list(items)  # Convert sets to lists for JSON
                    for order_id, items in self.matched_items.items()
                },
                'transaction_matches': self.transaction_matches,
                'timestamp': datetime.now().isoformat()
            }

            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    def get_unmatched_items(self, order_id: str, order_data: Dict) -> Tuple[List[Dict], int]:
        """
        Get items from an order that haven't been matched yet.

        Args:
            order_id: The order ID
            order_data: Order data with items list

        Returns:
            Tuple of (unmatched_items, total_amount_in_cents)
        """
        matched_indices = self.matched_items.get(order_id, set())
        unmatched_items = []
        total_amount = 0

        for i, item in enumerate(order_data.get('items', [])):
            if i not in matched_indices:
                unmatched_items.append({
                    'index': i,
                    **item
                })
                total_amount += item.get('amount', 0)

        return unmatched_items, total_amount

    def find_item_combinations(self, items: List[Dict], target_amount: int, tolerance: int = 0) -> List[List[int]]:
        """
        Find combinations of items that sum to approximately the target amount.

        Args:
            items: List of items with 'amount' and 'index' fields
            target_amount: Target amount in cents
            tolerance: Acceptable difference in cents (default 0 = exact match)

        Returns:
            List of item index combinations that match the target
        """
        # Sort items by amount for efficiency
        sorted_items = sorted(items, key=lambda x: x['amount'], reverse=True)

        results = []

        # Try single items first (most common case)
        for item in sorted_items:
            diff = abs(item['amount'] - target_amount)
            if diff <= tolerance:
                results.append([item['index']])

        # If no single item matches, try combinations
        if not results and len(items) <= 20:  # Limit complexity for large orders
            # Use dynamic programming for subset sum problem
            results.extend(self._find_subset_sum(sorted_items, target_amount, tolerance))

        return results

    def _find_subset_sum(self, items: List[Dict], target: int, tolerance: int) -> List[List[int]]:
        """
        Dynamic programming solution for subset sum with tolerance.

        Args:
            items: Sorted list of items
            target: Target amount
            tolerance: Acceptable tolerance

        Returns:
            List of item index combinations
        """
        n = len(items)
        if n == 0:
            return []

        # Create DP table
        # dp[i][j] = list of combinations using first i items that sum to approximately j
        max_sum = sum(item['amount'] for item in items)
        if max_sum < target - tolerance:
            return []  # Can't reach target even with all items

        results = []

        # Use recursive backtracking with memoization for efficiency
        def backtrack(index: int, current_sum: int, current_items: List[int]):
            # Check if we've found a valid combination
            if abs(current_sum - target) <= tolerance and current_items:
                results.append(current_items[:])
                return

            # Pruning: stop if we've exceeded target + tolerance
            if current_sum > target + tolerance or index >= n:
                return

            # Try including the current item
            item = items[index]
            backtrack(index + 1, current_sum + item['amount'], current_items + [item['index']])

            # Try excluding the current item
            backtrack(index + 1, current_sum, current_items)

        backtrack(0, 0, [])

        # Remove duplicates and return
        unique_results = []
        seen = set()
        for combo in results:
            combo_tuple = tuple(sorted(combo))
            if combo_tuple not in seen:
                seen.add(combo_tuple)
                unique_results.append(combo)

        return unique_results

    def match_split_payment(self, ynab_tx: Dict, order_data: Dict, account_name: str) -> Optional[Dict]:
        """
        Attempt to match a YNAB transaction to part of an order.

        Args:
            ynab_tx: YNAB transaction data
            order_data: Complete order data with all items
            account_name: Amazon account name

        Returns:
            Match result or None if no match found
        """
        order_id = order_data['order_id']
        ynab_amount = abs(ynab_tx['amount'])  # Amount in cents

        # Get unmatched items from the order
        unmatched_items, unmatched_total = self.get_unmatched_items(order_id, order_data)

        if not unmatched_items:
            return None  # All items already matched

        # Find combinations of items that match the transaction amount
        item_combinations = self.find_item_combinations(unmatched_items, ynab_amount)

        if not item_combinations:
            # No exact match - try matching if transaction amount equals remaining total
            if abs(unmatched_total - ynab_amount) <= 0:  # Exact match only
                # This transaction might cover all remaining items
                item_combination = [item['index'] for item in unmatched_items]
                item_combinations = [item_combination]
            else:
                return None

        # Use the first valid combination (could be enhanced with scoring)
        best_combination = item_combinations[0]

        # Create the match result
        matched_items_data = []
        matched_total = 0

        for item_index in best_combination:
            # Find the item data
            for item in unmatched_items:
                if item['index'] == item_index:
                    matched_items_data.append({
                        k: v for k, v in item.items() if k != 'index'
                    })
                    matched_total += item['amount']
                    break

        # Calculate confidence based on amount match and date alignment
        ynab_date = datetime.strptime(ynab_tx['date'], '%Y-%m-%d').date()

        # Use ship dates for date matching
        ship_dates = order_data.get('ship_dates', [])
        if ship_dates:
            # Find closest ship date
            date_diffs = []
            for ship_date in ship_dates:
                # Skip NaT (Not a Time) values
                if pd.isna(ship_date):
                    continue

                if hasattr(ship_date, 'date'):
                    ship_date = ship_date.date()
                elif isinstance(ship_date, str):
                    try:
                        ship_date = datetime.strptime(ship_date, '%Y-%m-%d').date()
                    except:
                        continue

                try:
                    date_diffs.append(abs((ynab_date - ship_date).days))
                except:
                    continue

            min_date_diff = min(date_diffs) if date_diffs else 7
        else:
            min_date_diff = 3  # Default if no ship dates

        # Calculate confidence
        amount_diff = abs(matched_total - ynab_amount)
        confidence = 1.0

        # Amount accuracy penalty
        if amount_diff == 0:
            confidence *= 1.0
        elif amount_diff <= 100:  # Within $1.00
            confidence *= 0.95
        else:
            # Use integer arithmetic for penalty calculation
            penalty_percent = min(30, (amount_diff * 100) // ynab_amount)  # Max 30% penalty
            # Convert penalty to basis points to avoid floating point
            penalty_basis_points = penalty_percent * 100  # 30% = 3000 basis points
            confidence_basis_points = max(7000, 10000 - penalty_basis_points)  # 70% minimum
            confidence *= confidence_basis_points / 10000  # Convert back for compatibility

        # Date alignment penalty
        if min_date_diff == 0:
            confidence *= 1.0
        elif min_date_diff <= 2:
            confidence *= 0.95
        elif min_date_diff <= 5:
            confidence *= 0.85
        else:
            confidence *= 0.75

        # Split payment indicator - slightly reduce confidence for splits
        confidence *= 0.95

        match_result = {
            'account': account_name,
            'amazon_orders': [{
                'order_id': order_id,
                'items': matched_items_data,
                'total': matched_total,
                'ship_dates': order_data.get('ship_dates', []),
                'order_date': order_data.get('order_date'),
                'is_partial': True,
                'matched_item_indices': best_combination
            }],
            'match_method': 'split_payment',
            'confidence': round(confidence, 2),
            'unmatched_amount': ynab_amount - matched_total
        }

        return match_result

    def record_match(self, transaction_id: str, order_id: str, item_indices: List[int]):
        """
        Record that certain items from an order have been matched.

        Args:
            transaction_id: YNAB transaction ID
            order_id: Amazon order ID
            item_indices: List of item indices that were matched
        """
        # Update matched items
        self.matched_items[order_id].update(item_indices)

        # Record transaction match
        self.transaction_matches[transaction_id] = {
            'order_id': order_id,
            'item_indices': item_indices,
            'timestamp': datetime.now().isoformat()
        }

        # Save to cache if configured
        self.save_cache()