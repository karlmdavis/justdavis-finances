#!/usr/bin/env python3
"""
Amazon Transaction Matching System - Batch Processor

Process multiple YNAB transactions in a date range and find all Amazon matches.

Usage:
    # Process a month of transactions
    python match_transactions_batch.py --start 2024-07-01 --end 2024-07-31

    # Process with custom output location
    python match_transactions_batch.py --start 2024-07-01 --end 2024-07-31 --output results/

    # Process with verbose logging
    python match_transactions_batch.py --start 2024-07-01 --end 2024-07-31 --verbose
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any
import subprocess
import sys

from match_single_transaction import load_all_accounts_data, find_matching_orders, is_amazon_transaction, milliunits_to_cents, cents_to_dollars_str, convert_match_result_for_json


def load_ynab_transactions(start_date: str, end_date: str, ynab_data_path: str = "ynab-data") -> List[Dict[str, Any]]:
    """
    Load YNAB transactions from cache within date range.
    Filter to Amazon-related transactions only.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        ynab_data_path: Path to YNAB data directory
        
    Returns:
        List of Amazon-related YNAB transactions
    """
    transactions_file = os.path.join(ynab_data_path, "transactions.json")
    
    if not os.path.exists(transactions_file):
        raise FileNotFoundError(f"YNAB transactions file not found: {transactions_file}")
    
    with open(transactions_file, 'r') as f:
        all_transactions = json.load(f)
    
    # Filter transactions by date range and Amazon payees
    amazon_transactions = []
    
    for tx in all_transactions:
        tx_date = tx.get('date', '')
        
        # Check date range
        if tx_date < start_date or tx_date > end_date:
            continue
            
        # Check if it's an Amazon transaction
        payee_name = tx.get('payee_name', '')
        if not is_amazon_transaction(payee_name):
            continue
            
        # Only include expense transactions (negative amounts)
        amount = tx.get('amount', 0)
        if amount >= 0:
            continue
            
        amazon_transactions.append(tx)
    
    return amazon_transactions


def process_batch(transactions: List[Dict[str, Any]], accounts_data: Dict[str, Any], verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Process all transactions through single matcher.
    Track statistics and timing.
    
    Args:
        transactions: List of YNAB transactions to process
        accounts_data: Dictionary of {account_name: (retail_df, digital_df)}
        verbose: Enable verbose logging
        
    Returns:
        List of match results
    """
    results = []
    total_transactions = len(transactions)
    
    for i, tx in enumerate(transactions):
        if verbose:
            print(f"Processing transaction {i+1}/{total_transactions}: {tx['payee_name']} - ${cents_to_dollars_str(milliunits_to_cents(tx['amount']))}")
        
        try:
            # Process through single matcher
            result = find_matching_orders(tx, accounts_data)
            results.append(result)
            
            if verbose and result.get('matches'):
                best = result['best_match']
                print(f"  -> Matched with {best['account']} (confidence {best['confidence']:.2f})")
            elif verbose:
                print(f"  -> No match found")
                
        except Exception as e:
            if verbose:
                print(f"  -> Error processing transaction: {e}")
            
            # Create error result
            error_result = {
                'ynab_transaction': {
                    'id': tx.get('id', ''),
                    'date': tx.get('date', ''),
                    'amount': milliunits_to_cents(tx.get('amount', 0)),
                    'payee_name': tx.get('payee_name', ''),
                    'account_name': tx.get('account_name', '')
                },
                'matches': [],
                'best_match': None,
                'error': str(e)
            }
            results.append(error_result)
    
    return results


def generate_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary statistics from match results.
    
    Args:
        results: List of match results
        
    Returns:
        Summary statistics dictionary
    """
    total_transactions = len(results)
    
    if total_transactions == 0:
        return {
            'total_transactions': 0,
            'matched': 0,
            'partial': 0,
            'unmatched': 0,
            'match_rate': 0.0,
            'average_confidence': 0.0,
            'total_amount_matched': 0.0,
            'total_amount_unmatched': 0.0
        }
    
    matched_count = 0
    partial_count = 0
    unmatched_count = 0
    total_confidence = 0.0
    total_amount_matched = 0.0
    total_amount_unmatched = 0.0
    
    # Count matches by account
    matches_by_account = {}
    
    for result in results:
        if result.get('matches'):
            # Has matches
            best_match = result.get('matches', [{}])[0]  # Get first/best match
            if best_match.get('unmatched_amount', 0) > 0.01:  # Has unmatched portion
                partial_count += 1
            else:
                matched_count += 1
            
            # Track confidence from best match
            if result.get('best_match'):
                total_confidence += result['best_match']['confidence']
                # Count by account
                account = result['best_match']['account']
                matches_by_account[account] = matches_by_account.get(account, 0) + 1
            
            # Calculate matched vs unmatched amounts
            tx_amount = abs(result['ynab_transaction']['amount'])
            unmatched = best_match.get('unmatched_amount', 0)
            matched_amount = tx_amount - unmatched
            total_amount_matched += matched_amount
            total_amount_unmatched += unmatched
        else:
            unmatched_count += 1
            tx_amount = abs(result['ynab_transaction']['amount'])
            total_amount_unmatched += tx_amount
    
    # Calculate averages
    matched_and_partial = matched_count + partial_count
    match_rate = matched_and_partial / total_transactions if total_transactions > 0 else 0.0
    average_confidence = total_confidence / matched_and_partial if matched_and_partial > 0 else 0.0
    
    return {
        'total_transactions': total_transactions,
        'matched': matched_count,
        'partial': partial_count,
        'unmatched': unmatched_count,
        'match_rate': round(match_rate, 3),
        'average_confidence': round(average_confidence, 2),
        'total_amount_matched': round(total_amount_matched, 2),
        'total_amount_unmatched': round(total_amount_unmatched, 2),
        'matches_by_account': matches_by_account
    }


def save_results(results: List[Dict[str, Any]], summary: Dict[str, Any], date_range: Dict[str, str], 
                output_dir: str = "results", amazon_data_date: str = None) -> str:
    """
    Save results to timestamped JSON file.
    
    Args:
        results: Match results
        summary: Summary statistics
        date_range: Date range processed
        output_dir: Output directory
        amazon_data_date: Date of Amazon data used
        
    Returns:
        Path to output file
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}_amazon_matching_results.json"
    filepath = os.path.join(output_dir, filename)
    
    # Convert results to JSON-safe format with string amounts
    json_results = [convert_match_result_for_json(result) for result in results]
    
    # Create complete output structure
    output = {
        'date_range': date_range,
        'summary': summary,
        'results': json_results,
        'processing_metadata': {
            'timestamp': datetime.now().isoformat(),
            'amazon_data_date': amazon_data_date,
            'ynab_data_date': datetime.now().isoformat(),
            'processing_time_seconds': None  # Will be set by caller
        }
    }
    
    # Save to file
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    return filepath


def main():
    """
    Command-line entry point with argument parsing.
    """
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output_dir = os.path.join(script_dir, 'results')
    
    parser = argparse.ArgumentParser(description='Batch process YNAB transactions for Amazon matches')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default=default_output_dir, help=f'Output directory (default: {default_output_dir})')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--ynab-data-path', default='ynab-data', help='Path to YNAB data directory')
    parser.add_argument('--amazon-data-path', default='amazon/data', help='Path to Amazon data directory')
    parser.add_argument('--accounts', nargs='*', help='Specific accounts to search (default: all)')
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    try:
        if args.verbose:
            print(f"Starting batch processing for date range: {args.start} to {args.end}")
        
        # Load YNAB transactions
        if args.verbose:
            print("Loading YNAB transactions...")
        transactions = load_ynab_transactions(args.start, args.end, args.ynab_data_path)
        
        if args.verbose:
            print(f"Found {len(transactions)} Amazon transactions to process")
        
        if len(transactions) == 0:
            print("No Amazon transactions found in the specified date range.")
            return 0
        
        # Load Amazon data
        if args.verbose:
            print("Loading Amazon data...")
        accounts_data = load_all_accounts_data(args.amazon_data_path, args.accounts)
        if args.verbose:
            print(f"Loaded data for accounts: {', '.join(accounts_data.keys())}")
        
        # Extract Amazon data date from directory name
        amazon_data_date = None
        try:
            import glob
            data_dirs = glob.glob(os.path.join(args.amazon_data_path, "*_amazon_data"))
            if data_dirs:
                latest_dir = max(data_dirs, key=os.path.getmtime)
                dir_name = os.path.basename(latest_dir)
                amazon_data_date = dir_name.split('_')[0]  # Extract date part
        except:
            amazon_data_date = "unknown"
        
        # Process batch
        if args.verbose:
            print("Processing transactions...")
        results = process_batch(transactions, accounts_data, args.verbose)
        
        # Generate summary
        summary = generate_summary(results)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Save results
        date_range = {'start': args.start, 'end': args.end}
        output_file = save_results(results, summary, date_range, args.output, amazon_data_date)
        
        # Update processing time in saved file
        with open(output_file, 'r') as f:
            output_data = json.load(f)
        output_data['processing_metadata']['processing_time_seconds'] = round(processing_time, 2)
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        # Print summary
        print(f"\nBatch processing completed in {processing_time:.2f} seconds")
        print(f"Results saved to: {output_file}")
        print(f"\nSummary:")
        print(f"  Total transactions: {summary['total_transactions']}")
        print(f"  Matched: {summary['matched']}")
        print(f"  Partial matches: {summary['partial']}")
        print(f"  Unmatched: {summary['unmatched']}")
        print(f"  Match rate: {summary['match_rate']:.1%}")
        print(f"  Average confidence: {summary['average_confidence']:.2f}")
        print(f"  Amount matched: ${cents_to_dollars_str(summary['total_amount_matched'])}")
        print(f"  Amount unmatched: ${cents_to_dollars_str(summary['total_amount_unmatched'])}")
        if summary.get('matches_by_account'):
            print(f"\n  Matches by Account:")
            for account, count in summary['matches_by_account'].items():
                print(f"    {account}: {count} matches")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())