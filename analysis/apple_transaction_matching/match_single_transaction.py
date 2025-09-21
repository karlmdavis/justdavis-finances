#!/usr/bin/env python3
"""
Apple Single Transaction Matcher

CLI tool for matching a single YNAB transaction to Apple receipts.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from apple_receipt_loader import load_apple_receipts, normalize_apple_receipt_data
from ynab_apple_filter import load_ynab_transactions, normalize_ynab_transaction_data
from apple_matcher import AppleMatcher
from match_scorer import create_match_result, AppleMatchType


def find_transaction_by_id(transaction_id: str, ynab_data_path: str = "ynab-data/transactions.json") -> dict:
    """
    Find a specific YNAB transaction by ID.
    
    Args:
        transaction_id: YNAB transaction UUID
        ynab_data_path: Path to YNAB transactions file
        
    Returns:
        Transaction dictionary
    """
    all_transactions = load_ynab_transactions(ynab_data_path)
    
    for transaction in all_transactions:
        if transaction.get('id') == transaction_id:
            # Normalize to match expected format
            normalized = normalize_ynab_transaction_data([transaction])
            if not normalized.empty:
                return normalized.iloc[0].to_dict()
    
    raise ValueError(f"Transaction {transaction_id} not found")


def create_transaction_from_params(transaction_id: str, date: str, amount: int, 
                                 payee_name: str, account_name: str) -> dict:
    """
    Create a transaction dictionary from command-line parameters.
    
    Args:
        transaction_id: Transaction UUID
        date: Date string (YYYY-MM-DD)
        amount: Amount in milliunits (negative for expenses)
        payee_name: Payee name
        account_name: Account name
        
    Returns:
        Normalized transaction dictionary
    """
    # Create a mock transaction in YNAB format
    mock_transaction = {
        'id': transaction_id,
        'date': date,
        'amount': amount,
        'payee_name': payee_name,
        'account_name': account_name,
        'memo': '',
        'cleared': 'uncleared',
        'approved': True,
        'category_name': 'Uncategorized'
    }
    
    # Normalize using the same function as real transactions
    normalized = normalize_ynab_transaction_data([mock_transaction])
    if normalized.empty:
        raise ValueError("Failed to normalize transaction parameters")
        
    return normalized.iloc[0].to_dict()


def format_match_result_for_output(result, include_items: bool = False) -> dict:
    """
    Format match result for JSON output.
    
    Args:
        result: MatchResult object from AppleMatcher
        include_items: Whether to include item details from receipts
        
    Returns:
        Formatted dictionary for JSON output
    """
    formatted_receipts = []
    
    for receipt in result.apple_receipts:
        formatted_receipt = {
            "apple_id": receipt.get("apple_id", ""),
            "receipt_date": receipt.get("receipt_date_str", ""),
            "order_id": receipt.get("order_id", ""),
            "document_number": receipt.get("document_number", ""),
            "total": receipt.get("total", 0.0),
            "currency": receipt.get("currency", "USD")
        }
        
        if include_items and "items" in receipt:
            formatted_receipt["items"] = receipt["items"]
            formatted_receipt["item_count"] = len(receipt.get("items", []))
        
        formatted_receipts.append(formatted_receipt)
    
    output = {
        "ynab_transaction": {
            "id": result.ynab_transaction.get("transaction_id", ""),
            "date": result.ynab_transaction.get("date_str", ""),
            "amount": result.ynab_transaction.get("amount_dollars", 0.0),
            "payee_name": result.ynab_transaction.get("payee_name", ""),
            "account_name": result.ynab_transaction.get("account_name", "")
        },
        "matched": result.matched,
        "apple_receipts": formatted_receipts,
        "unmatched_amount": result.unmatched_amount,
        "match_strategy": result.match_strategy.value if result.match_strategy else None,
        "match_confidence": result.match_confidence,
        "match_details": result.match_details or {}
    }
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Match a single YNAB transaction to Apple receipts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Match by transaction ID (looks up transaction from YNAB data)
  python match_single_transaction.py --transaction-id "abc123-def456-..."
  
  # Match by providing transaction details manually
  python match_single_transaction.py \
    --transaction-id "manual-001" \
    --date "2024-11-15" \
    --amount -1990 \
    --payee-name "APPLE.COM/BILL" \
    --account-name "Chase Credit Card"
    
  # Save result to file
  python match_single_transaction.py \
    --transaction-id "abc123-def456-..." \
    --output results/single_match.json
        """
    )
    
    # Transaction identification
    parser.add_argument("--transaction-id", required=True,
                       help="YNAB transaction UUID")
    
    # Optional manual transaction details (if not looking up from YNAB)
    parser.add_argument("--date", 
                       help="Transaction date (YYYY-MM-DD)")
    parser.add_argument("--amount", type=int,
                       help="Amount in milliunits (negative for expenses)")
    parser.add_argument("--payee-name",
                       help="Payee name from YNAB")
    parser.add_argument("--account-name", 
                       help="Account name from YNAB")
    
    # Data source paths
    parser.add_argument("--ynab-data-path", default="ynab-data/transactions.json",
                       help="Path to YNAB transactions JSON (default: ynab-data/transactions.json)")
    parser.add_argument("--apple-data-path", default="apple/exports",
                       help="Path to Apple exports directory (default: apple/exports)")
    
    # Output options
    parser.add_argument("--output", 
                       help="Output file path (default: print to stdout)")
    parser.add_argument("--include-items", action="store_true",
                       help="Include item details from Apple receipts")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")
    
    # Matching parameters
    parser.add_argument("--date-window", type=int, default=2,
                       help="Date window in days for matching (default: 2)")
    
    args = parser.parse_args()
    
    try:
        # Load Apple receipts
        if args.verbose:
            print("Loading Apple receipts...")
        apple_receipts = load_apple_receipts(args.apple_data_path)
        apple_receipts_df = normalize_apple_receipt_data(apple_receipts)
        
        if args.verbose:
            print(f"Loaded {len(apple_receipts_df)} Apple receipts")
        
        # Get transaction data
        if all([args.date, args.amount, args.payee_name, args.account_name]):
            # Use provided parameters
            if args.verbose:
                print("Using provided transaction parameters")
            transaction = create_transaction_from_params(
                args.transaction_id, args.date, args.amount, 
                args.payee_name, args.account_name
            )
        else:
            # Look up transaction from YNAB data
            if args.verbose:
                print(f"Looking up transaction {args.transaction_id} in YNAB data")
            transaction = find_transaction_by_id(args.transaction_id, args.ynab_data_path)
        
        if args.verbose:
            print(f"Transaction: ${transaction['amount_dollars']:.2f} on {transaction['date_str']} from {transaction['payee_name']}")
        
        # Create matcher and perform matching
        matcher = AppleMatcher(
            date_window_days=args.date_window
        )
        
        if args.verbose:
            print("Performing matching...")
        
        result = matcher.match_single_transaction(transaction, apple_receipts_df)
        
        # Format output
        output = format_match_result_for_output(result, args.include_items)
        
        # Add metadata
        output["processing_metadata"] = {
            "timestamp": datetime.now().isoformat(),
            "apple_receipts_available": len(apple_receipts_df),
            "matcher_config": {
                "date_window_days": args.date_window
            }
        }
        
        # Output result
        output_json = json.dumps(output, indent=2, default=str)
        
        if args.output:
            # Ensure output directory exists
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(output_json)
            
            if args.verbose:
                print(f"Results saved to {args.output}")
        else:
            print(output_json)
        
        # Print summary to stderr if verbose
        if args.verbose:
            if result.matched:
                print(f"✓ Match found with {result.match_confidence:.3f} confidence using {result.match_strategy.value}", file=sys.stderr)
                for receipt in result.apple_receipts:
                    print(f"  → Receipt {receipt['order_id']} for ${receipt['total']:.2f} on {receipt['receipt_date_str']}", file=sys.stderr)
            else:
                print("✗ No match found", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()