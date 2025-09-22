#!/usr/bin/env python3
"""Tests for Apple receipt parser module."""

import pytest
import tempfile
import os
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from receipt_parser import ReceiptParser


class TestReceiptParser:
    """Test cases for ReceiptParser functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.parser = ReceiptParser()

        # Sample email content with Apple receipt
        self.sample_receipt_html = """
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
        """

        # Sample email message
        self.sample_email_message = MIMEMultipart('alternative')
        self.sample_email_message['Subject'] = 'Your receipt from Apple'
        self.sample_email_message['From'] = 'no_reply@email.apple.com'
        self.sample_email_message['To'] = '***REMOVED***'
        self.sample_email_message['Date'] = 'Thu, 15 Aug 2024 12:00:00 +0000'

        # Add HTML part
        html_part = MIMEText(self.sample_receipt_html, 'html')
        self.sample_email_message.attach(html_part)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_eml_file(self, email_message, filename="test_receipt.eml"):
        """Create a test .eml file from email message."""
        filepath = os.path.join(self.temp_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(email_message.as_string())

        return filepath

    def test_parse_receipt_from_email_message(self):
        """Test parsing receipt from email message object."""
        result = self.parser.parse_receipt_from_message(self.sample_email_message)

        assert result is not None
        assert result['order_id'] == 'ML7PQ2XYZ'
        assert result['receipt_date'] == '2024-08-15'
        assert result['apple_id'] == '***REMOVED***'
        assert result['subtotal'] == 29.99
        assert result['tax'] == 2.98
        assert result['total'] == 32.97

        # Check items
        assert len(result['items']) == 1
        assert result['items'][0]['title'] == 'Logic Pro'
        assert result['items'][0]['cost'] == 29.99

    def test_parse_receipt_from_eml_file(self):
        """Test parsing receipt from .eml file."""
        eml_file = self.create_test_eml_file(self.sample_email_message)

        result = self.parser.parse_receipt_from_file(eml_file)

        assert result is not None
        assert result['order_id'] == 'ML7PQ2XYZ'
        assert result['receipt_date'] == '2024-08-15'
        assert result['apple_id'] == '***REMOVED***'
        assert result['total'] == 32.97

    def test_extract_html_from_email(self):
        """Test extraction of HTML content from email."""
        html_content = self.parser.extract_html_content(self.sample_email_message)

        assert html_content is not None
        assert 'Your receipt from Apple' in html_content
        assert 'ML7PQ2XYZ' in html_content
        assert 'Logic Pro' in html_content

    def test_multipart_email_handling(self):
        """Test handling of multipart emails with text and HTML."""
        # Create email with both text and HTML parts
        multipart_email = MIMEMultipart('alternative')
        multipart_email['Subject'] = 'Your receipt from Apple'
        multipart_email['From'] = 'no_reply@email.apple.com'

        # Add text part
        text_part = MIMEText('Plain text version of receipt', 'plain')
        multipart_email.attach(text_part)

        # Add HTML part
        html_part = MIMEText(self.sample_receipt_html, 'html')
        multipart_email.attach(html_part)

        result = self.parser.parse_receipt_from_message(multipart_email)

        # Should prefer HTML content
        assert result is not None
        assert result['order_id'] == 'ML7PQ2XYZ'

    def test_html_only_email_handling(self):
        """Test handling of HTML-only emails."""
        html_email = MIMEText(self.sample_receipt_html, 'html')
        html_email['Subject'] = 'Your receipt from Apple'
        html_email['From'] = 'no_reply@email.apple.com'

        result = self.parser.parse_receipt_from_message(html_email)

        assert result is not None
        assert result['order_id'] == 'ML7PQ2XYZ'

    def test_email_metadata_extraction(self):
        """Test extraction of email metadata."""
        metadata = self.parser.extract_email_metadata(self.sample_email_message)

        assert 'subject' in metadata
        assert 'from' in metadata
        assert 'to' in metadata
        assert 'date' in metadata

        assert metadata['subject'] == 'Your receipt from Apple'
        assert 'apple.com' in metadata['from']
        assert '***REMOVED***' in metadata['to']

    def test_apple_receipt_email_identification(self):
        """Test identification of Apple receipt emails."""
        # Valid Apple receipt email
        is_apple_receipt = self.parser.is_apple_receipt_email(self.sample_email_message)
        assert is_apple_receipt is True

        # Non-Apple email
        non_apple_email = MIMEText('Regular email content')
        non_apple_email['Subject'] = 'Regular subject'
        non_apple_email['From'] = 'someone@example.com'

        is_not_apple = self.parser.is_apple_receipt_email(non_apple_email)
        assert is_not_apple is False

        # Apple email but not receipt
        apple_non_receipt = MIMEText('Apple content but not receipt')
        apple_non_receipt['Subject'] = 'Apple Newsletter'
        apple_non_receipt['From'] = 'newsletter@apple.com'

        is_not_receipt = self.parser.is_apple_receipt_email(apple_non_receipt)
        assert is_not_receipt is False

    def test_batch_processing_eml_files(self):
        """Test batch processing of multiple .eml files."""
        # Create multiple test files
        eml_files = []
        for i in range(3):
            # Modify order ID for each file
            modified_html = self.sample_receipt_html.replace(
                'ML7PQ2XYZ',
                f'ORDER{i}ABC'
            )

            email_msg = MIMEText(modified_html, 'html')
            email_msg['Subject'] = 'Your receipt from Apple'

            eml_file = self.create_test_eml_file(email_msg, f'receipt_{i}.eml')
            eml_files.append(eml_file)

        # Process all files
        results = self.parser.batch_process_files(eml_files)

        assert len(results) == 3

        # Check that each receipt was parsed correctly
        order_ids = [result['order_id'] for result in results if result is not None]
        assert 'ORDER0ABC' in order_ids
        assert 'ORDER1ABC' in order_ids
        assert 'ORDER2ABC' in order_ids

    def test_malformed_email_handling(self):
        """Test handling of malformed or corrupted email files."""
        # Create malformed .eml file
        malformed_file = os.path.join(self.temp_dir, 'malformed.eml')
        with open(malformed_file, 'w', encoding='utf-8') as f:
            f.write('Not a valid email message')

        result = self.parser.parse_receipt_from_file(malformed_file)

        # Should handle gracefully
        assert result is None

    def test_missing_html_content_handling(self):
        """Test handling of emails without HTML content."""
        text_only_email = MIMEText('Text only receipt content', 'plain')
        text_only_email['Subject'] = 'Your receipt from Apple'

        result = self.parser.parse_receipt_from_message(text_only_email)

        # Should handle gracefully (may return None or attempt text parsing)
        # Behavior depends on implementation strategy

    def test_encoding_handling(self):
        """Test handling of different character encodings."""
        # Create email with special characters
        html_with_unicode = """
        <html>
        <body>
            <p>Order ID: UNI123ñéç</p>
            <p>Date: August 15, 2024</p>
            <p>Apple ID: user@tëst.com</p>
            <p>App: Café – Manager</p>
            <p>Total: $9.99</p>
        </body>
        </html>
        """

        unicode_email = MIMEText(html_with_unicode, 'html', 'utf-8')
        unicode_email['Subject'] = 'Your receipt from Apple'

        result = self.parser.parse_receipt_from_message(unicode_email)

        if result is not None:
            assert 'UNI123ñéç' in result['order_id'] or 'UNI123' in result['order_id']

    def test_parser_error_recovery(self):
        """Test parser error recovery with problematic HTML."""
        # HTML with parsing challenges
        problematic_html = """
        <html>
        <body>
            <p>Order ID: PROB123
            <p>Date: Invalid Date Format
            <p>Apple ID: invalid-email
            <div>Item: <span>Incomplete
            <p>Total: Not a number
        </body>
        </html>
        """

        problematic_email = MIMEText(problematic_html, 'html')
        problematic_email['Subject'] = 'Your receipt from Apple'

        result = self.parser.parse_receipt_from_message(problematic_email)

        # Should either return None or partial data without crashing
        if result is not None:
            # At minimum should extract what's possible
            assert 'PROB123' in result.get('order_id', '')

    def test_subscription_receipt_parsing(self):
        """Test parsing of subscription renewal receipts."""
        subscription_html = """
        <html>
        <body>
            <h1>Your receipt from Apple</h1>
            <p>Order ID: SUB123456</p>
            <p>Date: September 1, 2024</p>
            <p>Apple ID: user@example.com</p>
            <div>
                <span>iCloud+ 50GB (Monthly Subscription)</span>
                <span>$0.99</span>
            </div>
            <p>Total: $0.99</p>
        </body>
        </html>
        """

        subscription_email = MIMEText(subscription_html, 'html')
        subscription_email['Subject'] = 'Your receipt from Apple'

        result = self.parser.parse_receipt_from_message(subscription_email)

        assert result is not None
        assert result['order_id'] == 'SUB123456'
        assert result['total'] == 0.99
        assert len(result['items']) >= 1
        assert 'iCloud' in result['items'][0]['title']

    def test_free_app_receipt_parsing(self):
        """Test parsing of free app download receipts."""
        free_app_html = """
        <html>
        <body>
            <h1>Your receipt from Apple</h1>
            <p>Order ID: FREE123</p>
            <p>Date: September 5, 2024</p>
            <p>Apple ID: user@example.com</p>
            <div>
                <span>TestFlight</span>
                <span>FREE</span>
            </div>
            <p>Total: $0.00</p>
        </body>
        </html>
        """

        free_email = MIMEText(free_app_html, 'html')
        free_email['Subject'] = 'Your receipt from Apple'

        result = self.parser.parse_receipt_from_message(free_email)

        assert result is not None
        assert result['order_id'] == 'FREE123'
        assert result['total'] == 0.00
        assert len(result['items']) >= 1
        assert result['items'][0]['cost'] == 0.00

    def test_parsing_statistics_collection(self):
        """Test collection of parsing statistics."""
        # Process multiple receipts
        eml_files = []
        for i in range(5):
            eml_file = self.create_test_eml_file(
                self.sample_email_message,
                f'receipt_{i}.eml'
            )
            eml_files.append(eml_file)

        # Add one malformed file
        malformed_file = os.path.join(self.temp_dir, 'malformed.eml')
        with open(malformed_file, 'w') as f:
            f.write('Invalid content')
        eml_files.append(malformed_file)

        results = self.parser.batch_process_files(eml_files)
        stats = self.parser.get_parsing_statistics()

        assert 'total_processed' in stats
        assert 'successful_parses' in stats
        assert 'failed_parses' in stats

        assert stats['total_processed'] == 6
        assert stats['successful_parses'] == 5
        assert stats['failed_parses'] == 1

    def test_receipt_validation(self):
        """Test validation of parsed receipt data."""
        result = self.parser.parse_receipt_from_message(self.sample_email_message)

        # Validate structure
        is_valid = self.parser.validate_receipt_data(result)
        assert is_valid is True

        # Test with incomplete data
        incomplete_result = {
            'order_id': 'TEST123',
            # Missing required fields
        }

        is_invalid = self.parser.validate_receipt_data(incomplete_result)
        assert is_invalid is False

    def test_duplicate_receipt_detection(self):
        """Test detection of duplicate receipts."""
        # Create two identical receipts
        result1 = self.parser.parse_receipt_from_message(self.sample_email_message)
        result2 = self.parser.parse_receipt_from_message(self.sample_email_message)

        # Should detect as duplicates
        is_duplicate = self.parser.is_duplicate_receipt(result1, result2)
        assert is_duplicate is True

        # Create different receipt
        different_html = self.sample_receipt_html.replace('ML7PQ2XYZ', 'DIFFERENT123')
        different_email = MIMEText(different_html, 'html')
        different_email['Subject'] = 'Your receipt from Apple'

        result3 = self.parser.parse_receipt_from_message(different_email)

        # Should not be duplicate
        is_not_duplicate = self.parser.is_duplicate_receipt(result1, result3)
        assert is_not_duplicate is False


if __name__ == '__main__':
    pytest.main([__file__])