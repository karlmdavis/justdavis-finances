#!/usr/bin/env python3
"""
Interactive Apple Unmatched Transaction Explorer

This script helps you analyze and explore unmatched transactions from the Apple 
receipt matching system. It provides various views and filters to understand 
why transactions weren't matched.
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd


def find_latest_results_file() -> str:
    """Find the most recent Apple matching results file."""
    results_dir = Path(__file__).parent / "results"
    if not results_dir.exists():
        raise FileNotFoundError("Results directory not found. Run the batch matcher first.")
    
    # Find all Apple matching results files
    pattern = "*apple_matching_results.json"
    files = list(results_dir.glob(pattern))
    
    if not files:
        raise FileNotFoundError("No Apple matching results files found. Run the batch matcher first.")
    
    # Return the most recent file
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)


def load_unmatched_transactions(filepath: str) -> List[Dict[str, Any]]:
    """Load unmatched transactions from results file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        unmatched = [r for r in data['results'] if not r['matched']]
        print(f"Loaded {len(unmatched)} unmatched transactions from {len(data['results'])} total")
        print(f"Date range: {data['date_range']['start']} to {data['date_range']['end']}")
        return unmatched
        
    except FileNotFoundError:
        print(f"Error: Results file not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in results file: {filepath}")
        sys.exit(1)


def categorize_unmatched(unmatched: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize unmatched transactions by likely reason."""
    categories = {
        'Apple Services (Subscriptions)': [],
        'APPLE.COM/BILL (iCloud/Subscriptions)': [],
        'Apple Store (Hardware)': [],
        'Other Apple Transactions': []
    }
    
    for tx in unmatched:
        payee = tx['ynab_transaction']['payee_name']
        
        if payee == 'Apple Services':
            categories['Apple Services (Subscriptions)'].append(tx)
        elif 'APPLE.COM/BILL' in payee:
            categories['APPLE.COM/BILL (iCloud/Subscriptions)'].append(tx)
        elif 'Apple Store' in payee:
            categories['Apple Store (Hardware)'].append(tx)
        else:
            categories['Other Apple Transactions'].append(tx)
    
    return categories


def print_transaction_summary(tx: Dict[str, Any], show_details: bool = False) -> None:
    """Print a formatted summary of a transaction."""
    t = tx['ynab_transaction']
    date_str = t['date']
    amount_str = f"${t['amount']:.2f}".rjust(8)
    payee = t['payee_name'][:40]  # Truncate long payee names
    account = t['account_name'][:20]  # Truncate long account names
    
    print(f"  {amount_str} | {date_str} | {payee:<40} | {account}")
    
    if show_details:
        reason = tx.get('match_details', {}).get('reason', 'Unknown')
        print(f"           Reason: {reason}")
        print(f"           ID: {t['id']}")


def show_category_summary(categories: Dict[str, List[Dict[str, Any]]]) -> None:
    """Show a summary of all categories."""
    print("\n" + "="*80)
    print("UNMATCHED TRANSACTION SUMMARY BY CATEGORY")
    print("="*80)
    
    total_unmatched = sum(len(transactions) for transactions in categories.values())
    
    for category, transactions in categories.items():
        if transactions:
            percentage = (len(transactions) / total_unmatched) * 100
            print(f"\n{category}: {len(transactions)} transactions ({percentage:.1f}%)")
            
            # Show total amount for this category
            total_amount = sum(tx['ynab_transaction']['amount'] for tx in transactions)
            print(f"Total amount: ${total_amount:.2f}")
            
            # Show a few examples
            print("Examples:")
            for tx in transactions[:3]:
                print_transaction_summary(tx)
            
            if len(transactions) > 3:
                print(f"  ... and {len(transactions) - 3} more")


def show_category_details(category_name: str, transactions: List[Dict[str, Any]], 
                         limit: int = None, show_details: bool = False) -> None:
    """Show detailed view of transactions in a category."""
    print(f"\n" + "="*80)
    print(f"{category_name.upper()}: {len(transactions)} transactions")
    print("="*80)
    
    if not transactions:
        print("No transactions in this category.")
        return
    
    # Sort by amount (highest first)
    sorted_transactions = sorted(transactions, key=lambda x: x['ynab_transaction']['amount'], reverse=True)
    
    # Apply limit if specified
    if limit:
        sorted_transactions = sorted_transactions[:limit]
        print(f"Showing top {limit} by amount:")
    
    print(f"{'Amount':<8} | {'Date':<10} | {'Payee':<40} | {'Account'}")
    print("-" * 80)
    
    for tx in sorted_transactions:
        print_transaction_summary(tx, show_details)


def show_date_analysis(unmatched: List[Dict[str, Any]]) -> None:
    """Show analysis by date patterns."""
    print("\n" + "="*80)
    print("UNMATCHED TRANSACTIONS BY DATE")
    print("="*80)
    
    # Convert to DataFrame for easier date analysis
    data = []
    for tx in unmatched:
        t = tx['ynab_transaction']
        data.append({
            'date': datetime.strptime(t['date'], '%Y-%m-%d'),
            'amount': t['amount'],
            'payee': t['payee_name']
        })
    
    df = pd.DataFrame(data)
    
    # Group by month
    monthly = df.groupby(df['date'].dt.to_period('M')).agg({
        'amount': ['count', 'sum'],
        'payee': lambda x: list(x.unique())
    }).round(2)
    
    print("Monthly breakdown:")
    print(f"{'Month':<10} | {'Count':<5} | {'Total Amount':<12} | {'Unique Payees'}")
    print("-" * 60)
    
    for period, row in monthly.iterrows():
        count = row[('amount', 'count')]
        total = row[('amount', 'sum')]
        payees = len(row[('payee', '<lambda>')])
        print(f"{period!s:<10} | {count:<5} | ${total:<11.2f} | {payees}")


def show_amount_analysis(unmatched: List[Dict[str, Any]]) -> None:
    """Show analysis by amount ranges."""
    print("\n" + "="*80)
    print("UNMATCHED TRANSACTIONS BY AMOUNT")
    print("="*80)
    
    amounts = [tx['ynab_transaction']['amount'] for tx in unmatched]
    
    # Define amount ranges
    ranges = [
        (0, 10, "Under $10"),
        (10, 50, "$10 - $50"),
        (50, 100, "$50 - $100"),
        (100, 500, "$100 - $500"),
        (500, float('inf'), "Over $500")
    ]
    
    print(f"{'Range':<15} | {'Count':<5} | {'Total Amount'}")
    print("-" * 40)
    
    for min_amt, max_amt, label in ranges:
        range_transactions = [tx for tx in unmatched 
                            if min_amt <= tx['ynab_transaction']['amount'] < max_amt]
        count = len(range_transactions)
        total = sum(tx['ynab_transaction']['amount'] for tx in range_transactions)
        
        print(f"{label:<15} | {count:<5} | ${total:.2f}")


def export_to_csv(unmatched: List[Dict[str, Any]], filepath: str) -> None:
    """Export unmatched transactions to CSV."""
    data = []
    for tx in unmatched:
        t = tx['ynab_transaction']
        data.append({
            'id': t['id'],
            'date': t['date'],
            'amount': t['amount'],
            'payee_name': t['payee_name'],
            'account_name': t['account_name'],
            'reason': tx.get('match_details', {}).get('reason', 'Unknown')
        })
    
    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False)
    print(f"Exported {len(data)} unmatched transactions to: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Explore unmatched Apple transactions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show summary of all categories
  python view_unmatched.py
  
  # Show detailed view of Apple Services transactions
  python view_unmatched.py --category services
  
  # Show date analysis
  python view_unmatched.py --analysis date
  
  # Export to CSV
  python view_unmatched.py --export unmatched.csv
  
  # Use specific results file
  python view_unmatched.py --file results/2025-09-14_17-49-10_apple_matching_results.json
        """
    )
    
    parser.add_argument("--file", help="Specific results file to analyze (default: latest)")
    parser.add_argument("--category", choices=['services', 'icloud', 'store', 'other'],
                       help="Show detailed view of specific category")
    parser.add_argument("--analysis", choices=['date', 'amount'], 
                       help="Show specific analysis type")
    parser.add_argument("--export", help="Export to CSV file")
    parser.add_argument("--limit", type=int, default=20, 
                       help="Limit number of transactions shown (default: 20)")
    parser.add_argument("--details", action="store_true", 
                       help="Show additional details for each transaction")
    
    args = parser.parse_args()
    
    # Determine which file to use
    if args.file:
        filepath = args.file
    else:
        try:
            filepath = find_latest_results_file()
            print(f"Using latest results file: {filepath}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Load unmatched transactions
    unmatched = load_unmatched_transactions(filepath)
    
    if not unmatched:
        print("No unmatched transactions found!")
        return
    
    # Categorize transactions
    categories = categorize_unmatched(unmatched)
    
    # Handle specific requests
    if args.export:
        export_to_csv(unmatched, args.export)
        return
    
    if args.analysis == 'date':
        show_date_analysis(unmatched)
        return
    
    if args.analysis == 'amount':
        show_amount_analysis(unmatched)
        return
    
    if args.category:
        category_map = {
            'services': 'Apple Services (Subscriptions)',
            'icloud': 'APPLE.COM/BILL (iCloud/Subscriptions)',
            'store': 'Apple Store (Hardware)',
            'other': 'Other Apple Transactions'
        }
        category_name = category_map[args.category]
        show_category_details(category_name, categories[category_name], 
                            args.limit, args.details)
        return
    
    # Default: show summary
    show_category_summary(categories)
    
    print(f"\n\nUse --help to see additional options for detailed analysis.")


if __name__ == "__main__":
    main()