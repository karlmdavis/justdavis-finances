#!/usr/bin/env python3
"""
Re-analyze Apple receipt formats based on metadata insights.

This creates a corrected analysis that focuses on the actual parsing strategies needed
rather than structural differences that were misleading in the original analysis.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def get_metadata_file() -> Path:
    """Get the receipt metadata file."""
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    if not email_dirs:
        raise FileNotFoundError("No Apple email data directories found")
    
    email_dir = max(email_dirs)
    return email_dir / "extracted_content" / "receipt_metadata.json"

def load_metadata():
    """Load and return receipt metadata."""
    metadata_file = get_metadata_file()
    with open(metadata_file, 'r') as f:
        return json.load(f)

def analyze_formats(metadata):
    """Analyze the real format patterns."""
    print("="*60)
    print("CORRECTED APPLE RECEIPT FORMAT ANALYSIS")
    print("="*60)
    
    # Filter to actual purchase receipts only
    receipts = [m for m in metadata if m['purchase_type'] == 'purchase_receipt']
    print(f"Analyzing {len(receipts)} actual purchase receipts (out of {len(metadata)} total emails)")
    
    # Parsing method breakdown
    plain_text_receipts = [r for r in receipts if r['parsing_source'] == 'plain_text']
    html_receipts = [r for r in receipts if r['parsing_source'] == 'html']
    
    print(f"\nPARSING METHOD BREAKDOWN:")
    print(f"Plain text parsing: {len(plain_text_receipts)} receipts ({len(plain_text_receipts)/len(receipts)*100:.1f}%)")
    print(f"HTML parsing required: {len(html_receipts)} receipts ({len(html_receipts)/len(receipts)*100:.1f}%)")
    
    # Timeline analysis
    by_year = defaultdict(lambda: {'plain_text': 0, 'html_aapl': 0, 'html_custom': 0})
    
    for receipt in receipts:
        if not receipt['file_date']:
            continue
        year = receipt['file_date'][:4]
        
        if receipt['parsing_source'] == 'plain_text':
            by_year[year]['plain_text'] += 1
        elif receipt.get('has_custom_classes'):
            by_year[year]['html_custom'] += 1
        else:
            by_year[year]['html_aapl'] += 1
    
    print(f"\nTIMELINE ANALYSIS:")
    print(f"Year | Plain Text | HTML (aapl-*) | HTML (custom-*) | Total")
    print("-" * 60)
    for year in sorted(by_year.keys()):
        data = by_year[year]
        total = sum(data.values())
        print(f"{year} | {data['plain_text']:10} | {data['html_aapl']:12} | {data['html_custom']:14} | {total:5}")
    
    # HTML format analysis
    print(f"\nHTML FORMAT ANALYSIS ({len(html_receipts)} receipts):")
    
    aapl_class_receipts = [r for r in html_receipts if r.get('has_aapl_classes')]
    custom_class_receipts = [r for r in html_receipts if r.get('has_custom_classes')]
    
    print(f"Legacy table format (aapl-* classes): {len(aapl_class_receipts)}")
    print(f"Modern CSS format (custom-* classes): {len(custom_class_receipts)}")
    
    # Date ranges for HTML formats
    if aapl_class_receipts:
        aapl_dates = [r['file_date'] for r in aapl_class_receipts if r['file_date']]
        if aapl_dates:
            print(f"  Legacy format date range: {min(aapl_dates)} to {max(aapl_dates)}")
    
    if custom_class_receipts:
        custom_dates = [r['file_date'] for r in custom_class_receipts if r['file_date']]
        if custom_dates:
            print(f"  Modern format date range: {min(custom_dates)} to {max(custom_dates)}")
    
    # Format transition analysis
    print(f"\nFORMAT TRANSITION ANALYSIS:")
    
    # Check 2024+ receipts
    recent_receipts = [r for r in receipts if r['file_date'] and r['file_date'] >= '2024-01-01']
    recent_plain = [r for r in recent_receipts if r['parsing_source'] == 'plain_text']
    recent_html_aapl = [r for r in recent_receipts if r['parsing_source'] == 'html' and r.get('has_aapl_classes')]
    recent_html_custom = [r for r in recent_receipts if r['parsing_source'] == 'html' and r.get('has_custom_classes')]
    
    print(f"2024+ receipts: {len(recent_receipts)} total")
    print(f"  Plain text available: {len(recent_plain)} ({len(recent_plain)/len(recent_receipts)*100:.1f}%)")
    print(f"  HTML with aapl-* classes: {len(recent_html_aapl)} ({len(recent_html_aapl)/len(recent_receipts)*100:.1f}%)")
    print(f"  HTML with custom-* classes: {len(recent_html_custom)} ({len(recent_html_custom)/len(recent_receipts)*100:.1f}%)")
    
    # Financial structure analysis
    print(f"\nFINANCIAL STRUCTURE PATTERNS:")
    
    has_subtotal = [r for r in receipts if r.get('has_subtotal')]
    has_tax = [r for r in receipts if r.get('has_tax')]
    
    print(f"Receipts with subtotal: {len(has_subtotal)} ({len(has_subtotal)/len(receipts)*100:.1f}%)")
    print(f"Receipts with tax: {len(has_tax)} ({len(has_tax)/len(receipts)*100:.1f}%)")
    
    # Item count analysis
    single_item = [r for r in receipts if r.get('item_count') == 1]
    multi_item = [r for r in receipts if r.get('item_count', 0) > 1]
    unknown_items = [r for r in receipts if r.get('item_count', 0) == 0]
    
    print(f"\nITEM COUNT PATTERNS:")
    print(f"Single item purchases: {len(single_item)}")
    print(f"Multi-item purchases: {len(multi_item)}")
    print(f"Unknown item count: {len(unknown_items)}")
    
    return {
        'total_receipts': len(receipts),
        'plain_text_receipts': len(plain_text_receipts),
        'html_receipts': len(html_receipts),
        'aapl_class_receipts': len(aapl_class_receipts),
        'custom_class_receipts': len(custom_class_receipts),
        'timeline': dict(by_year)
    }

def generate_parsing_strategy(analysis_results):
    """Generate the corrected parsing strategy."""
    print(f"\n" + "="*60)
    print("CORRECTED PARSING STRATEGY")
    print("="*60)
    
    print(f"""
Based on the metadata analysis, here are the THREE parsing approaches needed:

## 1. Plain Text Parser (Primary)
- **Coverage**: {analysis_results['plain_text_receipts']}/{analysis_results['total_receipts']} receipts ({analysis_results['plain_text_receipts']/analysis_results['total_receipts']*100:.1f}%)
- **Time period**: Primarily 2020-2023, very few in 2024+
- **Advantages**: Consistent format, easy parsing, reliable extraction
- **Use case**: Parse receipt text files when available

## 2. Legacy HTML Parser (Secondary) 
- **Coverage**: {analysis_results['aapl_class_receipts']} receipts (HTML-only receipts from 2024+)
- **Detection**: Look for `aapl-desktop-tbl`, `aapl-mobile-tbl` classes
- **Approach**: CSS selector-based extraction using semantic Apple classes
- **Use case**: 2024+ receipts without plain text, legacy HTML format

## 3. Modern HTML Parser (Newest)
- **Coverage**: {analysis_results['custom_class_receipts']} receipts (newest 2024+ format)
- **Detection**: Look for `custom-*` classes and minimal table structure
- **Approach**: CSS selector targeting custom classes
- **Use case**: Latest 2024+ receipt format

## Implementation Priority:
1. **Plain Text Parser**: Handle 80%+ of all receipts
2. **Legacy HTML Parser**: Handle most 2024+ receipts
3. **Modern HTML Parser**: Handle newest 2024+ format

## Format Detection Strategy:
```python
def detect_format(receipt_files):
    if txt_file_exists and txt_file_has_content:
        return 'plain_text'
    elif html_contains('custom-'):
        return 'modern_html' 
    elif html_contains('aapl-'):
        return 'legacy_html'
    else:
        return 'unknown'
```

The key insight: This is NOT about parallel systems or structural differences.
It's about **temporal evolution** and **content availability**.
""")

def main():
    """Main analysis function."""
    try:
        metadata = load_metadata()
        analysis_results = analyze_formats(metadata)
        generate_parsing_strategy(analysis_results)
        
        return 0
    except Exception as e:
        print(f"Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())