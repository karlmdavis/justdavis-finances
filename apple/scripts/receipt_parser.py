#!/usr/bin/env python3
"""
Apple Receipt Parser System

Implements the three-parser architecture identified through corrected analysis:
1. PlainTextParser (67.9% coverage) - Handles 2020-2023 receipts
2. LegacyHTMLParser (26.3% coverage) - Handles 2024+ aapl-* classes
3. ModernHTMLParser (5.8% coverage) - Handles 2025+ custom-* classes

Based on corrected format analysis showing temporal evolution rather than parallel systems.
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
    """Represents a parsed Apple receipt with standardized data."""
    
    def __init__(self):
        self.format_detected: Optional[str] = None
        self.apple_id: Optional[str] = None
        self.receipt_date: Optional[str] = None
        self.order_id: Optional[str] = None
        self.document_number: Optional[str] = None
        self.subtotal: Optional[float] = None
        self.tax: Optional[float] = None
        self.total: Optional[float] = None
        self.currency: str = "USD"
        self.payment_method: Optional[str] = None
        self.billed_to: Optional[Dict[str, str]] = None
        self.items: List[Dict[str, Any]] = []
        self.parsing_metadata: Dict[str, Any] = {}
    
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
        self.format_name = "base"
    
    def can_parse(self, base_name: str, content_dir: Path) -> bool:
        """Check if this parser can handle the receipt format."""
        raise NotImplementedError
    
    def parse(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse the receipt and return structured data."""
        raise NotImplementedError
    
    def _clean_amount(self, amount_str: str) -> Optional[float]:
        """Clean and convert amount string to float."""
        if not amount_str:
            return None
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,]', '', amount_str.strip())
            return float(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None
    
    def _validate_financial_data(self, receipt: ParsedReceipt):
        """Validate financial calculations."""
        if receipt.subtotal and receipt.tax and receipt.total:
            calculated_total = receipt.subtotal + receipt.tax
            if abs(calculated_total - receipt.total) > 0.01:
                logger.warning(f"Financial mismatch: {receipt.subtotal} + {receipt.tax} != {receipt.total}")

class PlainTextParser(BaseReceiptParser):
    """Parser for plain text receipts (2020-2023, primary format)."""
    
    def __init__(self):
        super().__init__()
        self.format_name = "plain_text"
    
    def can_parse(self, base_name: str, content_dir: Path) -> bool:
        """Check if plain text file exists and has meaningful content."""
        txt_path = content_dir / f"{base_name}.txt"
        if not txt_path.exists():
            return False
        
        try:
            # Check file size (should be substantial)
            if txt_path.stat().st_size < 100:
                return False
            
            # Check for key receipt indicators
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read(500)  # Check first 500 chars
                return any(indicator in content for indicator in [
                    'ORDER ID:', 'DOCUMENT NO.:', 'APPLE ID', 'TOTAL:'
                ])
        except Exception:
            return False
    
    def parse(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse plain text receipt."""
        receipt = ParsedReceipt()
        receipt.format_detected = self.format_name
        
        txt_path = content_dir / f"{base_name}.txt"
        
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Extract metadata with regex patterns
            self._extract_metadata(receipt, content, lines)
            
            # Extract items
            self._extract_items(receipt, lines)
            
            # Validate financial data
            self._validate_financial_data(receipt)
            
            receipt.parsing_metadata = {
                'selectors_successful': [],
                'selectors_failed': [],
                'fallback_used': False,
                'extraction_method': 'regex_patterns'
            }
            
        except Exception as e:
            logger.error(f"Failed to parse plain text receipt {base_name}: {e}")
            receipt.parsing_metadata['errors'] = [str(e)]
        
        return receipt
    
    def _extract_metadata(self, receipt: ParsedReceipt, content: str, lines: List[str]):
        """Extract metadata using regex patterns."""
        
        # Order ID
        order_match = re.search(r'ORDER ID:\s+(\w+)', content)
        if order_match:
            receipt.order_id = order_match.group(1)
        
        # Document number
        doc_match = re.search(r'DOCUMENT NO\.:\s+(\d+)', content)
        if doc_match:
            receipt.document_number = doc_match.group(1)
        
        # Apple ID (email)
        email_match = re.search(r'([\w\.-]+@[\w\.-]+\.\w+)', content)
        if email_match:
            receipt.apple_id = email_match.group(1)
        
        # Date
        date_match = re.search(r'DATE:\s+(.+)', content)
        if date_match:
            receipt.receipt_date = date_match.group(1).strip()
        
        # Financial amounts
        total_match = re.search(r'TOTAL:\s+\$([0-9,.]+)', content)
        if total_match:
            receipt.total = self._clean_amount(total_match.group(1))
        
        # Try multiple patterns for subtotal and tax
        subtotal_patterns = [
            r'Subtotal\s+\$([0-9,.]+)',           # Simple format
            r'^\s*Subtotal\s+\$([0-9,.]+)',      # Line-start format  
            r'Subtotal\s*\$([0-9,.]+)'           # No space format
        ]
        for pattern in subtotal_patterns:
            subtotal_match = re.search(pattern, content, re.MULTILINE)
            if subtotal_match:
                receipt.subtotal = self._clean_amount(subtotal_match.group(1))
                break
        
        tax_patterns = [
            r'Tax\s+\$([0-9,.]+)',               # Simple format
            r'^\s*Tax\s+\$([0-9,.]+)',          # Line-start format
            r'Tax\s*\$([0-9,.]+)'               # No space format  
        ]
        for pattern in tax_patterns:
            tax_match = re.search(pattern, content, re.MULTILINE)
            if tax_match:
                receipt.tax = self._clean_amount(tax_match.group(1))
                break
    
    def _extract_items(self, receipt: ParsedReceipt, lines: List[str]):
        """Extract items from plain text, including multi-line items."""
        current_section = None
        
        # Define section patterns that identify purchase categories
        section_patterns = [
            'App Store', 'Books', 'Apple Books', 'Music', 'Movies', 'TV Shows', 'iTunes Store',
            'iCloud', 'iCloud+', 'Apple Services', 'Apple One', 'Apple Music', 
            'Apple News+', 'Apple TV', 'Apple TV+', 'Apple Arcade', 'Apple Fitness+'
        ]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Look for section headers
            if line in section_patterns:
                current_section = line
                i += 1
                continue
                
            # Also check for section dividers (lines with only dashes)
            if re.match(r'^-+$', line.strip()) and len(line.strip()) > 10:
                i += 1
                continue
            
            # Skip known non-item lines
            skip_patterns = [
                'Apple Receipt', 'APPLE ID', 'BILLED TO', 'ORDER ID:', 
                'DOCUMENT NO.:', 'DATE:', 'TOTAL:', 'Get help', 'Learn how',
                'Apple respects', 'Terms of Sale', 'Subtotal', 'Tax'
            ]
            if any(skip in line for skip in skip_patterns):
                i += 1
                continue
            
            # Skip lines that are just "TOTAL" (which appear as items incorrectly)
            if line.strip() in ['TOTAL', 'Subtotal', 'Tax']:
                i += 1
                continue
            
            # Look for item lines (line ending with price)
            price_match = re.search(r'(.+?)\s+\$([0-9,.]+)$', line)
            if price_match and current_section:
                item_name = price_match.group(1).strip()
                item_price = self._clean_amount(price_match.group(2))
                
                # Skip financial summary lines that aren't actual items
                if item_name in ['TOTAL', 'Subtotal', 'Tax']:
                    i += 1
                    continue
                
                # Skip items with template variables (Apple's placeholder text)
                if '@@' in item_name:
                    # Try to clean up the template - often it's in the middle
                    clean_name = re.sub(r'\s+with\s+@@[^@]+@@\s+of\s+', ' ', item_name)
                    clean_name = re.sub(r'@@[^@]+@@', '[Storage Amount]', clean_name)
                    item_name = clean_name.strip()
                
                if item_name and len(item_name) > 2:  # Avoid false matches
                    # Now collect multi-line metadata for this item
                    subtitle = None
                    artist = None
                    device = None
                    item_type = current_section.lower()
                    
                    # Look ahead for metadata lines (lines without prices that aren't empty or dividers)
                    j = i + 1
                    metadata_lines = []
                    while j < len(lines):
                        next_line = lines[j].strip()
                        
                        # Stop if we hit empty line, divider, or another item with price
                        if (not next_line or 
                            re.match(r'^-+$', next_line) or 
                            re.search(r'\$([0-9,.]+)$', next_line) or
                            next_line in section_patterns or
                            any(skip in next_line for skip in skip_patterns)):
                            break
                            
                        metadata_lines.append(next_line)
                        j += 1
                    
                    # Process metadata lines to extract subtitle, artist, device
                    for meta_line in metadata_lines:
                        # Common patterns for different metadata types
                        if any(word in meta_line.lower() for word in ['iphone', 'ipad', 'mac', 'apple tv', 'watch']):
                            device = meta_line
                        elif any(word in meta_line.lower() for word in ['book', 'movie', 'tv show', 'app', 'music', 'song', 'album']):
                            # This might be item type info, could be subtitle
                            if not subtitle:
                                subtitle = meta_line
                        elif meta_line and not subtitle:
                            # First non-device line becomes subtitle (often author, artist, etc.)
                            subtitle = meta_line
                        elif meta_line and not artist and subtitle != meta_line:
                            # Second metadata line might be artist if different from subtitle
                            artist = meta_line
                    
                    # Specific handling for subscriptions and renewals
                    if 'Automatic Renewal' in item_name:
                        if metadata_lines and 'Monthly' in metadata_lines[0]:
                            subtitle = metadata_lines[0]
                        if len(metadata_lines) > 1 and 'Renews' in metadata_lines[1]:
                            if not subtitle:
                                subtitle = metadata_lines[1]
                    
                    receipt.items.append({
                        'title': item_name,
                        'subtitle': subtitle,
                        'type': item_type,
                        'artist': artist,
                        'device': device,
                        'cost': item_price,
                        'selector_used': 'text_line_parsing'
                    })
                    
                    # Skip the metadata lines we just processed
                    i = j
                    continue
            
            i += 1

class LegacyHTMLParser(BaseReceiptParser):
    """Parser for legacy HTML receipts (2024+ with aapl-* classes)."""
    
    def __init__(self):
        super().__init__()
        self.format_name = "legacy_html"
    
    def can_parse(self, base_name: str, content_dir: Path) -> bool:
        """Check for legacy HTML format with aapl-* classes."""
        html_path = content_dir / f"{base_name}-formatted-simple.html"
        if not html_path.exists():
            return False
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Look for aapl-* classes but not custom-* classes
            has_aapl = bool(soup.select('[class*="aapl-"]'))
            has_custom = bool(soup.select('[class*="custom-"]'))
            
            return has_aapl and not has_custom
        except Exception:
            return False
    
    def parse(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse legacy HTML receipt."""
        receipt = ParsedReceipt()
        receipt.format_detected = self.format_name
        
        html_path = content_dir / f"{base_name}-formatted-simple.html"
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract metadata using CSS selectors
            self._extract_metadata_html(receipt, soup)
            
            # Extract items
            self._extract_items_html(receipt, soup)
            
            # Validate financial data
            self._validate_financial_data(receipt)
            
            receipt.parsing_metadata = {
                'selectors_successful': [],
                'selectors_failed': [],
                'fallback_used': False,
                'extraction_method': 'css_selectors'
            }
            
        except Exception as e:
            logger.error(f"Failed to parse legacy HTML receipt {base_name}: {e}")
            receipt.parsing_metadata['errors'] = [str(e)]
        
        return receipt
    
    def _extract_metadata_html(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract metadata from legacy HTML using CSS selectors."""
        
        # Try multiple selector patterns for each field
        selectors_tried = []
        
        # Order ID - need to handle structure in legacy format
        order_selectors = [
            'span:-soup-contains("ORDER ID") ~ span a',  # Legacy: sibling span with link
            'span:-soup-contains("ORDER ID") ~ span',    # Legacy: sibling span
            'td:-soup-contains("ORDER ID") span a',      # Direct child span with link
            'td:-soup-contains("ORDER ID") a',           # Direct child link
            '*:-soup-contains("Order ID:") + *'
        ]
        receipt.order_id = self._extract_with_fallbacks(soup, order_selectors, selectors_tried)
        
        # Document number - Legacy HTML has it after a <br/> following "DOCUMENT NO."
        doc_element = soup.select_one('span:-soup-contains("DOCUMENT NO.")')
        doc_text = None
        
        if doc_element:
            parent_td = doc_element.find_parent('td')
            if parent_td:
                # Get all text from the td and look for the document number
                text = parent_td.get_text()
                doc_match = re.search(r'DOCUMENT NO\.\s*(\d+)', text)
                if doc_match:
                    doc_text = doc_match.group(1)
                else:
                    # Try to find just the number after "DOCUMENT NO."
                    lines = text.strip().split('\n')
                    for i, line in enumerate(lines):
                        if "DOCUMENT NO." in line and i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line.isdigit():
                                doc_text = next_line
                                break
        
        receipt.document_number = doc_text
        
        # Apple ID
        apple_id_selectors = [
            'span:-soup-contains("APPLE ID") + span',
            'td:-soup-contains("APPLE ID") + td'
        ]
        receipt.apple_id = self._extract_with_fallbacks(soup, apple_id_selectors, selectors_tried)
        
        # If Apple ID not found with selectors, try text search
        if not receipt.apple_id:
            text_content = soup.get_text()
            email_match = re.search(r'([\w\.-]+@[\w\.-]+\.\w+)', text_content)
            if email_match:
                receipt.apple_id = email_match.group(1)
        
        # Financial amounts - Legacy HTML uses complex nested table structure
        subtotal_selectors = [
            'td:-soup-contains("Subtotal") + td + td span',  # Legacy nested table format
            'td:-soup-contains("Subtotal") + td span',       # Alternative format
            'span:-soup-contains("Subtotal") + span',        # Simple adjacent
        ]
        subtotal_text = self._extract_with_fallbacks(soup, subtotal_selectors, selectors_tried)
        receipt.subtotal = self._clean_amount(subtotal_text)
        
        tax_selectors = [
            'td:-soup-contains("Tax") + td + td span',       # Legacy nested table format
            'td:-soup-contains("Tax") + td span',            # Alternative format
            'span:-soup-contains("Tax") + span',             # Simple adjacent
        ]
        tax_text = self._extract_with_fallbacks(soup, tax_selectors, selectors_tried)
        receipt.tax = self._clean_amount(tax_text)
        
        total_selectors = [
            'td:-soup-contains("TOTAL") + td + td',          # Legacy nested table format
            'td.aapl-mobile-cell:-soup-contains("TOTAL") + td.aapl-mobile-cell', # Mobile format
            'td:-soup-contains("TOTAL") + td',               # Alternative format
        ]
        total_text = self._extract_with_fallbacks(soup, total_selectors, selectors_tried)
        receipt.total = self._clean_amount(total_text)
        
        receipt.parsing_metadata['selectors_tried'] = selectors_tried
    
    def _extract_items_html(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract items from legacy HTML - desktop version only to avoid duplication."""
        
        items_found = []
        
        # Scope selection to desktop div only (avoid mobile duplication)
        # If no desktop div exists, fall back to searching entire document
        desktop_div = soup.select_one('div.aapl-desktop-div')
        search_root = desktop_div if desktop_div else soup
        
        # Look for items with semantic classes within the desktop version
        for item_element in search_root.select('span.title'):
            title = item_element.get_text(strip=True)
            
            # Try to find associated price
            price_element = None
            parent = item_element.find_parent('tr') or item_element.find_parent('td')
            if parent:
                price_element = parent.select_one('td.price-cell, .price, *:-soup-contains("$")')
            
            price = None
            if price_element:
                price_text = price_element.get_text(strip=True)
                price = self._clean_amount(price_text)
            
            # Only include items with valid price (skip items without cost)
            if price is None or price <= 0:
                continue
            
            # Try to find artist/developer
            artist_element = None
            if parent:
                artist_element = parent.select_one('span.artist')
            artist = artist_element.get_text(strip=True) if artist_element else None
            
            # Try to find device
            device_element = None
            if parent:
                device_element = parent.select_one('span.device')
            device = device_element.get_text(strip=True) if device_element else None
            
            # Try to find type
            type_element = None
            if parent:
                type_element = parent.select_one('span.type')
            item_type = type_element.get_text(strip=True) if type_element else 'item'
            
            items_found.append({
                'title': title,
                'subtitle': None,
                'type': item_type,
                'artist': artist,
                'device': device,
                'cost': price,
                'selector_used': 'div.aapl-desktop-div span.title'
            })
        
        # No deduplication - preserve all items including legitimate duplicates
        receipt.items = items_found
    
    def _extract_with_fallbacks(self, soup: BeautifulSoup, selectors: List[str], selectors_tried: List[str]) -> Optional[str]:
        """Try multiple selectors until one works."""
        for selector in selectors:
            try:
                selectors_tried.append(selector)
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return None

class ModernHTMLParser(BaseReceiptParser):
    """Parser for modern HTML receipts (2025+ with custom-* classes)."""
    
    def __init__(self):
        super().__init__()
        self.format_name = "modern_html"
    
    def can_parse(self, base_name: str, content_dir: Path) -> bool:
        """Check for modern HTML format with custom-* classes."""
        html_path = content_dir / f"{base_name}-formatted-simple.html"
        if not html_path.exists():
            return False
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Look for custom-* classes and minimal table structure
            has_custom = bool(soup.select('[class*="custom-"]'))
            table_count = len(soup.select('table'))
            
            return has_custom and table_count <= 3
        except Exception:
            return False
    
    def parse(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """Parse modern HTML receipt."""
        receipt = ParsedReceipt()
        receipt.format_detected = self.format_name
        
        html_path = content_dir / f"{base_name}-formatted-simple.html"
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract metadata using known custom classes
            self._extract_metadata_modern(receipt, soup)
            
            # Extract items
            self._extract_items_modern(receipt, soup)
            
            # Validate financial data
            self._validate_financial_data(receipt)
            
            receipt.parsing_metadata = {
                'selectors_successful': [],
                'selectors_failed': [],
                'fallback_used': False,
                'extraction_method': 'modern_css_selectors'
            }
            
        except Exception as e:
            logger.error(f"Failed to parse modern HTML receipt {base_name}: {e}")
            receipt.parsing_metadata['errors'] = [str(e)]
        
        return receipt
    
    def _extract_metadata_modern(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract metadata from modern HTML using adjacent sibling patterns."""
        
        selectors_successful = []
        selectors_failed = []
        
        # Order ID - using adjacent sibling pattern
        order_element = soup.select_one('p:-soup-contains("Order ID:") + p')
        if order_element:
            receipt.order_id = order_element.get_text(strip=True)
            selectors_successful.append('p:-soup-contains("Order ID:") + p')
        else:
            selectors_failed.append('p:-soup-contains("Order ID:") + p')
        
        # Document number
        doc_element = soup.select_one('p:-soup-contains("Document:") + p')
        if doc_element:
            receipt.document_number = doc_element.get_text(strip=True)
            selectors_successful.append('p:-soup-contains("Document:") + p')
        else:
            selectors_failed.append('p:-soup-contains("Document:") + p')
        
        # Apple Account
        apple_element = soup.select_one('p:-soup-contains("Apple Account:") + p')
        if apple_element:
            receipt.apple_id = apple_element.get_text(strip=True)
            selectors_successful.append('p:-soup-contains("Apple Account:") + p')
        else:
            selectors_failed.append('p:-soup-contains("Apple Account:") + p')
        
        # Financial amounts in payment section
        subtotal_element = soup.select_one('p:-soup-contains("Subtotal") + div p, p:-soup-contains("Subtotal") ~ * p')
        if subtotal_element:
            receipt.subtotal = self._clean_amount(subtotal_element.get_text(strip=True))
            selectors_successful.append('subtotal_selector')
        else:
            selectors_failed.append('subtotal_selector')
        
        tax_element = soup.select_one('p:-soup-contains("Tax") + div p, p:-soup-contains("Tax") ~ * p')
        if tax_element:
            receipt.tax = self._clean_amount(tax_element.get_text(strip=True))
            selectors_successful.append('tax_selector')
        else:
            selectors_failed.append('tax_selector')
        
        # Payment method and final total
        payment_element = soup.select_one('p.custom-15zbox7')
        if payment_element:
            receipt.payment_method = payment_element.get_text(strip=True)
            selectors_successful.append('p.custom-15zbox7')
        else:
            selectors_failed.append('p.custom-15zbox7')
        
        total_element = soup.select_one('p.custom-jhluqm')
        if total_element:
            receipt.total = self._clean_amount(total_element.get_text(strip=True))
            selectors_successful.append('p.custom-jhluqm')
        else:
            selectors_failed.append('p.custom-jhluqm')
        
        receipt.parsing_metadata['selectors_successful'] = selectors_successful
        receipt.parsing_metadata['selectors_failed'] = selectors_failed
    
    def _extract_items_modern(self, receipt: ParsedReceipt, soup: BeautifulSoup):
        """Extract items from modern HTML using known custom classes."""
        
        items_found = []
        
        # Look for items in subscription table rows
        item_rows = soup.select('tr.subscription-lockup')
        for row in item_rows:
            # Service/item name
            name_element = row.select_one('p.custom-gzadzy')
            name = name_element.get_text(strip=True) if name_element else None
            
            # Service type/description
            type_element = row.select_one('p.custom-wogfc8')
            subtitle = type_element.get_text(strip=True) if type_element else None
            
            # Price
            price_element = row.select_one('p.custom-137u684')
            price = self._clean_amount(price_element.get_text(strip=True)) if price_element else None
            
            if name:
                items_found.append({
                    'title': name,
                    'subtitle': subtitle,
                    'type': 'subscription',
                    'artist': None,
                    'device': None,
                    'cost': price,
                    'selector_used': 'p.custom-gzadzy'
                })
        
        receipt.items = items_found

class AppleReceiptParser:
    """Main receipt parser that coordinates the three format-specific parsers."""
    
    def __init__(self):
        # Keep plain text first until HTML parsers are fixed - plain text extracts clean data
        # HTML parsers currently have extraction issues (mangled apple_id, missing dates)
        self.parsers = [
            PlainTextParser(),     # Try first - 67.9% coverage, clean extraction
            LegacyHTMLParser(),    # Try second - 26.3% coverage, needs debugging
            ModernHTMLParser()     # Try last - 5.8% coverage, best potential data quality
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
        receipt.parsing_metadata = {
            'errors': ['No parser available for this receipt format']
        }
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
    """Test the parser system on a few sample receipts."""
    try:
        content_dir = get_extracted_content_dir()
        logger.info(f"Using extracted content directory: {content_dir}")
        
        parser = AppleReceiptParser()
        
        # Test with a few examples from each format
        test_cases = [
            # Plain text example (2020-2023)
            '20201104_071514_Your receipt from Apple__72b38622',
            # Legacy HTML example (2024+)
            '20240916_034902_Your receipt from Apple__b7a09dca',
            # Modern HTML example (2025+)
            '20250420_212800_Your receipt from Apple__172a0351'
        ]
        
        for base_name in test_cases:
            if any((content_dir / f"{base_name}{ext}").exists() for ext in ['.txt', '.html', '-formatted-simple.html']):
                logger.info(f"\nTesting parser with: {base_name}")
                
                # Detect format
                format_detected = parser.detect_format(base_name, content_dir)
                logger.info(f"Format detected: {format_detected}")
                
                # Parse receipt
                receipt = parser.parse_receipt(base_name, content_dir)
                
                # Display results
                logger.info(f"Parsed receipt:")
                logger.info(f"  Apple ID: {receipt.apple_id}")
                logger.info(f"  Order ID: {receipt.order_id}")
                logger.info(f"  Total: ${receipt.total:.2f}" if receipt.total else "  Total: None")
                logger.info(f"  Items: {len(receipt.items)}")
                
                if receipt.items:
                    for item in receipt.items[:2]:  # Show first 2 items
                        logger.info(f"    - {item['title']}: ${item['cost']:.2f}" if item['cost'] else f"    - {item['title']}: No price")
                
                logger.info(f"  Parsing metadata: {receipt.parsing_metadata}")
            else:
                logger.warning(f"Test case not found: {base_name}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Parser test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())