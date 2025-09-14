#!/usr/bin/env python3
"""
Export Apple Receipts to JSON

This script uses the receipt parser system to convert all Apple receipt emails 
to structured JSON format. It processes all receipts in the extracted content
directory and exports them to timestamped JSON files.

Features:
- Processes all 327 purchase receipts using the three-parser system
- Creates individual JSON files for each receipt
- Creates a summary JSON file with all receipts
- Provides detailed statistics and validation
- Handles all three format types (plain text, legacy HTML, modern HTML)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import logging

# Import our parser system
from receipt_parser import AppleReceiptParser, ParsedReceipt, get_extracted_content_dir

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_output_dir() -> Path:
    """Create and return the output directory for exported receipts."""
    script_dir = Path(__file__).parent
    output_dir = script_dir.parent / "exports" 
    output_dir.mkdir(exist_ok=True)
    return output_dir

def load_receipt_metadata() -> List[Dict[str, Any]]:
    """Load the receipt metadata to identify purchase receipts."""
    try:
        content_dir = get_extracted_content_dir()
        metadata_file = content_dir / "receipt_metadata.json"
        
        if not metadata_file.exists():
            logger.error("Receipt metadata not found. Run extract_receipt_metadata.py first.")
            return []
        
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load receipt metadata: {e}")
        return []

def export_individual_receipts(parser: AppleReceiptParser, receipt_list: List[str], output_dir: Path) -> Dict[str, Any]:
    """Export each receipt to an individual JSON file."""
    
    content_dir = get_extracted_content_dir()
    individual_dir = output_dir / "individual_receipts"
    individual_dir.mkdir(exist_ok=True)
    
    stats = {
        'total_processed': 0,
        'successful_parses': 0,
        'failed_parses': 0,
        'format_breakdown': {'plain_text': 0, 'legacy_html': 0, 'modern_html': 0, 'unknown': 0},
        'errors': []
    }
    
    logger.info(f"Exporting {len(receipt_list)} receipts to individual JSON files...")
    
    for base_name in receipt_list:
        stats['total_processed'] += 1
        
        try:
            # Parse the receipt
            receipt = parser.parse_receipt(base_name, content_dir)
            
            # Track format statistics
            format_type = receipt.format_detected or 'unknown'
            stats['format_breakdown'][format_type] += 1
            
            # Convert to dictionary
            receipt_data = receipt.to_dict()
            receipt_data['base_name'] = base_name  # Add metadata
            
            # Export to individual file
            output_file = individual_dir / f"{base_name}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(receipt_data, f, indent=2, default=str)
            
            stats['successful_parses'] += 1
            
            if stats['total_processed'] % 50 == 0:
                logger.info(f"Processed {stats['total_processed']} receipts...")
                
        except Exception as e:
            stats['failed_parses'] += 1
            error_msg = f"Failed to export {base_name}: {str(e)}"
            stats['errors'].append(error_msg)
            logger.error(error_msg)
    
    return stats

def export_combined_receipts(parser: AppleReceiptParser, receipt_list: List[str], output_dir: Path) -> List[Dict[str, Any]]:
    """Export all receipts to a single combined JSON file."""
    
    content_dir = get_extracted_content_dir()
    combined_receipts = []
    
    logger.info(f"Creating combined export of {len(receipt_list)} receipts...")
    
    for i, base_name in enumerate(receipt_list):
        try:
            # Parse the receipt
            receipt = parser.parse_receipt(base_name, content_dir)
            
            # Convert to dictionary and add metadata
            receipt_data = receipt.to_dict()
            receipt_data['base_name'] = base_name
            
            combined_receipts.append(receipt_data)
            
            if (i + 1) % 100 == 0:
                logger.info(f"Combined export: processed {i + 1} receipts...")
                
        except Exception as e:
            logger.error(f"Failed to include {base_name} in combined export: {e}")
    
    return combined_receipts

def generate_export_summary(stats: Dict[str, Any], combined_receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a summary of the export process."""
    
    # Calculate additional statistics from parsed receipts
    total_amount = 0.0
    receipts_with_totals = 0
    items_count = 0
    apple_ids = set()
    date_range = {'earliest': None, 'latest': None}
    
    for receipt in combined_receipts:
        if receipt.get('total'):
            total_amount += receipt['total']
            receipts_with_totals += 1
        
        items_count += len(receipt.get('items', []))
        
        if receipt.get('apple_id'):
            apple_ids.add(receipt['apple_id'])
        
        # Track date range (from receipt date or filename)
        receipt_date = receipt.get('receipt_date') or receipt.get('base_name', '')[:8]
        if receipt_date:
            if not date_range['earliest'] or receipt_date < date_range['earliest']:
                date_range['earliest'] = receipt_date
            if not date_range['latest'] or receipt_date > date_range['latest']:
                date_range['latest'] = receipt_date
    
    summary = {
        'export_timestamp': datetime.now().isoformat(),
        'total_receipts_exported': len(combined_receipts),
        'parsing_statistics': stats,
        'financial_summary': {
            'total_amount_parsed': round(total_amount, 2),
            'receipts_with_financial_data': receipts_with_totals,
            'average_receipt_amount': round(total_amount / receipts_with_totals, 2) if receipts_with_totals > 0 else 0
        },
        'content_summary': {
            'total_items_parsed': items_count,
            'unique_apple_ids': len(apple_ids),
            'apple_ids': sorted(list(apple_ids)),
            'date_range': date_range
        },
        'format_coverage': {
            'plain_text_coverage': f"{stats['format_breakdown']['plain_text']} receipts ({stats['format_breakdown']['plain_text']/len(combined_receipts)*100:.1f}%)",
            'legacy_html_coverage': f"{stats['format_breakdown']['legacy_html']} receipts ({stats['format_breakdown']['legacy_html']/len(combined_receipts)*100:.1f}%)",
            'modern_html_coverage': f"{stats['format_breakdown']['modern_html']} receipts ({stats['format_breakdown']['modern_html']/len(combined_receipts)*100:.1f}%)"
        }
    }
    
    return summary

def main():
    """Main export function."""
    try:
        logger.info("Starting Apple receipt export to JSON...")
        
        # Load metadata to identify purchase receipts
        logger.info("Loading receipt metadata...")
        all_metadata = load_receipt_metadata()
        if not all_metadata:
            logger.error("No metadata found. Cannot proceed.")
            return 1
        
        # Filter to actual purchase receipts
        purchase_receipts = [m for m in all_metadata if m.get('purchase_type') == 'purchase_receipt']
        receipt_list = [m['base_name'] for m in purchase_receipts]
        
        logger.info(f"Found {len(purchase_receipts)} purchase receipts out of {len(all_metadata)} total emails")
        
        # Initialize parser
        parser = AppleReceiptParser()
        
        # Create output directory
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = get_output_dir() / f"{timestamp}_apple_receipts_export"
        output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Exporting to: {output_dir}")
        
        # Export individual receipts
        stats = export_individual_receipts(parser, receipt_list, output_dir)
        
        # Export combined receipts
        combined_receipts = export_combined_receipts(parser, receipt_list, output_dir)
        
        # Save combined export
        combined_file = output_dir / "all_receipts_combined.json"
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(combined_receipts, f, indent=2, default=str)
        
        logger.info(f"Saved combined export: {combined_file}")
        
        # Generate and save export summary
        summary = generate_export_summary(stats, combined_receipts)
        summary_file = output_dir / "export_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Saved export summary: {summary_file}")
        
        # Display final statistics
        logger.info("\n" + "="*60)
        logger.info("EXPORT COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        logger.info(f"Total receipts processed: {stats['total_processed']}")
        logger.info(f"Successful exports: {stats['successful_parses']}")
        logger.info(f"Failed exports: {stats['failed_parses']}")
        logger.info(f"Success rate: {stats['successful_parses']/stats['total_processed']*100:.1f}%")
        
        logger.info(f"\nFormat breakdown:")
        for format_type, count in stats['format_breakdown'].items():
            if count > 0:
                logger.info(f"  {format_type}: {count} receipts ({count/stats['total_processed']*100:.1f}%)")
        
        logger.info(f"\nFinancial summary:")
        logger.info(f"  Total amount: ${summary['financial_summary']['total_amount_parsed']:,.2f}")
        logger.info(f"  Average receipt: ${summary['financial_summary']['average_receipt_amount']:,.2f}")
        logger.info(f"  Date range: {summary['content_summary']['date_range']['earliest']} to {summary['content_summary']['date_range']['latest']}")
        
        logger.info(f"\nOutput directory: {output_dir}")
        logger.info(f"Individual receipts: {output_dir / 'individual_receipts'}")
        logger.info(f"Combined file: {combined_file}")
        logger.info(f"Summary file: {summary_file}")
        
        if stats['errors']:
            logger.warning(f"\nWarnings/Errors ({len(stats['errors'])}):")
            for error in stats['errors'][:10]:  # Show first 10 errors
                logger.warning(f"  {error}")
            if len(stats['errors']) > 10:
                logger.warning(f"  ... and {len(stats['errors']) - 10} more errors")
        
        return 0
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())