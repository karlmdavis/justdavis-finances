#!/usr/bin/env python3
"""Integration tests for Apple receipt extraction system."""

import pytest
import tempfile
import os
import json
import email
from email.mime.text import MIMEText

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from export_receipts_to_json import AppleReceiptExporter


class TestAppleReceiptExtractionIntegration:
    """Integration tests for the complete Apple receipt extraction system."""

    def setup_method(self):
        """Set up test fixtures with realistic data."""
        self.temp_dir = tempfile.mkdtemp()

        # Sample Apple receipt emails
        self.receipt_emails = [
            {
                'filename': 'receipt_1.eml',
                'html': """
                <html>
                <head><title>Your receipt from Apple</title></head>
                <body>
                    <div id="receipt-header">
                        <h1>Your receipt from Apple</h1>
                        <p>Order ID: ML7PQ2XYZ</p>
                        <p>Date: August 15, 2024</p>
                        <p>Apple ID: ***REMOVED***</p>
                    </div>
                    <table class="items-table">
                        <tr>
                            <td class="item-name">Logic Pro</td>
                            <td class="item-price">$29.99</td>
                        </tr>
                    </table>
                    <div class="totals">
                        <p>Subtotal: $29.99</p>
                        <p>Tax: $2.98</p>
                        <p>Total: $32.97</p>
                    </div>
                </body>
                </html>
                """,
                'subject': 'Your receipt from Apple',
                'from': 'no_reply@email.apple.com',
                'to': '***REMOVED***'
            },
            {
                'filename': 'receipt_2.eml',
                'html': """
                <html>
                <body>
                    <h1>Your receipt from Apple</h1>
                    <p>Order ID: ABCDEF123</p>
                    <p>Date: August 16, 2024</p>
                    <p>Apple ID: erica_apple@***REMOVED***</p>
                    <div class="purchase-summary">
                        <div class="item">
                            <span class="title">TestFlight</span>
                            <span class="cost">$0.00</span>
                        </div>
                        <div class="item">
                            <span class="title">Productivity App</span>
                            <span class="cost">$4.99</span>
                        </div>
                        <div class="item">
                            <span class="title">Game Add-on</span>
                            <span class="cost">$14.99</span>
                        </div>
                        <div class="subtotal">Subtotal: $19.98</div>
                        <div class="tax">Tax: $1.98</div>
                        <div class="total">Total: $21.96</div>
                    </div>
                </body>
                </html>
                """,
                'subject': 'Your receipt from Apple',
                'from': 'no_reply@email.apple.com',
                'to': 'erica_apple@***REMOVED***'
            },
            {
                'filename': 'subscription.eml',
                'html': """
                <html>
                <body>
                    <h1>Your receipt from Apple</h1>
                    <p>Order ID: SUB789012</p>
                    <p>Date: September 1, 2024</p>
                    <p>Apple ID: ***REMOVED***</p>
                    <div>
                        <span>iCloud+ 50GB (Monthly)</span>
                        <span>$0.99</span>
                    </div>
                    <p>Total: $0.99</p>
                </body>
                </html>
                """,
                'subject': 'Your receipt from Apple',
                'from': 'no_reply@email.apple.com',
                'to': '***REMOVED***'
            }
        ]

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_email_files(self):
        """Create test email files in temporary directory."""
        email_dir = os.path.join(self.temp_dir, 'apple', 'data')
        os.makedirs(email_dir, exist_ok=True)

        eml_files = []

        for receipt_data in self.receipt_emails:
            # Create email message
            email_msg = MIMEText(receipt_data['html'], 'html')
            email_msg['Subject'] = receipt_data['subject']
            email_msg['From'] = receipt_data['from']
            email_msg['To'] = receipt_data['to']
            email_msg['Date'] = 'Thu, 15 Aug 2024 12:00:00 +0000'

            # Write to .eml file
            eml_path = os.path.join(email_dir, receipt_data['filename'])
            with open(eml_path, 'w', encoding='utf-8') as f:
                f.write(email_msg.as_string())

            eml_files.append(eml_path)

        return email_dir, eml_files

    def create_apple_exports_structure(self):
        """Create Apple exports directory structure."""
        exports_dir = os.path.join(self.temp_dir, 'apple', 'exports')
        os.makedirs(exports_dir, exist_ok=True)

        # Create account-specific directories
        karl_dir = os.path.join(exports_dir, '***REMOVED***')
        erica_dir = os.path.join(exports_dir, 'erica_apple@***REMOVED***')
        os.makedirs(karl_dir, exist_ok=True)
        os.makedirs(erica_dir, exist_ok=True)

        return exports_dir

    def test_end_to_end_receipt_extraction(self):
        """Test complete workflow from .eml files to JSON export."""
        # Set up test data
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        # Initialize exporter
        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        # Process all emails
        results = exporter.process_all_emails()

        # Should have processed 3 receipts
        assert len(results) >= 3

        # Check that receipts were parsed correctly
        order_ids = [result['order_id'] for result in results if result is not None]
        assert 'ML7PQ2XYZ' in order_ids
        assert 'ABCDEF123' in order_ids
        assert 'SUB789012' in order_ids

        # Check account attribution
        apple_ids = [result['apple_id'] for result in results if result is not None]
        assert '***REMOVED***' in apple_ids
        assert 'erica_apple@***REMOVED***' in apple_ids

    def test_multi_account_organization(self):
        """Test organization of receipts by Apple account."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        # Process and organize by account
        exporter.process_all_emails()
        exporter.organize_by_account()

        # Check that JSON files were created for each account
        karl_dir = os.path.join(exports_dir, '***REMOVED***')
        erica_dir = os.path.join(exports_dir, 'erica_apple@***REMOVED***')

        karl_files = [f for f in os.listdir(karl_dir) if f.endswith('.json')]
        erica_files = [f for f in os.listdir(erica_dir) if f.endswith('.json')]

        assert len(karl_files) >= 1
        assert len(erica_files) >= 1

        # Verify file content
        karl_json_file = os.path.join(karl_dir, karl_files[0])
        with open(karl_json_file, 'r', encoding='utf-8') as f:
            karl_receipts = json.load(f)

        # Should contain Karl's receipts
        assert len(karl_receipts) >= 2  # Logic Pro + Subscription
        karl_order_ids = [receipt['order_id'] for receipt in karl_receipts]
        assert 'ML7PQ2XYZ' in karl_order_ids
        assert 'SUB789012' in karl_order_ids

        # Verify Erica's receipts
        erica_json_file = os.path.join(erica_dir, erica_files[0])
        with open(erica_json_file, 'r', encoding='utf-8') as f:
            erica_receipts = json.load(f)

        assert len(erica_receipts) >= 1
        erica_order_ids = [receipt['order_id'] for receipt in erica_receipts]
        assert 'ABCDEF123' in erica_order_ids

    def test_receipt_data_validation(self):
        """Test validation of extracted receipt data."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        results = exporter.process_all_emails()

        # Validate each receipt
        for result in results:
            if result is not None:
                # Required fields
                assert 'order_id' in result
                assert 'receipt_date' in result
                assert 'apple_id' in result
                assert 'total' in result
                assert 'items' in result

                # Data types
                assert isinstance(result['total'], (int, float))
                assert isinstance(result['items'], list)

                # Valid values
                assert result['order_id'] != ''
                assert '@' in result['apple_id']
                assert result['total'] >= 0

    def test_different_receipt_formats_handling(self):
        """Test handling of different Apple receipt formats."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        results = exporter.process_all_emails()

        # Should successfully parse different formats
        parsed_receipts = [r for r in results if r is not None]
        assert len(parsed_receipts) == 3

        # Verify specific receipt types
        logic_pro_receipt = next(r for r in parsed_receipts if r['order_id'] == 'ML7PQ2XYZ')
        assert logic_pro_receipt['total'] == 32.97
        assert len(logic_pro_receipt['items']) == 1

        multi_item_receipt = next(r for r in parsed_receipts if r['order_id'] == 'ABCDEF123')
        assert multi_item_receipt['total'] == 21.96
        assert len(multi_item_receipt['items']) == 3

        subscription_receipt = next(r for r in parsed_receipts if r['order_id'] == 'SUB789012')
        assert subscription_receipt['total'] == 0.99
        assert len(subscription_receipt['items']) >= 1

    def test_zero_cost_items_preservation(self):
        """Test that zero-cost items are preserved in exports."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        results = exporter.process_all_emails()

        # Find multi-item receipt with free item
        multi_item_receipt = next(r for r in results if r and r['order_id'] == 'ABCDEF123')

        # Should preserve TestFlight (free item)
        item_costs = [item['cost'] for item in multi_item_receipt['items']]
        assert 0.00 in item_costs

        item_titles = [item['title'] for item in multi_item_receipt['items']]
        assert 'TestFlight' in item_titles

    def test_timestamped_export_files(self):
        """Test that export files are timestamped correctly."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        exporter.process_all_emails()
        exporter.organize_by_account()

        # Check file naming patterns
        karl_dir = os.path.join(exports_dir, '***REMOVED***')
        karl_files = os.listdir(karl_dir)

        json_files = [f for f in karl_files if f.endswith('.json')]
        assert len(json_files) >= 1

        # Should have timestamp in filename
        json_file = json_files[0]
        assert '_apple_receipts.json' in json_file
        # Should match pattern YYYY-MM-DD_apple_receipts.json

    def test_error_recovery_with_malformed_emails(self):
        """Test error recovery when some emails are malformed."""
        email_dir, eml_files = self.create_test_email_files()

        # Add malformed email file
        malformed_file = os.path.join(email_dir, 'malformed.eml')
        with open(malformed_file, 'w', encoding='utf-8') as f:
            f.write('This is not a valid email')

        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        # Should handle gracefully and process valid emails
        results = exporter.process_all_emails()

        # Should still process valid emails
        valid_results = [r for r in results if r is not None]
        assert len(valid_results) >= 3  # Original 3 valid receipts

    def test_duplicate_receipt_handling(self):
        """Test handling of duplicate receipts."""
        email_dir, eml_files = self.create_test_email_files()

        # Create duplicate of first receipt
        duplicate_file = os.path.join(email_dir, 'receipt_1_duplicate.eml')
        with open(eml_files[0], 'r', encoding='utf-8') as f:
            duplicate_content = f.read()

        with open(duplicate_file, 'w', encoding='utf-8') as f:
            f.write(duplicate_content)

        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir,
            deduplicate=True
        )

        results = exporter.process_all_emails()

        # Should deduplicate based on order_id
        order_ids = [r['order_id'] for r in results if r is not None]
        unique_order_ids = set(order_ids)

        # Should not have duplicate ML7PQ2XYZ
        assert order_ids.count('ML7PQ2XYZ') == 1
        assert len(unique_order_ids) == 3  # Still 3 unique receipts

    def test_processing_statistics_generation(self):
        """Test generation of processing statistics."""
        email_dir, eml_files = self.create_test_email_files()

        # Add non-Apple email
        non_apple_email = MIMEText('Regular email content', 'plain')
        non_apple_email['Subject'] = 'Not an Apple receipt'
        non_apple_email['From'] = 'someone@example.com'

        non_apple_file = os.path.join(email_dir, 'non_apple.eml')
        with open(non_apple_file, 'w', encoding='utf-8') as f:
            f.write(non_apple_email.as_string())

        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        results = exporter.process_all_emails()
        stats = exporter.get_processing_statistics()

        assert 'total_emails_processed' in stats
        assert 'apple_receipts_found' in stats
        assert 'successful_parses' in stats
        assert 'failed_parses' in stats

        assert stats['total_emails_processed'] == 4  # 3 Apple + 1 non-Apple
        assert stats['apple_receipts_found'] == 3
        assert stats['successful_parses'] == 3

    def test_date_range_filtering(self):
        """Test filtering receipts by date range."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        # Filter to only receipts from August 16 onward
        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir,
            start_date='2024-08-16'
        )

        results = exporter.process_all_emails()

        # Should filter out the August 15 receipt
        valid_results = [r for r in results if r is not None]
        receipt_dates = [r['receipt_date'] for r in valid_results]

        # Should not include 2024-08-15
        assert '2024-08-15' not in receipt_dates
        assert '2024-08-16' in receipt_dates or '2024-09-01' in receipt_dates

    def test_large_batch_processing_performance(self):
        """Test performance with larger batches of emails."""
        email_dir, eml_files = self.create_test_email_files()

        # Create additional test emails
        for i in range(20):  # Add 20 more emails
            additional_html = self.receipt_emails[0]['html'].replace(
                'ML7PQ2XYZ',
                f'BATCH{i:03d}XYZ'
            )

            email_msg = MIMEText(additional_html, 'html')
            email_msg['Subject'] = 'Your receipt from Apple'
            email_msg['From'] = 'no_reply@email.apple.com'

            additional_file = os.path.join(email_dir, f'batch_receipt_{i}.eml')
            with open(additional_file, 'w', encoding='utf-8') as f:
                f.write(email_msg.as_string())

        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        # Measure processing time
        import time
        start_time = time.time()

        results = exporter.process_all_emails()

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete in reasonable time (< 10 seconds for 23 emails)
        assert processing_time < 10.0

        # Should process all emails
        valid_results = [r for r in results if r is not None]
        assert len(valid_results) >= 23

    def test_export_file_structure_validation(self):
        """Test that exported JSON files have correct structure."""
        email_dir, eml_files = self.create_test_email_files()
        exports_dir = self.create_apple_exports_structure()

        exporter = AppleReceiptExporter(
            email_data_dir=email_dir,
            export_base_dir=exports_dir
        )

        exporter.process_all_emails()
        exporter.organize_by_account()

        # Check Karl's export file
        karl_dir = os.path.join(exports_dir, '***REMOVED***')
        karl_files = [f for f in os.listdir(karl_dir) if f.endswith('.json')]

        assert len(karl_files) >= 1

        karl_json_file = os.path.join(karl_dir, karl_files[0])
        with open(karl_json_file, 'r', encoding='utf-8') as f:
            receipts_data = json.load(f)

        # Should be a list of receipts
        assert isinstance(receipts_data, list)

        # Each receipt should have required structure
        for receipt in receipts_data:
            assert 'order_id' in receipt
            assert 'receipt_date' in receipt
            assert 'apple_id' in receipt
            assert 'total' in receipt
            assert 'items' in receipt

            # Items should be properly structured
            for item in receipt['items']:
                assert 'title' in item
                assert 'cost' in item
                assert isinstance(item['cost'], (int, float))


if __name__ == '__main__':
    pytest.main([__file__])