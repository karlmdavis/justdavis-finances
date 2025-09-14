#!/usr/bin/env python3
"""
YNAB Apple Transaction Filter Module

Filters YNAB transactions to identify Apple-related purchases.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd


def load_ynab_transactions(ynab_data_path: str = "ynab-data/transactions.json") -> List[Dict[str, Any]]:
    """
    Load YNAB transactions from the cached JSON file.
    
    Args:
        ynab_data_path: Path to YNAB transactions JSON file
        
    Returns:
        List of transaction dictionaries
    """
    transactions_file = Path(ynab_data_path)
    if not transactions_file.exists():
        raise FileNotFoundError(f"YNAB transactions file not found: {transactions_file}")
        
    with open(transactions_file, 'r') as f:
        transactions = json.load(f)
        
    print(f"Loaded {len(transactions)} YNAB transactions")
    return transactions


def is_apple_transaction(payee_name: str) -> bool:
    """
    Check if a payee name matches Apple transaction patterns.
    Excludes transfers, payments, and false positives.
    
    Args:
        payee_name: Payee name from YNAB transaction
        
    Returns:
        True if this appears to be an Apple transaction that should have receipts
    """
    if not payee_name:
        return False
        
    # Convert to lowercase for case-insensitive matching
    payee_lower = payee_name.lower()
    
    # Exclude transfers and payments (these shouldn't have receipts)
    exclusion_patterns = [
        r'transfer.*apple',     # "Transfer : Apple Card"
        r'apple.*plumbing',     # False positive: "Apple Plumbing"
        r'snapple',             # False positive: "Snapple"
        r'pineapple',           # False positive: "Pineapple"
        r'apple.*payment',      # "Apple Card Payment"
    ]
    
    for pattern in exclusion_patterns:
        if re.search(pattern, payee_lower):
            return False
    
    # Apple payee patterns
    apple_patterns = [
        r'\bapple\b',           # "Apple", "APPLE.COM", etc.
        r'\bitunes\b',          # "iTunes", "iTunes Store"
        r'\bapp\s*store\b',     # "App Store", "AppStore"
        r'apple\.com',          # "APPLE.COM/BILL"
        r'apple\s*services',    # "Apple Services"
        r'apple\s*music',       # "Apple Music"
        r'icloud',              # "iCloud"
        r'apple\s*tv',          # "Apple TV"
        r'apple\s*arcade',      # "Apple Arcade"
        r'apple\s*news',        # "Apple News"
        r'apple\s*fitness',     # "Apple Fitness"
        r'apple\s*one',         # "Apple One"
    ]
    
    # Check each pattern
    for pattern in apple_patterns:
        if re.search(pattern, payee_lower):
            return True
            
    return False


def filter_apple_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter YNAB transactions to only Apple-related ones.
    
    Args:
        transactions: List of all YNAB transactions
        
    Returns:
        List of Apple-related transactions
    """
    apple_transactions = []
    
    for transaction in transactions:
        payee_name = transaction.get('payee_name', '')
        
        if is_apple_transaction(payee_name):
            apple_transactions.append(transaction)
    
    print(f"Found {len(apple_transactions)} Apple transactions out of {len(transactions)} total")
    return apple_transactions


def normalize_ynab_transaction_data(transactions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize YNAB transaction data into a standardized DataFrame.
    
    Args:
        transactions: Raw transaction data from YNAB JSON
        
    Returns:
        DataFrame with normalized transaction data
    """
    normalized_data = []
    
    for transaction in transactions:
        try:
            # Convert amount from milliunits to dollars
            amount_milliunits = transaction.get('amount', 0)
            amount_dollars = milliunits_to_dollars(amount_milliunits)
            
            # Parse transaction date
            date_str = transaction.get('date', '')
            transaction_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
            
            # Create normalized record
            normalized_record = {
                'transaction_id': transaction.get('id', ''),
                'date': transaction_date,
                'date_str': date_str,
                'amount_milliunits': amount_milliunits,
                'amount_dollars': amount_dollars,
                'payee_name': transaction.get('payee_name', ''),
                'account_name': transaction.get('account_name', ''),
                'category_name': transaction.get('category_name', ''),
                'memo': transaction.get('memo', ''),
                'cleared': transaction.get('cleared', ''),
                'approved': transaction.get('approved', False),
                'account_id': transaction.get('account_id', ''),
                'payee_id': transaction.get('payee_id', ''),
                'category_id': transaction.get('category_id', ''),
                'import_payee_name': transaction.get('import_payee_name', ''),
                'import_payee_name_original': transaction.get('import_payee_name_original', '')
            }
            
            normalized_data.append(normalized_record)
            
        except Exception as e:
            print(f"Warning: Failed to normalize transaction {transaction.get('id', 'unknown')}: {e}")
            continue
    
    df = pd.DataFrame(normalized_data)
    
    # Sort by date for easier processing
    if not df.empty:
        df = df.sort_values('date')
        
    print(f"Normalized {len(df)} transactions successfully")
    return df


def milliunits_to_dollars(milliunits: int) -> float:
    """
    Convert YNAB milliunits to dollars.
    
    YNAB stores amounts as milliunits (1000 milliunits = $1.00)
    Negative amounts represent expenses.
    
    Args:
        milliunits: Amount in YNAB milliunits
        
    Returns:
        Amount in dollars (positive for expenses)
    """
    # Convert to dollars and make expenses positive for easier comparison
    dollars = abs(milliunits) / 1000.0
    return dollars


def filter_transactions_by_date_range(transactions_df: pd.DataFrame, 
                                      start_date: str, 
                                      end_date: str) -> pd.DataFrame:
    """
    Filter transactions to a specific date range.
    
    Args:
        transactions_df: DataFrame of transactions
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        
    Returns:
        Filtered DataFrame
    """
    if transactions_df.empty:
        return transactions_df
        
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Filter transactions within date range
    mask = (transactions_df['date'] >= start_dt) & (transactions_df['date'] <= end_dt)
    filtered_df = transactions_df[mask].copy()
    
    print(f"Filtered to {len(filtered_df)} transactions between {start_date} and {end_date}")
    return filtered_df


def get_apple_transaction_summary(transactions_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate summary statistics for Apple transactions.
    
    Args:
        transactions_df: DataFrame of Apple transactions
        
    Returns:
        Dictionary with summary statistics
    """
    if transactions_df.empty:
        return {"total_transactions": 0}
        
    summary = {
        "total_transactions": len(transactions_df),
        "total_amount": transactions_df['amount_dollars'].sum(),
        "date_range": {
            "earliest": transactions_df['date'].min().strftime("%Y-%m-%d") if not transactions_df['date'].isnull().all() else None,
            "latest": transactions_df['date'].max().strftime("%Y-%m-%d") if not transactions_df['date'].isnull().all() else None
        },
        "accounts": transactions_df['account_name'].value_counts().to_dict(),
        "payee_patterns": transactions_df['payee_name'].value_counts().head(10).to_dict(),
        "average_amount": transactions_df['amount_dollars'].mean(),
        "categories": transactions_df['category_name'].value_counts().to_dict()
    }
    
    return summary


if __name__ == "__main__":
    # Test the filter
    try:
        # Load all YNAB transactions
        all_transactions = load_ynab_transactions()
        
        # Filter to Apple transactions
        apple_transactions = filter_apple_transactions(all_transactions)
        
        # Normalize to DataFrame
        apple_df = normalize_ynab_transaction_data(apple_transactions)
        
        # Generate summary
        summary = get_apple_transaction_summary(apple_df)
        
        print("\nApple Transaction Summary:")
        print(f"Total Apple transactions: {summary['total_transactions']}")
        print(f"Total amount: ${summary['total_amount']:.2f}")
        print(f"Date range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}")
        print(f"Average amount: ${summary['average_amount']:.2f}")
        print(f"Accounts: {', '.join(summary['accounts'].keys())}")
        print("\nTop payee patterns:")
        for payee, count in list(summary['payee_patterns'].items())[:5]:
            print(f"  {payee}: {count} transactions")
        
    except Exception as e:
        print(f"Error testing YNAB Apple filter: {e}")