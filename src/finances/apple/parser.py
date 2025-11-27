#!/usr/bin/env python3
"""
Apple Receipt Parser Module

Professional Apple receipt parsing with support for multiple HTML formats.
Handles both legacy and modern Apple receipt email formats with robust extraction.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..core.dates import FinancialDate
from ..core.money import Money

logger = logging.getLogger(__name__)

# Selector size validation thresholds (based on production receipt analysis)
#
# These limits prevent selectors from matching entire containers instead of target values.
# Analysis of 870 production receipts (96% table_format, 4% modern_format) showed:
#
# LARGE_CONTAINER_MAX_CHARS = 200
#   - Billing/payment sections: typically 120-180 chars
#   - Margin: 2.5x headroom allows for verbose receipts
#   - Catches: Accidentally selecting entire receipt body (5000+ chars)
#
# SMALL_CONTAINER_MAX_CHARS = 80
#   - Field labels ("Apple Account:", "Order ID:"): typically 15-40 chars
#   - Table headers: typically 30-60 chars
#   - Margin: 2x headroom for internationalization
#   - Catches: Selecting table rows instead of headers (200+ chars)
#
# VALUE_MAX_CHARS = 80
#   - Prices ($12.34): typically 5-10 chars
#   - Order IDs (ML7PQ2XYZ): typically 10-15 chars
#   - Email addresses: typically 20-40 chars
#   - Margin: 2x headroom for edge cases
#   - Catches: Selecting field labels instead of values (100+ chars)
#
LARGE_CONTAINER_MAX_CHARS = 200
SMALL_CONTAINER_MAX_CHARS = 80
VALUE_MAX_CHARS = 80


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

    def parse_receipt(self, base_name: str, content_dir: Path) -> ParsedReceipt:
        """
        Parse HTML receipt using format-specific parsers.

        Args:
            base_name: Base name of the receipt files
            content_dir: Directory containing receipt content

        Returns:
            ParsedReceipt object with extracted data
        """
        receipt = ParsedReceipt(base_name=base_name)

        html_path = content_dir / f"{base_name}-formatted-simple.html"
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        with open(html_path, encoding="utf-8") as f:
            content = f.read()

        soup = BeautifulSoup(content, "lxml")

        # Detect format type
        receipt.format_detected = self._detect_format(soup)
        logger.info(f"Detected format: {receipt.format_detected}")

        # Dispatch to format-specific parser
        if receipt.format_detected == "table_format":
            self._parse_table_format(receipt, soup)
        elif receipt.format_detected == "modern_format":
            self._parse_modern_format(receipt, soup)
        else:
            logger.warning(f"Unknown format detected: {receipt.format_detected}")

        logger.info(f"Successfully parsed receipt: {receipt.order_id or base_name}")

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

        return receipt

    def _detect_format(self, soup: BeautifulSoup) -> str:
        """
        Detect which Apple receipt format this HTML uses.

        Returns:
            "table_format": 2020-2023 era table-based receipts with .aapl-* classes
            "modern_format": 2025+ CSS-in-JS receipts with .custom-* classes
        """
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
                # Try to parse date directly
                try:
                    from datetime import datetime

                    date_obj = datetime.strptime(date_text, "%b %d, %Y")
                    receipt.receipt_date = FinancialDate(date=date_obj.date())
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse date: {date_text}")

        # Fallback: Try transitional format - look for date pattern without label
        if not receipt.receipt_date:
            from datetime import datetime

            # Search for spans containing date-like text (e.g., "June 16, 2024")
            for span in soup.find_all("span"):
                text = span.get_text(strip=True)
                # Try parsing with full month name
                try:
                    date_obj = datetime.strptime(text, "%B %d, %Y")
                    receipt.receipt_date = FinancialDate(date=date_obj.date())
                    break
                except (ValueError, TypeError):
                    # Also try abbreviated month
                    try:
                        date_obj = datetime.strptime(text, "%b %d, %Y")
                        receipt.receipt_date = FinancialDate(date=date_obj.date())
                        break
                    except (ValueError, TypeError):
                        continue

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

        # Fallback: Try transitional format with <b>Order ID:</b> pattern
        if not receipt.order_id:
            b_tag = soup.find("b", string=re.compile(r"Order ID:?", re.IGNORECASE))
            if b_tag and b_tag.parent:
                # Get parent span text and remove the label
                span_text = b_tag.parent.get_text(strip=True)
                # Remove label (everything up to and including the colon)
                order_text = re.sub(r"^.*?Order ID:?\s*", "", span_text, flags=re.IGNORECASE).strip()
                if order_text:
                    receipt.order_id = order_text

        # Extract document number
        doc_span = soup.find("span", string=re.compile(r"\s*DOCUMENT NO\.\s*"))
        if doc_span and doc_span.parent:
            td = doc_span.parent
            doc_text = td.get_text(strip=True).replace("DOCUMENT NO.", "").strip()
            if doc_text:
                receipt.document_number = doc_text

        # Fallback: Try transitional format with <b>Document:</b> pattern
        if not receipt.document_number:
            b_tag = soup.find("b", string=re.compile(r"Document:?", re.IGNORECASE))
            if b_tag and b_tag.parent:
                span_text = b_tag.parent.get_text(strip=True)
                doc_text = re.sub(r"^.*?Document:?\s*", "", span_text, flags=re.IGNORECASE).strip()
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
                cost_cents = self._parse_currency(price_text)
                if cost_cents is None:
                    logger.warning(f"Could not parse price: {price_text}")
                    continue
                cost = Money.from_cents(cost_cents)

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
                    amount_text = amount_td.get_text(strip=True)
                    amount_cents = self._parse_currency(amount_text)
                    if amount_cents is not None:
                        receipt.subtotal = Money.from_cents(amount_cents)
                    else:
                        logger.debug(f"Could not parse subtotal: {amount_text}")

        # Find "Tax" text
        tax_elem = soup.find(string=re.compile(r"^Tax$"))
        if tax_elem:
            parent = tax_elem.find_parent("tr")
            if parent:
                amount_td = parent.find_all("td")[-1]
                if amount_td:
                    amount_text = amount_td.get_text(strip=True)
                    amount_cents = self._parse_currency(amount_text)
                    if amount_cents is not None:
                        receipt.tax = Money.from_cents(amount_cents)
                    else:
                        logger.debug(f"Could not parse tax: {amount_text}")

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
                        amount_cents = self._parse_currency(text)
                        if amount_cents is not None:
                            receipt.total = Money.from_cents(amount_cents)
                            break
                        else:
                            logger.debug(f"Could not parse total: {text}")

        # Fallback: For transitional format, look for inline-styled elements
        if not receipt.total or not receipt.items:
            # Find all spans with font-weight: 600 styling (potential titles)
            title_spans = soup.find_all("span", style=re.compile(r"font-weight:\s*600"))

            # Find all spans with dollar amounts (potential prices)
            price_candidates = []
            for span in soup.find_all("span"):
                text = span.get_text(strip=True)
                if "$" in text and re.match(r"^\$[\d,]+\.\d{2}$", text):
                    cost_cents = self._parse_currency(text)
                    if cost_cents is not None:
                        price_candidates.append((span, cost_cents, text))

            # Try to pair titles with prices based on proximity
            for title_span in title_spans:
                title = title_span.get_text(strip=True)
                # Skip if title is empty or too long (likely not an item title)
                if not title or len(title) > 100:
                    continue

                # Look for price near this title (in same table or nearby)
                parent_table = title_span.find_parent("table")
                if parent_table:
                    # Find prices within the same table
                    for price_span, cost_cents, _price_text in price_candidates:
                        if parent_table.find(lambda tag, span=price_span: tag == span):
                            cost = Money.from_cents(cost_cents)
                            # Add item if not already present
                            if not receipt.items:
                                item = ParsedItem(title=title, cost=cost, quantity=1, subscription=False)
                                receipt.items.append(item)
                            # Set total if not already set
                            if not receipt.total:
                                receipt.total = cost
                            break

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
            # Find subtotal/tax in subtotal-group div (more structural approach)
            subtotal_group = billing_section.find("div", class_=lambda c: c and "subtotal-group" in c)
            if subtotal_group and isinstance(subtotal_group, Tag):
                # Find all p tags within the group
                all_p_tags = subtotal_group.find_all("p")
                for p_tag in all_p_tags:
                    label = p_tag.get_text().strip()
                    # Get sibling div with amount
                    sibling = p_tag.find_next_sibling("div")
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

            # Total is after the <hr> separator - find hr then next p+div pair
            hr_tag = billing_section.find("hr")
            if hr_tag:
                # Find next p tag after the hr (payment method)
                payment_method_tag = hr_tag.find_next_sibling("p")
                if payment_method_tag:
                    # Get the next div sibling (contains total amount)
                    total_div = payment_method_tag.find_next_sibling("div")
                    if total_div and isinstance(total_div, Tag):
                        amount_tag = total_div.find("p")
                        if amount_tag and isinstance(amount_tag, Tag):
                            amount_text = amount_tag.get_text().strip()
                            amount_cents = self._parse_currency(amount_text)
                            if amount_cents is not None:
                                total = Money.from_cents(amount_cents)

        receipt.subtotal = subtotal
        receipt.tax = tax
        receipt.total = total

        # Extract items
        receipt.items = self._extract_modern_format_items(soup)

        # Update parsing metadata
        receipt.parsing_metadata["extraction_method"] = "modern_format_parser"

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
        - First p tag in content td: title
        - Any p tag with "Renews" text: subscription indicator
        - Last td with p tag: price
        """
        items = []

        # Find all subscription lockup rows
        item_rows = soup.find_all("tr", class_="subscription-lockup")

        for row in item_rows:
            # Extract title - look for p tag with "gzadzy" in class (appears consistent)
            title_tag = row.find("p", class_=lambda c: c and "gzadzy" in c)
            if not title_tag:
                continue

            title = title_tag.get_text().strip()

            # Check if subscription - look for any p tag containing "Renews" (robust approach)
            subscription = False
            all_p_tags = row.find_all("p")
            for tag in all_p_tags:
                if "Renews" in tag.get_text():
                    subscription = True
                    break

            # Extract price - find last td (price column) and get p tag (structural approach)
            all_tds = row.find_all("td")
            price_tag = None
            if all_tds:
                # Price is in the last td
                last_td = all_tds[-1]
                if isinstance(last_td, Tag):
                    price_tag = last_td.find("p")

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
