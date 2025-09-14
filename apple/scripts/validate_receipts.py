#!/usr/bin/env python3
"""
Apple Receipt Validation Tools

This script provides comprehensive validation of exported Apple receipts to ensure
data integrity, identify parsing issues, and provide analytical insights.

Features:
- Financial data validation (subtotal + tax = total)
- Completeness validation (required fields present)
- Cross-format consistency analysis
- Outlier detection for amounts and items
- Temporal analysis of parsing quality
- Detailed reporting with actionable insights
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from collections import defaultdict
import statistics
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReceiptValidator:
    """Comprehensive validation system for Apple receipts."""
    
    def __init__(self):
        self.validation_rules = []
        self.format_expectations = {}
        self.setup_format_expectations()
        self.setup_validation_rules()
    
    def setup_format_expectations(self):
        """Setup format-specific field expectations."""
        self.format_expectations = {
            'plain_text': {
                'required_fields': ['format_detected', 'apple_id', 'base_name', 'order_id', 'total'],
                'expected_item_fields': ['title', 'cost'],
                'optional_item_fields': ['subtitle', 'artist', 'device', 'type'],
                'financial_completeness_expected': True,
                'metadata_richness_expected': False  # Plain text has limited metadata
            },
            'legacy_html': {
                'required_fields': ['format_detected', 'apple_id', 'base_name', 'order_id', 'total'],
                'expected_item_fields': ['title', 'cost', 'type'],
                'optional_item_fields': ['subtitle', 'artist', 'device'],
                'financial_completeness_expected': True,
                'metadata_richness_expected': True  # HTML can extract rich metadata
            },
            'modern_html': {
                'required_fields': ['format_detected', 'apple_id', 'base_name', 'order_id', 'total'],
                'expected_item_fields': ['title', 'cost', 'type'],
                'optional_item_fields': ['subtitle', 'artist', 'device'],
                'financial_completeness_expected': True,
                'metadata_richness_expected': True  # Modern HTML has rich metadata
            }
        }
    
    def get_format_expectations(self, format_type: str) -> Dict[str, Any]:
        """Get expectations for a specific receipt format."""
        return self.format_expectations.get(format_type, self.format_expectations['plain_text'])
    
    def setup_validation_rules(self):
        """Setup validation rules for receipt data."""
        self.validation_rules = [
            ('financial_integrity', self.validate_financial_integrity),
            ('required_fields', self.validate_required_fields),
            ('data_types', self.validate_data_types),
            ('item_consistency', self.validate_item_consistency),
            ('amount_sanity', self.validate_amount_sanity),
            ('date_format', self.validate_date_format),
            ('parsing_metadata', self.validate_parsing_metadata)
        ]
    
    def validate_financial_integrity(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that financial calculations are correct."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        subtotal = receipt.get('subtotal')
        tax = receipt.get('tax')
        total = receipt.get('total')
        
        if subtotal is not None and tax is not None and total is not None:
            calculated_total = subtotal + tax
            tolerance = 0.01  # $0.01 tolerance for rounding
            
            if abs(calculated_total - total) > tolerance:
                result['passed'] = False
                result['errors'].append(
                    f"Financial mismatch: ${subtotal:.2f} + ${tax:.2f} = ${calculated_total:.2f} != ${total:.2f}"
                )
        
        # Check for negative amounts
        for field, amount in [('subtotal', subtotal), ('tax', tax), ('total', total)]:
            if amount is not None and amount < 0:
                result['warnings'].append(f"Negative amount for {field}: ${amount:.2f}")
        
        return result
    
    def validate_required_fields(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that required fields are present with format awareness."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        format_type = receipt.get('format_detected', 'plain_text')
        expectations = self.get_format_expectations(format_type)
        
        # Check format-specific required fields
        for field in expectations['required_fields']:
            if not receipt.get(field):
                result['passed'] = False
                result['errors'].append(f"Missing required field: {field}")
        
        # Only warn about missing optional fields that we don't expect for this format
        # For example, don't warn about missing payment_method since most formats don't include it
        optional_but_valuable_fields = ['document_number']
        
        for field in optional_but_valuable_fields:
            if not receipt.get(field):
                result['warnings'].append(f"Missing recommended field: {field}")
        
        # Check items array exists and has content
        items = receipt.get('items', [])
        if not items:
            result['warnings'].append("No items found in receipt")
        
        return result
    
    def validate_data_types(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that data types are correct."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        type_checks = [
            ('subtotal', (int, float, type(None))),
            ('tax', (int, float, type(None))),
            ('total', (int, float, type(None))),
            ('items', list),
            ('apple_id', (str, type(None))),
            ('order_id', (str, type(None)))
        ]
        
        for field, expected_types in type_checks:
            value = receipt.get(field)
            if value is not None and not isinstance(value, expected_types):
                result['passed'] = False
                result['errors'].append(f"Wrong type for {field}: expected {expected_types}, got {type(value)}")
        
        return result
    
    def validate_item_consistency(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate item data consistency with format awareness."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        format_type = receipt.get('format_detected', 'plain_text')
        expectations = self.get_format_expectations(format_type)
        
        items = receipt.get('items', [])
        if not items:
            result['warnings'].append("No items found in receipt")
            return result
        
        # Check each item structure
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                result['errors'].append(f"Item {i} is not a dictionary")
                continue
            
            # Check required item fields for this format
            for field in expectations['expected_item_fields']:
                if not item.get(field):
                    if field == 'title':
                        result['warnings'].append(f"Item {i} missing title")
                    elif field == 'cost':
                        result['warnings'].append(f"Item {i} missing cost")
                    elif field == 'type' and expectations['metadata_richness_expected']:
                        # Only warn about missing type for HTML formats where it's expected
                        result['warnings'].append(f"Item {i} missing type (expected for {format_type})")
            
            # Validate item cost
            cost = item.get('cost')
            if cost is not None:
                if not isinstance(cost, (int, float)):
                    result['errors'].append(f"Item {i} cost is not numeric: {cost}")
                elif cost < 0:
                    result['warnings'].append(f"Item {i} has negative cost: ${cost:.2f}")
        
        # Keep strict financial validation - item costs must match subtotal when both present
        if receipt.get('subtotal'):
            item_costs = [item.get('cost', 0) for item in items if item.get('cost') is not None]
            if item_costs:
                total_item_cost = sum(item_costs)
                subtotal = receipt.get('subtotal')
                if abs(total_item_cost - subtotal) > 0.01:
                    result['warnings'].append(
                        f"Item costs (${total_item_cost:.2f}) don't match subtotal (${subtotal:.2f})"
                    )
        
        return result
    
    def validate_amount_sanity(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that amounts are within reasonable ranges."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        total = receipt.get('total')
        if total is not None:
            # Check for unreasonably high amounts (likely parsing errors)
            if total > 1000:
                result['warnings'].append(f"Very high total amount: ${total:.2f}")
            elif total > 10000:
                result['errors'].append(f"Extremely high total amount: ${total:.2f}")
            
            # Check for zero amounts (possible parsing failure)
            if total == 0:
                result['warnings'].append("Zero total amount")
        
        return result
    
    def validate_date_format(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate date format consistency."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        receipt_date = receipt.get('receipt_date')
        if receipt_date and isinstance(receipt_date, str):
            # Check for consistent date formatting
            if len(receipt_date) < 8:
                result['warnings'].append(f"Unusual date format: {receipt_date}")
        
        return result
    
    def validate_parsing_metadata(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parsing metadata completeness."""
        result = {'passed': True, 'warnings': [], 'errors': []}
        
        metadata = receipt.get('parsing_metadata', {})
        if not metadata:
            result['warnings'].append("No parsing metadata available")
            return result
        
        # Check for parsing errors
        if metadata.get('errors'):
            result['passed'] = False
            result['errors'].extend([f"Parsing error: {e}" for e in metadata['errors']])
        
        return result
    
    def categorize_warnings(self, receipts: List[Dict[str, Any]], validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize warnings by type to provide better insights."""
        warning_categories = {
            'financial_discrepancies': [],
            'missing_optional_data': [],
            'data_quality_issues': [],
            'format_limitations': []
        }
        
        for receipt in receipts:
            base_name = receipt.get('base_name', 'unknown')
            detailed_results = validation_results['detailed_results'].get(base_name, {})
            
            # Check if this receipt has warnings
            has_warnings = any(r.get('warnings', []) for r in detailed_results.get('rules', {}).values())
            if not has_warnings:
                continue
            
            format_type = receipt.get('format_detected', 'plain_text')
            expectations = self.get_format_expectations(format_type)
            
            # Categorize warnings by type
            for rule_name, rule_result in detailed_results.get('rules', {}).items():
                for warning in rule_result.get('warnings', []):
                    warning_info = {
                        'receipt': base_name,
                        'format': format_type,
                        'rule': rule_name,
                        'message': warning
                    }
                    
                    # Categorize based on warning content
                    if 'don\'t match subtotal' in warning or 'costs' in warning:
                        warning_categories['financial_discrepancies'].append(warning_info)
                    elif 'missing' in warning.lower() and ('subtitle' in warning or 'artist' in warning or 'type' in warning):
                        if not expectations['metadata_richness_expected']:
                            warning_categories['format_limitations'].append(warning_info)
                        else:
                            warning_categories['missing_optional_data'].append(warning_info)
                    elif 'missing' in warning.lower():
                        warning_categories['data_quality_issues'].append(warning_info)
                    else:
                        warning_categories['data_quality_issues'].append(warning_info)
        
        return warning_categories

def load_exported_receipts(export_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load exported receipts and summary."""
    combined_file = export_dir / "all_receipts_combined.json"
    summary_file = export_dir / "export_summary.json"
    
    if not combined_file.exists():
        raise FileNotFoundError(f"Combined receipts file not found: {combined_file}")
    
    with open(combined_file, 'r') as f:
        receipts = json.load(f)
    
    summary = {}
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
    
    return receipts, summary

def run_validation(receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run comprehensive validation on all receipts."""
    validator = ReceiptValidator()
    
    validation_results = {
        'total_receipts': len(receipts),
        'validation_summary': {},
        'failed_receipts': [],
        'warning_receipts': [],
        'detailed_results': {}
    }
    
    rule_stats = defaultdict(lambda: {'passed': 0, 'failed': 0, 'warnings': 0})
    
    for receipt in receipts:
        base_name = receipt.get('base_name', 'unknown')
        receipt_results = {'rules': {}, 'overall_passed': True}
        
        for rule_name, rule_func in validator.validation_rules:
            result = rule_func(receipt)
            receipt_results['rules'][rule_name] = result
            
            if result['passed']:
                rule_stats[rule_name]['passed'] += 1
            else:
                rule_stats[rule_name]['failed'] += 1
                receipt_results['overall_passed'] = False
            
            if result['warnings']:
                rule_stats[rule_name]['warnings'] += 1
        
        validation_results['detailed_results'][base_name] = receipt_results
        
        if not receipt_results['overall_passed']:
            validation_results['failed_receipts'].append(base_name)
        
        # Count receipts with any warnings
        has_warnings = any(r['warnings'] for r in receipt_results['rules'].values())
        if has_warnings:
            validation_results['warning_receipts'].append(base_name)
    
    validation_results['validation_summary'] = dict(rule_stats)
    
    # Add warning categorization
    validation_results['warning_categories'] = validator.categorize_warnings(receipts, validation_results)
    
    return validation_results

def analyze_parsing_quality(receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze parsing quality across different formats and time periods."""
    
    analysis = {
        'format_analysis': defaultdict(lambda: {
            'count': 0, 'complete_financial_data': 0, 'has_items': 0,
            'avg_items': 0, 'total_amount': 0.0
        }),
        'temporal_analysis': defaultdict(lambda: {
            'count': 0, 'parsing_success_rate': 0.0
        }),
        'completeness_metrics': {
            'with_order_id': 0,
            'with_document_number': 0,
            'with_complete_financial': 0,
            'with_items': 0,
            'with_payment_method': 0
        }
    }
    
    for receipt in receipts:
        format_type = receipt.get('format_detected', 'unknown')
        base_name = receipt.get('base_name', '')
        
        # Format analysis
        format_stats = analysis['format_analysis'][format_type]
        format_stats['count'] += 1
        
        if all(receipt.get(field) is not None for field in ['subtotal', 'tax', 'total']):
            format_stats['complete_financial_data'] += 1
        
        items = receipt.get('items', [])
        if items:
            format_stats['has_items'] += 1
            format_stats['avg_items'] += len(items)
        
        if receipt.get('total'):
            format_stats['total_amount'] += receipt['total']
        
        # Temporal analysis (extract year from base_name)
        if len(base_name) >= 4:
            year = base_name[:4]
            if year.isdigit():
                temporal_stats = analysis['temporal_analysis'][year]
                temporal_stats['count'] += 1
        
        # Completeness metrics
        metrics = analysis['completeness_metrics']
        if receipt.get('order_id'):
            metrics['with_order_id'] += 1
        if receipt.get('document_number'):
            metrics['with_document_number'] += 1
        if all(receipt.get(field) is not None for field in ['subtotal', 'tax', 'total']):
            metrics['with_complete_financial'] += 1
        if receipt.get('items'):
            metrics['with_items'] += 1
        if receipt.get('payment_method'):
            metrics['with_payment_method'] += 1
    
    # Calculate averages
    for format_type, stats in analysis['format_analysis'].items():
        if stats['has_items'] > 0:
            stats['avg_items'] = stats['avg_items'] / stats['has_items']
    
    return analysis

def generate_validation_report(validation_results: Dict[str, Any], 
                             parsing_analysis: Dict[str, Any],
                             export_summary: Dict[str, Any],
                             output_dir: Path):
    """Generate comprehensive validation report."""
    
    report = {
        'validation_timestamp': datetime.now().isoformat(),
        'export_summary': export_summary,
        'validation_overview': {
            'total_receipts_validated': validation_results['total_receipts'],
            'receipts_passed': validation_results['total_receipts'] - len(validation_results['failed_receipts']),
            'receipts_failed': len(validation_results['failed_receipts']),
            'receipts_with_warnings': len(validation_results['warning_receipts']),
            'overall_success_rate': (validation_results['total_receipts'] - len(validation_results['failed_receipts'])) / validation_results['total_receipts'] * 100
        },
        'rule_breakdown': validation_results['validation_summary'],
        'parsing_quality_analysis': parsing_analysis,
        'warning_categories': validation_results.get('warning_categories', {}),
        'failed_receipts': validation_results['failed_receipts'][:20],  # Top 20 failures
        'receipts_with_warnings': validation_results['warning_receipts'][:20]  # Top 20 warnings
    }
    
    # Save detailed report
    report_file = output_dir / "validation_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    return report

def print_validation_summary(report: Dict[str, Any]):
    """Print a human-readable validation summary."""
    
    print("\n" + "="*70)
    print("APPLE RECEIPT VALIDATION REPORT")
    print("="*70)
    
    overview = report['validation_overview']
    print(f"📊 Total Receipts Validated: {overview['total_receipts_validated']}")
    print(f"✅ Receipts Passed: {overview['receipts_passed']}")
    print(f"❌ Receipts Failed: {overview['receipts_failed']}")
    print(f"⚠️  Receipts with Warnings: {overview['receipts_with_warnings']}")
    print(f"🎯 Overall Success Rate: {overview['overall_success_rate']:.1f}%")
    
    print(f"\n📋 VALIDATION RULES BREAKDOWN:")
    print("-" * 50)
    for rule_name, stats in report['rule_breakdown'].items():
        total = stats['passed'] + stats['failed']
        success_rate = (stats['passed'] / total * 100) if total > 0 else 0
        print(f"{rule_name:20} | Pass: {stats['passed']:3} | Fail: {stats['failed']:3} | Warn: {stats['warnings']:3} | Rate: {success_rate:5.1f}%")
    
    print(f"\n🎨 FORMAT ANALYSIS:")
    print("-" * 50)
    parsing_analysis = report['parsing_quality_analysis']
    for format_type, stats in parsing_analysis['format_analysis'].items():
        complete_rate = (stats['complete_financial_data'] / stats['count'] * 100) if stats['count'] > 0 else 0
        items_rate = (stats['has_items'] / stats['count'] * 100) if stats['count'] > 0 else 0
        print(f"{format_type:15} | Count: {stats['count']:3} | Financial: {complete_rate:5.1f}% | Items: {items_rate:5.1f}% | Avg Items: {stats['avg_items']:.1f}")
    
    print(f"\n📈 COMPLETENESS METRICS:")
    print("-" * 50)
    metrics = parsing_analysis['completeness_metrics']
    total = overview['total_receipts_validated']
    for field, count in metrics.items():
        rate = (count / total * 100) if total > 0 else 0
        print(f"{field.replace('_', ' ').title():20} | {count:3}/{total} ({rate:5.1f}%)")
    
    if report['failed_receipts']:
        print(f"\n❌ SAMPLE FAILED RECEIPTS:")
        print("-" * 50)
        for receipt in report['failed_receipts'][:10]:
            print(f"  • {receipt}")
    
    # Enhanced warning breakdown by category
    if 'warning_categories' in report:
        warning_categories = report['warning_categories']
        
        # Show financial discrepancies (most important)
        if warning_categories['financial_discrepancies']:
            print(f"\n💰 FINANCIAL DISCREPANCIES ({len(warning_categories['financial_discrepancies'])}):")
            print("-" * 50)
            for warning in warning_categories['financial_discrepancies'][:5]:
                print(f"  • {warning['receipt']}: {warning['message']}")
        
        # Show data quality issues
        if warning_categories['data_quality_issues']:
            print(f"\n⚠️  DATA QUALITY ISSUES ({len(warning_categories['data_quality_issues'])}):")
            print("-" * 50)
            for warning in warning_categories['data_quality_issues'][:5]:
                print(f"  • {warning['receipt']}: {warning['message']}")
        
        # Show missing optional data (less critical)
        if warning_categories['missing_optional_data']:
            print(f"\nℹ️  MISSING OPTIONAL DATA ({len(warning_categories['missing_optional_data'])}):")
            print("-" * 50)
            for warning in warning_categories['missing_optional_data'][:3]:
                print(f"  • {warning['receipt']} ({warning['format']}): {warning['message']}")
        
        # Format limitations (informational only)
        if warning_categories['format_limitations']:
            print(f"\n📄 FORMAT LIMITATIONS ({len(warning_categories['format_limitations'])} - informational):")
            print("-" * 50)
            for warning in warning_categories['format_limitations'][:3]:
                print(f"  • {warning['receipt']} ({warning['format']}): {warning['message']}")
    
    elif report['receipts_with_warnings']:
        print(f"\n⚠️  SAMPLE RECEIPTS WITH WARNINGS:")
        print("-" * 50)
        for receipt in report['receipts_with_warnings'][:10]:
            print(f"  • {receipt}")

def find_latest_export() -> Path:
    """Find the most recent export directory."""
    script_dir = Path(__file__).parent
    exports_dir = script_dir.parent / "exports"
    
    if not exports_dir.exists():
        raise FileNotFoundError("No exports directory found")
    
    export_dirs = [d for d in exports_dir.glob("*_apple_receipts_export") if d.is_dir()]
    if not export_dirs:
        raise FileNotFoundError("No export directories found")
    
    return max(export_dirs)  # Most recent by name (timestamp-based)

def main():
    """Main validation function."""
    try:
        logger.info("Starting Apple receipt validation...")
        
        # Find latest export
        export_dir = find_latest_export()
        logger.info(f"Validating export: {export_dir}")
        
        # Load receipts and summary
        receipts, export_summary = load_exported_receipts(export_dir)
        logger.info(f"Loaded {len(receipts)} receipts for validation")
        
        # Run validation
        logger.info("Running validation rules...")
        validation_results = run_validation(receipts)
        
        # Analyze parsing quality
        logger.info("Analyzing parsing quality...")
        parsing_analysis = analyze_parsing_quality(receipts)
        
        # Generate report
        logger.info("Generating validation report...")
        report = generate_validation_report(
            validation_results, parsing_analysis, export_summary, export_dir
        )
        
        # Print summary
        print_validation_summary(report)
        
        logger.info(f"Validation report saved: {export_dir / 'validation_report.json'}")
        
        # Return success code based on validation results
        failed_count = len(validation_results['failed_receipts'])
        if failed_count == 0:
            logger.info("🎉 All receipts passed validation!")
            return 0
        else:
            logger.warning(f"⚠️  {failed_count} receipts failed validation")
            return 1
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())