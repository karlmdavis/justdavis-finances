#!/usr/bin/env python3
"""
Amazon Transaction Matching System - Single Transaction Matcher

Matches a single YNAB transaction to corresponding Amazon orders by analyzing
order data and grouping by shipment dates.

Usage:
    python match_single_transaction.py \
        --transaction-id "24bd348e-41cc-4759-940e-4e2d01b00859" \
        --date "2024-07-27" \
        --amount -478430 \
        --payee-name "Amazon.com*R79WI77Q0" \
        --account-name "Chase Credit Card"
"""

import argparse
import json
import csv
import re
import os
import glob
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from decimal import Decimal


def dollars_to_cents(dollar_str: str) -> int:
    """Convert dollar string like '9.53' to 953 cents"""
    if not dollar_str or dollar_str == 'nan' or dollar_str == '':
        return 0
    try:
        return int(Decimal(str(dollar_str)) * 100)
    except:
        return 0


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
    
    Args:
        data_dir: Path to account data directory
        
    Returns:
        Tuple of (retail_df, digital_df)
    """
    
    # Load retail orders
    retail_csv = os.path.join(data_dir, "Retail.OrderHistory.1", "Retail.OrderHistory.1.csv")
    if os.path.exists(retail_csv):
        retail_df = pd.read_csv(retail_csv)
        # Convert date columns with ISO8601 format, handle "Not Available" values
        retail_df['Order Date'] = pd.to_datetime(retail_df['Order Date'], format='ISO8601', errors='coerce')
        retail_df['Ship Date'] = pd.to_datetime(retail_df['Ship Date'], format='ISO8601', errors='coerce')
        # Convert amount columns to integer cents
        retail_df['Total Owed'] = retail_df['Total Owed'].apply(lambda x: dollars_to_cents(str(x)) if pd.notna(x) else 0)
        retail_df['Unit Price'] = retail_df['Unit Price'].apply(lambda x: dollars_to_cents(str(x)) if pd.notna(x) else 0)
        retail_df['Unit Price Tax'] = retail_df['Unit Price Tax'].apply(lambda x: dollars_to_cents(str(x)) if pd.notna(x) else 0)
        retail_df['Total Discounts'] = retail_df['Total Discounts'].apply(lambda x: dollars_to_cents(str(x)) if pd.notna(x) else 0)
    else:
        retail_df = pd.DataFrame()
        print(f"Warning: Retail orders file not found at {retail_csv}")
    
    # Load digital orders
    digital_dir = os.path.join(data_dir, "Digital-Ordering.1")
    digital_orders_csv = os.path.join(digital_dir, "Digital Orders.csv")
    digital_items_csv = os.path.join(digital_dir, "Digital Items.csv")
    digital_monetary_csv = os.path.join(digital_dir, "Digital Orders Monetary.csv")
    
    if os.path.exists(digital_orders_csv):
        try:
            # Load digital order data with encoding handling for BOM
            orders_df = pd.read_csv(digital_orders_csv, encoding='utf-8-sig')
            items_df = pd.read_csv(digital_items_csv, encoding='utf-8-sig') if os.path.exists(digital_items_csv) else pd.DataFrame()
            monetary_df = pd.read_csv(digital_monetary_csv, encoding='utf-8-sig') if os.path.exists(digital_monetary_csv) else pd.DataFrame()
            
            # Convert order date with ISO8601 format, handle "Not Available" values
            orders_df['OrderDate'] = pd.to_datetime(orders_df['OrderDate'], format='ISO8601', errors='coerce')
            
            # Merge the dataframes if they exist
            if not items_df.empty and 'OrderId' in items_df.columns:
                digital_df = orders_df.merge(items_df, on='OrderId', how='left', suffixes=('', '_item'))
            else:
                digital_df = orders_df
                
            if not monetary_df.empty and 'OrderId' in monetary_df.columns:
                digital_df = digital_df.merge(monetary_df, on='OrderId', how='left', suffixes=('', '_monetary'))
        except Exception as e:
            print(f"Warning: Error loading digital orders: {e}")
            digital_df = pd.DataFrame()
    else:
        digital_df = pd.DataFrame()
        print(f"Warning: Digital orders files not found in {digital_dir}")
    
    return retail_df, digital_df


def is_amazon_transaction(payee_name: str) -> bool:
    """
    Check if payee name matches Amazon patterns, excluding AWS infrastructure services.
    
    Args:
        payee_name: The payee name from YNAB transaction
        
    Returns:
        True if this appears to be an Amazon transaction that should be matched
    """
    if not payee_name:
        return False
    
    payee_lower = payee_name.lower()
    
    # Exclude AWS infrastructure services - these don't have corresponding order data
    aws_exclusions = [
        r"amazon web services",
        r"aws",
        r"amazon.*web.*service"
    ]
    
    if any(re.search(pattern, payee_lower) for pattern in aws_exclusions):
        return False
    
    # Include all other Amazon services (retail, Kindle, Prime Video, Prime membership)
    amazon_patterns = [
        r"amazon",
        r"amzn",
        r"AMAZON",
        r"AMZN"
    ]
    
    return any(re.search(pattern.lower(), payee_lower) for pattern in amazon_patterns)


def group_orders_by_id(orders_df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Group orders by Order ID and calculate totals.
    
    Args:
        orders_df: DataFrame with order data
        
    Returns:
        Dictionary of {order_id: order_summary}
    """
    if orders_df.empty:
        return {}
    
    grouped = {}
    for order_id, group in orders_df.groupby('Order ID'):
        order_summary = {
            'order_id': order_id,
            'items': [],
            'total': 0,
            'order_date': None,
            'ship_dates': []
        }
        
        for _, row in group.iterrows():
            # Calculate item amount from unit price * quantity + tax
            unit_price = int(row.get('Unit Price', 0))
            quantity = int(row.get('Quantity', 1))
            unit_tax = int(row.get('Unit Price Tax', 0))
            # Item amount = (unit price + unit tax) * quantity
            item_amount = (unit_price + unit_tax) * quantity
            
            item = {
                'name': row.get('Product Name', ''),
                'amount': item_amount,  # Use calculated amount instead of Total Owed
                'ship_date': row.get('Ship Date'),
                'unit_price': unit_price,
                'quantity': quantity,
                'asin': row.get('ASIN', '')
            }
            order_summary['items'].append(item)
            order_summary['total'] += item_amount  # Add calculated amount to total
            
            # Track unique ship dates
            ship_date = row.get('Ship Date')
            if ship_date and ship_date not in order_summary['ship_dates']:
                order_summary['ship_dates'].append(ship_date)
        
        # Set order date (should be same for all items in order)
        order_summary['order_date'] = group.iloc[0].get('Order Date')
        order_summary['ship_dates'] = sorted(order_summary['ship_dates'])
        
        grouped[order_id] = order_summary
    
    return grouped


def group_by_shipment(orders_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Group orders by Order ID + Ship Date combination.
    
    Args:
        orders_df: DataFrame with order data
        
    Returns:
        List of shipment groups with totals
    """
    if orders_df.empty:
        return []
    
    shipment_groups = []
    
    # Group by Order ID first, then by Ship Date within each order
    for order_id, order_group in orders_df.groupby('Order ID'):
        for ship_date, shipment_group in order_group.groupby('Ship Date'):
            group_summary = {
                'order_id': order_id,
                'ship_date': ship_date,
                'items': [],
                'total': 0,
                'order_date': shipment_group.iloc[0].get('Order Date')
            }
            
            for _, row in shipment_group.iterrows():
                # Calculate item amount from unit price * quantity + tax
                unit_price = int(row.get('Unit Price', 0))
                quantity = int(row.get('Quantity', 1))
                unit_tax = int(row.get('Unit Price Tax', 0))
                # Item amount = (unit price + unit tax) * quantity
                item_amount = (unit_price + unit_tax) * quantity
                
                item = {
                    'name': row.get('Product Name', ''),
                    'amount': item_amount,  # Use calculated amount instead of Total Owed
                    'unit_price': unit_price,
                    'quantity': quantity,
                    'asin': row.get('ASIN', '')
                }
                group_summary['items'].append(item)
                group_summary['total'] += item_amount  # Add calculated amount to total
            
            shipment_groups.append(group_summary)
    
    return shipment_groups


def group_by_ship_date_only(orders_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Group orders by Order ID + Ship Date (date only, ignoring time) combination.
    This helps match orders where items shipped at different times on the same day.
    
    Args:
        orders_df: DataFrame with order data
        
    Returns:
        List of daily shipment groups with totals
    """
    if orders_df.empty:
        return []
    
    # Add a date-only column for grouping, handling NaT values
    orders_df = orders_df.copy()
    orders_df['Ship Date Only'] = orders_df['Ship Date'].apply(lambda x: x.date() if pd.notna(x) else None)
    
    shipment_groups = []
    
    # Group by Order ID first, then by Ship Date (date only) within each order
    for order_id, order_group in orders_df.groupby('Order ID'):
        for ship_date_only, daily_group in order_group.groupby('Ship Date Only'):
            group_summary = {
                'order_id': order_id,
                'ship_date': ship_date_only,  # Date only
                'items': [],
                'total': 0,
                'order_date': daily_group.iloc[0].get('Order Date'),
                'ship_times': []  # Track different ship times within the day
            }
            
            for _, row in daily_group.iterrows():
                # Calculate item amount from unit price * quantity + tax
                unit_price = int(row.get('Unit Price', 0))
                quantity = int(row.get('Quantity', 1))
                unit_tax = int(row.get('Unit Price Tax', 0))
                # Item amount = (unit price + unit tax) * quantity
                item_amount = (unit_price + unit_tax) * quantity
                
                item = {
                    'name': row.get('Product Name', ''),
                    'amount': item_amount,  # Use calculated amount instead of Total Owed
                    'unit_price': unit_price,
                    'quantity': quantity,
                    'asin': row.get('ASIN', '')
                }
                group_summary['items'].append(item)
                group_summary['total'] += item_amount  # Add calculated amount to total
                
                # Track different ship times within the day
                ship_time = row.get('Ship Date')
                if ship_time and ship_time not in group_summary['ship_times']:
                    group_summary['ship_times'].append(ship_time)
            
            group_summary['ship_times'] = sorted(group_summary['ship_times'])
            shipment_groups.append(group_summary)
    
    return shipment_groups


def calculate_match_confidence(ynab_amount: float, amazon_total: float, date_diff_days: int) -> float:
    """
    Calculate confidence score (0.0 to 1.0) for a match.
    
    Factors:
    - Amount accuracy (exact match vs. small discrepancy)
    - Date alignment (same day vs. processing delay)
    - Match completeness (full vs. partial explanation)
    
    Args:
        ynab_amount: YNAB transaction amount (positive)
        amazon_total: Amazon order total
        date_diff_days: Absolute difference in days between transaction and ship date
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    confidence = 1.0
    
    # Amount matching penalties
    amount_diff = abs(ynab_amount - amazon_total)
    if amount_diff == 0:
        amount_penalty = 0
    elif amount_diff <= 0.01:  # Rounding error
        amount_penalty = 0.05
    elif amount_diff <= 0.10:  # Small discrepancy
        amount_penalty = 0.15
    elif amount_diff <= ynab_amount * 0.02:  # Within 2%
        amount_penalty = 0.25
    else:
        # Proportional penalty for larger differences
        amount_penalty = min(0.5, amount_diff / ynab_amount)
    
    # Date matching penalties - more forgiving for exact amounts
    if amount_diff <= 1:  # Exact amount
        # Exact amounts get much more forgiving date penalty
        date_penalty = min(0.20, date_diff_days * 0.08)
    else:
        # Regular date penalty for non-exact amounts
        date_penalty = min(0.30, date_diff_days * 0.15)
    
    # Calculate final confidence
    confidence = max(0, confidence - amount_penalty - date_penalty)
    
    # Special boosts for exact amount matches
    if amount_diff == 0:
        if date_diff_days <= 2:
            confidence = max(confidence, 0.90)
        elif date_diff_days <= 5:
            confidence = max(confidence, 0.85)
    elif amount_diff <= 0.01 and date_diff_days <= 2:
        confidence = max(confidence, 0.85)
    
    return round(confidence, 2)


def find_matching_orders_single_account(ynab_tx: Dict[str, Any], retail_orders: pd.DataFrame, digital_orders: pd.DataFrame, account_name: str) -> Optional[Dict[str, Any]]:
    """
    Find matching orders for a single account.
    
    Args:
        ynab_tx: YNAB transaction dictionary
        retail_orders: Retail orders DataFrame for this account
        digital_orders: Digital orders DataFrame for this account
        account_name: Name of the account being searched
        
    Returns:
        Match result for this account or None if no match
    """
    # Convert amount from milliunits to cents
    ynab_amount = milliunits_to_cents(ynab_tx['amount'])
    ynab_date = datetime.strptime(ynab_tx['date'], '%Y-%m-%d').date()
    
    # Initialize match structure for this account
    best_match = None
    
    # Check if this is an Amazon transaction
    if not is_amazon_transaction(ynab_tx['payee_name']):
        return None
    
    # Combine retail and digital orders for matching
    all_matches = []
    
    # Process retail orders
    if not retail_orders.empty:
        # Filter orders within reasonable date window (±7 days)
        # Handle NaT values gracefully - include orders with missing ship dates
        date_window_start = ynab_date - timedelta(days=7)
        date_window_end = ynab_date + timedelta(days=7)
        
        # Create mask that handles NaT values - include rows with missing ship dates
        # First check for non-null dates, then apply date operations only to valid dates
        valid_dates_mask = retail_orders['Ship Date'].notna()
        date_range_mask = (
            (retail_orders.loc[valid_dates_mask, 'Ship Date'].dt.date >= date_window_start) &
            (retail_orders.loc[valid_dates_mask, 'Ship Date'].dt.date <= date_window_end)
        )
        
        # Combine masks: include orders with valid dates in range OR orders with missing ship dates
        ship_date_mask = pd.Series(False, index=retail_orders.index)
        ship_date_mask.loc[valid_dates_mask] = date_range_mask
        ship_date_mask |= retail_orders['Ship Date'].isna()
        
        relevant_orders = retail_orders[ship_date_mask].copy()
        
        if not relevant_orders.empty:
            # Try different matching strategies
            
            # Strategy 0: Exact Amount Priority Match
            # Search for exact amounts first, regardless of complexity
            daily_shipment_groups = group_by_ship_date_only(relevant_orders)
            for group in daily_shipment_groups:
                amount_diff = abs(ynab_amount - group['total'])
                if amount_diff <= 1:  # Essentially exact match (allow for floating point precision)
                    if group['ship_date'] is None:
                        continue  # Skip groups with no ship date
                    ship_date = group['ship_date'] if isinstance(group['ship_date'], date) else group['ship_date'].date()
                    date_diff = abs((ynab_date - ship_date).days)
                    # For exact matches, allow wider date window with good confidence
                    if date_diff <= 5:  # Extended window for exact matches
                        confidence = calculate_match_confidence(ynab_amount, group['total'], date_diff)
                        # Boost confidence for exact amount matches
                        if amount_diff == 0:
                            confidence = max(confidence, 0.90)
                        
                        # Convert to expected order format
                        order_data = {
                            'order_id': group['order_id'],
                            'items': group['items'],
                            'total': group['total'],
                            'ship_dates': group['ship_times'],
                            'order_date': group['order_date']
                        }
                        
                        all_matches.append({
                            'orders': [order_data],
                            'total': group['total'],
                            'method': 'exact_amount_priority',
                            'confidence': confidence,
                            'date_diff': date_diff
                        })
            
            # Strategy 1: Exact Complete Order Match (Multi-Day Support)
            orders_by_id = group_orders_by_id(relevant_orders)
            for order_id, order_data in orders_by_id.items():
                amount_diff = abs(ynab_amount - order_data['total'])
                if amount_diff <= 1:  # Essentially exact match
                    # Support both single-day and multi-day orders for exact amounts
                    if len(order_data['ship_dates']) >= 1:
                        # For multi-day orders, use the earliest ship date for date_diff calculation
                        # Filter out any NaT values before finding minimum
                        valid_ship_dates = [d for d in order_data['ship_dates'] if pd.notna(d)]
                        if not valid_ship_dates:
                            continue  # Skip if no valid ship dates
                        earliest_ship_date = min(valid_ship_dates).date()
                        date_diff = abs((ynab_date - earliest_ship_date).days)
                        
                        # For exact amounts, be more lenient with date windows (up to 7 days)
                        if date_diff <= 7:
                            confidence = calculate_match_confidence(ynab_amount, order_data['total'], date_diff)
                            
                            # Determine method name based on shipping pattern
                            if len(order_data['ship_dates']) == 1:
                                method = 'exact_single_order'
                            else:
                                method = 'exact_multi_day_order'
                                # Boost confidence for exact multi-day matches since they're more reliable
                                confidence = max(confidence, 0.90)
                            
                            all_matches.append({
                                'orders': [order_data],
                                'total': order_data['total'],
                                'method': method,
                                'confidence': confidence,
                                'date_diff': date_diff
                            })
            
            # Strategy 2: Exact Shipment Group Match
            shipment_groups = group_by_shipment(relevant_orders)
            for group in shipment_groups:
                amount_diff = abs(ynab_amount - group['total'])
                if amount_diff <= 1:  # Essentially exact match
                    if group['ship_date'] is None:
                        continue  # Skip groups with no ship date
                    ship_date = group['ship_date'].date()
                    date_diff = abs((ynab_date - ship_date).days)
                    confidence = calculate_match_confidence(ynab_amount, group['total'], date_diff)
                    
                    # Convert shipment group to order format
                    order_data = {
                        'order_id': group['order_id'],
                        'items': group['items'],
                        'total': group['total'],
                        'ship_dates': [group['ship_date']],
                        'order_date': group['order_date']
                    }
                    
                    all_matches.append({
                        'orders': [order_data],
                        'total': group['total'],
                        'method': 'exact_shipment_group',
                        'confidence': confidence,
                        'date_diff': date_diff
                    })
            
            # Strategy 3: Multiple Orders/Shipments Same Day (Enhanced)
            # Use date-only grouping to catch multi-shipment orders better
            # Group all shipments by ship date (ignoring existing matches from Strategy 0)
            shipments_by_date = {}
            for group in shipment_groups:
                if group['ship_date'] is None:
                    continue  # Skip groups with no ship date
                ship_date = group['ship_date'].date()
                if ship_date not in shipments_by_date:
                    shipments_by_date[ship_date] = []
                shipments_by_date[ship_date].append(group)
            
            # Also include daily groups from Strategy 0 that weren't exact matches
            for group in daily_shipment_groups:
                if group['ship_date'] is None:
                    continue  # Skip groups with no ship date
                ship_date = group['ship_date'] if isinstance(group['ship_date'], date) else group['ship_date'].date()
                amount_diff = abs(ynab_amount - group['total'])
                # Only include if not already caught by Strategy 0
                if amount_diff >= 0.01:
                    if ship_date not in shipments_by_date:
                        shipments_by_date[ship_date] = []
                    # Convert daily group to shipment group format for compatibility
                    pseudo_shipment = {
                        'order_id': group['order_id'],
                        'ship_date': group['ship_times'][0] if group['ship_times'] else ship_date,
                        'total': group['total'],
                        'items': group['items'],
                        'order_date': group['order_date']
                    }
                    shipments_by_date[ship_date].append(pseudo_shipment)
            
            # Check combinations of orders/shipments on the same day
            for ship_date, day_shipments in shipments_by_date.items():
                if len(day_shipments) > 1:
                    # Try combining all shipments for this date
                    combined_total = sum(s['total'] for s in day_shipments)
                    amount_diff = abs(ynab_amount - combined_total)
                    if amount_diff <= 1:
                        date_diff = abs((ynab_date - ship_date).days)
                        confidence = calculate_match_confidence(ynab_amount, combined_total, date_diff)
                        
                        # Convert to order format
                        combined_orders = []
                        for shipment in day_shipments:
                            order_data = {
                                'order_id': shipment['order_id'],
                                'items': shipment['items'],
                                'total': shipment['total'],
                                'ship_dates': [shipment['ship_date']],
                                'order_date': shipment['order_date']
                            }
                            combined_orders.append(order_data)
                        
                        all_matches.append({
                            'orders': combined_orders,
                            'total': combined_total,
                            'method': 'multiple_orders_same_day',
                            'confidence': confidence,
                            'date_diff': date_diff
                        })
            
            # Strategy 4: Date Window Match (Enhanced for Exact Matches)
            # Look for approximate matches with flexible date windows
            for group in shipment_groups:
                if group['ship_date'] is None:
                    continue  # Skip groups with no ship date
                ship_date = group['ship_date'].date()
                date_diff = abs((ynab_date - ship_date).days)
                amount_diff = abs(ynab_amount - group['total'])
                
                # Determine appropriate date window based on amount accuracy
                if amount_diff <= 1:  # Exact amount match
                    max_date_diff = 5  # Allow ±5 days for exact amounts
                    min_confidence = 0.80
                elif amount_diff <= ynab_amount * 0.02:  # Within 2%
                    max_date_diff = 3  # Allow ±3 days for very close amounts
                    min_confidence = 0.75
                else:
                    max_date_diff = 2  # Standard ±2 days for approximate matches
                    min_confidence = 0.70
                
                if date_diff <= max_date_diff:
                    if amount_diff <= ynab_amount * 0.10:  # Within 10%
                        confidence = calculate_match_confidence(ynab_amount, group['total'], date_diff)
                        
                        # Boost confidence for exact amounts
                        if amount_diff <= 1:
                            confidence = max(confidence, 0.85)
                        
                        if confidence >= min_confidence:
                            order_data = {
                                'order_id': group['order_id'],
                                'items': group['items'],
                                'total': group['total'],
                                'ship_dates': [group['ship_date']],
                                'order_date': group['order_date']
                            }
                            
                            # Use more specific method name for exact matches
                            method = 'exact_amount_date_window' if amount_diff <= 1 else 'date_window_match'
                            
                            all_matches.append({
                                'orders': [order_data],
                                'total': group['total'],
                                'method': method,
                                'confidence': confidence,
                                'date_diff': date_diff
                            })
    
    # Process digital orders (digital items charged on order date, not ship date)
    if not digital_orders.empty:
        # Filter digital orders within date window (±3 days for digital purchases)
        date_window_start = ynab_date - timedelta(days=3)
        date_window_end = ynab_date + timedelta(days=3)
        
        # Parse OrderDate and filter by date range
        digital_orders_copy = digital_orders.copy()
        digital_orders_copy['OrderDate'] = pd.to_datetime(digital_orders_copy['OrderDate'], format='ISO8601', errors='coerce')
        
        # Filter orders within date window
        valid_dates_mask = digital_orders_copy['OrderDate'].notna()
        date_range_mask = (
            (digital_orders_copy.loc[valid_dates_mask, 'OrderDate'].dt.date >= date_window_start) &
            (digital_orders_copy.loc[valid_dates_mask, 'OrderDate'].dt.date <= date_window_end)
        )
        
        digital_date_mask = pd.Series(False, index=digital_orders_copy.index)
        digital_date_mask.loc[valid_dates_mask] = date_range_mask
        relevant_digital = digital_orders_copy[digital_date_mask].copy()
        
        if not relevant_digital.empty:
            # Group by OrderId and sum prices
            digital_groups = {}
            for order_id, group in relevant_digital.groupby('OrderId'):
                # Calculate total price for this order
                total_price_cents = sum(dollars_to_cents(str(price)) for price in group['OurPrice'] if pd.notna(price))
                
                if total_price_cents > 0:  # Only consider orders with actual charges
                    order_date = group['OrderDate'].iloc[0].date()
                    date_diff = abs((ynab_date - order_date).days)
                    amount_diff = abs(ynab_amount - total_price_cents)
                    
                    # Calculate confidence for digital match
                    confidence = 0.5  # Base confidence for digital orders
                    if amount_diff <= 1:  # Exact match
                        confidence = 1.0
                    elif amount_diff <= 5:  # Within 5 cents
                        confidence = 0.9
                    elif amount_diff <= 10:  # Within 10 cents
                        confidence = 0.8
                    
                    # Date proximity bonus
                    if date_diff == 0:
                        confidence += 0.1
                    elif date_diff <= 1:
                        confidence += 0.05
                    
                    confidence = min(confidence, 1.0)  # Cap at 1.0
                    
                    # Create order data structure
                    order_items = []
                    for _, item in group.iterrows():
                        item_price = dollars_to_cents(str(item['OurPrice'])) if pd.notna(item['OurPrice']) else 0
                        if item_price > 0:  # Only include charged items
                            order_items.append({
                                'name': item.get('ProductName', 'Unknown Digital Item'),
                                'amount': item_price,
                                'order_date': order_date.strftime('%Y-%m-%d'),
                                'type': 'digital'
                            })
                    
                    if order_items:  # Only add if we have chargeable items
                        order_data = {
                            'order_id': order_id,
                            'total': total_price_cents,
                            'items': order_items,
                            'order_date': order_date.strftime('%Y-%m-%d'),
                            'type': 'digital'
                        }
                        
                        all_matches.append({
                            'orders': [order_data],
                            'total': total_price_cents,
                            'method': 'digital_order_match',
                            'confidence': confidence,
                            'date_diff': date_diff
                        })
    
    # Select the best match for this account
    if all_matches:
        # Sort by confidence (desc), then by date difference (asc)
        match = max(all_matches, key=lambda x: (x['confidence'], -x['date_diff']))
        
        best_match = {
            'account': account_name,
            'amazon_orders': match['orders'],
            'match_method': match['method'],
            'confidence': match['confidence'],
            'unmatched_amount': ynab_amount - match['total']
        }
    
    return best_match


def find_matching_orders(ynab_tx: Dict[str, Any], accounts_data: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]) -> Dict[str, Any]:
    """
    Main matching logic - searches across all accounts.
    
    Args:
        ynab_tx: YNAB transaction dictionary
        accounts_data: Dictionary of {account_name: (retail_df, digital_df)}
        
    Returns:
        Match result dictionary with all matches from all accounts
    """
    # Convert amount from milliunits to cents
    ynab_amount = milliunits_to_cents(ynab_tx['amount'])
    
    # Initialize result structure
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
    
    # Search each account for matches
    all_account_matches = []
    for account_name, (retail_df, digital_df) in accounts_data.items():
        match = find_matching_orders_single_account(ynab_tx, retail_df, digital_df, account_name)
        if match:
            all_account_matches.append(match)
    
    # Sort all matches by confidence
    all_account_matches.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Add all matches to result
    result['matches'] = all_account_matches
    
    # Identify best match
    if all_account_matches:
        best = all_account_matches[0]
        result['best_match'] = {
            'account': best['account'],
            'confidence': best['confidence']
        }
    
    return result


def main():
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(description='Match a single YNAB transaction to Amazon orders')
    parser.add_argument('--transaction-id', required=True, help='YNAB transaction ID')
    parser.add_argument('--date', required=True, help='Transaction date (YYYY-MM-DD)')
    parser.add_argument('--amount', type=int, required=True, help='Transaction amount in milliunits')
    parser.add_argument('--payee-name', required=True, help='Payee name')
    parser.add_argument('--account-name', required=True, help='Account name')
    parser.add_argument('--amazon-data-path', default='amazon/data', help='Path to Amazon data directory')
    parser.add_argument('--accounts', nargs='*', help='Specific accounts to search (default: all)')
    parser.add_argument('--output', help='Output file path (default: print to stdout)')
    
    args = parser.parse_args()
    
    # Create transaction dictionary
    ynab_transaction = {
        'id': args.transaction_id,
        'date': args.date,
        'amount': args.amount,
        'payee_name': args.payee_name,
        'account_name': args.account_name
    }
    
    try:
        # Load Amazon data for all accounts or specified accounts
        accounts_data = load_all_accounts_data(args.amazon_data_path, args.accounts)
        
        # Find matching orders across all accounts
        result = find_matching_orders(ynab_transaction, accounts_data)
        
        # Convert to JSON-safe format with string amounts
        json_result = convert_match_result_for_json(result)
        
        # Format output
        output_json = json.dumps(json_result, indent=2, default=str)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_json)
            print(f"Results written to {args.output}")
        else:
            print(output_json)
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())