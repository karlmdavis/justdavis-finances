#!/usr/bin/env python3
"""
Apple Batch Transaction Matcher

CLI tool for batch matching YNAB transactions to Apple receipts within a date range.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from apple_receipt_loader import load_apple_receipts, normalize_apple_receipt_data, filter_receipts_by_date_range
from ynab_apple_filter import (load_ynab_transactions, filter_apple_transactions, 
                              normalize_ynab_transaction_data, filter_transactions_by_date_range)
from apple_matcher import AppleMatcher, batch_match_transactions, generate_match_summary
from match_scorer import score_batch_results


def format_results_for_output(results, include_items: bool = False) -> list:
    """
    Format match results for JSON output.
    
    Args:
        results: List of MatchResult objects
        include_items: Whether to include item details from receipts
        
    Returns:
        List of formatted result dictionaries
    """
    formatted_results = []
    
    for result in results:
        # Format Apple receipts
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
        
        # Format result
        formatted_result = {
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
        
        formatted_results.append(formatted_result)
    
    return formatted_results


def save_results_to_file(results_data: dict, output_dir: str) -> str:
    """
    Save results to a timestamped JSON file.
    
    Args:
        results_data: Complete results dictionary
        output_dir: Output directory path
        
    Returns:
        Path to the saved file
    """
    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}_apple_matching_results.json"
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = output_path / filename
    with open(file_path, 'w') as f:
        json.dump(results_data, f, indent=2, default=str)
    
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="Batch match YNAB transactions to Apple receipts within a date range",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all Apple transactions in November 2024
  python match_transactions_batch.py --start 2024-11-01 --end 2024-11-30
  
  # Process with verbose output and save to custom location
  python match_transactions_batch.py \
    --start 2024-10-01 --end 2024-10-31 \
    --output results/october_matches \
    --verbose
    
  # Use custom date window (items included by default)
  python match_transactions_batch.py \
    --start 2024-11-01 --end 2024-11-30 \
    --date-window 3
        """
    )
    
    # Date range (required)
    parser.add_argument("--start", required=True,
                       help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True,
                       help="End date (YYYY-MM-DD)")
    
    # Data source paths
    parser.add_argument("--ynab-data-path", default="ynab-data/transactions.json",
                       help="Path to YNAB transactions JSON (default: ynab-data/transactions.json)")
    parser.add_argument("--apple-data-path", default="apple/exports",
                       help="Path to Apple exports directory (default: apple/exports)")
    
    # Output options
    parser.add_argument("--output", default="analysis/apple_transaction_matching/results",
                       help="Output directory (default: analysis/apple_transaction_matching/results)")
    parser.add_argument("--include-items", action="store_true", default=True,
                       help="Include item details from Apple receipts (default: True)")
    parser.add_argument("--no-include-items", action="store_false", dest="include_items",
                       help="Disable including item details from Apple receipts")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose progress output")
    
    # Matching parameters
    parser.add_argument("--date-window", type=int, default=2,
                       help="Date window in days for matching (default: 2)")
    
    args = parser.parse_args()
    
    start_time = datetime.now()
    
    try:
        # Validate date range
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
        
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")
        
        # Load and filter Apple receipts
        if args.verbose:
            print("Loading Apple receipts...")
        apple_receipts = load_apple_receipts(args.apple_data_path)
        apple_receipts_df = normalize_apple_receipt_data(apple_receipts)
        apple_filtered_df = filter_receipts_by_date_range(apple_receipts_df, args.start, args.end)
        
        if args.verbose:
            print(f"Loaded {len(apple_receipts_df)} total Apple receipts")
            print(f"Filtered to {len(apple_filtered_df)} receipts in date range")
        
        # Load and filter YNAB transactions
        if args.verbose:
            print("Loading YNAB transactions...")
        all_transactions = load_ynab_transactions(args.ynab_data_path)
        apple_transactions = filter_apple_transactions(all_transactions)
        ynab_df = normalize_ynab_transaction_data(apple_transactions)
        ynab_filtered_df = filter_transactions_by_date_range(ynab_df, args.start, args.end)
        
        if args.verbose:
            print(f"Loaded {len(all_transactions)} total YNAB transactions")
            print(f"Found {len(apple_transactions)} Apple transactions")
            print(f"Filtered to {len(ynab_filtered_df)} Apple transactions in date range")
        
        if ynab_filtered_df.empty:
            print("No Apple transactions found in the specified date range")
            return
        
        # Create matcher and perform batch matching
        if args.verbose:
            print(f"Matching {len(ynab_filtered_df)} transactions to {len(apple_filtered_df)} receipts...")
        
        matcher = AppleMatcher(
            date_window_days=args.date_window
        )
        
        results = batch_match_transactions(ynab_filtered_df, apple_filtered_df, matcher)
        
        # Generate summaries
        match_summary = generate_match_summary(results)
        scorer_summary = score_batch_results([
            {
                "ynab_transaction": r.ynab_transaction,
                "matched": r.matched,
                "match_confidence": r.match_confidence,
                "match_strategy": r.match_strategy.value if r.match_strategy else None
            }
            for r in results
        ])
        
        # Format results for output
        formatted_results = format_results_for_output(results, args.include_items)
        
        # Build complete output
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        output_data = {
            "date_range": {
                "start": args.start,
                "end": args.end
            },
            "summary": {
                **match_summary,
                **scorer_summary
            },
            "results": formatted_results,
            "processing_metadata": {
                "timestamp": end_time.isoformat(),
                "processing_time_seconds": round(processing_time, 2),
                "apple_receipts_total": len(apple_receipts_df),
                "apple_receipts_in_range": len(apple_filtered_df),
                "ynab_transactions_total": len(all_transactions),
                "apple_transactions_total": len(apple_transactions),
                "apple_transactions_in_range": len(ynab_filtered_df),
                "matcher_config": {
                    "date_window_days": args.date_window
                }
            }
        }
        
        # Save results
        output_file = save_results_to_file(output_data, args.output)
        
        # Print summary
        print(f"\nApple Transaction Matching Results")
        print(f"Date Range: {args.start} to {args.end}")
        print(f"Total Transactions: {match_summary['total_transactions']}")
        print(f"Matched: {match_summary['matched']} ({match_summary['match_rate']:.1%})")
        print(f"Average Confidence: {match_summary['average_confidence']:.3f}")
        print(f"Total Amount Matched: ${match_summary['total_amount_matched']:.2f}")
        print(f"Total Amount Unmatched: ${match_summary['total_amount_unmatched']:.2f}")
        print(f"Processing Time: {processing_time:.2f} seconds")
        print(f"Results saved to: {output_file}")
        
        if args.verbose:
            print(f"\nStrategy Breakdown:")
            for strategy, count in match_summary.get('strategy_breakdown', {}).items():
                print(f"  {strategy}: {count}")
            
            print(f"\nConfidence Distribution:")
            conf_dist = scorer_summary.get('confidence_distribution', {})
            for level, count in conf_dist.items():
                print(f"  {level}: {count}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()