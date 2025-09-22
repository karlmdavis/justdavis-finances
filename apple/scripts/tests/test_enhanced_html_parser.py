#!/usr/bin/env python3
"""Tests for Apple receipt HTML parser."""

import pytest
from bs4 import BeautifulSoup

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_html_parser import EnhancedHTMLParser


class TestEnhancedHTMLParser:
    """Test cases for EnhancedHTMLParser functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = EnhancedHTMLParser()

        # Sample modern receipt HTML
        self.modern_receipt_html = """
        <html>
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
                <tr>
                    <td class="item-name">Final Cut Pro</td>
                    <td class="item-price">$19.99</td>
                </tr>
            </table>
            <div class="totals">
                <p>Subtotal: $49.98</p>
                <p>Tax: $4.99</p>
                <p>Total: $54.97</p>
            </div>
        </body>
        </html>
        """

        # Sample legacy receipt HTML (different structure)
        self.legacy_receipt_html = """
        <html>
        <body>
            <div class="receipt-info">
                <span>Receipt for order ML7PQ2XYZ</span>
                <span>Purchased on 08/15/2024</span>
                <span>Apple ID: ***REMOVED***</span>
            </div>
            <div class="purchase-summary">
                <div class="item">
                    <span class="title">Logic Pro</span>
                    <span class="cost">$29.99</span>
                </div>
                <div class="item">
                    <span class="title">Final Cut Pro</span>
                    <span class="cost">$19.99</span>
                </div>
                <div class="subtotal">Subtotal: $49.98</div>
                <div class="tax">Tax: $4.99</div>
                <div class="total">Total: $54.97</div>
            </div>
        </body>
        </html>
        """

        # Minimal receipt HTML
        self.minimal_receipt_html = """
        <html>
        <body>
            <p>Order: SIMPLE123</p>
            <p>Date: 2024-08-20</p>
            <p>TestFlight</p>
            <p>$0.00</p>
            <p>Total: $0.00</p>
        </body>
        </html>
        """

    def test_parse_modern_receipt_format(self):
        """Test parsing of modern receipt HTML format."""
        result = self.parser.parse_receipt_html(self.modern_receipt_html)

        assert result is not None
        assert result['order_id'] == 'ML7PQ2XYZ'
        assert result['receipt_date'] == '2024-08-15'
        assert result['apple_id'] == '***REMOVED***'
        assert result['subtotal'] == 49.98
        assert result['tax'] == 4.99
        assert result['total'] == 54.97

        # Check items
        assert len(result['items']) == 2
        assert any(item['title'] == 'Logic Pro' and item['cost'] == 29.99 for item in result['items'])
        assert any(item['title'] == 'Final Cut Pro' and item['cost'] == 19.99 for item in result['items'])

    def test_parse_legacy_receipt_format(self):
        """Test parsing of legacy receipt HTML format."""
        result = self.parser.parse_receipt_html(self.legacy_receipt_html)

        assert result is not None
        assert result['order_id'] == 'ML7PQ2XYZ'
        assert result['receipt_date'] == '2024-08-15'
        assert result['apple_id'] == '***REMOVED***'
        assert result['subtotal'] == 49.98
        assert result['tax'] == 4.99
        assert result['total'] == 54.97

        # Check items
        assert len(result['items']) == 2
        assert any(item['title'] == 'Logic Pro' and item['cost'] == 29.99 for item in result['items'])
        assert any(item['title'] == 'Final Cut Pro' and item['cost'] == 19.99 for item in result['items'])

    def test_parse_minimal_receipt(self):
        """Test parsing of minimal receipt HTML."""
        result = self.parser.parse_receipt_html(self.minimal_receipt_html)

        assert result is not None
        assert result['order_id'] == 'SIMPLE123'
        assert result['receipt_date'] == '2024-08-20'
        assert result['total'] == 0.00

        # Should handle free app
        assert len(result['items']) >= 1
        assert any(item['cost'] == 0.00 for item in result['items'])

    def test_extract_order_id_various_formats(self):
        """Test extraction of order IDs from various HTML formats."""
        # Standard format
        html1 = '<p>Order ID: ML7PQ2XYZ</p>'
        soup1 = BeautifulSoup(html1, 'html.parser')
        order_id1 = self.parser.extract_order_id(soup1)
        assert order_id1 == 'ML7PQ2XYZ'

        # Alternative format
        html2 = '<span>Receipt for order ABC123DEF</span>'
        soup2 = BeautifulSoup(html2, 'html.parser')
        order_id2 = self.parser.extract_order_id(soup2)
        assert order_id2 == 'ABC123DEF'

        # Document number format
        html3 = '<div>Document No: DOC789XYZ</div>'
        soup3 = BeautifulSoup(html3, 'html.parser')
        order_id3 = self.parser.extract_order_id(soup3)
        assert order_id3 == 'DOC789XYZ'

    def test_extract_date_various_formats(self):
        """Test extraction of dates from various HTML formats."""
        # Standard format
        html1 = '<p>Date: August 15, 2024</p>'
        soup1 = BeautifulSoup(html1, 'html.parser')
        date1 = self.parser.extract_date(soup1)
        assert date1 == '2024-08-15'

        # Numeric format
        html2 = '<span>Purchased on 08/15/2024</span>'
        soup2 = BeautifulSoup(html2, 'html.parser')
        date2 = self.parser.extract_date(soup2)
        assert date2 == '2024-08-15'

        # ISO format
        html3 = '<div>2024-08-15</div>'
        soup3 = BeautifulSoup(html3, 'html.parser')
        date3 = self.parser.extract_date(soup3)
        assert date3 == '2024-08-15'

    def test_extract_apple_id_various_formats(self):
        """Test extraction of Apple IDs from various HTML formats."""
        # Standard format
        html1 = '<p>Apple ID: ***REMOVED***</p>'
        soup1 = BeautifulSoup(html1, 'html.parser')
        apple_id1 = self.parser.extract_apple_id(soup1)
        assert apple_id1 == '***REMOVED***'

        # Account format
        html2 = '<span>Account: erica@example.com</span>'
        soup2 = BeautifulSoup(html2, 'html.parser')
        apple_id2 = self.parser.extract_apple_id(soup2)
        assert apple_id2 == 'erica@example.com'

        # Email in text
        html3 = '<div>Purchased by test.user@domain.org</div>'
        soup3 = BeautifulSoup(html3, 'html.parser')
        apple_id3 = self.parser.extract_apple_id(soup3)
        assert apple_id3 == 'test.user@domain.org'

    def test_extract_items_table_format(self):
        """Test extraction of items from table format."""
        table_html = """
        <table>
            <tr>
                <td>Logic Pro</td>
                <td>$29.99</td>
            </tr>
            <tr>
                <td>Final Cut Pro</td>
                <td>$19.99</td>
            </tr>
            <tr>
                <td>Free App</td>
                <td>$0.00</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(table_html, 'html.parser')
        items = self.parser.extract_items(soup)

        assert len(items) == 3
        assert any(item['title'] == 'Logic Pro' and item['cost'] == 29.99 for item in items)
        assert any(item['title'] == 'Final Cut Pro' and item['cost'] == 19.99 for item in items)
        assert any(item['title'] == 'Free App' and item['cost'] == 0.00 for item in items)

    def test_extract_items_div_format(self):
        """Test extraction of items from div-based format."""
        div_html = """
        <div class="items">
            <div class="item">
                <span class="title">Logic Pro</span>
                <span class="cost">$29.99</span>
            </div>
            <div class="item">
                <span class="title">Final Cut Pro</span>
                <span class="cost">$19.99</span>
            </div>
        </div>
        """
        soup = BeautifulSoup(div_html, 'html.parser')
        items = self.parser.extract_items(soup)

        assert len(items) == 2
        assert any(item['title'] == 'Logic Pro' and item['cost'] == 29.99 for item in items)
        assert any(item['title'] == 'Final Cut Pro' and item['cost'] == 19.99 for item in items)

    def test_extract_financial_totals(self):
        """Test extraction of subtotal, tax, and total amounts."""
        totals_html = """
        <div>
            <p>Subtotal: $49.98</p>
            <p>Tax: $4.99</p>
            <p>Total: $54.97</p>
        </div>
        """
        soup = BeautifulSoup(totals_html, 'html.parser')

        subtotal = self.parser.extract_subtotal(soup)
        tax = self.parser.extract_tax(soup)
        total = self.parser.extract_total(soup)

        assert subtotal == 49.98
        assert tax == 4.99
        assert total == 54.97

    def test_parse_currency_amounts(self):
        """Test parsing of various currency amount formats."""
        assert self.parser.parse_currency('$29.99') == 29.99
        assert self.parser.parse_currency('$0.99') == 0.99
        assert self.parser.parse_currency('$0.00') == 0.00
        assert self.parser.parse_currency('$100.00') == 100.00
        assert self.parser.parse_currency('FREE') == 0.00
        assert self.parser.parse_currency('') == 0.00

        # Without dollar sign
        assert self.parser.parse_currency('29.99') == 29.99

        # With extra whitespace
        assert self.parser.parse_currency(' $29.99 ') == 29.99

    def test_parse_date_formats(self):
        """Test parsing of various date formats."""
        assert self.parser.parse_date('August 15, 2024') == '2024-08-15'
        assert self.parser.parse_date('08/15/2024') == '2024-08-15'
        assert self.parser.parse_date('2024-08-15') == '2024-08-15'
        assert self.parser.parse_date('Aug 15, 2024') == '2024-08-15'

        # Handle different separators
        assert self.parser.parse_date('08-15-2024') == '2024-08-15'
        assert self.parser.parse_date('15/08/2024') == '2024-08-15'  # European format

    def test_malformed_html_handling(self):
        """Test handling of malformed or incomplete HTML."""
        # Missing required fields
        incomplete_html = """
        <html>
        <body>
            <p>Some content but no order info</p>
        </body>
        </html>
        """

        result = self.parser.parse_receipt_html(incomplete_html)
        # Should handle gracefully, possibly returning None or partial data

    def test_empty_html_handling(self):
        """Test handling of empty or invalid HTML."""
        # Empty HTML
        result1 = self.parser.parse_receipt_html('')
        assert result1 is None

        # Invalid HTML
        result2 = self.parser.parse_receipt_html('<invalid>')
        assert result2 is None

        # HTML with no content
        result3 = self.parser.parse_receipt_html('<html><body></body></html>')
        assert result3 is None

    def test_subscription_receipt_handling(self):
        """Test handling of subscription receipts."""
        subscription_html = """
        <html>
        <body>
            <p>Order: SUB123456</p>
            <p>Date: September 1, 2024</p>
            <p>Apple ID: user@example.com</p>
            <div class="item">
                <span>iCloud+ 50GB (Monthly)</span>
                <span>$0.99</span>
            </div>
            <p>Total: $0.99</p>
        </body>
        </html>
        """

        result = self.parser.parse_receipt_html(subscription_html)

        assert result is not None
        assert result['order_id'] == 'SUB123456'
        assert result['total'] == 0.99
        assert len(result['items']) == 1
        assert 'iCloud' in result['items'][0]['title']

    def test_in_app_purchase_receipt_handling(self):
        """Test handling of in-app purchase receipts."""
        iap_html = """
        <html>
        <body>
            <p>Order: IAP789012</p>
            <p>Date: September 5, 2024</p>
            <p>Apple ID: gamer@example.com</p>
            <div class="item">
                <span>Game Name - Extra Lives Pack</span>
                <span>$4.99</span>
            </div>
            <div class="item">
                <span>Game Name - Premium Currency</span>
                <span>$9.99</span>
            </div>
            <p>Total: $14.98</p>
        </body>
        </html>
        """

        result = self.parser.parse_receipt_html(iap_html)

        assert result is not None
        assert result['order_id'] == 'IAP789012'
        assert result['total'] == 14.98
        assert len(result['items']) == 2

    def test_international_currency_handling(self):
        """Test handling of international currencies (if applicable)."""
        # This test assumes the parser might encounter non-USD currencies
        intl_html = """
        <html>
        <body>
            <p>Order: INTL123</p>
            <p>Date: 2024-09-10</p>
            <p>Apple ID: user@example.com</p>
            <div class="item">
                <span>App Name</span>
                <span>€9.99</span>
            </div>
            <p>Total: €9.99</p>
        </body>
        </html>
        """

        result = self.parser.parse_receipt_html(intl_html)

        # Should handle gracefully, possibly converting or noting currency
        if result is not None:
            assert result['order_id'] == 'INTL123'
            # Currency handling depends on implementation

    def test_receipt_format_detection(self):
        """Test detection of different receipt formats."""
        # Modern format
        modern_format = self.parser.detect_receipt_format(
            BeautifulSoup(self.modern_receipt_html, 'html.parser')
        )
        assert modern_format in ['modern', 'table', 'structured']

        # Legacy format
        legacy_format = self.parser.detect_receipt_format(
            BeautifulSoup(self.legacy_receipt_html, 'html.parser')
        )
        assert legacy_format in ['legacy', 'div', 'simple']

    def test_parser_robustness_with_variations(self):
        """Test parser robustness with HTML variations."""
        # Different attribute names and structures
        variant_html = """
        <html>
        <body>
            <section id="receipt-details">
                <h2>Purchase Receipt</h2>
                <div data-order="VAR123ABC"></div>
                <div data-date="2024-09-15"></div>
                <div data-account="variant@test.com"></div>
                <ul class="purchase-items">
                    <li data-item="App A" data-price="12.99"></li>
                    <li data-item="App B" data-price="7.99"></li>
                </ul>
                <div class="summary">
                    <span data-total="20.98"></span>
                </div>
            </section>
        </body>
        </html>
        """

        result = self.parser.parse_receipt_html(variant_html)

        # Should adapt to structural variations
        # Exact behavior depends on implementation flexibility

    def test_text_cleanup_and_normalization(self):
        """Test text cleanup and normalization functionality."""
        # Test cleanup of extracted text
        dirty_text = "  \n\t  App Name\u00a0\u2013 Extra Content  \n  "
        clean_text = self.parser.clean_text(dirty_text)

        assert clean_text.strip() != dirty_text
        assert 'App Name' in clean_text
        # Should remove extra whitespace and normalize characters


if __name__ == '__main__':
    pytest.main([__file__])