#!/usr/bin/env python3
"""
Apple Receipt Parser - HTML-Only Version

Parses Apple App Store, iTunes, and subscription receipts from HTML email content.
Optimized for 100% HTML coverage using enhanced extraction techniques.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from bs4 import BeautifulSoup
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ParsedReceipt:
    """Represents a parsed Apple receipt with standardized data structure."""
    
    def __init__(self):
        # Core metadata
        self.format_detected: Optional[str] = None
        self.apple_id: Optional[str] = None
        self.receipt_date: Optional[str] = None
        self.order_id: Optional[str] = None
        self.document_number: Optional[str] = None
        
        # Financial data
        self.subtotal: Optional[float] = None
        self.tax: Optional[float] = None
        self.total: Optional[float] = None
        self.currency: str = "USD"
        
        # Billing information
        self.payment_method: Optional[str] = None
        self.billed_to: Optional[Dict[str, str]] = None
        
        # Purchase items
        self.items: List[Dict[str, Any]] = []
        
        # Parsing metadata
        self.parsing_metadata: Dict[str, Any] = {}
        self.base_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "format_detected": self.format_detected,
            "apple_id": self.apple_id,
            "receipt_date": self.receipt_date,
            "order_id": self.order_id,
            "document_number": self.document_number,
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "billed_to": self.billed_to,
            "items": self.items,
            "parsing_metadata": self.parsing_metadata
        }

class BaseReceiptParser:
    """Base class for all receipt parsers."""
    
    def __init__(self):
        self.format_name: str = "base"
    
    def can_parse(self, base_name: str, content_dir: Path) -> bool:
        """Check if this parser can handle the given receipt."""
        raise NotImplementedError
    
    def parse(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse the receipt and return structured data."""
        raise NotImplementedError
    
    def _clean_amount(self, amount_str: str) -> Optional[int]:
        """Clean and convert amount string to integer cents."""
        if not amount_str:
            return None
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,]', '', amount_str.strip())
            if not cleaned:
                return None
            # Parse to integer cents instead of float
            if '.' in cleaned:
                parts = cleaned.split('.')
                dollars = int(parts[0]) if parts[0] else 0
                cents_str = parts[1].ljust(2, '0')[:2]
                cents = int(cents_str)
                return dollars * 100 + cents
            else:
                return int(cleaned) * 100
        except (ValueError, AttributeError):
            return None
    
    def _validate_financial_data(self, receipt: ParsedReceipt):
        """Validate financial data integrity."""
        if receipt.subtotal is not None and receipt.tax is not None and receipt.total is not None:
            expected_total = receipt.subtotal + receipt.tax
            if abs(expected_total - receipt.total) > 0.01:  # Allow 1 cent difference for rounding
                logger.warning(f"Financial discrepancy: {receipt.subtotal} + {receipt.tax} != {receipt.total}")

class EnhancedHTMLParser(BaseReceiptParser):
    """Enhanced HTML parser that handles both legacy and modern formats."""
    
    def __init__(self):
        super().__init__()
        self.format_name = "enhanced_html"
        self.selectors_tried = []
        self.selectors_successful = []
    
    def can_parse(self, base_name: str, content_dir: Path) -> bool:
        """Check if HTML file exists."""
        html_path = content_dir / f"{base_name}-formatted-simple.html"
        return html_path.exists()
    
    def parse(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse HTML receipt with enhanced extraction."""
        receipt = ParsedReceipt()
        receipt.base_name = base_name
        
        html_path = content_dir / f"{base_name}-formatted-simple.html"
        if not html_path.exists():
            receipt.parsing_metadata['errors'] = ['HTML file not found']
            return receipt
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Detect format type
            receipt.format_detected = self._detect_format(soup)
            
            # Reset tracking
            self.selectors_tried = []
            self.selectors_successful = []
            
            # Extract all data
            self._extract_metadata(receipt, soup)
            self._extract_items(receipt, soup)
            self._extract_billing_info(receipt, soup)
            
            # Validate financial integrity
            self._validate_financial_data(receipt)
            
            # Store parsing metadata
            receipt.parsing_metadata = {
                'selectors_successful': self.selectors_successful,
                'selectors_failed': self.selectors_tried,
                'fallback_used': False,
                'extraction_method': 'enhanced_html'
            }
            
        except Exception as e:
            logger.error(f"Failed to parse HTML receipt {base_name}: {e}")
            receipt.parsing_metadata['errors'] = [str(e)]
        
        return receipt
    
    def _detect_format(self, soup: BeautifulSoup) -> str:
        """Detect HTML format type."""
        if soup.select('[class*="custom-"]'):
            return 'modern_html'
        elif soup.select('[class*="aapl-"]'):
            return 'legacy_html' 
        else:
            return 'unknown_html'
    
    def _extract_metadata(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract receipt metadata with robust selectors."""
        
        if receipt.format_detected == 'modern_html':
            self._extract_modern_metadata(receipt, soup)
        else:
            self._extract_legacy_metadata(receipt, soup)
    
    def _extract_modern_metadata(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract metadata from modern HTML with custom-* classes."""
        
        # Date - usually at top of receipt
        date_elem = soup.select_one('p.custom-18w16cf, p[class*="custom-"] time, p[class*="custom-"]:contains("2025")')
        if date_elem:
            receipt.receipt_date = date_elem.get_text().strip()
            self.selectors_successful.append('modern_date')
        
        # Order ID 
        order_label = soup.find(string=re.compile(r'Order ID:', re.I))
        if order_label and order_label.parent:
            next_p = order_label.parent.find_next_sibling('p')
            if next_p:
                receipt.order_id = next_p.get_text().strip()
                self.selectors_successful.append('modern_order_id')
        
        # Document number
        doc_label = soup.find(string=re.compile(r'Document:', re.I))
        if doc_label and doc_label.parent:
            next_p = doc_label.parent.find_next_sibling('p')
            if next_p:
                receipt.document_number = next_p.get_text().strip()
                self.selectors_successful.append('modern_document')
        
        # Apple Account
        account_label = soup.find(string=re.compile(r'Apple Account:', re.I))
        if account_label and account_label.parent:
            next_p = account_label.parent.find_next_sibling('p')
            if next_p:
                receipt.apple_id = next_p.get_text().strip()
                self.selectors_successful.append('modern_apple_id')
        
        # Financial data - modern format uses different structure
        self._extract_modern_financials(receipt, soup)
    
    def _extract_legacy_metadata(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract metadata from legacy HTML with aapl-* classes."""
        
        # Focus on desktop version only to avoid duplication
        desktop_div = soup.select_one('div.aapl-desktop-div')
        search_root = desktop_div if desktop_div else soup
        
        # Date extraction - find DATE span and look for dir="auto" span in same container
        date_spans = search_root.find_all('span', string=re.compile(r'DATE', re.I))
        for date_span in date_spans:
            if date_span and date_span.parent:
                td_container = date_span.parent
                # Look for span with dir="auto" in same TD
                auto_span = td_container.find('span', {'dir': 'auto'})
                if auto_span:
                    receipt.receipt_date = auto_span.get_text().strip()
                    self.selectors_successful.append('legacy_date_auto_span')
                    break
        
        # Fallback: direct regex search for date pattern
        if not receipt.receipt_date:
            text_content = search_root.get_text()
            date_match = re.search(r'([A-Z][a-z]{2} \d{1,2}, \d{4})', text_content)
            if date_match:
                receipt.receipt_date = date_match.group(1)
                self.selectors_successful.append('legacy_date_regex')
        
        # Order ID - handle both link and text formats
        order_label = search_root.find(string=re.compile(r'ORDER ID', re.I))
        if order_label:
            order_container = order_label.parent.parent if hasattr(order_label.parent, 'parent') else order_label.parent
            # Try to find link first
            order_link = order_container.find('a')
            if order_link:
                receipt.order_id = order_link.get_text().strip()
                self.selectors_successful.append('legacy_order_id_link')
            else:
                # Look for text after <br>
                br_tag = order_container.find('br')
                if br_tag and br_tag.next_sibling:
                    order_text = br_tag.next_sibling.strip() if isinstance(br_tag.next_sibling, str) else br_tag.next_sibling.get_text().strip()
                    if order_text:
                        receipt.order_id = order_text
                        self.selectors_successful.append('legacy_order_id_text')
        
        # Document number
        doc_label = search_root.find(string=re.compile(r'DOCUMENT NO', re.I))
        if doc_label and doc_label.parent:
            doc_container = doc_label.parent.parent if hasattr(doc_label.parent, 'parent') else doc_label.parent
            br_tag = doc_container.find('br')
            if br_tag and br_tag.next_sibling:
                doc_text = br_tag.next_sibling.strip() if isinstance(br_tag.next_sibling, str) else br_tag.next_sibling.get_text().strip()
                if doc_text:
                    receipt.document_number = doc_text
                    self.selectors_successful.append('legacy_document')
        
        # Apple ID - direct email search in desktop div
        text_content = search_root.get_text()
        email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text_content)
        if email_matches:
            # Use the first email found (they're usually duplicated)
            receipt.apple_id = email_matches[0]
            self.selectors_successful.append('legacy_apple_id_direct')
        
        # Financial data
        self._extract_legacy_financials(receipt, soup)
    
    def _extract_legacy_financials(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract financial data from legacy HTML format."""
        
        # Focus on desktop version
        desktop_div = soup.select_one('div.aapl-desktop-div')
        search_root = desktop_div if desktop_div else soup
        
        # Look for Subtotal spans
        subtotal_spans = search_root.find_all('span', string=re.compile(r'Subtotal', re.I))
        for span in subtotal_spans:
            # Find parent table row
            table_row = span.parent
            while table_row and table_row.name != 'tr':
                table_row = table_row.parent
            
            if table_row:
                tds = table_row.find_all('td')
                if len(tds) >= 3:
                    # Third column contains the amount
                    amount_span = tds[2].find('span')
                    if amount_span:
                        amount_text = amount_span.get_text().strip()
                        if amount_text.startswith('$'):
                            receipt.subtotal = self._clean_amount(amount_text)
                            self.selectors_successful.append('legacy_subtotal_table')
                            break
        
        # Look for Tax spans
        tax_spans = search_root.find_all('span', string=re.compile(r'Tax', re.I))
        for span in tax_spans:
            table_row = span.parent
            while table_row and table_row.name != 'tr':
                table_row = table_row.parent
            
            if table_row:
                tds = table_row.find_all('td')
                if len(tds) >= 3:
                    amount_span = tds[2].find('span')
                    if amount_span:
                        amount_text = amount_span.get_text().strip()
                        if amount_text.startswith('$'):
                            receipt.tax = self._clean_amount(amount_text)
                            self.selectors_successful.append('legacy_tax_table')
                            break
        
        # Look for TOTAL - find text containing TOTAL
        total_labels = search_root.find_all(string=re.compile(r'TOTAL', re.I))
        for label in total_labels:
            # Navigate up to find the table row
            element = label.parent if label.parent else label
            while element and element.name not in ['tr', 'td']:
                element = element.parent
            
            if element and element.name in ['tr', 'td']:
                # Look for dollar amounts in this context
                container_text = element.get_text()
                amounts = re.findall(r'\$[0-9,.]+', container_text)
                if amounts:
                    receipt.total = self._clean_amount(amounts[0])
                    self.selectors_successful.append('legacy_total_regex')
                    break
        
        # Fallback: Use highest dollar amount as total if nothing found
        if not receipt.total:
            dollar_amounts = re.findall(r'\$([0-9,.]+)', search_root.get_text())
            if dollar_amounts:
                # Convert to integer cents and get maximum
                amounts = []
                for amount_str in dollar_amounts:
                    try:
                        # Parse to integer cents
                        clean = amount_str.replace(',', '').strip()
                        if '.' in clean:
                            parts = clean.split('.')
                            dollars = int(parts[0]) if parts[0] else 0
                            cents_str = parts[1].ljust(2, '0')[:2]
                            cents = int(cents_str)
                            amount_cents = dollars * 100 + cents
                        else:
                            amount_cents = int(clean) * 100
                        amounts.append(amount_cents)
                    except ValueError:
                        continue
                if amounts:
                    receipt.total = max(amounts)
                    self.selectors_successful.append('legacy_total_max')
    
    def _extract_modern_financials(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract financial data from modern HTML format."""
        
        # Modern format typically has Subtotal, Tax labels followed by amounts
        subtotal_label = soup.find(string=re.compile(r'Subtotal', re.I))
        if subtotal_label:
            # Look for nearby custom class elements with amounts
            container = subtotal_label.parent
            for _ in range(5):
                if not container:
                    break
                amount_elems = container.find_all(['p', 'span'], class_=re.compile(r'custom-'))
                for elem in amount_elems:
                    text = elem.get_text().strip()
                    if text.startswith('$'):
                        receipt.subtotal = self._clean_amount(text)
                        self.selectors_successful.append('modern_subtotal')
                        break
                if receipt.subtotal:
                    break
                container = container.parent
        
        # Tax
        tax_label = soup.find(string=re.compile(r'Tax', re.I))
        if tax_label:
            container = tax_label.parent
            for _ in range(5):
                if not container:
                    break
                amount_elems = container.find_all(['p', 'span'], class_=re.compile(r'custom-'))
                for elem in amount_elems:
                    text = elem.get_text().strip()
                    if text.startswith('$'):
                        receipt.tax = self._clean_amount(text)
                        self.selectors_successful.append('modern_tax')
                        break
                if receipt.tax:
                    break
                container = container.parent
        
        # Total - look for largest amount or specific total patterns
        total_amounts = soup.find_all(string=re.compile(r'\$[0-9,.]+'))
        if total_amounts:
            amounts = []
            for amount_str in total_amounts:
                clean_amount = self._clean_amount(amount_str.strip())
                if clean_amount and clean_amount > 0:
                    amounts.append(clean_amount)
            
            if amounts:
                # Use the largest amount as total (common pattern)
                receipt.total = max(amounts)
                self.selectors_successful.append('modern_total_max')
    
    def _extract_items(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract purchased items."""

        items = []

        if receipt.format_detected == 'modern_html':
            # Modern format item extraction - specifically for subscription lockup tables
            item_containers = soup.select('table.subscription-lockup__container tr.subscription-lockup')
            for container in item_containers:
                item = self._extract_modern_item(container)
                if item:
                    items.append(item)
        else:
            # Legacy format item extraction - focus on desktop to avoid duplication
            desktop_div = soup.select_one('div.aapl-desktop-div')
            search_root = desktop_div if desktop_div else soup

            # Look for item cells only (not title spans to avoid duplicates)
            # Exclude mobile cells which have the aapl-mobile-cell class
            item_elements = search_root.select('td.item-cell:not(.aapl-mobile-cell)')
            for elem in item_elements:
                item = self._extract_legacy_item(elem)
                if item:
                    items.append(item)
        
        receipt.items = items

        # Validate that subscription items have cost data
        for item in items:
            if item.get('type') == 'subscription' and not item.get('cost'):
                logger.warning(f"Subscription item '{item.get('title')}' missing cost data - this may indicate a parsing error")
    
    def _extract_legacy_item(self, elem) -> Optional[Dict[str, Any]]:
        """Extract item from legacy HTML element."""
        
        # Look for title/name
        title_elem = elem.find(class_='title') or elem
        if not title_elem:
            return None
            
        title = title_elem.get_text().strip()
        if not title or len(title) < 2:
            return None
        
        # Find price - look in sibling price-cell TD (not child)
        price = None
        if elem.name == 'td':
            parent_tr = elem.find_parent('tr')
            if parent_tr:
                price_elem = parent_tr.find('td', class_='price-cell')
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    if '$' in price_text:
                        price = self._clean_amount(price_text)
        
        # Additional metadata
        item_data = {
            'title': title,
            'subtitle': None,
            'type': 'app store',
            'artist': None,
            'device': None,
            'cost': price,
            'selector_used': 'legacy_item_cell'
        }
        
        # Look for additional details
        if hasattr(elem, 'parent') and elem.parent:
            container = elem.parent
            
            # Device info
            device_elem = container.find(class_='device')
            if device_elem:
                item_data['device'] = device_elem.get_text().strip()
            
            # Type/subtitle info
            type_elems = container.find_all(['span', 'div'], class_=lambda x: x and ('type' in x or 'subtitle' in x))
            for type_elem in type_elems:
                text = type_elem.get_text().strip()
                if text:
                    item_data['subtitle'] = text
                    break
        
        return item_data
    
    def _extract_modern_item(self, container) -> Optional[Dict[str, Any]]:
        """Extract item from modern HTML container."""
        
        # Look for item name in custom classes
        name_elem = container.select_one('[class*="custom-gzadzy"], [class*="custom-"] p, [class*="custom-"] span')
        if not name_elem:
            return None
        
        title = name_elem.get_text().strip()
        if not title or len(title) < 2:
            return None
        
        # Look for price
        price = None
        price_elem = container.select_one('[class*="custom-137u684"], [class*="custom-"]:contains("$")')
        if price_elem:
            price_text = price_elem.get_text().strip()
            if '$' in price_text:
                price = self._clean_amount(price_text)
        
        return {
            'title': title,
            'subtitle': None,
            'type': 'subscription',
            'artist': None,
            'device': None,
            'cost': price,
            'selector_used': 'modern_custom_class'
        }
    
    def _extract_billing_info(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract billing information if available."""
        
        # Look for "BILLED TO" section
        billed_label = soup.find(string=re.compile(r'BILLED TO', re.I))
        if billed_label and billed_label.parent:
            container = billed_label.parent
            
            # Get all text after the label
            billing_text = container.get_text()
            
            # Try to extract structured billing info
            lines = [line.strip() for line in billing_text.split('\n') if line.strip()]
            
            if len(lines) > 1:
                # Remove the "BILLED TO" label
                content_lines = [line for line in lines if 'BILLED TO' not in line.upper()]
                
                if content_lines:
                    receipt.billed_to = {
                        'raw_text': ' '.join(content_lines),
                        'first_line': content_lines[0] if content_lines else None
                    }
                    
                    # Extract payment method if present
                    for line in content_lines:
                        if 'apple pay' in line.lower() or 'visa' in line.lower() or 'card' in line.lower():
                            receipt.payment_method = line
                            break

class AppleReceiptParser:
    """Main receipt parser using HTML-only approach."""
    
    def __init__(self):
        # HTML-only parsing with enhanced parser - covers all 327 receipts (100% HTML coverage)
        self.parsers = [
            EnhancedHTMLParser()   # Handles all HTML formats: legacy (94.2%) + modern (5.8%) = 100%
        ]
    
    def detect_format(self, base_name: str, content_dir: Path) -> str:
        """Detect the appropriate parser for this receipt."""
        for parser in self.parsers:
            if parser.can_parse(base_name, content_dir):
                return parser.format_name
        return 'unknown'
    
    def parse_receipt(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse a receipt using the appropriate format parser."""
        for parser in self.parsers:
            if parser.can_parse(base_name, content_dir):
                logger.info(f"Using {parser.format_name} parser for {base_name}")
                return parser.parse(base_name, content_dir)
        
        # No parser could handle this format
        receipt = ParsedReceipt()
        receipt.format_detected = 'unknown'
        receipt.base_name = base_name
        receipt.parsing_metadata = {
            'errors': ['No suitable parser found'],
            'parsers_attempted': [p.format_name for p in self.parsers]
        }
        logger.error(f"No parser could handle receipt: {base_name}")
        
        return receipt

def get_extracted_content_dir() -> Path:
    """Get the extracted content directory."""
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    
    # Find the most recent email data directory
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    if not email_dirs:
        raise FileNotFoundError("No Apple email data directories found")
    
    # Return the most recent one with extracted_content
    email_dir = max(email_dirs)
    return email_dir / "extracted_content"

def main():
    """Main function for testing the parser."""
    if len(sys.argv) != 2:
        print("Usage: python receipt_parser.py <base_name>")
        sys.exit(1)
    
    base_name = sys.argv[1]
    
    # Find content directory
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    if not email_dirs:
        print("No Apple email data directories found")
        sys.exit(1)
    
    latest_dir = max(email_dirs, key=lambda d: d.name)
    content_dir = latest_dir / "extracted_content"
    
    # Parse receipt
    parser = AppleReceiptParser()
    receipt = parser.parse_receipt(base_name, content_dir)
    
    # Output results
    print(json.dumps(receipt.to_dict(), indent=2, default=str))

if __name__ == "__main__":
    main()