#!/usr/bin/env python3
"""
Simplified Amazon Transaction Matching Batch Processor

Uses the new 3-strategy architecture for clean, maintainable code.
Replaces both match_transactions_batch.py and match_transactions_batch_v2.py
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from match_single_transaction import load_all_accounts_data, is_amazon_transaction, milliunits_to_cents, cents_to_dollars_str, convert_match_result_for_json, SimplifiedMatcher
from split_payment_matcher import SplitPaymentMatcher


def load_ynab_transactions(start_date: str, end_date: str, ynab_data_path: str = "ynab-data") -> List[Dict[str, Any]]:
    """Load YNAB transactions from cache within date range."""
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


def process_batch(transactions: List[Dict[str, Any]], 
                 accounts_data: Dict[str, Any], 
                 enable_split: bool = True,
                 cache_file: Optional[str] = None,
                 verbose: bool = False) -> List[Dict[str, Any]]:
    """Process all transactions using simplified matching engine."""
    results = []
    total_transactions = len(transactions)
    
    # Initialize split payment matcher if enabled
    split_matcher = None
    if enable_split:
        split_matcher = SplitPaymentMatcher(cache_file)
        
        if verbose:
            if cache_file:
                print(f"Split payment matching enabled with file cache at {cache_file}")
            else:
                print(f"Split payment matching enabled with in-memory cache")
    
    # Initialize simplified matcher
    matcher = SimplifiedMatcher(split_matcher)
    
    for i, tx in enumerate(transactions):
        if verbose:
            print(f"Processing transaction {i+1}/{total_transactions}: {tx['payee_name']} - ${cents_to_dollars_str(milliunits_to_cents(tx['amount']))}")
        
        try:
            # Process through simplified matcher
            result = matcher.find_matches(tx, accounts_data)
            
            # Record split payment matches if applicable
            if enable_split and result.get('matches'):
                best_match = result['matches'][0]
                if best_match.get('match_method') == 'split_payment':
                    matcher.record_split_payment_match(tx['id'], best_match)
            
            results.append(result)
            
            if verbose and result.get('matches'):
                best = result['best_match']
                method = result['matches'][0]['match_method']
                print(f"  -> Matched with {best['account']} using {method} (confidence {best['confidence']:.2f})")
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
    """Calculate summary statistics from match results."""
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
            'total_amount_unmatched': 0.0,
            'strategies_used': {}
        }
    
    matched_count = 0
    partial_count = 0
    unmatched_count = 0
    total_confidence = 0.0
    total_amount_matched = 0.0
    total_amount_unmatched = 0.0
    
    # Count matches by account and strategy
    matches_by_account = {}
    strategies_used = {}
    
    for result in results:
        if result.get('matches'):
            best_match = result.get('matches', [{}])[0]
            
            # Count strategy usage
            method = best_match.get('match_method', 'unknown')
            strategies_used[method] = strategies_used.get(method, 0) + 1
            
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
        'matches_by_account': matches_by_account,
        'strategies_used': strategies_used
    }


def save_results(results: List[Dict[str, Any]], summary: Dict[str, Any], date_range: Dict[str, str], 
                output_dir: str = "results", amazon_data_date: str = None) -> str:
    """Save results to timestamped JSON file."""
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}_simplified_matching_results.json"
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
            'processing_time_seconds': None,  # Will be set by caller
            'architecture': 'simplified_3_strategy',
            'strategies': ['complete_match', 'split_payment', 'fuzzy_match']
        }
    }
    
    # Save to file
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    return filepath


def main():
    """Command-line entry point."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output_dir = os.path.join(script_dir, 'results')
    
    parser = argparse.ArgumentParser(description='Simplified Amazon Transaction Matching Batch Processor')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default=default_output_dir, help=f'Output directory (default: {default_output_dir})')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--disable-split', action='store_true', help='Disable split payment matching')
    parser.add_argument('--cache-file', help='Optional file path for persistent split payment cache (default: in-memory)')
    parser.add_argument('--ynab-data-path', default='ynab-data', help='Path to YNAB data directory')
    parser.add_argument('--amazon-data-path', default='amazon/data', help='Path to Amazon data directory')
    parser.add_argument('--accounts', nargs='*', help='Specific accounts to search (default: all)')
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    try:
        if args.verbose:
            print(f"Starting simplified batch processing for date range: {args.start} to {args.end}")
            print(f"Architecture: 3-strategy simplified system")
            if not args.disable_split:
                print("Split payment matching is ENABLED")
        
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
        
        # Extract Amazon data date
        amazon_data_date = None
        try:
            import glob
            data_dirs = glob.glob(os.path.join(args.amazon_data_path, "*_amazon_data"))
            if data_dirs:
                latest_dir = max(data_dirs, key=os.path.getmtime)
                dir_name = os.path.basename(latest_dir)
                amazon_data_date = dir_name.split('_')[0]
        except:
            amazon_data_date = "unknown"
        
        # Process batch
        if args.verbose:
            print("Processing transactions...")
        results = process_batch(transactions, accounts_data, not args.disable_split, args.cache_file, args.verbose)
        
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
        print(f"\nSimplified batch processing completed in {processing_time:.2f} seconds")
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
        
        if summary.get('strategies_used'):
            print(f"\n  Strategies Used:")
            for strategy, count in summary['strategies_used'].items():
                print(f"    {strategy}: {count} matches")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())