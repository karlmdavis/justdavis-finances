#!/usr/bin/env python3
"""
Analyze Apple receipt email formats to identify variations over time.

This script loads .eml files, extracts receipt HTML, and analyzes structure
to identify different format versions and when they changed.

Usage:
    uv run python apple/scripts/analyze_receipt_formats.py --input apple/data/YYYY-MM-DD_apple_emails
"""

import os
import sys
import email
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup
import re


class ReceiptFormatAnalyzer:
    """Analyzes Apple receipt formats to identify variations."""
    
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.formats_found = {}
        self.format_examples = {}
        self.format_timeline = defaultdict(list)
        
    def load_eml_files(self) -> List[Path]:
        """Load all .eml files from input directory."""
        eml_files = list(self.input_dir.glob("*.eml"))
        print(f"Found {len(eml_files)} .eml files to analyze")
        return sorted(eml_files)
    
    def extract_html_from_email(self, eml_path: Path) -> Optional[str]:
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
    
    def extract_receipt_date(self, msg_path: Path) -> Optional[datetime]:
        """Extract date from email."""
        try:
            with open(msg_path, 'rb') as f:
                msg = email.message_from_bytes(f.read())
            date_str = msg.get('Date', '')
            if date_str:
                return email.utils.parsedate_to_datetime(date_str)
        except:
            pass
        return None
    
    def analyze_html_structure(self, html: str) -> Dict:
        """Analyze HTML structure to identify format characteristics."""
        soup = BeautifulSoup(html, 'lxml')
        
        structure = {
            'has_tables': len(soup.find_all('table')) > 0,
            'table_count': len(soup.find_all('table')),
            'has_divs': len(soup.find_all('div')) > 0,
            'div_count': len(soup.find_all('div')),
            'has_order_id': False,
            'has_receipt_label': False,
            'has_items_table': False,
            'has_total_row': False,
            'css_classes': set(),
            'id_attributes': set(),
            'key_elements': []
        }
        
        # Look for order ID patterns
        order_id_patterns = [
            r'Order ID[:\s]+([A-Z0-9]+)',
            r'Order Number[:\s]+([A-Z0-9]+)',
            r'Receipt[:\s]+([A-Z0-9]+)',
        ]
        
        text_content = soup.get_text()
        for pattern in order_id_patterns:
            if re.search(pattern, text_content, re.IGNORECASE):
                structure['has_order_id'] = True
                break
        
        # Look for receipt label
        if 'Your receipt from Apple' in text_content:
            structure['has_receipt_label'] = True
        
        # Look for items table (various possible indicators)
        for table in soup.find_all('table'):
            table_text = table.get_text().lower()
            if any(word in table_text for word in ['subtotal', 'tax', 'total', 'price', 'amount']):
                structure['has_items_table'] = True
                structure['has_total_row'] = 'total' in table_text
                break
        
        # Collect CSS classes and IDs for fingerprinting
        for elem in soup.find_all(True):
            if elem.get('class'):
                structure['css_classes'].update(elem.get('class'))
            if elem.get('id'):
                structure['id_attributes'].add(elem.get('id'))
        
        # Convert sets to lists for JSON serialization
        structure['css_classes'] = list(structure['css_classes'])
        structure['id_attributes'] = list(structure['id_attributes'])
        
        # Identify key structural elements
        if soup.find('table', {'class': 'receipt'}):
            structure['key_elements'].append('receipt_table_class')
        if soup.find('div', {'class': 'apple-receipt'}):
            structure['key_elements'].append('apple_receipt_div')
        if soup.find('td', string=re.compile(r'Order ID', re.IGNORECASE)):
            structure['key_elements'].append('order_id_cell')
        
        return structure
    
    def generate_format_signature(self, structure: Dict) -> str:
        """Generate a signature to identify unique formats."""
        # Create signature based on key structural elements
        sig_parts = [
            f"tables:{structure['table_count']}",
            f"divs:{structure['div_count']}",
            f"order:{structure['has_order_id']}",
            f"items:{structure['has_items_table']}",
            f"total:{structure['has_total_row']}",
        ]
        
        # Add key elements to signature
        sig_parts.extend(structure['key_elements'])
        
        # Create hash of signature
        sig_string = "|".join(sorted(sig_parts))
        return hashlib.md5(sig_string.encode()).hexdigest()[:12]
    
    def analyze_all_receipts(self):
        """Analyze all receipt emails."""
        eml_files = self.load_eml_files()
        
        if not eml_files:
            print("No .eml files found to analyze")
            return
        
        print("\nAnalyzing receipt formats...")
        print("-" * 40)
        
        # Sample emails across time periods
        # Take every Nth email to get good time distribution
        sample_size = min(100, len(eml_files))
        step = max(1, len(eml_files) // sample_size)
        sampled_files = eml_files[::step]
        
        print(f"Sampling {len(sampled_files)} emails from {len(eml_files)} total")
        
        for i, eml_path in enumerate(sampled_files, 1):
            print(f"[{i}/{len(sampled_files)}] Analyzing {eml_path.name}...", end='')
            
            # Extract HTML
            html = self.extract_html_from_email(eml_path)
            if not html:
                print(" ✗ (no HTML)")
                continue
            
            # Get receipt date
            receipt_date = self.extract_receipt_date(eml_path)
            
            # Analyze structure
            structure = self.analyze_html_structure(html)
            
            # Generate format signature
            signature = self.generate_format_signature(structure)
            
            # Store format info
            if signature not in self.formats_found:
                self.formats_found[signature] = {
                    'signature': signature,
                    'structure': structure,
                    'first_seen': receipt_date,
                    'last_seen': receipt_date,
                    'count': 0,
                    'example_file': str(eml_path.name)
                }
                # Save example
                self.format_examples[signature] = (eml_path, html)
            
            # Update format info
            format_info = self.formats_found[signature]
            format_info['count'] += 1
            
            if receipt_date:
                if receipt_date < format_info['first_seen']:
                    format_info['first_seen'] = receipt_date
                if receipt_date > format_info['last_seen']:
                    format_info['last_seen'] = receipt_date
                
                # Track timeline
                year_month = receipt_date.strftime('%Y-%m')
                self.format_timeline[year_month].append(signature)
            
            print(" ✓")
        
        self.save_analysis_results()
        self.save_format_examples()
    
    def save_analysis_results(self):
        """Save analysis results to documentation."""
        output_file = Path('apple/docs/receipt_formats.md')
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write("# Apple Receipt Format Analysis\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"## Summary\n\n")
            f.write(f"- Formats identified: {len(self.formats_found)}\n")
            f.write(f"- Emails analyzed: {sum(fmt['count'] for fmt in self.formats_found.values())}\n\n")
            
            f.write("## Format Versions\n\n")
            
            # Sort formats by first seen date
            sorted_formats = sorted(
                self.formats_found.values(),
                key=lambda x: x['first_seen'] if x['first_seen'] else datetime.min
            )
            
            for i, fmt in enumerate(sorted_formats, 1):
                f.write(f"### Format {i} (Signature: {fmt['signature']})\n\n")
                
                if fmt['first_seen']:
                    f.write(f"- **First seen:** {fmt['first_seen'].strftime('%Y-%m-%d')}\n")
                    f.write(f"- **Last seen:** {fmt['last_seen'].strftime('%Y-%m-%d')}\n")
                f.write(f"- **Occurrences:** {fmt['count']}\n")
                f.write(f"- **Example file:** {fmt['example_file']}\n\n")
                
                f.write("**Structure characteristics:**\n")
                structure = fmt['structure']
                f.write(f"- Tables: {structure['table_count']}\n")
                f.write(f"- Divs: {structure['div_count']}\n")
                f.write(f"- Has Order ID: {structure['has_order_id']}\n")
                f.write(f"- Has Items Table: {structure['has_items_table']}\n")
                f.write(f"- Has Total Row: {structure['has_total_row']}\n")
                
                if structure['key_elements']:
                    f.write(f"- Key elements: {', '.join(structure['key_elements'])}\n")
                
                f.write("\n")
            
            # Timeline analysis
            f.write("## Format Timeline\n\n")
            f.write("| Year-Month | Format Signatures Used |\n")
            f.write("|------------|------------------------|\n")
            
            for year_month in sorted(self.format_timeline.keys()):
                signatures = set(self.format_timeline[year_month])
                f.write(f"| {year_month} | {', '.join(signatures)} |\n")
        
        print(f"\nFormat analysis saved to {output_file}")
    
    def save_format_examples(self):
        """Save example emails for each format."""
        examples_dir = Path('apple/examples')
        examples_dir.mkdir(exist_ok=True)
        
        for signature, (eml_path, html) in self.format_examples.items():
            # Save example email
            example_eml = examples_dir / f"format_{signature}_example.eml"
            with open(eml_path, 'rb') as src:
                with open(example_eml, 'wb') as dst:
                    dst.write(src.read())
            
            # Save extracted HTML for inspection
            example_html = examples_dir / f"format_{signature}_example.html"
            with open(example_html, 'w', encoding='utf-8') as f:
                f.write(html)
            
            print(f"Saved example for format {signature}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze Apple receipt email formats')
    parser.add_argument(
        '--input',
        type=str,
        help='Input directory containing .eml files',
        required=False
    )
    
    args = parser.parse_args()
    
    # Find input directory
    if args.input:
        input_dir = Path(args.input)
    else:
        # Find most recent email directory
        data_dir = Path('apple/data')
        if not data_dir.exists():
            print("Error: apple/data directory not found")
            print("Please run fetch_receipt_emails.py first")
            sys.exit(1)
        
        email_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir() and 'apple_emails' in d.name])
        if not email_dirs:
            print("Error: No email directories found in apple/data")
            print("Please run fetch_receipt_emails.py first")
            sys.exit(1)
        
        input_dir = email_dirs[-1]  # Use most recent
        print(f"Using most recent email directory: {input_dir}")
    
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print("Apple Receipt Format Analyzer")
    print("=" * 60)
    
    analyzer = ReceiptFormatAnalyzer(input_dir)
    analyzer.analyze_all_receipts()
    
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()