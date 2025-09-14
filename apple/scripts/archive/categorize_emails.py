#!/usr/bin/env python3
"""
Categorize Apple emails by type (receipts vs other notifications).

This script analyzes the fetched emails to separate actual purchase receipts
from subscription notifications, download confirmations, etc.
"""

import os
import email
from pathlib import Path
from collections import defaultdict
import json
from datetime import datetime


def categorize_emails(input_dir: str):
    """Categorize emails by their type based on subject and content."""
    
    input_path = Path(input_dir)
    eml_files = list(input_path.glob("*.eml"))
    
    categories = defaultdict(list)
    
    print(f"Analyzing {len(eml_files)} emails...")
    print("-" * 40)
    
    for eml_file in eml_files:
        try:
            with open(eml_file, 'rb') as f:
                msg = email.message_from_bytes(f.read())
            
            subject = msg.get('Subject', '')
            date_str = msg.get('Date', '')
            
            # Parse date
            try:
                date_obj = email.utils.parsedate_to_datetime(date_str)
                date_formatted = date_obj.strftime('%Y-%m-%d')
            except:
                date_formatted = 'unknown'
            
            # Categorize based on subject
            email_info = {
                'file': eml_file.name,
                'subject': subject,
                'date': date_formatted
            }
            
            # Determine category
            if 'Your receipt from Apple' in subject:
                categories['purchase_receipts'].append(email_info)
            elif 'Your recent download' in subject:
                categories['download_notifications'].append(email_info)
            elif 'Subscription Confirmation' in subject or 'Your Subscription Confirmation' in subject:
                categories['subscription_confirmations'].append(email_info)
            elif 'Your Subscription Renewal' in subject:
                categories['subscription_renewals'].append(email_info)
            elif 'Your Subscription is Expiring' in subject:
                categories['subscription_expiring'].append(email_info)
            elif 'Your Subscription Price Increase' in subject:
                categories['price_increase_notices'].append(email_info)
            else:
                categories['other'].append(email_info)
                
        except Exception as e:
            print(f"Error processing {eml_file.name}: {e}")
    
    # Print summary
    print("\nEmail Categories Summary:")
    print("=" * 50)
    
    total = 0
    for category, emails in sorted(categories.items()):
        count = len(emails)
        total += count
        print(f"{category:30} : {count:4} emails")
    
    print("-" * 50)
    print(f"{'Total':30} : {total:4} emails")
    
    # Show date ranges for purchase receipts
    if 'purchase_receipts' in categories:
        receipts = categories['purchase_receipts']
        dates = [r['date'] for r in receipts if r['date'] != 'unknown']
        if dates:
            dates.sort()
            print(f"\nPurchase receipts date range:")
            print(f"  Earliest: {dates[0]}")
            print(f"  Latest: {dates[-1]}")
    
    # Save categorization results
    output_file = input_path.parent / 'email_categories.json'
    output_data = {
        'analysis_date': datetime.now().isoformat(),
        'total_emails': total,
        'categories': {k: v for k, v in categories.items()}
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nCategorization saved to: {output_file}")
    
    # Create a list of just receipt files
    if 'purchase_receipts' in categories:
        receipt_files = [r['file'] for r in categories['purchase_receipts']]
        receipt_list_file = input_path.parent / 'receipt_files.txt'
        with open(receipt_list_file, 'w') as f:
            for file in sorted(receipt_files):
                f.write(f"{file}\n")
        print(f"Receipt file list saved to: {receipt_list_file}")
        print(f"\nFound {len(receipt_files)} actual purchase receipts to process")
    
    return categories


def main():
    """Main entry point."""
    # Find most recent email directory
    data_dir = Path('apple/data')
    email_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir() and 'apple_emails' in d.name])
    
    if not email_dirs:
        print("No email directories found. Run fetch_receipt_emails.py first.")
        return
    
    input_dir = email_dirs[-1]
    print(f"Using email directory: {input_dir}")
    print("=" * 50)
    
    categorize_emails(input_dir)


if __name__ == "__main__":
    main()