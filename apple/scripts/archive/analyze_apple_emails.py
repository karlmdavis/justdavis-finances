#!/usr/bin/env python3
"""
Analyze Apple-related emails to discover patterns for receipt extraction.

This script connects to an IMAP server and searches for various Apple-related
email patterns to understand:
1. Subject line variations
2. Sender addresses
3. Date ranges available
4. Total email counts

Usage:
    # Create .env file with credentials (see .env.template)
    uv run python apple/scripts/analyze_apple_emails.py
"""

import imaplib
import email
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple
import re
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)


def connect_to_imap() -> imaplib.IMAP4_SSL:
    """Connect to IMAP server using environment variables."""
    server = os.environ.get('IMAP_SERVER')
    username = os.environ.get('IMAP_USERNAME')
    password = os.environ.get('IMAP_PASSWORD')
    
    if not all([server, username, password]):
        print("Error: Missing IMAP credentials")
        print("Please create a .env file with IMAP_SERVER, IMAP_USERNAME, and IMAP_PASSWORD")
        print("See .env.template for an example.")
        sys.exit(1)
    
    print(f"Connecting to {server} as {username}...")
    
    try:
        # Try standard SSL port first
        mail = imaplib.IMAP4_SSL(server, 993)
        mail.login(username, password)
        print("Successfully connected to IMAP server")
        return mail
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)


def search_emails(mail: imaplib.IMAP4_SSL, search_criteria: str, folder: str = "INBOX") -> List[str]:
    """Search emails using given criteria."""
    try:
        mail.select(folder)
        result, data = mail.search(None, search_criteria)
        if result == 'OK':
            return data[0].split() if data[0] else []
        return []
    except Exception as e:
        print(f"Search error for criteria '{search_criteria}': {e}")
        return []


def analyze_email_headers(mail: imaplib.IMAP4_SSL, email_ids: List[str], limit: int = 20) -> Dict:
    """Analyze email headers to extract patterns."""
    subjects = []
    senders = []
    dates = []
    
    # Limit analysis to prevent overwhelming
    sample_ids = email_ids[:min(limit, len(email_ids))]
    
    for email_id in sample_ids:
        try:
            result, data = mail.fetch(email_id, '(BODY[HEADER])')
            if result == 'OK':
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = msg.get('Subject', '')
                sender = msg.get('From', '')
                date_str = msg.get('Date', '')
                
                subjects.append(subject)
                senders.append(sender)
                
                # Parse date
                try:
                    date_tuple = email.utils.parsedate_to_datetime(date_str)
                    dates.append(date_tuple)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error fetching email {email_id}: {e}")
    
    return {
        'subjects': subjects,
        'senders': senders,
        'dates': dates
    }


def main():
    """Main analysis function."""
    print("=" * 60)
    print("Apple Email Pattern Discovery")
    print("=" * 60)
    
    mail = connect_to_imap()
    
    # Search patterns to try
    search_patterns = [
        ('FROM "apple.com"', 'Emails from apple.com domain'),
        ('SUBJECT "receipt"', 'Emails with "receipt" in subject'),
        ('SUBJECT "Your receipt from Apple"', 'Standard Apple receipt subject'),
        ('SUBJECT "Invoice from Apple"', 'Apple invoice emails'),
        ('FROM "no_reply@email.apple.com"', 'From no_reply address'),
        ('FROM "do_not_reply@apple.com"', 'From do_not_reply address'),
        ('SUBJECT "Your subscription"', 'Subscription-related emails'),
        ('SUBJECT "Order confirmation"', 'Order confirmation emails'),
    ]
    
    results = {}
    all_email_ids = set()
    
    print("\nSearching for Apple email patterns...")
    print("-" * 40)
    
    for criteria, description in search_patterns:
        email_ids = search_emails(mail, criteria)
        count = len(email_ids)
        results[criteria] = {
            'description': description,
            'count': count,
            'ids': email_ids
        }
        all_email_ids.update(email_ids)
        print(f"{description:40} : {count:5} emails")
    
    print(f"\nTotal unique Apple-related emails found: {len(all_email_ids)}")
    
    # Analyze the most promising pattern
    receipt_pattern = 'SUBJECT "Your receipt from Apple"'
    if results[receipt_pattern]['count'] > 0:
        print(f"\nAnalyzing '{receipt_pattern}' emails in detail...")
        print("-" * 40)
        
        email_ids = results[receipt_pattern]['ids']
        analysis = analyze_email_headers(mail, email_ids, limit=20)
        
        # Extract unique patterns
        unique_subjects = list(set(analysis['subjects']))
        unique_senders = list(set(analysis['senders']))
        
        print(f"\nUnique subject lines found ({len(unique_subjects)}):")
        for subject in unique_subjects[:10]:
            print(f"  - {subject}")
        
        print(f"\nUnique senders found ({len(unique_senders)}):")
        for sender in unique_senders[:10]:
            print(f"  - {sender}")
        
        if analysis['dates']:
            dates_sorted = sorted(analysis['dates'])
            earliest = dates_sorted[0]
            latest = dates_sorted[-1]
            print(f"\nDate range in sample:")
            print(f"  Earliest: {earliest.strftime('%Y-%m-%d')}")
            print(f"  Latest: {latest.strftime('%Y-%m-%d')}")
    
    # Try broader Apple search
    print("\n" + "=" * 60)
    print("Broader Apple Email Search")
    print("=" * 60)
    
    # Search for all Apple emails in last 5 years
    five_years_ago = (datetime.now() - timedelta(days=365*5)).strftime("%d-%b-%Y")
    broad_search = f'(FROM "apple.com" SINCE {five_years_ago})'
    
    print(f"\nSearching: {broad_search}")
    broad_ids = search_emails(mail, broad_search)
    print(f"Found {len(broad_ids)} total Apple emails since {five_years_ago}")
    
    if len(broad_ids) > 0:
        # Sample analysis of broader set
        print("\nSampling broader Apple email set...")
        sample_size = min(50, len(broad_ids))
        sample_ids = broad_ids[::max(1, len(broad_ids)//sample_size)]  # Even distribution
        
        analysis = analyze_email_headers(mail, sample_ids, limit=50)
        
        # Categorize subjects
        subject_patterns = defaultdict(int)
        for subject in analysis['subjects']:
            if 'receipt' in subject.lower():
                subject_patterns['Receipt'] += 1
            elif 'invoice' in subject.lower():
                subject_patterns['Invoice'] += 1
            elif 'subscription' in subject.lower():
                subject_patterns['Subscription'] += 1
            elif 'order' in subject.lower():
                subject_patterns['Order'] += 1
            elif 'purchase' in subject.lower():
                subject_patterns['Purchase'] += 1
            else:
                subject_patterns['Other'] += 1
        
        print("\nEmail categories in sample:")
        for category, count in sorted(subject_patterns.items(), key=lambda x: x[1], reverse=True):
            print(f"  {category:15} : {count:3} emails")
    
    # Save findings
    output_file = 'apple/docs/email_analysis.md'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("# Apple Email Analysis Results\n\n")
        f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Search Pattern Results\n\n")
        f.write("| Search Pattern | Description | Count |\n")
        f.write("|----------------|-------------|-------|\n")
        for criteria, data in results.items():
            f.write(f"| `{criteria}` | {data['description']} | {data['count']} |\n")
        
        f.write(f"\n## Summary\n\n")
        f.write(f"- Total unique Apple emails found: {len(all_email_ids)}\n")
        f.write(f"- Recommended search pattern: `SUBJECT \"Your receipt from Apple\"`\n")
        f.write(f"- Alternative patterns to consider:\n")
        f.write(f"  - `FROM \"apple.com\"` for broader search\n")
        f.write(f"  - `FROM \"no_reply@email.apple.com\"` for specific sender\n")
        
        if len(broad_ids) > 0:
            f.write(f"\n## Historical Data\n\n")
            f.write(f"- Emails since {five_years_ago}: {len(broad_ids)}\n")
            f.write(f"- Categories found in sample:\n")
            for category, count in sorted(subject_patterns.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  - {category}: {count}\n")
    
    print(f"\nAnalysis complete! Results saved to {output_file}")
    
    mail.logout()


if __name__ == "__main__":
    main()