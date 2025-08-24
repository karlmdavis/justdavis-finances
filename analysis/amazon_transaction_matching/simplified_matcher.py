#!/usr/bin/env python3
"""
Simplified Amazon Transaction Matching Engine

Implements the recommended 3-strategy architecture:
1. Complete Match - handles exact order/shipment matches
2. Split Payment - handles partial orders (keep existing logic)  
3. Fuzzy Match - handles approximate matches

Replaces the complex 5-strategy system with cleaner, maintainable code.
"""

import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple

from order_grouper import group_orders, GroupingLevel, get_order_candidates
from match_scorer import MatchScorer, MatchType, ConfidenceThresholds
from split_payment_matcher import SplitPaymentMatcher


def is_amazon_transaction(payee_name: str) -> bool:
    """Check if payee name matches Amazon patterns."""
    if not payee_name:
        return False
    
    patterns = ["amazon", "amzn"]
    payee_lower = payee_name.lower()
    return any(pattern in payee_lower for pattern in patterns)


def milliunits_to_cents(milliunits: int) -> int:
    """Convert YNAB milliunits to cents (1000 milliunits = 100 cents)"""
    return abs(milliunits // 10)


class CompleteMatchStrategy:
    """Strategy 1: Complete Match - handles exact order/shipment matches"""
    
    @staticmethod
    def find_matches(ynab_tx: Dict[str, Any], 
                    retail_orders: pd.DataFrame, 
                    account_name: str) -> List[Dict[str, Any]]:
        """
        Find complete order or shipment matches.
        
        This consolidates the logic from:
        - exact_amount_priority
        - exact_single_order  
        - exact_multi_day_order
        - exact_shipment_group
        """
        matches = []
        ynab_amount = milliunits_to_cents(ynab_tx['amount'])
        ynab_date = datetime.strptime(ynab_tx['date'], '%Y-%m-%d').date()
        
        # Filter orders within reasonable date window (±7 days)
        date_window_start = ynab_date - timedelta(days=7)
        date_window_end = ynab_date + timedelta(days=7)
        
        # Create mask that handles NaT values
        ship_date_mask = (
            (retail_orders['Ship Date'].dt.date >= date_window_start) &
            (retail_orders['Ship Date'].dt.date <= date_window_end)
        ) | retail_orders['Ship Date'].isna()
        
        relevant_orders = retail_orders[ship_date_mask].copy()
        
        if relevant_orders.empty:
            return matches
        
        # Get candidates from all grouping levels
        candidates = get_order_candidates(relevant_orders, ynab_amount, ynab_date, tolerance=100)
        
        # Process complete order candidates
        for order in candidates['complete_orders']:
            confidence = MatchScorer.calculate_confidence(
                ynab_amount=ynab_amount,
                amazon_total=order['total'],
                ynab_date=ynab_date,
                amazon_ship_dates=order['ship_dates'],
                match_type=MatchType.COMPLETE_ORDER,
                multi_day=len(order['ship_dates']) > 1
            )
            
            if ConfidenceThresholds.meets_threshold(confidence, MatchType.COMPLETE_ORDER):
                # Determine method name based on grouping level and shipping pattern
                if len(order['ship_dates']) == 1:
                    method = 'complete_single_order'
                else:
                    method = 'complete_multi_day_order'
                
                match = MatchScorer.create_match_result(
                    ynab_tx=ynab_tx,
                    amazon_orders=[{
                        'order_id': order['order_id'],
                        'items': order['items'],
                        'total': order['total'],
                        'ship_dates': order['ship_dates'],
                        'order_date': order['order_date']
                    }],
                    match_method=method,
                    confidence=confidence,
                    account=account_name
                )
                matches.append(match)
        
        # Process shipment candidates
        for shipment in candidates['shipments']:
            confidence = MatchScorer.calculate_confidence(
                ynab_amount=ynab_amount,
                amazon_total=shipment['total'],
                ynab_date=ynab_date,
                amazon_ship_dates=[shipment['ship_date']],
                match_type=MatchType.COMPLETE_ORDER
            )
            
            if ConfidenceThresholds.meets_threshold(confidence, MatchType.COMPLETE_ORDER):
                match = MatchScorer.create_match_result(
                    ynab_tx=ynab_tx,
                    amazon_orders=[{
                        'order_id': shipment['order_id'],
                        'items': shipment['items'],
                        'total': shipment['total'],
                        'ship_dates': [shipment['ship_date']],
                        'order_date': shipment['order_date']
                    }],
                    match_method='complete_shipment',
                    confidence=confidence,
                    account=account_name
                )
                matches.append(match)
        
        # Process daily shipment candidates  
        for daily in candidates['daily_shipments']:
            confidence = MatchScorer.calculate_confidence(
                ynab_amount=ynab_amount,
                amazon_total=daily['total'],
                ynab_date=ynab_date,
                amazon_ship_dates=[daily['ship_date']],
                match_type=MatchType.COMPLETE_ORDER
            )
            
            if ConfidenceThresholds.meets_threshold(confidence, MatchType.COMPLETE_ORDER):
                match = MatchScorer.create_match_result(
                    ynab_tx=ynab_tx,
                    amazon_orders=[{
                        'order_id': daily['order_id'],
                        'items': daily['items'],
                        'total': daily['total'],
                        'ship_dates': daily['ship_times'],
                        'order_date': daily['order_date']
                    }],
                    match_method='complete_daily_shipment',
                    confidence=confidence,
                    account=account_name
                )
                matches.append(match)
        
        return matches


class FuzzyMatchStrategy:
    """Strategy 3: Fuzzy Match - handles approximate matches with tolerance"""
    
    @staticmethod
    def find_matches(ynab_tx: Dict[str, Any],
                    retail_orders: pd.DataFrame,
                    account_name: str) -> List[Dict[str, Any]]:
        """
        Find approximate matches with flexible tolerances.
        
        This consolidates the logic from:
        - date_window_match
        - exact_amount_date_window (when not exact)
        """
        matches = []
        ynab_amount = milliunits_to_cents(ynab_tx['amount'])
        ynab_date = datetime.strptime(ynab_tx['date'], '%Y-%m-%d').date()
        
        # Use wider date window for fuzzy matching
        date_window_start = ynab_date - timedelta(days=10)
        date_window_end = ynab_date + timedelta(days=10)
        
        # Create mask that handles NaT values
        ship_date_mask = (
            (retail_orders['Ship Date'].dt.date >= date_window_start) &
            (retail_orders['Ship Date'].dt.date <= date_window_end)
        ) | retail_orders['Ship Date'].isna()
        
        relevant_orders = retail_orders[ship_date_mask].copy()
        
        if relevant_orders.empty:
            return matches
        
        # Use more generous tolerance for fuzzy matching
        fuzzy_tolerance = max(500, int(ynab_amount * 0.15))  # At least $5 or 15% of amount
        
        # Get candidates with fuzzy tolerance
        candidates = get_order_candidates(relevant_orders, ynab_amount, ynab_date, tolerance=fuzzy_tolerance)
        
        # Process all candidate types with fuzzy scoring
        all_candidates = []
        all_candidates.extend(candidates['complete_orders'])
        all_candidates.extend(candidates['shipments'])  
        all_candidates.extend(candidates['daily_shipments'])
        
        for candidate in all_candidates:
            ship_dates = candidate.get('ship_dates', [candidate.get('ship_date')])
            if candidate.get('ship_times'):  # Daily shipments
                ship_dates = candidate['ship_times']
            
            confidence = MatchScorer.calculate_confidence(
                ynab_amount=ynab_amount,
                amazon_total=candidate['total'],
                ynab_date=ynab_date,
                amazon_ship_dates=ship_dates,
                match_type=MatchType.FUZZY_MATCH
            )
            
            if ConfidenceThresholds.meets_threshold(confidence, MatchType.FUZZY_MATCH):
                # Determine if this is a multi-order combination or single order
                if candidate.get('grouping_level') == 'order':
                    method = 'fuzzy_order_match'
                else:
                    method = 'fuzzy_shipment_match'
                
                match = MatchScorer.create_match_result(
                    ynab_tx=ynab_tx,
                    amazon_orders=[{
                        'order_id': candidate['order_id'],
                        'items': candidate['items'],
                        'total': candidate['total'],
                        'ship_dates': ship_dates,
                        'order_date': candidate['order_date']
                    }],
                    match_method=method,
                    confidence=confidence,
                    account=account_name,
                    unmatched_amount=abs(ynab_amount - candidate['total'])
                )
                matches.append(match)
        
        return matches


class SimplifiedMatcher:
    """Main simplified matching engine"""
    
    def __init__(self, split_matcher: Optional[SplitPaymentMatcher] = None):
        """
        Initialize simplified matcher.
        
        Args:
            split_matcher: Optional split payment matcher instance
        """
        self.split_matcher = split_matcher
        self.complete_strategy = CompleteMatchStrategy()
        self.fuzzy_strategy = FuzzyMatchStrategy()
    
    def find_matches(self, ynab_tx: Dict[str, Any],
                    accounts_data: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]) -> Dict[str, Any]:
        """
        Find matches using simplified 3-strategy architecture.
        
        Args:
            ynab_tx: YNAB transaction dictionary
            accounts_data: Dictionary of {account_name: (retail_df, digital_df)}
            
        Returns:
            Match result dictionary with all matches from all accounts
        """
        # Initialize result structure
        ynab_amount = milliunits_to_cents(ynab_tx['amount'])
        result = {
            'ynab_transaction': {
                'id': ynab_tx['id'],
                'date': ynab_tx['date'], 
                'amount': -ynab_amount,  # Keep negative for expenses
                'payee_name': ynab_tx['payee_name'],
                'account_name': ynab_tx['account_name']
            },
            'matches': [],
            'best_match': None
        }
        
        # Check if this is an Amazon transaction
        if not is_amazon_transaction(ynab_tx['payee_name']):
            return result
        
        # Collect all matches from all strategies and accounts
        all_matches = []
        
        # Search each account
        for account_name, (retail_df, digital_df) in accounts_data.items():
            if retail_df.empty:
                continue
            
            # Strategy 1: Complete Match
            complete_matches = self.complete_strategy.find_matches(ynab_tx, retail_df, account_name)
            all_matches.extend(complete_matches)
            
            # Strategy 2: Split Payment (if enabled)
            if self.split_matcher:
                split_matches = self._find_split_payment_matches(ynab_tx, retail_df, account_name)
                all_matches.extend(split_matches)
            
            # Strategy 3: Fuzzy Match (only if no high-confidence matches found)
            if not any(match['confidence'] >= 0.90 for match in all_matches):
                fuzzy_matches = self.fuzzy_strategy.find_matches(ynab_tx, retail_df, account_name)
                all_matches.extend(fuzzy_matches)
        
        # Sort matches by confidence (descending)
        all_matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Add all matches to result
        result['matches'] = all_matches
        
        # Identify best match
        if all_matches:
            best = all_matches[0]
            result['best_match'] = {
                'account': best['account'],
                'confidence': best['confidence']
            }
        
        return result
    
    def _find_split_payment_matches(self, ynab_tx: Dict[str, Any],
                                   retail_df: pd.DataFrame,
                                   account_name: str) -> List[Dict[str, Any]]:
        """Find split payment matches using existing split payment matcher"""
        if not self.split_matcher:
            return []
        
        matches = []
        ynab_amount = milliunits_to_cents(ynab_tx['amount'])
        
        # Group orders by ID to get complete order data
        orders_by_id = group_orders(retail_df, GroupingLevel.ORDER)
        
        # Try each order as a potential split payment source
        for order_id, order_data in orders_by_id.items():
            # Check if this order could be a split payment candidate
            unmatched_items, unmatched_total = self.split_matcher.get_unmatched_items(order_id, order_data)
            
            if not unmatched_items:
                continue  # All items already matched
            
            # Only consider if transaction could be part of this order
            if ynab_amount > order_data['total'] * 1.1:  # Transaction can't be more than 110% of order
                continue
            
            # Try to match
            match = self.split_matcher.match_split_payment(
                {'amount': -ynab_amount, 'date': ynab_tx['date']},
                order_data,
                account_name
            )
            
            if match:
                matches.append(match)
        
        return matches
    
    def record_split_payment_match(self, transaction_id: str, match: Dict[str, Any]):
        """Record a split payment match in the split matcher"""
        if self.split_matcher and match.get('match_method') == 'split_payment':
            order = match['amazon_orders'][0]
            order_id = order['order_id']
            item_indices = order.get('matched_item_indices', [])
            self.split_matcher.record_match(transaction_id, order_id, item_indices)