#!/usr/bin/env python3
"""
Extract metadata from Apple receipt emails to understand format patterns.

This script analyzes both plain text and HTML versions of receipt emails to extract
metadata that might help identify the real structural differences vs. purchase type
differences.
"""

import os
import sys
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_script_dir() -> Path:
    """Get the directory containing this script."""
    return Path(__file__).parent

def get_extracted_content_dir() -> Path:
    """Get the extracted content directory."""
    script_dir = get_script_dir()
    data_dir = script_dir.parent / "data"
    
    # Find the most recent email data directory
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    if not email_dirs:
        raise FileNotFoundError("No Apple email data directories found")
    
    # Return the most recent one with extracted_content
    email_dir = max(email_dirs)
    return email_dir / "extracted_content"

def parse_plain_text_receipt(content: str) -> Dict[str, Any]:
    """Parse plain text receipt content to extract metadata."""
    metadata = {
        'has_plain_text': True,
        'apple_id': None,
        'order_id': None, 
        'document_number': None,
        'receipt_date': None,
        'total_amount': None,
        'subtotal_amount': None,
        'tax_amount': None,
        'has_subtotal': False,
        'has_tax': False,
        'items': [],
        'item_count': 0,
        'purchase_categories': [],
        'sections': [],
        'is_subscription_renewal': False,
        'is_subscription_confirmation': False,
    }
    
    lines = content.split('\n')
    
    # Extract basic info
    for line in lines:
        line = line.strip()
        
        # Apple ID
        if not metadata['apple_id'] and '@' in line and '.com' in line:
            # Look for email pattern
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
            if email_match:
                metadata['apple_id'] = email_match.group()
        
        # Order ID
        order_match = re.match(r'ORDER ID:\s+(\w+)', line)
        if order_match:
            metadata['order_id'] = order_match.group(1)
        
        # Document number
        doc_match = re.match(r'DOCUMENT NO\.:\s+(\d+)', line)
        if doc_match:
            metadata['document_number'] = doc_match.group(1)
        
        # Date
        date_match = re.match(r'DATE:\s+(.+)', line)
        if date_match:
            metadata['receipt_date'] = date_match.group(1).strip()
        
        # Amounts
        total_match = re.match(r'TOTAL:\s+\$([0-9,.]+)', line)
        if total_match:
            metadata['total_amount'] = float(total_match.group(1).replace(',', ''))
        
        subtotal_match = re.search(r'Subtotal\s+\$([0-9,.]+)', line)
        if subtotal_match:
            metadata['subtotal_amount'] = float(subtotal_match.group(1).replace(',', ''))
            metadata['has_subtotal'] = True
        
        tax_match = re.search(r'Tax\s+\$([0-9,.]+)', line)
        if tax_match:
            metadata['tax_amount'] = float(tax_match.group(1).replace(',', ''))
            metadata['has_tax'] = True
    
    # Identify sections and items
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Section headers
        if line in ['App Store', 'Books', 'Music', 'Movies', 'TV Shows', 'iTunes Store']:
            current_section = line
            if current_section not in metadata['sections']:
                metadata['sections'].append(current_section)
            continue
        
        # Skip known non-item lines
        if any(skip in line for skip in ['Apple Receipt', 'APPLE ID', 'BILLED TO', 'ORDER ID:', 'DOCUMENT NO.:', 'DATE:', 'TOTAL:', 'Get help', 'Learn how', 'Apple respects', 'Terms of Sale']):
            continue
        
        # Look for item lines (heuristic: line with price at end)
        price_match = re.search(r'\$([0-9,.]+)$', line)
        if price_match and current_section:
            item_name = re.sub(r'\s+\$[0-9,.]+$', '', line).strip()
            if item_name and len(item_name) > 2:  # Avoid false matches
                metadata['items'].append({
                    'name': item_name,
                    'section': current_section,
                    'price': float(price_match.group(1).replace(',', ''))
                })
    
    metadata['item_count'] = len(metadata['items'])
    metadata['purchase_categories'] = list(set(metadata['sections']))
    
    return metadata

def parse_html_receipt(content: str) -> Dict[str, Any]:
    """Parse HTML receipt content to extract metadata."""
    metadata = {
        'has_plain_text': False,
        'apple_id': None,
        'order_id': None,
        'document_number': None,
        'receipt_date': None,
        'total_amount': None,
        'subtotal_amount': None,
        'tax_amount': None,
        'has_subtotal': False,
        'has_tax': False,
        'items': [],
        'item_count': 0,
        'purchase_categories': [],
        'sections': [],
        'is_subscription_renewal': False,
        'is_subscription_confirmation': False,
        'has_custom_classes': False,
        'has_aapl_classes': False,
        'table_count': 0,
        'div_count': 0,
        'format_indicators': [],
    }
    
    try:
        soup = BeautifulSoup(content, 'lxml')
        
        # Count structural elements
        metadata['table_count'] = len(soup.find_all('table'))
        metadata['div_count'] = len(soup.find_all('div'))
        
        # Check for format indicators
        if soup.find(class_=re.compile(r'custom-')):
            metadata['has_custom_classes'] = True
            metadata['format_indicators'].append('modern_css')
        
        if soup.find(class_=re.compile(r'aapl-')):
            metadata['has_aapl_classes'] = True
            metadata['format_indicators'].append('legacy_table')
        
        # Extract text content for basic parsing
        text_content = soup.get_text()
        
        # Apple ID
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text_content)
        if email_match:
            metadata['apple_id'] = email_match.group()
        
        # Order ID - try multiple patterns
        order_patterns = [
            r'Order ID:\s*(\w+)',
            r'ORDER ID\s*(\w+)',
            r'Order:\s*(\w+)',
        ]
        for pattern in order_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                metadata['order_id'] = match.group(1)
                break
        
        # Document number - try multiple patterns  
        doc_patterns = [
            r'Document:\s*(\d+)',
            r'DOCUMENT NO\.:\s*(\d+)',
            r'Document Number:\s*(\d+)',
        ]
        for pattern in doc_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                metadata['document_number'] = match.group(1)
                break
        
        # Extract financial amounts
        subtotal_match = re.search(r'Subtotal.*?\$([0-9,.]+)', text_content, re.IGNORECASE)
        if subtotal_match:
            metadata['subtotal_amount'] = float(subtotal_match.group(1).replace(',', ''))
            metadata['has_subtotal'] = True
        
        tax_match = re.search(r'Tax.*?\$([0-9,.]+)', text_content, re.IGNORECASE)
        if tax_match:
            metadata['tax_amount'] = float(tax_match.group(1).replace(',', ''))
            metadata['has_tax'] = True
        
        # Total - try multiple patterns
        total_patterns = [
            r'TOTAL.*?\$([0-9,.]+)',
            r'Total.*?\$([0-9,.]+)',
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                metadata['total_amount'] = float(match.group(1).replace(',', ''))
                break
        
        # Look for section headers
        section_headers = ['App Store', 'Books', 'Music', 'Movies', 'TV Shows', 'iTunes Store', 'Apple One']
        for header in section_headers:
            if header in text_content:
                metadata['sections'].append(header)
        
        metadata['purchase_categories'] = metadata['sections']
        
        # Count items (rough heuristic)
        price_matches = re.findall(r'\$([0-9,.]+)', text_content)
        if price_matches:
            # Exclude subtotal, tax, total from item count estimate
            item_prices = [p for p in price_matches if float(p.replace(',', '')) not in [
                metadata.get('subtotal_amount', -1),
                metadata.get('tax_amount', -1), 
                metadata.get('total_amount', -1)
            ]]
            metadata['item_count'] = len(item_prices)
        
    except Exception as e:
        logger.warning(f"Failed to parse HTML: {e}")
    
    return metadata

def determine_purchase_type(filename: str, metadata: Dict[str, Any]) -> str:
    """Determine the type of purchase based on filename and content."""
    filename_lower = filename.lower()
    
    if 'subscription renewal' in filename_lower:
        metadata['is_subscription_renewal'] = True
        return 'subscription_renewal'
    elif 'subscription confirmation' in filename_lower:
        metadata['is_subscription_confirmation'] = True  
        return 'subscription_confirmation'
    elif 'recent download' in filename_lower:
        return 'download_notification'
    elif 'receipt from apple' in filename_lower:
        return 'purchase_receipt'
    elif 'price increase' in filename_lower:
        return 'price_increase_notice'
    elif 'expiring' in filename_lower:
        return 'expiration_notice'
    else:
        return 'unknown'

def extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract date from filename in YYYYMMDD format."""
    match = re.match(r'^(\d{8})_', filename)
    if match:
        date_str = match.group(1)
        try:
            # Convert YYYYMMDD to YYYY-MM-DD
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except:
            pass
    return None

def process_receipt_file(base_name: str, content_dir: Path) -> Dict[str, Any]:
    """Process a single receipt and extract metadata."""
    logger.info(f"Processing {base_name}")
    
    metadata = {
        'base_name': base_name,
        'file_date': extract_date_from_filename(base_name),
        'purchase_type': None,
        'has_plain_text': False,
        'has_html': False,
        'parsing_source': None,
        'errors': []
    }
    
    # Determine purchase type from filename
    metadata['purchase_type'] = determine_purchase_type(base_name, metadata)
    
    # Try plain text first (more reliable)
    txt_path = content_dir / f"{base_name}.txt"
    if txt_path.exists():
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                txt_content = f.read()
            
            txt_metadata = parse_plain_text_receipt(txt_content)
            metadata.update(txt_metadata)
            metadata['parsing_source'] = 'plain_text'
            
        except Exception as e:
            error_msg = f"Failed to parse plain text: {str(e)}"
            metadata['errors'].append(error_msg)
            logger.warning(f"  {error_msg}")
    
    # Fall back to HTML if no plain text or plain text parsing failed
    if not metadata.get('apple_id') or metadata['parsing_source'] != 'plain_text':
        simple_html_path = content_dir / f"{base_name}-formatted-simple.html"
        if simple_html_path.exists():
            try:
                with open(simple_html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                html_metadata = parse_html_receipt(html_content)
                # Merge HTML metadata, keeping plain text values if they exist
                for key, value in html_metadata.items():
                    if key not in metadata or metadata[key] is None:
                        metadata[key] = value
                
                if metadata['parsing_source'] != 'plain_text':
                    metadata['parsing_source'] = 'html'
                    
            except Exception as e:
                error_msg = f"Failed to parse HTML: {str(e)}"
                metadata['errors'].append(error_msg)
                logger.warning(f"  {error_msg}")
    
    return metadata

def main():
    """Main function to extract metadata from all receipts."""
    try:
        # Get directories
        content_dir = get_extracted_content_dir()
        logger.info(f"Using extracted content directory: {content_dir}")
        
        # Find all base names (receipts) by looking for .html files
        html_files = list(content_dir.glob("*.html"))
        base_names = set()
        for html_file in html_files:
            if not html_file.name.endswith('-formatted.html') and not html_file.name.endswith('-formatted-simple.html'):
                base_names.add(html_file.stem)
        
        base_names = sorted(base_names)
        logger.info(f"Found {len(base_names)} receipt files to process")
        
        # Process each receipt
        all_metadata = []
        for base_name in base_names:
            metadata = process_receipt_file(base_name, content_dir)
            all_metadata.append(metadata)
        
        # Save results
        output_path = content_dir / "receipt_metadata.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, default=str)
        
        logger.info(f"Saved metadata for {len(all_metadata)} receipts to: {output_path}")
        
        # Summary statistics
        logger.info("\n" + "="*50)
        logger.info("METADATA EXTRACTION SUMMARY")
        logger.info("="*50)
        
        total_files = len(all_metadata)
        plain_text_parsed = sum(1 for m in all_metadata if m['parsing_source'] == 'plain_text')
        html_parsed = sum(1 for m in all_metadata if m['parsing_source'] == 'html')
        with_errors = sum(1 for m in all_metadata if m['errors'])
        
        logger.info(f"Total files processed: {total_files}")
        logger.info(f"Parsed from plain text: {plain_text_parsed}")
        logger.info(f"Parsed from HTML: {html_parsed}")
        logger.info(f"Files with errors: {with_errors}")
        
        # Purchase type breakdown
        purchase_types = {}
        for metadata in all_metadata:
            ptype = metadata.get('purchase_type', 'unknown')
            purchase_types[ptype] = purchase_types.get(ptype, 0) + 1
        
        logger.info("\nPurchase type breakdown:")
        for ptype, count in sorted(purchase_types.items()):
            logger.info(f"  {ptype}: {count}")
        
        # Format indicators breakdown
        format_counts = {
            'has_custom_classes': 0,
            'has_aapl_classes': 0, 
            'both': 0,
            'neither': 0
        }
        
        for metadata in all_metadata:
            has_custom = metadata.get('has_custom_classes', False)
            has_aapl = metadata.get('has_aapl_classes', False)
            
            if has_custom and has_aapl:
                format_counts['both'] += 1
            elif has_custom:
                format_counts['has_custom_classes'] += 1
            elif has_aapl:
                format_counts['has_aapl_classes'] += 1
            else:
                format_counts['neither'] += 1
        
        logger.info(f"\nFormat class breakdown:")
        for fmt, count in format_counts.items():
            logger.info(f"  {fmt}: {count}")
        
        # Financial structure patterns
        has_subtotal = sum(1 for m in all_metadata if m.get('has_subtotal', False))
        has_tax = sum(1 for m in all_metadata if m.get('has_tax', False))
        
        logger.info(f"\nFinancial structure:")
        logger.info(f"  Has subtotal: {has_subtotal}")
        logger.info(f"  Has tax: {has_tax}")
        
        # Date range analysis
        dates_with_data = [m['file_date'] for m in all_metadata if m['file_date']]
        if dates_with_data:
            logger.info(f"\nDate range: {min(dates_with_data)} to {max(dates_with_data)}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to extract metadata: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())