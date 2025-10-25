#!/usr/bin/env python3
"""
Apple Receipt Parser Module

Professional Apple receipt parsing with support for multiple HTML formats.
Handles both legacy and modern Apple receipt email formats with robust extraction.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..core.dates import FinancialDate
from ..core.money import Money

logger = logging.getLogger(__name__)

# Selector size validation thresholds
LARGE_CONTAINER_MAX_CHARS = 200  # For section containers
SMALL_CONTAINER_MAX_CHARS = 80  # For field labels/headers
VALUE_MAX_CHARS = 80  # For extracted values


@dataclass
class ParsedItem:
    """Represents a single purchased item from an Apple receipt."""

    title: str
    cost: Money  # Item cost (upgraded from int cents to Money type)
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
    receipt_date: FinancialDate | None = None  # Upgraded from str to FinancialDate
    order_id: str | None = None
    document_number: str | None = None

    # Financial data (upgraded from int cents to Money type)
    subtotal: Money | None = None
    tax: Money | None = None
    total: Money | None = None
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
        """
        Convert to dictionary for JSON serialization.

        Note: Converts Money to cents and FinancialDate to string for JSON compatibility.
        """
        # Manually handle each field to avoid asdict() recursive conversion issues
        return {
            "format_detected": self.format_detected,
            "apple_id": self.apple_id,
            "receipt_date": self.receipt_date.to_iso_string() if self.receipt_date else None,
            "order_id": self.order_id,
            "document_number": self.document_number,
            "subtotal": self.subtotal.to_cents() if self.subtotal else None,
            "tax": self.tax.to_cents() if self.tax else None,
            "total": self.total.to_cents() if self.total else None,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "billed_to": self.billed_to,
            "items": [
                {
                    "title": item.title,
                    "cost": item.cost.to_cents(),
                    "quantity": item.quantity,
                    "subscription": item.subscription,
                    "item_type": item.item_type,
                    "metadata": item.metadata,
                }
                for item in self.items
            ],
            "parsing_metadata": self.parsing_metadata,
            "base_name": self.base_name,
        }

    def add_item(self, title: str, cost: Money, **kwargs: Any) -> None:
        """Add an item to the receipt."""
        item = ParsedItem(title=title, cost=cost, **kwargs)
        self.items.append(item)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedReceipt":
        """
        Create ParsedReceipt from dictionary (inverse of to_dict).

        Args:
            data: Dictionary with receipt data (from JSON)

        Returns:
            ParsedReceipt instance with typed fields
        """
        # Convert items from dicts to ParsedItem instances
        items = [
            ParsedItem(
                title=item_data["title"],
                cost=Money.from_cents(item_data["cost"]),
                quantity=item_data.get("quantity", 1),
                subscription=item_data.get("subscription", False),
                item_type=item_data.get("item_type"),
                metadata=item_data.get("metadata", {}),
            )
            for item_data in data.get("items", [])
        ]

        return cls(
            format_detected=data.get("format_detected"),
            apple_id=data.get("apple_id"),
            receipt_date=(
                FinancialDate.from_string(data["receipt_date"]) if data.get("receipt_date") else None
            ),
            order_id=data.get("order_id"),
            document_number=data.get("document_number"),
            subtotal=Money.from_cents(data["subtotal"]) if data.get("subtotal") is not None else None,
            tax=Money.from_cents(data["tax"]) if data.get("tax") is not None else None,
            total=Money.from_cents(data["total"]) if data.get("total") is not None else None,
            currency=data.get("currency", "USD"),
            payment_method=data.get("payment_method"),
            billed_to=data.get("billed_to"),
            items=items,
            parsing_metadata=data.get("parsing_metadata", {}),
            base_name=data.get("base_name"),
        )


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

            # Detect format
            receipt.format_detected = self._detect_format(soup)

            # Dispatch to format-specific parser
            if receipt.format_detected == "table_format":
                self._parse_table_format(receipt, soup)
            elif receipt.format_detected == "modern_format":
                self._parse_modern_format(receipt, soup)
            else:
                logger.warning(f"Unknown format detected: {receipt.format_detected}")

        except Exception as e:
            logger.error(f"Error parsing HTML content for {receipt_id}: {e}")
            if "parsing_metadata" not in receipt.__dict__:
                receipt.parsing_metadata = {}
            receipt.parsing_metadata["errors"] = [str(e)]

        return receipt

    def _detect_format(self, soup: BeautifulSoup) -> str:
        """
        Detect which Apple receipt format this HTML uses.

        Returns:
            "table_format": 2020-2023 era table-based receipts with .aapl-* classes
            "modern_format": 2025+ CSS-in-JS receipts with .custom-* classes
        """
        try:
            # Check for modern format (CSS-in-JS with .custom-* classes)
            if soup.find(class_=re.compile(r"^custom-")):
                return "modern_format"

            # Check for table format (.aapl-* classes, table structure)
            if soup.find(class_=re.compile(r"^aapl-")):
                return "table_format"

            # Check for table-based format (fallback)
            if soup.find("table"):
                return "table_format"

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
                    return "table_format"  # Default to table format for unrecognized Apple receipts

            return "unknown"

        except Exception as e:
            logger.warning(f"Error detecting format: {e}")
            return "detection_failed"

    def _parse_table_format(self, receipt: ParsedReceipt, soup: BeautifulSoup) -> None:
        """
        Parse table_format (2020-2023 era) receipts with .aapl-* classes.

        Uses targeted selectors to extract all receipt fields.
        """
        # Extract Apple ID / Apple Account
        # Try multiple strategies
        # Strategy 1: Find label span and get sibling text
        for label in ["APPLE ID", "APPLE ACCOUNT"]:
            label_span = soup.find("span", string=lambda text, lbl=label: text and lbl in text.strip())
            if label_span and label_span.parent:
                # Get the parent td and extract all text (with spaces as separators)
                td_text = label_span.parent.get_text(separator=" ", strip=True)
                # Use regex to extract just the email address (with word boundaries)
                email_pattern = r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
                match = re.search(email_pattern, td_text)
                if match:
                    receipt.apple_id = match.group()
                    break

        # Strategy 2: If not found, search for any text containing an email address near apple account labels
        if not receipt.apple_id:
            # Find all spans/divs and look for email addresses
            for elem in soup.find_all(["span", "td"]):
                text = elem.get_text(separator=" ", strip=True)
                # Check if this element contains an email address
                if "@" in text and "." in text:
                    # Check if "APPLE" label is nearby (in parent or siblings)
                    parent_text = elem.parent.get_text(separator=" ").upper() if elem.parent else ""
                    if "APPLE" in parent_text and ("ID" in parent_text or "ACCOUNT" in parent_text):
                        # Extract just the email part using regex (with word boundaries)
                        email_pattern = r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
                        match = re.search(email_pattern, text)
                        if match:
                            receipt.apple_id = match.group()
                            break

        # Extract receipt date
        date_span = soup.find("span", string=re.compile(r"\s*DATE\s*"))
        if date_span and date_span.parent:
            # Get next sibling or text after <br>
            td = date_span.parent
            # Get all text and remove "DATE" label
            date_text = td.get_text(strip=True).replace("DATE", "").strip()
            if date_text:
                normalized_date = self._normalize_date(date_text)
                if normalized_date:
                    try:
                        receipt.receipt_date = FinancialDate.from_string(normalized_date)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse date: {date_text}")

        # Extract order ID
        order_span = soup.find("span", string=re.compile(r"\s*ORDER ID\s*"))
        if order_span and order_span.parent:
            # Order ID is often in a link or span after the label
            td = order_span.parent
            # Try to find link with order ID
            link = td.find("a")
            if link:
                receipt.order_id = link.get_text(strip=True)
            else:
                # Extract from text
                order_text = td.get_text(strip=True).replace("ORDER ID", "").strip()
                if order_text:
                    receipt.order_id = order_text

        # Extract document number
        doc_span = soup.find("span", string=re.compile(r"\s*DOCUMENT NO\.\s*"))
        if doc_span and doc_span.parent:
            td = doc_span.parent
            doc_text = td.get_text(strip=True).replace("DOCUMENT NO.", "").strip()
            if doc_text:
                receipt.document_number = doc_text

        # Extract items (look for elements with class="title")
        title_elements = soup.find_all("span", class_="title")
        items = []

        for title_elem in title_elements:
            # Get the title text
            title = title_elem.get_text(strip=True)

            # Find the parent row (tr) to get the price
            tr = title_elem.find_parent("tr")
            if not tr:
                continue

            # Find price in the same row
            price_td = tr.find("td", class_="price-cell")
            if price_td:
                price_text = price_td.get_text(strip=True)
                price_text = price_text.replace("$", "").replace(",", "").strip()
                try:
                    cost_cents = int(float(price_text) * 100)
                    cost = Money.from_cents(cost_cents)
                except (ValueError, AttributeError):
                    logger.warning(f"Could not parse price: {price_text}")
                    continue

                # Check if it's a subscription (look for "Renews" text in the row)
                row_text = tr.get_text()
                is_subscription = "Renews" in row_text or "renews" in row_text

                item = ParsedItem(title=title, cost=cost, quantity=1, subscription=is_subscription)
                items.append(item)

        receipt.items = items

        # Extract subtotal, tax, total
        # Find "Subtotal" text
        subtotal_elem = soup.find(string=re.compile(r"Subtotal"))
        if subtotal_elem:
            # Navigate to parent structure and find the amount
            parent = subtotal_elem.find_parent("tr")
            if parent:
                # Find the td with the amount (usually last td in the row)
                amount_td = parent.find_all("td")[-1]
                if amount_td:
                    amount_text = amount_td.get_text(strip=True).replace("$", "").replace(",", "").strip()
                    try:  # noqa: SIM105
                        receipt.subtotal = Money.from_cents(int(float(amount_text) * 100))
                    except (ValueError, AttributeError):
                        pass

        # Find "Tax" text
        tax_elem = soup.find(string=re.compile(r"^Tax$"))
        if tax_elem:
            parent = tax_elem.find_parent("tr")
            if parent:
                amount_td = parent.find_all("td")[-1]
                if amount_td:
                    amount_text = amount_td.get_text(strip=True).replace("$", "").replace(",", "").strip()
                    try:  # noqa: SIM105
                        receipt.tax = Money.from_cents(int(float(amount_text) * 100))
                    except (ValueError, AttributeError):
                        pass

        # Find "TOTAL" text
        total_elem = soup.find(string=re.compile(r"TOTAL"))
        if total_elem:
            # Navigate to find the total amount
            parent_tr = total_elem.find_parent("tr")
            if parent_tr:
                # Find td with the total amount
                amount_tds = parent_tr.find_all("td")
                for td in reversed(amount_tds):  # Check from end
                    text = td.get_text(strip=True)
                    if "$" in text:
                        amount_text = text.replace("$", "").replace(",", "").strip()
                        try:
                            receipt.total = Money.from_cents(int(float(amount_text) * 100))
                            break
                        except (ValueError, AttributeError):
                            pass

    def _parse_modern_format(self, receipt: ParsedReceipt, soup: BeautifulSoup) -> None:
        """
        Parse modern_format (2025+) receipts with CSS-in-JS .custom-* classes.

        Uses targeted selectors for CSS-in-JS HTML structure.
        """
        receipt.receipt_date = self._extract_modern_format_date(soup)
        receipt.apple_id = self._extract_modern_format_field(soup, "Apple Account:")
        receipt.order_id = self._extract_modern_format_field(soup, "Order ID:")
        receipt.document_number = self._extract_modern_format_field(soup, "Document:")

        # Extract billing amounts from payment information section
        subtotal = None
        tax = None
        total = None

        billing_section = soup.find("div", class_=lambda c: c and "payment-information" in c)
        if billing_section and isinstance(billing_section, Tag):
            # Find all p tags with amounts
            amount_rows = billing_section.find_all("p", class_=lambda c: c and "4tra68" in c)

            for row in amount_rows:
                label = row.get_text().strip()
                # Get sibling div with amount
                sibling = row.find_next_sibling("div")
                if not sibling:
                    continue

                amount_tag = sibling.find("p")
                if not amount_tag:
                    continue

                amount_text = amount_tag.get_text().strip()
                amount_cents = self._parse_currency(amount_text)
                if amount_cents is None:
                    continue

                if "Subtotal" in label:
                    subtotal = Money.from_cents(amount_cents)
                elif "Tax" in label:
                    tax = Money.from_cents(amount_cents)

            # Total is in p with class containing "15zbox7" (payment method row)
            total_rows = billing_section.find_all("p", class_=lambda c: c and "15zbox7" in c)
            for row in total_rows:
                # Get sibling div with total amount
                sibling = row.find_next_sibling("div")
                if not sibling:
                    continue

                amount_tag = sibling.find("p")
                if not amount_tag:
                    continue

                amount_text = amount_tag.get_text().strip()
                amount_cents = self._parse_currency(amount_text)
                if amount_cents is not None:
                    total = Money.from_cents(amount_cents)
                    break

        receipt.subtotal = subtotal
        receipt.tax = tax
        receipt.total = total

        # Extract items
        receipt.items = self._extract_modern_format_items(soup)

        # Update parsing metadata
        receipt.parsing_metadata["extraction_method"] = "modern_format_parser"

    def _extract_metadata(self, receipt: ParsedReceipt, soup: BeautifulSoup) -> None:
        """Extract core metadata from the receipt."""
        # Extract Apple ID
        receipt.apple_id = self._extract_apple_id(soup)

        # Extract receipt date (returns FinancialDate now)
        receipt.receipt_date = self._extract_receipt_date(soup)

        # Extract order/document ID
        receipt.order_id = self._extract_order_id(soup)
        receipt.document_number = self._extract_document_number(soup)

        # Extract financial totals (returns Money now)
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
            {"selector": 'td:-soup-contains("Apple ID"), th:-soup-contains("Apple ID")', "method": "sibling"},
            # Generic patterns
            {"selector": "span, div, td", "method": "email_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "Apple ID")
        return str(result) if result is not None else None

    def _extract_receipt_date(self, soup: BeautifulSoup) -> FinancialDate | None:
        """Extract receipt date as FinancialDate."""
        selectors = [
            # Legacy formats
            {"selector": ".aapl-receipt-date, .aapl-date", "method": "text"},
            # Modern formats
            {"selector": ".custom-date, .receipt-date", "method": "text"},
            {"selector": 'td:-soup-contains("Date"), th:-soup-contains("Date")', "method": "sibling"},
            # Generic patterns
            {"selector": "span, div, td", "method": "date_pattern"},
        ]

        date_text = self._try_selectors(soup, selectors, "receipt date")
        if date_text:
            normalized_date = self._normalize_date(date_text)
            if normalized_date:
                try:
                    return FinancialDate.from_string(normalized_date)
                except (ValueError, TypeError):
                    # Log which selector succeeded to debug why we got bad data
                    successful_selector = (
                        self.selectors_successful[-1] if self.selectors_successful else "unknown"
                    )
                    logger.debug(
                        f"Selector '{successful_selector}' returned text that couldn't be parsed as date: {normalized_date}"
                    )
                    return None
        return None

    def _extract_order_id(self, soup: BeautifulSoup) -> str | None:
        """Extract order ID."""
        selectors = [
            # Legacy formats
            {"selector": ".aapl-order-id, .aapl-order", "method": "text"},
            # Modern formats
            {"selector": ".custom-order-id, .order-id", "method": "text"},
            # Find span containing "ORDER ID" and get next span sibling
            {"selector": 'span:-soup-contains("ORDER ID")', "method": "span_sibling"},
            {"selector": 'td:-soup-contains("Order ID"), th:-soup-contains("Order ID")', "method": "sibling"},
            # Generic patterns (fallback)
            {"selector": "span, div, td", "method": "order_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "order ID")
        return str(result) if result is not None else None

    def _extract_document_number(self, soup: BeautifulSoup) -> str | None:
        """Extract document number."""
        selectors = [
            {
                "selector": 'td:-soup-contains("Document No"), th:-soup-contains("Document No")',
                "method": "sibling",
            },
            {"selector": ".document-number, .doc-number", "method": "text"},
            {"selector": "span, div, td", "method": "document_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "document number")
        return str(result) if result is not None else None

    def _extract_subtotal(self, soup: BeautifulSoup) -> Money | None:
        """Extract subtotal amount as Money."""
        selectors = [
            {"selector": ".aapl-subtotal, .subtotal", "method": "currency"},
            # Match span containing "Subtotal", then get parent td's sibling
            {
                "selector": 'span:-soup-contains("Subtotal")',
                "method": "parent_sibling_currency",
            },
            {"selector": "span, div, td", "method": "subtotal_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "subtotal")
        if result is not None and not isinstance(result, str):
            return Money.from_cents(int(result))
        return None

    def _extract_tax(self, soup: BeautifulSoup) -> Money | None:
        """Extract tax amount as Money."""
        selectors = [
            {"selector": ".aapl-tax, .tax", "method": "currency"},
            # Match td containing "TAX" (all caps) directly, then get sibling td
            {
                "selector": 'td:-soup-contains("TAX")',
                "method": "total_sibling_currency",  # Reuse same logic as total
            },
            # Match span containing "Tax", then get parent td's sibling
            {
                "selector": 'span:-soup-contains("Tax")',
                "method": "parent_sibling_currency",
            },
            {"selector": "span, div, td", "method": "tax_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "tax")
        if result is not None and not isinstance(result, str):
            return Money.from_cents(int(result))
        return None

    def _extract_total(self, soup: BeautifulSoup) -> Money | None:
        """Extract total amount as Money."""
        selectors = [
            {"selector": ".aapl-total, .total, .grand-total", "method": "currency"},
            # Match td/span containing "TOTAL" (all caps) to avoid matching "Subtotal"
            {
                "selector": 'td:-soup-contains("TOTAL")',
                "method": "total_sibling_currency",
            },
            {"selector": "span, div, td", "method": "total_pattern"},
        ]

        result = self._try_selectors(soup, selectors, "total")
        if result is not None and not isinstance(result, str):
            return Money.from_cents(int(result))
        return None

    def _extract_payment_method(self, soup: BeautifulSoup) -> str | None:
        """Extract payment method."""
        selectors = [
            {"selector": ".aapl-payment, .payment-method", "method": "text"},
            {
                "selector": 'td:-soup-contains("Payment Method"), th:-soup-contains("Payment Method")',
                "method": "sibling",
            },
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
                    logger.debug(f"Found {len(items)} items using {strategy.__name__}")
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
                                        cost=Money.from_cents(cost),
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
                                title=item_name,
                                cost=Money.from_cents(cost),
                                metadata={"extraction_method": "list_based"},
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
                        title=item_name,
                        cost=Money.from_cents(item_cost),
                        metadata={"extraction_method": "legacy_format"},
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
                        title=item_name,
                        cost=Money.from_cents(item_cost),
                        metadata={"extraction_method": "modern_format"},
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
            'td:-soup-contains("Billed to"), th:-soup-contains("Billed to")',
        ]

        for selector in address_selectors:
            try:
                if ":-soup-contains(" in selector:
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

    def _try_selectors(self, soup: BeautifulSoup, selectors: list[dict[str, Any]], field_name: str) -> Any:
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

                elif method in [
                    "currency",
                    "sibling_currency",
                    "parent_sibling_currency",
                    "total_sibling_currency",
                    "span_sibling",
                    "sibling",
                ]:
                    if method == "sibling" or method == "span_sibling":
                        # Find element and get next sibling (for non-currency fields like order_id)
                        elem = soup.select_one(selector)
                        if elem:
                            # For span_sibling, specifically look for next span
                            sibling_tags = ["span"] if method == "span_sibling" else ["td", "div", "span"]
                            sibling = elem.find_next_sibling(sibling_tags)
                            if sibling:
                                text = sibling.get_text().strip()
                                self.selectors_successful.append(f"{field_name}:{selector}")
                                return text  # Return text directly, not currency
                            else:
                                continue
                        else:
                            continue
                    elif method == "sibling_currency":
                        elem = soup.select_one(selector)
                        if elem:
                            sibling = elem.find_next_sibling(["td", "div", "span"])
                            if sibling:
                                text = sibling.get_text().strip()
                            else:
                                continue
                        else:
                            continue
                    elif method == "parent_sibling_currency":
                        # Find span with keyword, go up to parent td, then to sibling td
                        elem = soup.select_one(selector)
                        if elem:
                            # Go up to parent td
                            parent = elem.find_parent(["td", "th"])
                            if parent:
                                # Get next non-empty sibling td (skip spacers)
                                sibling = parent.find_next_sibling(["td", "th"])
                                while sibling and not sibling.get_text().strip():
                                    sibling = sibling.find_next_sibling(["td", "th"])

                                if sibling:
                                    text = sibling.get_text().strip()
                                else:
                                    continue
                            else:
                                continue
                        else:
                            continue
                    elif method == "total_sibling_currency":
                        # Find td containing "TOTAL" or "TAX" directly (not nested in container)
                        # Try all matching elements, not just first one
                        all_matches = soup.select(selector)
                        matched = False

                        # Determine the expected exact text based on selector
                        # This prevents "TOTAL" selector from matching "SUBTOTAL"
                        expected_keywords = []
                        if "TOTAL" in selector:
                            expected_keywords.append("TOTAL")
                        if "TAX" in selector:
                            expected_keywords.append("TAX")

                        for elem in all_matches:
                            elem_text = elem.get_text().strip()

                            # Skip if this element contains way more than just the keyword
                            # (it's a container, not the target element)
                            if len(elem_text) > 50:
                                continue

                            # Must be an exact match (not "SUBTOTAL" when looking for "TOTAL")
                            if not any(elem_text == keyword for keyword in expected_keywords):
                                continue

                            # Get next non-empty sibling td (skip spacers)
                            sibling = elem.find_next_sibling(["td", "th"])
                            while sibling and not sibling.get_text().strip():
                                sibling = sibling.find_next_sibling(["td", "th"])

                            if sibling:
                                text = sibling.get_text().strip()
                                matched = True
                                break

                        if not matched:
                            continue
                    else:  # "currency"
                        elem = soup.select_one(selector)
                        if elem:
                            text = elem.get_text().strip()
                        else:
                            continue

                    # SANITY CHECK: If we captured a huge text blob, the selector is wrong
                    if len(text) > 1000:
                        raise ValueError(
                            f"Selector '{selector}' for field '{field_name}' captured {len(text)} chars - "
                            f"likely matched a container element instead of the target field. "
                            f"First 200 chars: '{text[:200]}...'"
                        )

                    currency_result: int | None = self._parse_currency(text)
                    if currency_result is not None:
                        self.selectors_successful.append(f"{field_name}:{selector}")
                        return currency_result

                # Pattern-based extraction methods
                elif method.endswith("_pattern"):
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text().strip()

                        # SANITY CHECK: If we captured a huge text blob, the selector is wrong
                        if len(text) > 1000:
                            raise ValueError(
                                f"Pattern selector '{selector}' for field '{field_name}' captured {len(text)} chars - "
                                f"likely matched a container element. Selector pattern '{selector}' is too broad. "
                                f"First 200 chars: '{text[:200]}...'"
                            )

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
            # Pattern 1: Uppercase alphanumeric ID (case-sensitive to avoid matching random words)
            pattern1 = r"\b[A-Z0-9]{8,15}\b"
            match = re.search(pattern1, text)  # Case-sensitive!
            if match:
                return match.group(0)

            # Patterns 2-3: With keywords (case-insensitive keywords, but uppercase IDs)
            patterns_with_keywords = [
                r"\bOrder\s*#?\s*([A-Z0-9]+)\b",
                r"\bID\s*:?\s*([A-Z0-9]+)\b",
            ]
            for pattern in patterns_with_keywords:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1) if len(match.groups()) > 0 else match.group(0)
            return None

        elif pattern_type == "document_pattern":
            match = re.search(r"\bDocument\s*No\.?\s*:?\s*([A-Z0-9]+)\b", text, re.IGNORECASE)
            return match.group(1) if match else None

        elif pattern_type in ["subtotal_pattern", "tax_pattern", "total_pattern"]:
            text_lower = text.lower()

            # Determine which keyword to look for
            if pattern_type == "subtotal_pattern":
                keyword = "subtotal"
            elif pattern_type == "tax_pattern":
                keyword = "tax"
            else:  # total_pattern
                keyword = "total"

            if keyword in text_lower:
                # Find currency value NEAR the keyword (within 100 chars)
                # This prevents extracting from giant text blobs
                keyword_pos = text_lower.find(keyword)
                # Extract a window of text around the keyword
                window_start = max(0, keyword_pos - 20)
                window_end = min(len(text), keyword_pos + 100)
                text_window = text[window_start:window_end]

                result = self._parse_currency(text_window)
                return result
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
        REQUIRES currency symbol ($) prefix to avoid matching random numbers.
        This ensures compliance with the repository's zero-floating-point policy.

        Args:
            text: Currency string (e.g., "$45.99" - must include $ prefix)

        Returns:
            Amount in integer cents, or None if parsing fails
        """
        if not text:
            return None

        # Look for currency symbol followed by amount (prevent matching "Save 3%" as "$3.00")
        # Match $45.99 or $45 but NOT "45.99" without $
        match = re.search(r"[\$£€¥]\s*(\d+)(?:\.(\d{1,2}))?", text)
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

        # Return original text if we can't parse it
        # This allows caller to log what was actually extracted for debugging
        return date_text

    def _select_large_container(self, soup: BeautifulSoup, selector: str) -> str | None:
        """
        Select a large container element (e.g., billing section, item table).

        Allows up to LARGE_CONTAINER_MAX_CHARS (200) characters.
        Throws ValueError if selector captures more (likely matched wrong element).

        Args:
            soup: BeautifulSoup parsed HTML
            selector: CSS selector for container

        Returns:
            Extracted text or None if not found

        Raises:
            ValueError: If captured text exceeds 200 chars
        """
        elem = soup.select_one(selector)
        if not elem:
            return None

        text = elem.get_text().strip()

        if len(text) > LARGE_CONTAINER_MAX_CHARS:
            raise ValueError(
                f"Selector '{selector}' captured {len(text)} chars - "
                f"likely matched a container element instead of target section. "
                f"First 200 chars: '{text[:200]}...'"
            )

        return text

    def _select_small_container(self, soup: BeautifulSoup, selector: str) -> str | None:
        """
        Select a small container element (e.g., table header, field label).

        Allows up to SMALL_CONTAINER_MAX_CHARS (80) characters.
        Throws ValueError if selector captures more (wrong element).

        Args:
            soup: BeautifulSoup parsed HTML
            selector: CSS selector for container

        Returns:
            Extracted text or None if not found

        Raises:
            ValueError: If captured text exceeds 80 chars
        """
        elem = soup.select_one(selector)
        if not elem:
            return None

        text = elem.get_text().strip()

        if len(text) > SMALL_CONTAINER_MAX_CHARS:
            raise ValueError(
                f"Selector '{selector}' captured {len(text)} chars - "
                f"exceeded small container limit ({SMALL_CONTAINER_MAX_CHARS}). "
                f"First 80 chars: '{text[:80]}...'"
            )

        return text

    def _select_value(self, soup: BeautifulSoup, selector: str) -> str | None:
        """
        Select a value element (e.g., price, date, order ID).

        Allows up to VALUE_MAX_CHARS (80) characters.
        Throws ValueError if selector captures more (wrong element).

        Args:
            soup: BeautifulSoup parsed HTML
            selector: CSS selector for value

        Returns:
            Extracted text or None if not found

        Raises:
            ValueError: If captured text exceeds 80 chars
        """
        elem = soup.select_one(selector)
        if not elem:
            return None

        text = elem.get_text().strip()

        if len(text) > VALUE_MAX_CHARS:
            raise ValueError(
                f"Selector '{selector}' captured {len(text)} chars - "
                f"exceeded value limit ({VALUE_MAX_CHARS}). "
                f"First 80 chars: '{text[:80]}...'"
            )

        return text

    def _extract_modern_format_date(self, soup: BeautifulSoup) -> FinancialDate | None:
        """
        Extract receipt date from modern format HTML.

        Modern format has: <p class="custom-18w16cf">October 11, 2025</p>
        """
        # Find p tag with date pattern (Month Day, Year)
        date_candidates = soup.find_all("p", class_=lambda c: c and c.startswith("custom-"))

        for p_tag in date_candidates:
            text = p_tag.get_text().strip()
            # Try to parse date like "October 11, 2025"
            try:
                from datetime import datetime

                date_obj = datetime.strptime(text, "%B %d, %Y")
                return FinancialDate(date=date_obj.date())
            except ValueError:
                continue

        return None

    def _extract_modern_format_field(self, soup: BeautifulSoup, label: str) -> str | None:
        """
        Extract field from modern format using label pattern.

        Modern format has:
        <p class="custom-f41j3e">Label:</p>
        <p class="custom-zresjj">Value</p>
        """
        # Find p tag containing label
        label_tags = soup.find_all("p", string=lambda s: s and label in s)

        for label_tag in label_tags:
            # Get next sibling p tag
            value_tag = label_tag.find_next_sibling("p")
            if value_tag and isinstance(value_tag, Tag):
                value = value_tag.get_text().strip()
                if value and value != label:
                    return str(value)

        return None

    def _extract_modern_format_items(self, soup: BeautifulSoup) -> list:
        """
        Extract items from modern format HTML.

        Modern format has subscription lockup rows with:
        - p.custom-gzadzy: title
        - p.custom-wogfc8 with "Renews": subscription details
        - p.custom-137u684: price
        """
        items = []

        # Find all subscription lockup rows
        item_rows = soup.find_all("tr", class_="subscription-lockup")

        for row in item_rows:
            # Extract title
            title_tag = row.find("p", class_=lambda c: c and "gzadzy" in c)
            if not title_tag:
                continue

            title = title_tag.get_text().strip()

            # Check if subscription (has "Renews" text)
            subscription = False
            subscription_tags = row.find_all("p", class_=lambda c: c and "wogfc8" in c)
            for tag in subscription_tags:
                if "Renews" in tag.get_text():
                    subscription = True
                    break

            # Extract price
            price_tag = row.find("p", class_=lambda c: c and "137u684" in c)
            if not price_tag:
                continue

            price_text = price_tag.get_text().strip()
            cost_cents = self._parse_currency(price_text)
            if cost_cents is None:
                continue

            cost = Money.from_cents(cost_cents)

            items.append(
                ParsedItem(
                    title=title,
                    cost=cost,
                    quantity=1,
                    subscription=subscription,
                    item_type=None,
                    metadata={"extraction_method": "modern_format_targeted"},
                )
            )

        return items
