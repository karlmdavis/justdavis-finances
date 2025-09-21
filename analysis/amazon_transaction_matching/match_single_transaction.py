#!/usr/bin/env python3
"""
Simplified Amazon Transaction Matching Engine

Implements the recommended 2-strategy architecture:
1. Complete Match - handles exact order/shipment matches (penny-perfect only)
2. Split Payment - handles partial orders with exact item matches

Replaces the complex 5-strategy system with cleaner, maintainable code.
All matches must be penny-perfect - no tolerance for amount differences.
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


def cents_to_dollars_str(cents: int) -> str:
    """Convert 953 cents to '9.53' string"""
    return f"{cents / 100:.2f}"


def convert_match_result_for_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert match result with cent amounts to JSON-safe format with string amounts"""
    import copy
    json_result = copy.deepcopy(result)
    
    # Convert YNAB transaction amount
    if 'ynab_transaction' in json_result and 'amount' in json_result['ynab_transaction']:
        amount_cents = json_result['ynab_transaction']['amount']
        json_result['ynab_transaction']['amount'] = cents_to_dollars_str(abs(amount_cents))
    
    # Convert match amounts
    if 'matches' in json_result:
        for match in json_result['matches']:
            if 'total_match_amount' in match:
                match['total_match_amount'] = cents_to_dollars_str(match['total_match_amount'])
            if 'unmatched_amount' in match:
                match['unmatched_amount'] = cents_to_dollars_str(match['unmatched_amount'])
            if 'orders' in match:
                for order in match['orders']:
                    if 'total' in order:
                        order['total'] = cents_to_dollars_str(order['total'])
                    if 'items' in order:
                        for item in order['items']:
                            if 'amount' in item:
                                item['amount'] = cents_to_dollars_str(item['amount'])
                            if 'unit_price' in item:
                                item['unit_price'] = cents_to_dollars_str(item['unit_price'])
    
    # Convert best_match amounts
    if 'best_match' in json_result and json_result['best_match']:
        best_match = json_result['best_match']
        if 'total_match_amount' in best_match:
            best_match['total_match_amount'] = cents_to_dollars_str(best_match['total_match_amount'])
        if 'unmatched_amount' in best_match:
            best_match['unmatched_amount'] = cents_to_dollars_str(best_match['unmatched_amount'])
    
    return json_result


def load_all_accounts_data(base_path: str = "amazon/data", accounts: Optional[List[str]] = None) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Load Amazon data for all accounts or specified accounts.
    
    Args:
        base_path: Base path to Amazon data directory
        accounts: Optional list of account names to load (default: all)
        
    Returns:
        Dictionary of {account_name: (retail_df, digital_df)}
    """
    import glob
    import os
    
    # Find all Amazon data directories
    data_dirs = glob.glob(os.path.join(base_path, "*_amazon_data"))
    if not data_dirs:
        raise FileNotFoundError(f"No Amazon data directories found in {base_path}")
    
    account_data = {}
    
    for data_dir in data_dirs:
        # Extract account name from directory name (format: YYYY-MM-DD_accountname_amazon_data)
        dir_name = os.path.basename(data_dir)
        parts = dir_name.split('_')
        if len(parts) >= 3 and parts[-2] == 'amazon' and parts[-1] == 'data':
            # Account name is everything between date and _amazon_data
            account_name = '_'.join(parts[1:-2])
        else:
            # Fallback: use directory name as-is
            account_name = dir_name
        
        # Skip if specific accounts requested and this isn't one of them
        if accounts and account_name not in accounts:
            continue
        
        print(f"Loading Amazon data for {account_name} from: {data_dir}")
        retail_df, digital_df = load_single_account_data(data_dir)
        account_data[account_name] = (retail_df, digital_df)
    
    if not account_data:
        if accounts:
            raise FileNotFoundError(f"No data found for accounts: {accounts}")
        else:
            raise FileNotFoundError(f"No Amazon data found in {base_path}")
    
    return account_data


def load_single_account_data(data_dir: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load Amazon data from a single account directory.
    Returns retail and digital order DataFrames.
    """
    import os
    import csv
    
    # Find retail order history files
    retail_dir = os.path.join(data_dir, "Retail.OrderHistory.1")
    retail_files = []
    if os.path.exists(retail_dir):
        for file in os.listdir(retail_dir):
            if file.endswith('.csv'):
                retail_files.append(os.path.join(retail_dir, file))
    
    # Load retail data
    retail_df = pd.DataFrame()
    if retail_files:
        retail_dfs = []
        for file in retail_files:
            try:
                df = pd.read_csv(file)
                retail_dfs.append(df)
            except Exception as e:
                print(f"Warning: Could not read {file}: {e}")
        
        if retail_dfs:
            retail_df = pd.concat(retail_dfs, ignore_index=True)
            
            # Parse dates
            if 'Ship Date' in retail_df.columns:
                retail_df['Ship Date'] = pd.to_datetime(retail_df['Ship Date'], format='ISO8601', errors='coerce')
            if 'Order Date' in retail_df.columns:
                retail_df['Order Date'] = pd.to_datetime(retail_df['Order Date'], format='ISO8601', errors='coerce')
    
    # Find digital order files
    digital_dir = os.path.join(data_dir, "Digital-Ordering.1")
    digital_df = pd.DataFrame()
    if os.path.exists(digital_dir):
        items_file = os.path.join(digital_dir, "Digital Items.csv")
        if os.path.exists(items_file):
            try:
                digital_df = pd.read_csv(items_file)
            except Exception as e:
                print(f"Warning: Could not read {items_file}: {e}")
    
    return retail_df, digital_df


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
        
        # Get candidates from all grouping levels - exact matches only (0 tolerance)
        candidates = get_order_candidates(relevant_orders, ynab_amount, ynab_date, tolerance=0)
        
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
            # Convert 110% check to integer arithmetic: amount > total * 1.1 becomes amount * 10 > total * 11
            if ynab_amount * 10 > order_data['total'] * 11:  # Transaction can't be more than 110% of order
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