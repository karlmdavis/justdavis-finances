#!/usr/bin/env python3
"""
Analyze Incomplete Apple Receipts

This script identifies and analyzes receipts that could not be fully parsed
or are missing expected data fields.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

def load_receipts(export_dir: Path) -> List[Dict[str, Any]]:
    """Load exported receipts."""
    combined_file = export_dir / "all_receipts_combined.json"
    with open(combined_file, 'r') as f:
        return json.load(f)

def analyze_incomplete_receipts(receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze receipts for missing or incomplete data."""
    
    analysis = {
        'total_receipts': len(receipts),
        'missing_financial_data': [],
        'incomplete_financial_data': [],
        'missing_items': [],
        'missing_document_number': [],
        'missing_receipt_date': [],
        'zero_amounts': [],
        'single_item_duplicates': [],
        'format_specific_issues': defaultdict(list)
    }
    
    for receipt in receipts:
        base_name = receipt.get('base_name', 'unknown')
        format_type = receipt.get('format_detected', 'unknown')
        
        # Check for missing financial data
        has_subtotal = receipt.get('subtotal') is not None
        has_tax = receipt.get('tax') is not None
        has_total = receipt.get('total') is not None
        
        if not has_total:
            analysis['missing_financial_data'].append({
                'base_name': base_name,
                'format': format_type,
                'issue': 'No total amount'
            })
        elif not (has_subtotal and has_tax):
            analysis['incomplete_financial_data'].append({
                'base_name': base_name,
                'format': format_type,
                'has_subtotal': has_subtotal,
                'has_tax': has_tax,
                'has_total': has_total,
                'total': receipt.get('total')
            })
        
        # Check for zero amounts
        if has_total and receipt['total'] == 0:
            analysis['zero_amounts'].append({
                'base_name': base_name,
                'format': format_type
            })
        
        # Check for missing items
        items = receipt.get('items', [])
        if not items:
            analysis['missing_items'].append({
                'base_name': base_name,
                'format': format_type,
                'has_total': has_total,
                'total': receipt.get('total')
            })
        
        # Check for duplicate items (parsing error indicator)
        if len(items) == 2:
            titles = [item.get('title', '') for item in items]
            if len(set(titles)) == 1:  # Same title
                analysis['single_item_duplicates'].append({
                    'base_name': base_name,
                    'format': format_type,
                    'item_title': titles[0],
                    'items': items
                })
        
        # Check for missing document number
        if not receipt.get('document_number'):
            analysis['missing_document_number'].append({
                'base_name': base_name,
                'format': format_type
            })
        
        # Check for missing receipt date
        if not receipt.get('receipt_date'):
            analysis['missing_receipt_date'].append({
                'base_name': base_name,
                'format': format_type
            })
        
        # Format-specific issues
        if format_type == 'legacy_html' and not has_subtotal:
            analysis['format_specific_issues']['legacy_html_no_financial'].append(base_name)
        
        if format_type == 'plain_text' and not items:
            analysis['format_specific_issues']['plain_text_no_items'].append(base_name)
    
    return analysis

def print_detailed_analysis(analysis: Dict[str, Any]):
    """Print detailed analysis of incomplete receipts."""
    
    print("\n" + "="*70)
    print("INCOMPLETE RECEIPT ANALYSIS")
    print("="*70)
    
    print(f"\n📊 OVERVIEW:")
    print(f"Total Receipts: {analysis['total_receipts']}")
    print(f"Missing ALL Financial Data: {len(analysis['missing_financial_data'])}")
    print(f"Incomplete Financial Data: {len(analysis['incomplete_financial_data'])}")
    print(f"Missing Items: {len(analysis['missing_items'])}")
    print(f"Missing Document Number: {len(analysis['missing_document_number'])}")
    print(f"Missing Receipt Date: {len(analysis['missing_receipt_date'])}")
    
    # Most concerning: Missing financial data
    if analysis['missing_financial_data']:
        print(f"\n❌ RECEIPTS WITH NO FINANCIAL DATA ({len(analysis['missing_financial_data'])}):")
        print("-" * 50)
        for receipt in analysis['missing_financial_data'][:10]:
            print(f"  • {receipt['base_name']} [{receipt['format']}]")
        if len(analysis['missing_financial_data']) > 10:
            print(f"  ... and {len(analysis['missing_financial_data']) - 10} more")
    
    # Incomplete financial data (missing subtotal or tax)
    if analysis['incomplete_financial_data']:
        print(f"\n⚠️  RECEIPTS WITH INCOMPLETE FINANCIAL DATA ({len(analysis['incomplete_financial_data'])}):")
        print("-" * 50)
        
        # Group by format
        by_format = defaultdict(list)
        for receipt in analysis['incomplete_financial_data']:
            by_format[receipt['format']].append(receipt)
        
        for format_type, receipts in by_format.items():
            print(f"\n  {format_type} format ({len(receipts)} receipts):")
            for receipt in receipts[:5]:
                status = []
                if not receipt['has_subtotal']:
                    status.append("no subtotal")
                if not receipt['has_tax']:
                    status.append("no tax")
                print(f"    • {receipt['base_name'][:50]}... - {', '.join(status)} - Total: ${receipt.get('total', 0):.2f}")
    
    # Missing items
    if analysis['missing_items']:
        print(f"\n📦 RECEIPTS WITH NO ITEMS ({len(analysis['missing_items'])}):")
        print("-" * 50)
        
        # Group by format
        by_format = defaultdict(list)
        for receipt in analysis['missing_items']:
            by_format[receipt['format']].append(receipt)
        
        for format_type, receipts in by_format.items():
            print(f"\n  {format_type} format ({len(receipts)} receipts):")
            for receipt in receipts[:5]:
                total_str = f"${receipt['total']:.2f}" if receipt.get('total') else "No total"
                print(f"    • {receipt['base_name'][:50]}... - {total_str}")
    
    # Format-specific issues
    if analysis['format_specific_issues']:
        print(f"\n🔍 FORMAT-SPECIFIC ISSUES:")
        print("-" * 50)
        for issue_type, receipts in analysis['format_specific_issues'].items():
            if receipts:
                print(f"  {issue_type}: {len(receipts)} receipts")
                for receipt in receipts[:3]:
                    print(f"    • {receipt}")
    
    # Missing dates (concerning for record-keeping)
    if analysis['missing_receipt_date']:
        print(f"\n📅 RECEIPTS WITH NO DATE ({len(analysis['missing_receipt_date'])}):")
        print("-" * 50)
        by_format = defaultdict(int)
        for receipt in analysis['missing_receipt_date']:
            by_format[receipt['format']] += 1
        for format_type, count in by_format.items():
            print(f"  {format_type}: {count} receipts")
    
    # Summary statistics
    print(f"\n📊 PARSING COMPLETENESS SUMMARY:")
    print("-" * 50)
    total = analysis['total_receipts']
    
    complete_financial = total - len(analysis['missing_financial_data']) - len(analysis['incomplete_financial_data'])
    print(f"Complete Financial Data: {complete_financial}/{total} ({complete_financial/total*100:.1f}%)")
    
    with_items = total - len(analysis['missing_items'])
    print(f"Has Items: {with_items}/{total} ({with_items/total*100:.1f}%)")
    
    with_doc_num = total - len(analysis['missing_document_number'])
    print(f"Has Document Number: {with_doc_num}/{total} ({with_doc_num/total*100:.1f}%)")
    
    with_date = total - len(analysis['missing_receipt_date'])
    print(f"Has Receipt Date: {with_date}/{total} ({with_date/total*100:.1f}%)")
    
    # Identify fully complete receipts
    problem_receipts = set()
    for field in ['missing_financial_data', 'incomplete_financial_data', 'missing_items', 
                  'missing_document_number', 'missing_receipt_date']:
        for receipt in analysis[field]:
            problem_receipts.add(receipt.get('base_name', receipt))
    
    fully_complete = total - len(problem_receipts)
    print(f"\n✅ FULLY COMPLETE RECEIPTS: {fully_complete}/{total} ({fully_complete/total*100:.1f}%)")
    print(f"❌ RECEIPTS WITH ISSUES: {len(problem_receipts)}/{total} ({len(problem_receipts)/total*100:.1f}%)")

def find_latest_export() -> Path:
    """Find the most recent export directory."""
    script_dir = Path(__file__).parent
    exports_dir = script_dir.parent / "exports"
    
    export_dirs = [d for d in exports_dir.glob("*_apple_receipts_export") if d.is_dir()]
    if not export_dirs:
        raise FileNotFoundError("No export directories found")
    
    return max(export_dirs)

def main():
    """Main analysis function."""
    try:
        # Find latest export
        export_dir = find_latest_export()
        print(f"Analyzing export: {export_dir.name}")
        
        # Load receipts
        receipts = load_receipts(export_dir)
        
        # Analyze incomplete receipts
        analysis = analyze_incomplete_receipts(receipts)
        
        # Print detailed analysis
        print_detailed_analysis(analysis)
        
        # Save analysis to file
        output_file = export_dir / "incomplete_receipts_analysis.json"
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        print(f"\n💾 Analysis saved to: {output_file}")
        
        return 0
        
    except Exception as e:
        print(f"Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())