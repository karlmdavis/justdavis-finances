#!/usr/bin/env python3
"""
Analyze only actual Apple receipt email formats (excluding other notifications).
"""

import os
import sys
import email
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup
import hashlib


def load_receipt_list(data_dir: Path) -> list:
    """Load list of actual receipt files."""
    receipt_list_file = data_dir.parent / 'receipt_files.txt'
    if not receipt_list_file.exists():
        print("Receipt file list not found. Run categorize_emails.py first.")
        sys.exit(1)
    
    with open(receipt_list_file, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def extract_html_from_email(eml_path: Path) -> str:
    """Extract HTML content from email."""
    try:
        with open(eml_path, 'rb') as f:
            msg = email.message_from_bytes(f.read())
        
        # Extract HTML part
        html_content = None
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    html_content = part.get_payload(decode=True)
                    break
        else:
            if msg.get_content_type() == 'text/html':
                html_content = msg.get_payload(decode=True)
        
        if html_content:
            # Try to decode with various encodings
            for encoding in ['utf-8', 'iso-8859-1', 'windows-1252']:
                try:
                    return html_content.decode(encoding)
                except:
                    continue
        
        return None
        
    except Exception as e:
        print(f"Error loading {eml_path}: {e}")
        return None


def analyze_receipt_structure(html: str) -> dict:
    """Analyze receipt HTML structure for key data fields."""
    soup = BeautifulSoup(html, 'lxml')
    
    structure = {
        'has_order_id': False,
        'has_document_no': False,
        'has_apple_id': False,
        'has_billed_to': False,
        'has_items_table': False,
        'has_subtotal': False,
        'has_tax': False,
        'has_total': False,
        'table_count': len(soup.find_all('table')),
        'format_signature': ''
    }
    
    text_content = soup.get_text()
    
    # Check for key fields
    if 'Order ID' in text_content:
        structure['has_order_id'] = True
    if 'Document No.' in text_content or 'Invoice No.' in text_content:
        structure['has_document_no'] = True
    if 'Apple ID' in text_content:
        structure['has_apple_id'] = True
    if 'Billed To' in text_content or 'Bill To' in text_content:
        structure['has_billed_to'] = True
    if 'Subtotal' in text_content:
        structure['has_subtotal'] = True
    if 'Tax' in text_content and 'Subtotal' in text_content:
        structure['has_tax'] = True
    if 'Total' in text_content or 'TOTAL' in text_content:
        structure['has_total'] = True
    
    # Check for items table
    for table in soup.find_all('table'):
        table_text = table.get_text().lower()
        if any(word in table_text for word in ['app', 'subscription', 'purchase', 'item']):
            structure['has_items_table'] = True
            break
    
    # Create format signature
    sig_parts = [
        f"tables:{structure['table_count']}",
        f"order:{structure['has_order_id']}",
        f"doc:{structure['has_document_no']}",
        f"items:{structure['has_items_table']}",
        f"total:{structure['has_total']}"
    ]
    sig_string = "|".join(sig_parts)
    structure['format_signature'] = hashlib.md5(sig_string.encode()).hexdigest()[:8]
    
    return structure


def main():
    """Main analysis function."""
    # Find most recent email directory
    data_dir = Path('apple/data')
    email_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir() and 'apple_emails' in d.name])
    
    if not email_dirs:
        print("No email directories found.")
        sys.exit(1)
    
    email_dir = email_dirs[-1]
    print(f"Using email directory: {email_dir}")
    
    # Load receipt file list
    receipt_files = load_receipt_list(email_dir)
    print(f"Analyzing {len(receipt_files)} actual purchase receipts...")
    print("-" * 50)
    
    formats = defaultdict(lambda: {'count': 0, 'examples': [], 'first_date': None, 'last_date': None})
    
    # Sample receipts for analysis
    sample_size = min(100, len(receipt_files))
    step = max(1, len(receipt_files) // sample_size)
    sampled_files = receipt_files[::step]
    
    for i, filename in enumerate(sampled_files, 1):
        filepath = email_dir / filename
        
        print(f"[{i}/{len(sampled_files)}] Analyzing {filename[:50]}...", end='')
        
        html = extract_html_from_email(filepath)
        if not html:
            print(" ✗ (no HTML)")
            continue
        
        structure = analyze_receipt_structure(html)
        sig = structure['format_signature']
        
        # Extract date from filename
        try:
            date_str = filename.split('_')[0]
            date_obj = datetime.strptime(date_str, '%Y%m%d')
        except:
            date_obj = None
        
        # Update format info
        formats[sig]['count'] += 1
        formats[sig]['structure'] = structure
        if len(formats[sig]['examples']) < 3:
            formats[sig]['examples'].append(filename)
        
        if date_obj:
            if not formats[sig]['first_date'] or date_obj < formats[sig]['first_date']:
                formats[sig]['first_date'] = date_obj
            if not formats[sig]['last_date'] or date_obj > formats[sig]['last_date']:
                formats[sig]['last_date'] = date_obj
        
        print(" ✓")
    
    # Print results
    print("\n" + "=" * 50)
    print("Receipt Format Analysis Results")
    print("=" * 50)
    
    sorted_formats = sorted(formats.items(), key=lambda x: x[1]['count'], reverse=True)
    
    for i, (sig, info) in enumerate(sorted_formats, 1):
        print(f"\nFormat {i} (signature: {sig})")
        print(f"  Count: {info['count']} receipts")
        if info['first_date']:
            print(f"  Date range: {info['first_date'].strftime('%Y-%m-%d')} to {info['last_date'].strftime('%Y-%m-%d')}")
        
        s = info['structure']
        print(f"  Structure:")
        print(f"    - Tables: {s['table_count']}")
        print(f"    - Has Order ID: {s['has_order_id']}")
        print(f"    - Has Document No: {s['has_document_no']}")
        print(f"    - Has Apple ID: {s['has_apple_id']}")
        print(f"    - Has Items Table: {s['has_items_table']}")
        print(f"    - Has Subtotal: {s['has_subtotal']}")
        print(f"    - Has Tax: {s['has_tax']}")
        print(f"    - Has Total: {s['has_total']}")
        print(f"  Examples:")
        for ex in info['examples'][:2]:
            print(f"    - {ex[:60]}...")
    
    print(f"\nTotal unique receipt formats found: {len(formats)}")
    
    # Save analysis
    output = {
        'analysis_date': datetime.now().isoformat(),
        'total_receipts_analyzed': len(sampled_files),
        'unique_formats': len(formats),
        'formats': [
            {
                'signature': sig,
                'count': info['count'],
                'date_range': {
                    'first': info['first_date'].isoformat() if info['first_date'] else None,
                    'last': info['last_date'].isoformat() if info['last_date'] else None
                },
                'structure': info['structure'],
                'examples': info['examples']
            }
            for sig, info in sorted_formats
        ]
    }
    
    output_file = Path('apple/data/receipt_format_analysis.json')
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nAnalysis saved to: {output_file}")


if __name__ == "__main__":
    main()