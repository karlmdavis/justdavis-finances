#!/usr/bin/env python3
"""
Apple Receipt Parser Module

Professional Apple receipt parsing with support for multiple HTML formats.
Handles both legacy and modern Apple receipt email formats with robust extraction.
"""

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ParsedItem:
    """Represents a single purchased item from an Apple receipt."""

    title: str
    cost: int  # Amount in cents (e.g., 4599 for $45.99)
    quantity: int = 1
    subscription: bool = False
    item_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedReceipt:
    """Represents a parsed Apple receipt with standardized data structure."""

    # Core metadata
    format_detected: str | None = None
    apple_id: str | None = None
    receipt_date: str | None = None
    order_id: str | None = None
    document_number: str | None = None

    # Financial data (amounts in cents, e.g., 4599 for $45.99)
    subtotal: int | None = None
    tax: int | None = None
    total: int | None = None
    currency: str = "USD"

    # Billing information
    payment_method: str | None = None
    billed_to: dict[str, str] | None = None

    # Purchase items
    items: list[ParsedItem] = field(default_factory=list)

    # Parsing metadata
    parsing_metadata: dict[str, Any] = field(default_factory=dict)
    base_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def add_item(self, title: str, cost: int, **kwargs: Any) -> None:
        """Add an item to the receipt (cost in cents)."""
        item = ParsedItem(title=title, cost=cost, **kwargs)
        self.items.append(item)


class AppleReceiptParser:
    """
    Enhanced Apple receipt parser supporting multiple HTML formats.

    Handles both legacy (aapl-*) and modern (custom-*) HTML formats with
    robust extraction and proper financial data handling.
    """

    def __init__(self) -> None:
        self.selectors_tried: list[str] = []
        self.selectors_successful: list[str] = []

    def parse_receipt(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """
        Parse HTML receipt with enhanced extraction.

        Args:
            base_name: Base name of the receipt files
            content_dir: Directory containing receipt content

        Returns:
            ParsedReceipt object with extracted data
        """
        receipt = ParsedReceipt(base_name=base_name)

        html_path = content_dir / f"{base_name}-formatted-simple.html"
        if not html_path.exists():
            receipt.parsing_metadata["errors"] = ["HTML file not found"]
            logger.error(f"HTML file not found: {html_path}")
            return receipt

        try:
            with open(html_path, encoding="utf-8") as f:
                content = f.read()

            soup = BeautifulSoup(content, "lxml")

            # Reset tracking
            self.selectors_tried = []
            self.selectors_successful = []

            # Detect format type
            receipt.format_detected = self._detect_format(soup)
            logger.info(f"Detected format: {receipt.format_detected}")

            # Extract all data
            self._extract_metadata(receipt, soup)
            self._extract_items(receipt, soup)
            self._extract_billing_info(receipt, soup)

            # Store parsing metadata
            receipt.parsing_metadata = {
                "selectors_successful": self.selectors_successful.copy(),
                "selectors_failed": [s for s in self.selectors_tried if s not in self.selectors_successful],
                "fallback_used": False,
                "extraction_method": "enhanced_html_parser",
                "total_selectors_tried": len(self.selectors_tried),
                "success_rate": len(self.selectors_successful) / max(len(self.selectors_tried), 1),
            }

            logger.info(f"Successfully parsed receipt: {receipt.order_id or base_name}")

        except Exception as e:
            logger.error(f"Error parsing receipt {base_name}: {e}")
            receipt.parsing_metadata["errors"] = [str(e)]

        return receipt

    def parse_html_content(self, html_content: str, receipt_id: str = "unknown") -> ParsedReceipt:
        """
        Parse HTML content directly without file system access.

        Args:
            html_content: Raw HTML content to parse
            receipt_id: Identifier for the receipt

        Returns:
            ParsedReceipt object with extracted data
        """
        receipt = ParsedReceipt(base_name=receipt_id)

        try:
            soup = BeautifulSoup(html_content, "lxml")

            # Reset tracking
            self.selectors_tried = []
            self.selectors_successful = []

            # Detect format and extract data
            receipt.format_detected = self._detect_format(soup)
            self._extract_metadata(receipt, soup)
            self._extract_items(receipt, soup)
            self._extract_billing_info(receipt, soup)

            # Store parsing metadata
            receipt.parsing_metadata = {
                "selectors_successful": self.selectors_successful.copy(),
                "selectors_failed": [s for s in self.selectors_tried if s not in self.selectors_successful],
                "extraction_method": "html_content_parser",
                "total_selectors_tried": len(self.selectors_tried),
                "success_rate": len(self.selectors_successful) / max(len(self.selectors_tried), 1),
            }

        except Exception as e:
            logger.error(f"Error parsing HTML content for {receipt_id}: {e}")
            receipt.parsing_metadata["errors"] = [str(e)]

        return receipt

    def _detect_format(self, soup: BeautifulSoup) -> str:
        """Detect the HTML format type of the receipt."""
        try:
            # Check for legacy format indicators
            if soup.find(class_=re.compile(r"^aapl-")):
                return "legacy_aapl"

            # Check for modern custom format
            if soup.find(class_=re.compile(r"^custom-")):
                return "modern_custom"

            # Check for table-based format
            if soup.find("table"):
                return "table_based"

            # Check for specific Apple receipt indicators
            apple_indicators = [
                "Apple Store",
                "iTunes Store",
                "App Store",
                "apple.com",
                "Your receipt from Apple",
            ]

            text_content = soup.get_text().lower()
            for indicator in apple_indicators:
                if indicator.lower() in text_content:
                    return "apple_generic"

            return "unknown"

        except Exception as e:
            logger.warning(f"Error detecting format: {e}")
            return "detection_failed"

    def _extract_metadata(self, receipt: ParsedReceipt, soup: BeautifulSoup) -> None:
        """Extract core metadata from the receipt."""
        # Extract Apple ID
        receipt.apple_id = self._extract_apple_id(soup)

        # Extract receipt date
        receipt.receipt_date = self._extract_receipt_date(soup)

        # Extract order/document ID
        receipt.order_id = self._extract_order_id(soup)
        receipt.document_number = self._extract_document_number(soup)

        # Extract financial totals
        receipt.subtotal = self._extract_subtotal(soup)
        receipt.tax = self._extract_tax(soup)
        receipt.total = self._extract_total(soup)

        # Extract payment method
        receipt.payment_method = self._extract_payment_method(soup)

    def _extract_apple_id(self, soup: BeautifulSoup) -> str | None:
        """Extract Apple ID from various locations in the receipt."""
        selectors = [
            # Legacy formats
            {"selector": ".aapl-text-large, .aapl-apple-id", "method": "text"},
            {"selector": "[data-apple-id]", "method": "attr", "attr": "data-apple-id"},
            # Modern formats
            {"selector": ".custom-apple-id, .apple-id", "method": "text"},
            {"selector": 'td:contains("Apple ID"), th:contains("Apple ID")', "method": "sibling"},
            # Generic patterns
            {"selector": "span, div, td", "method": "email_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "Apple ID")
        return str(result) if result is not None else None

    def _extract_receipt_date(self, soup: BeautifulSoup) -> str | None:
        """Extract receipt date."""
        selectors = [
            # Legacy formats
            {"selector": ".aapl-receipt-date, .aapl-date", "method": "text"},
            # Modern formats
            {"selector": ".custom-date, .receipt-date", "method": "text"},
            {"selector": 'td:contains("Date"), th:contains("Date")', "method": "sibling"},
            # Generic patterns
            {"selector": "span, div, td", "method": "date_pattern"},
        ]

        date_text = self._try_selectors(soup, selectors, "receipt date")
        if date_text:
            return self._normalize_date(date_text)
        return None

    def _extract_order_id(self, soup: BeautifulSoup) -> str | None:
        """Extract order ID."""
        selectors = [
            # Legacy formats
            {"selector": ".aapl-order-id, .aapl-order", "method": "text"},
            # Modern formats
            {"selector": ".custom-order-id, .order-id", "method": "text"},
            {"selector": 'td:contains("Order ID"), th:contains("Order ID")', "method": "sibling"},
            # Generic patterns
            {"selector": "span, div, td", "method": "order_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "order ID")
        return str(result) if result is not None else None

    def _extract_document_number(self, soup: BeautifulSoup) -> str | None:
        """Extract document number."""
        selectors = [
            {"selector": 'td:contains("Document No"), th:contains("Document No")', "method": "sibling"},
            {"selector": ".document-number, .doc-number", "method": "text"},
            {"selector": "span, div, td", "method": "document_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "document number")
        return str(result) if result is not None else None

    def _extract_subtotal(self, soup: BeautifulSoup) -> int | None:
        """Extract subtotal amount in cents."""
        selectors = [
            {"selector": ".aapl-subtotal, .subtotal", "method": "currency"},
            {"selector": 'td:contains("Subtotal"), th:contains("Subtotal")', "method": "sibling_currency"},
            {"selector": "span, div, td", "method": "subtotal_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "subtotal")
        return int(result) if result is not None and not isinstance(result, str) else None

    def _extract_tax(self, soup: BeautifulSoup) -> int | None:
        """Extract tax amount in cents."""
        selectors = [
            {"selector": ".aapl-tax, .tax", "method": "currency"},
            {"selector": 'td:contains("Tax"), th:contains("Tax")', "method": "sibling_currency"},
            {"selector": "span, div, td", "method": "tax_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "tax")
        return int(result) if result is not None and not isinstance(result, str) else None

    def _extract_total(self, soup: BeautifulSoup) -> int | None:
        """Extract total amount in cents."""
        selectors = [
            {"selector": ".aapl-total, .total, .grand-total", "method": "currency"},
            {"selector": 'td:contains("Total"), th:contains("Total")', "method": "sibling_currency"},
            {
                "selector": 'td:contains("Grand Total"), th:contains("Grand Total")',
                "method": "sibling_currency",
            },
            {"selector": "span, div, td", "method": "total_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "total")
        return int(result) if result is not None and not isinstance(result, str) else None

    def _extract_payment_method(self, soup: BeautifulSoup) -> str | None:
        """Extract payment method."""
        selectors = [
            {"selector": ".aapl-payment, .payment-method", "method": "text"},
            {"selector": 'td:contains("Payment Method"), th:contains("Payment Method")', "method": "sibling"},
            {"selector": "span, div, td", "method": "payment_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "payment method")
        return str(result) if result is not None else None

    def _extract_items(self, receipt: ParsedReceipt, soup: BeautifulSoup) -> None:
        """Extract purchased items from the receipt."""
        items_found = False

        # Try different item extraction strategies
        strategies = [
            self._extract_items_table_based,
            self._extract_items_list_based,
            self._extract_items_legacy_format,
            self._extract_items_modern_format,
        ]

        for strategy in strategies:
            try:
                items = strategy(soup)
                if items:
                    receipt.items.extend(items)
                    items_found = True
                    logger.info(f"Found {len(items)} items using {strategy.__name__}")
                    break
            except Exception as e:
                logger.warning(f"Strategy {strategy.__name__} failed: {e}")

        if not items_found:
            logger.warning("No items found using any extraction strategy")

    def _extract_items_table_based(self, soup: BeautifulSoup) -> list[ParsedItem]:
        """Extract items from table-based format."""
        items = []

        # Look for tables containing item data
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")

            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    # Try to identify item name and cost
                    text_cells = [cell.get_text().strip() for cell in cells]

                    # Look for currency patterns
                    for i, text in enumerate(text_cells):
                        if self._is_currency(text) and i > 0:
                            item_name = text_cells[i - 1]
                            cost = self._parse_currency(text)

                            if item_name and cost is not None and len(item_name) > 2:
                                items.append(
                                    ParsedItem(
                                        title=item_name,
                                        cost=cost,
                                        metadata={"extraction_method": "table_based"},
                                    )
                                )

        return items

    def _extract_items_list_based(self, soup: BeautifulSoup) -> list[ParsedItem]:
        """Extract items from list-based format."""
        items = []

        # Look for list elements
        lists = soup.find_all(["ul", "ol"])
        for list_elem in lists:
            list_items = list_elem.find_all("li")

            for li in list_items:
                text = li.get_text().strip()
                # Try to extract item name and cost from list item text
                match = re.search(r"(.+?)\s*[\$£€¥]\s*(\d+\.?\d*)", text)
                if match:
                    item_name = match.group(1).strip()
                    # Parse currency to cents
                    cost = self._parse_currency(match.group(2))

                    if cost is not None:
                        items.append(
                            ParsedItem(
                                title=item_name, cost=cost, metadata={"extraction_method": "list_based"}
                            )
                        )

        return items

    def _extract_items_legacy_format(self, soup: BeautifulSoup) -> list[ParsedItem]:
        """Extract items from legacy aapl-* format."""
        items = []

        # Look for legacy item containers
        item_containers = soup.find_all(class_=re.compile(r"aapl-item|aapl-product"))

        for container in item_containers:
            item_name = None
            item_cost = None

            # Try to find item name
            name_elem = container.find(class_=re.compile(r"aapl-item-name|aapl-product-name"))
            if name_elem:
                item_name = name_elem.get_text().strip()

            # Try to find item cost
            cost_elem = container.find(class_=re.compile(r"aapl-item-cost|aapl-price"))
            if cost_elem:
                cost_text = cost_elem.get_text().strip()
                item_cost = self._parse_currency(cost_text)

            if item_name and item_cost is not None:
                items.append(
                    ParsedItem(
                        title=item_name, cost=item_cost, metadata={"extraction_method": "legacy_format"}
                    )
                )

        return items

    def _extract_items_modern_format(self, soup: BeautifulSoup) -> list[ParsedItem]:
        """Extract items from modern custom-* format."""
        items = []

        # Look for modern item containers
        item_containers = soup.find_all(class_=re.compile(r"custom-item|custom-product|item-row"))

        for container in item_containers:
            item_name = None
            item_cost = None

            # Try to find item name
            name_elem = container.find(class_=re.compile(r"custom-item-name|item-name|product-name"))
            if name_elem:
                item_name = name_elem.get_text().strip()

            # Try to find item cost
            cost_elem = container.find(class_=re.compile(r"custom-item-cost|item-cost|price"))
            if cost_elem:
                cost_text = cost_elem.get_text().strip()
                item_cost = self._parse_currency(cost_text)

            if item_name and item_cost is not None:
                items.append(
                    ParsedItem(
                        title=item_name, cost=item_cost, metadata={"extraction_method": "modern_format"}
                    )
                )

        return items

    def _extract_billing_info(self, receipt: ParsedReceipt, soup: BeautifulSoup) -> None:
        """Extract billing information."""
        billing_info = {}

        # Look for billing address
        address_selectors = [
            ".aapl-billing-address, .billing-address",
            ".aapl-billed-to, .billed-to",
            'td:contains("Billed to"), th:contains("Billed to")',
        ]

        for selector in address_selectors:
            try:
                if ":contains(" in selector:
                    elem = soup.select_one(selector)
                    if elem:
                        # Get next sibling or cell
                        sibling = elem.find_next_sibling(["td", "div", "span"])
                        if sibling:
                            billing_info["address"] = sibling.get_text().strip()
                            break
                else:
                    elem = soup.select_one(selector)
                    if elem:
                        billing_info["address"] = elem.get_text().strip()
                        break
            except Exception as e:
                logger.debug(f"Error extracting billing info with selector {selector}: {e}")

        if billing_info:
            receipt.billed_to = billing_info

    def _try_selectors(self, soup: BeautifulSoup, selectors: list[dict], field_name: str) -> Any:
        """Try multiple selectors and return first successful result."""
        for selector_config in selectors:
            try:
                selector = selector_config["selector"]
                method = selector_config["method"]

                self.selectors_tried.append(f"{field_name}:{selector}")

                if method == "text":
                    elem = soup.select_one(selector)
                    if elem:
                        result = elem.get_text().strip()
                        if result:
                            self.selectors_successful.append(f"{field_name}:{selector}")
                            return result

                elif method == "attr":
                    elem = soup.select_one(selector)
                    if elem:
                        attr_result = elem.get(selector_config["attr"])
                        if attr_result:
                            self.selectors_successful.append(f"{field_name}:{selector}")
                            # BeautifulSoup elem.get() returns str or list[str]
                            if isinstance(attr_result, str):
                                return attr_result
                            else:
                                # Must be a list
                                return str(attr_result[0]) if attr_result else None

                elif method == "sibling":
                    elem = soup.select_one(selector)
                    if elem:
                        sibling = elem.find_next_sibling(["td", "div", "span"])
                        if sibling:
                            result = sibling.get_text().strip()
                            if result:
                                self.selectors_successful.append(f"{field_name}:{selector}")
                                return result

                elif method == "currency" or method == "sibling_currency":
                    if method == "sibling_currency":
                        elem = soup.select_one(selector)
                        if elem:
                            sibling = elem.find_next_sibling(["td", "div", "span"])
                            if sibling:
                                text = sibling.get_text().strip()
                            else:
                                continue
                        else:
                            continue
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            text = elem.get_text().strip()
                        else:
                            continue

                    currency_result: int | None = self._parse_currency(text)
                    if currency_result is not None:
                        self.selectors_successful.append(f"{field_name}:{selector}")
                        return currency_result

                # Pattern-based extraction methods
                elif method.endswith("_pattern"):
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text().strip()
                        result = self._extract_by_pattern(text, method)
                        if result:
                            self.selectors_successful.append(f"{field_name}:{selector}")
                            return result

            except Exception as e:
                logger.debug(f"Selector failed: {selector} - {e}")

        return None

    def _extract_by_pattern(self, text: str, pattern_type: str) -> Any:
        """Extract data using regex patterns."""
        if pattern_type == "email_pattern":
            match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
            return match.group(0) if match else None

        elif pattern_type == "date_pattern":
            # Try various date formats
            date_patterns = [
                r"\b\d{1,2}/\d{1,2}/\d{4}\b",
                r"\b\d{4}-\d{2}-\d{2}\b",
                r"\b[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\b",
                r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b",
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(0)
            return None

        elif pattern_type == "order_pattern":
            # Look for order ID patterns
            patterns = [
                r"\b[A-Z0-9]{8,15}\b",  # Generic alphanumeric ID
                r"\bOrder\s*#?\s*([A-Z0-9]+)\b",
                r"\bID\s*:?\s*([A-Z0-9]+)\b",
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1) if len(match.groups()) > 0 else match.group(0)
            return None

        elif pattern_type == "document_pattern":
            match = re.search(r"\bDocument\s*No\.?\s*:?\s*([A-Z0-9]+)\b", text, re.IGNORECASE)
            return match.group(1) if match else None

        elif pattern_type in ["subtotal_pattern", "tax_pattern", "total_pattern"]:
            if (
                (pattern_type == "subtotal_pattern" and "subtotal" in text.lower())
                or (pattern_type == "tax_pattern" and "tax" in text.lower())
                or (pattern_type == "total_pattern" and ("total" in text.lower() or "grand" in text.lower()))
            ):
                return self._parse_currency(text)
            return None

        elif pattern_type == "payment_pattern":
            payment_indicators = ["visa", "mastercard", "amex", "apple pay", "paypal", "ending in"]
            if any(indicator in text.lower() for indicator in payment_indicators):
                return text
            return None

        return None

    def _is_currency(self, text: str) -> bool:
        """Check if text contains currency information."""
        currency_pattern = r"[\$£€¥]\s*\d+\.?\d*"
        return bool(re.search(currency_pattern, text))

    def _parse_currency(self, text: str) -> int | None:
        """
        Parse currency string to integer cents using integer-only arithmetic.

        Converts dollar amounts like "$45.99" to integer cents (4599).
        This ensures compliance with the repository's zero-floating-point policy.

        Args:
            text: Currency string (e.g., "$45.99", "12.34")

        Returns:
            Amount in integer cents, or None if parsing fails
        """
        if not text:
            return None

        # Remove common currency symbols and whitespace
        cleaned = re.sub(r"[\$£€¥,\s]", "", text)

        # Extract dollars and cents separately as integers (zero-floating-point policy)
        match = re.search(r"(\d+)(?:\.(\d{1,2}))?", cleaned)
        if match:
            try:
                dollars = int(match.group(1))
                cents_str = match.group(2) or "0"
                # Pad cents to 2 digits (e.g., "5" becomes "50")
                if len(cents_str) == 1:
                    cents_str = cents_str + "0"
                cents_part = int(cents_str)
                # Combine using integer arithmetic only
                total_cents = dollars * 100 + cents_part
                return total_cents
            except ValueError:
                return None

        return None

    def _normalize_date(self, date_text: str) -> str:
        """Normalize date string to standard format."""
        if not date_text:
            return date_text

        # Try to parse various date formats and normalize to YYYY-MM-DD
        date_patterns = [
            ("%m/%d/%Y", r"\d{1,2}/\d{1,2}/\d{4}"),
            ("%Y-%m-%d", r"\d{4}-\d{2}-\d{2}"),
            ("%b %d, %Y", r"[A-Za-z]{3}\s+\d{1,2},\s+\d{4}"),
            ("%d %b %Y", r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}"),
        ]

        for date_format, pattern in date_patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    parsed_date = datetime.strptime(match.group(), date_format)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # Return original if we can't parse it
        return date_text
