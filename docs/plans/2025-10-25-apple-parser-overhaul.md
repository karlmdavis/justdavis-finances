# Apple Receipt Parser Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace brittle, wildcard-selector-based Apple receipt parser with robust, format-specific parsers that use targeted selectors with size validation.

**Architecture:** Two dedicated parsers (table_format and modern_format) sharing common selector utility methods with three validation tiers (large container, small container, value). Comprehensive parameterized tests using real production HTML files.

**Tech Stack:** Python 3.11+, BeautifulSoup4, pytest (parameterized tests), Money/FinancialDate primitives

---

## Investigation Summary

**Format Statistics (from 870 production receipts):**
- 836 receipts (96%): `legacy_aapl` format → rename to `table_format`
- 34 receipts (4%): `modern_custom` format → rename to `modern_format`

**User's hypothesis was INCORRECT:**
- NOT "purchase vs subscription" distinction
- ACTUALLY "2020-era table-based vs 2025+ CSS-in-JS" HTML structure

**Better Format Names:**
- `table_format`: 2020-2023 receipts with traditional HTML tables, `.aapl-*` classes
- `modern_format`: 2025+ receipts with CSS-in-JS styling, `.custom-*` classes, subscription-focused

**Current Parser Problems:**
1. Date extraction: 100% failure rate (all receipts have null `receipt_date`)
2. Item extraction: Massive duplication (52+ items for single-item purchases)
3. Wildcard selectors: `"span, div, td"` capturing entire containers instead of target values
4. No size validation: Allows 5000+ character extractions without error

**Production Data Samples:**
- Table format: `data/apple/emails/20201024_084743_Your_receipt_from_Apple._d6f911bd-formatted-simple.html`
- Modern format: `data/apple/emails/20251014_130109_Your_receipt_from_Apple._42f10feb-formatted-simple.html`

---

## Task 1: Create Selector Utility Methods with Size Validation

**Files:**
- Modify: `src/finances/apple/parser.py:750-850`

**Step 1: Add size validation constants**

Add after imports section (line ~15):

```python
# Selector size validation thresholds
LARGE_CONTAINER_MAX_CHARS = 200  # For section containers
SMALL_CONTAINER_MAX_CHARS = 80   # For field labels/headers
VALUE_MAX_CHARS = 80             # For extracted values
```

**Step 2: Write test for large container selector**

Create: `tests/unit/test_apple/test_parser_utilities.py`

```python
"""Unit tests for Apple parser selector utilities."""

import pytest
from bs4 import BeautifulSoup
from finances.apple.parser import AppleReceiptParser


class TestSelectorUtilities:
    """Test selector utility methods with size validation."""

    def test_select_large_container_accepts_200_chars(self):
        """Large container selector allows up to 200 characters."""
        html = f"<div class='container'>{'x' * 200}</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_large_container(soup, "div.container")
        assert result is not None
        assert len(result) == 200

    def test_select_large_container_rejects_201_chars(self):
        """Large container selector throws on >200 characters."""
        html = f"<div class='container'>{'x' * 201}</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match="captured 201 chars.*likely matched a container"):
            parser._select_large_container(soup, "div.container")

    def test_select_small_container_accepts_80_chars(self):
        """Small container selector allows up to 80 characters."""
        html = f"<td class='label'>{'x' * 80}</td>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_small_container(soup, "td.label")
        assert result is not None
        assert len(result) == 80

    def test_select_small_container_rejects_81_chars(self):
        """Small container selector throws on >80 characters."""
        html = f"<td class='label'>{'x' * 81}</td>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match="captured 81 chars.*exceeded small container limit"):
            parser._select_small_container(soup, "td.label")

    def test_select_value_accepts_80_chars(self):
        """Value selector allows up to 80 characters."""
        html = f"<span class='value'>{'$' + '9' * 79}</span>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_value(soup, "span.value")
        assert result is not None
        assert len(result) == 80

    def test_select_value_rejects_81_chars(self):
        """Value selector throws on >80 characters."""
        html = f"<span class='value'>{'$' + '9' * 80}</span>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match="captured 81 chars.*exceeded value limit"):
            parser._select_value(soup, "span.value")

    def test_select_value_returns_none_when_not_found(self):
        """Value selector returns None when element not found."""
        html = "<div>no matching element</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_value(soup, "span.missing")
        assert result is None
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py -v`

Expected: All tests FAIL with "AttributeError: 'AppleReceiptParser' object has no attribute '_select_large_container'"

**Step 4: Implement selector utility methods**

Add to `src/finances/apple/parser.py` after line ~850 (after existing helper methods):

```python
def _select_large_container(
    self, soup: BeautifulSoup, selector: str
) -> str | None:
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


def _select_small_container(
    self, soup: BeautifulSoup, selector: str
) -> str | None:
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
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py -v`

Expected: All 9 tests PASS

**Step 6: Commit**

```bash
git add src/finances/apple/parser.py tests/unit/test_apple/test_parser_utilities.py
git commit -m "feat(apple): add selector utilities with size validation

- Add three selector utility methods with distinct size limits
- Large containers: 200 char limit (sections, tables)
- Small containers: 80 char limit (labels, headers)
- Values: 80 char limit (prices, dates, IDs)
- All methods throw ValueError if limit exceeded
- Comprehensive unit tests for all three methods"
```

---

## Task 2: Create Parameterized Tests for Production HTML

**Files:**
- Create: `tests/integration/test_apple_parser_production.py`
- Create: `tests/fixtures/apple/table_format_samples.py`
- Create: `tests/fixtures/apple/modern_format_samples.py`

**Step 1: Identify representative production samples**

Run: `ls -1 data/apple/emails/ | grep "2020.*formatted-simple.html" | head -3`

Copy 2-3 filenames for table format samples.

Run: `ls -1 data/apple/emails/ | grep "2025.*formatted-simple.html" | head -3`

Copy 2-3 filenames for modern format samples.

**Step 2: Create table format sample fixtures**

Create: `tests/fixtures/apple/table_format_samples.py`

```python
"""
Expected values for table_format (2020-era) Apple receipt samples.

These are real production receipts with expected extraction values.
Used for parameterized integration tests.
"""

from finances.core import Money, FinancialDate


# Sample 1: Single app purchase
TABLE_SAMPLE_1 = {
    "html_filename": "20201024_084743_Your_receipt_from_Apple._d6f911bd-formatted-simple.html",
    "expected": {
        "format_detected": "table_format",
        "apple_id": "karl_apple@justdavis.com",
        "receipt_date": FinancialDate.from_string("2020-10-23"),
        "order_id": "MSBQLG265J",
        "document_number": "114382498203",
        "subtotal": None,  # Not shown separately for single-item
        "tax": None,  # Not shown separately
        "total": Money.from_cents(999),  # $9.99
        "items": [
            {
                "title": "Slay the Spire",
                "cost": Money.from_cents(999),
                "quantity": 1,
                "subscription": False,
            }
        ],
    },
}

# TODO: Add 1-2 more samples after first passes
TABLE_SAMPLES = [TABLE_SAMPLE_1]
```

**Step 3: Create modern format sample fixtures**

Create: `tests/fixtures/apple/modern_format_samples.py`

```python
"""
Expected values for modern_format (2025+) Apple receipt samples.

These are real production receipts with expected extraction values.
Used for parameterized integration tests.
"""

from finances.core import Money, FinancialDate


# Sample 1: Subscription renewals
MODERN_SAMPLE_1 = {
    "html_filename": "20251014_130109_Your_receipt_from_Apple._42f10feb-formatted-simple.html",
    "expected": {
        "format_detected": "modern_format",
        "apple_id": "karl_apple@justdavis.com",
        "receipt_date": FinancialDate.from_string("2025-10-11"),
        "order_id": "MSD3B7XL1D",
        "document_number": "776034761448",
        "subtotal": Money.from_cents(2498),  # $24.98
        "tax": Money.from_cents(150),  # $1.50
        "total": Money.from_cents(2648),  # $26.48
        "items": [
            {
                "title": "RISE: Sleep Tracker",
                "cost": Money.from_cents(999),
                "quantity": 1,
                "subscription": True,
            },
            {
                "title": "YNAB",
                "cost": Money.from_cents(1499),
                "quantity": 1,
                "subscription": True,
            },
        ],
    },
}

# TODO: Add 1-2 more samples after first passes
MODERN_SAMPLES = [MODERN_SAMPLE_1]
```

**Step 4: Write parameterized test that reports ALL failures**

Create: `tests/integration/test_apple_parser_production.py`

```python
"""
Integration tests for Apple parser using real production HTML.

Tests ALL fields for each sample and reports comprehensive failure list.
"""

import pytest
from pathlib import Path
from finances.apple.parser import AppleReceiptParser
from tests.fixtures.apple.table_format_samples import TABLE_SAMPLES
from tests.fixtures.apple.modern_format_samples import MODERN_SAMPLES


class TestAppleParserProduction:
    """Test parser against real production HTML files."""

    @pytest.mark.parametrize("sample", TABLE_SAMPLES)
    def test_table_format_parsing(self, sample):
        """Test table_format (2020-era) receipt parsing with ALL field validation."""
        # Arrange
        html_path = Path("data/apple/emails") / sample["html_filename"]
        expected = sample["expected"]
        failures = []

        # Act
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        parser = AppleReceiptParser()
        receipt = parser.parse(html_content)

        # Assert ALL fields and collect failures
        if receipt.format_detected != expected["format_detected"]:
            failures.append(
                f"format_detected: expected '{expected['format_detected']}', "
                f"got '{receipt.format_detected}'"
            )

        if receipt.apple_id != expected["apple_id"]:
            failures.append(
                f"apple_id: expected '{expected['apple_id']}', "
                f"got '{receipt.apple_id}'"
            )

        if receipt.receipt_date != expected["receipt_date"]:
            failures.append(
                f"receipt_date: expected {expected['receipt_date']}, "
                f"got {receipt.receipt_date}"
            )

        if receipt.order_id != expected["order_id"]:
            failures.append(
                f"order_id: expected '{expected['order_id']}', "
                f"got '{receipt.order_id}'"
            )

        if receipt.document_number != expected["document_number"]:
            failures.append(
                f"document_number: expected '{expected['document_number']}', "
                f"got '{receipt.document_number}'"
            )

        if receipt.subtotal != expected["subtotal"]:
            failures.append(
                f"subtotal: expected {expected['subtotal']}, "
                f"got {receipt.subtotal}"
            )

        if receipt.tax != expected["tax"]:
            failures.append(
                f"tax: expected {expected['tax']}, got {receipt.tax}"
            )

        if receipt.total != expected["total"]:
            failures.append(
                f"total: expected {expected['total']}, got {receipt.total}"
            )

        if len(receipt.items) != len(expected["items"]):
            failures.append(
                f"items length: expected {len(expected['items'])}, "
                f"got {len(receipt.items)}"
            )
        else:
            # Check each item
            for i, (actual_item, expected_item) in enumerate(
                zip(receipt.items, expected["items"])
            ):
                if expected_item["title"] not in actual_item.title:
                    failures.append(
                        f"items[{i}].title: expected to contain "
                        f"'{expected_item['title']}', got '{actual_item.title}'"
                    )

                if actual_item.cost != expected_item["cost"]:
                    failures.append(
                        f"items[{i}].cost: expected {expected_item['cost']}, "
                        f"got {actual_item.cost}"
                    )

                if actual_item.quantity != expected_item["quantity"]:
                    failures.append(
                        f"items[{i}].quantity: expected {expected_item['quantity']}, "
                        f"got {actual_item.quantity}"
                    )

                if actual_item.subscription != expected_item["subscription"]:
                    failures.append(
                        f"items[{i}].subscription: expected {expected_item['subscription']}, "
                        f"got {actual_item.subscription}"
                    )

        # Report ALL failures at once
        if failures:
            failure_report = "\n".join([f"  - {f}" for f in failures])
            pytest.fail(
                f"\n{len(failures)} field(s) failed for {sample['html_filename']}:\n"
                f"{failure_report}"
            )

    @pytest.mark.parametrize("sample", MODERN_SAMPLES)
    def test_modern_format_parsing(self, sample):
        """Test modern_format (2025+) receipt parsing with ALL field validation."""
        # Arrange
        html_path = Path("data/apple/emails") / sample["html_filename"]
        expected = sample["expected"]
        failures = []

        # Act
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        parser = AppleReceiptParser()
        receipt = parser.parse(html_content)

        # Assert ALL fields and collect failures (same as table_format test)
        if receipt.format_detected != expected["format_detected"]:
            failures.append(
                f"format_detected: expected '{expected['format_detected']}', "
                f"got '{receipt.format_detected}'"
            )

        if receipt.apple_id != expected["apple_id"]:
            failures.append(
                f"apple_id: expected '{expected['apple_id']}', "
                f"got '{receipt.apple_id}'"
            )

        if receipt.receipt_date != expected["receipt_date"]:
            failures.append(
                f"receipt_date: expected {expected['receipt_date']}, "
                f"got {receipt.receipt_date}"
            )

        if receipt.order_id != expected["order_id"]:
            failures.append(
                f"order_id: expected '{expected['order_id']}', "
                f"got '{receipt.order_id}'"
            )

        if receipt.document_number != expected["document_number"]:
            failures.append(
                f"document_number: expected '{expected['document_number']}', "
                f"got '{receipt.document_number}'"
            )

        if receipt.subtotal != expected["subtotal"]:
            failures.append(
                f"subtotal: expected {expected['subtotal']}, "
                f"got {receipt.subtotal}"
            )

        if receipt.tax != expected["tax"]:
            failures.append(
                f"tax: expected {expected['tax']}, got {receipt.tax}"
            )

        if receipt.total != expected["total"]:
            failures.append(
                f"total: expected {expected['total']}, got {receipt.total}"
            )

        if len(receipt.items) != len(expected["items"]):
            failures.append(
                f"items length: expected {len(expected['items'])}, "
                f"got {len(receipt.items)}"
            )
        else:
            # Check each item
            for i, (actual_item, expected_item) in enumerate(
                zip(receipt.items, expected["items"])
            ):
                if expected_item["title"] not in actual_item.title:
                    failures.append(
                        f"items[{i}].title: expected to contain "
                        f"'{expected_item['title']}', got '{actual_item.title}'"
                    )

                if actual_item.cost != expected_item["cost"]:
                    failures.append(
                        f"items[{i}].cost: expected {expected_item['cost']}, "
                        f"got {actual_item.cost}"
                    )

                if actual_item.quantity != expected_item["quantity"]:
                    failures.append(
                        f"items[{i}].quantity: expected {expected_item['quantity']}, "
                        f"got {actual_item.quantity}"
                    )

                if actual_item.subscription != expected_item["subscription"]:
                    failures.append(
                        f"items[{i}].subscription: expected {expected_item['subscription']}, "
                        f"got {actual_item.subscription}"
                    )

        # Report ALL failures at once
        if failures:
            failure_report = "\n".join([f"  - {f}" for f in failures])
            pytest.fail(
                f"\n{len(failures)} field(s) failed for {sample['html_filename']}:\n"
                f"{failure_report}"
            )
```

**Step 5: Run tests to capture baseline failures**

Run: `uv run pytest tests/integration/test_apple_parser_production.py -v`

Expected: Tests FAIL with comprehensive list of all field mismatches

Save output to: `docs/plans/2025-10-25-parser-baseline-failures.txt`

**Step 6: Commit**

```bash
git add tests/integration/test_apple_parser_production.py \
  tests/fixtures/apple/table_format_samples.py \
  tests/fixtures/apple/modern_format_samples.py \
  docs/plans/2025-10-25-parser-baseline-failures.txt
git commit -m "test(apple): add comprehensive production HTML parsing tests

- Parameterized tests for table_format and modern_format
- Test fixtures with expected values for real production receipts
- ALL field validation with collected failure reporting
- Baseline failure output captured for reference"
```

---

## Task 3: Rename Format Detection

**Files:**
- Modify: `src/finances/apple/parser.py:200-250`

**Step 1: Write test for format name migration**

Add to `tests/unit/test_apple/test_parser_utilities.py`:

```python
def test_format_detection_uses_new_names():
    """Format detection returns 'table_format' and 'modern_format', not legacy names."""
    # Table format (2020-era)
    table_html = """
    <table class="aapl-desktop-tbl">
      <tr><td>APPLE ID</td><td>test@example.com</td></tr>
    </table>
    """
    soup = BeautifulSoup(table_html, "html.parser")
    parser = AppleReceiptParser()
    format_name = parser._detect_format(soup)
    assert format_name == "table_format"

    # Modern format (2025+)
    modern_html = """
    <div class="custom-hzv07h">
      <p>Apple Account: test@example.com</p>
    </div>
    """
    soup = BeautifulSoup(modern_html, "html.parser")
    format_name = parser._detect_format(soup)
    assert format_name == "modern_format"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py::test_format_detection_uses_new_names -v`

Expected: FAIL with "'legacy_aapl' != 'table_format'"

**Step 3: Update format detection logic**

Find `_detect_format` method in `src/finances/apple/parser.py` (around line 200-250).

Replace format return values:

```python
def _detect_format(self, soup: BeautifulSoup) -> str:
    """
    Detect which Apple receipt format this HTML uses.

    Returns:
        "table_format": 2020-2023 era table-based receipts with .aapl-* classes
        "modern_format": 2025+ CSS-in-JS receipts with .custom-* classes
    """
    # Check for modern format (CSS-in-JS with .custom-* classes)
    if soup.select_one("[class^='custom-']"):
        return "modern_format"

    # Check for table format (.aapl-* classes, table structure)
    if soup.select_one(".aapl-desktop-tbl") or soup.select_one(".aapl-mobile-tbl"):
        return "table_format"

    # Default to table format (older receipts)
    return "table_format"
```

**Step 4: Update test fixtures to use new names**

In `tests/fixtures/apple/table_format_samples.py`, change:
```python
"format_detected": "table_format",  # Was "legacy_aapl"
```

In `tests/fixtures/apple/modern_format_samples.py`, change:
```python
"format_detected": "modern_format",  # Was "modern_custom"
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py::test_format_detection_uses_new_names -v`

Expected: PASS

Run: `uv run pytest tests/integration/test_apple_parser_production.py -v`

Expected: Still FAIL but with updated format names in output

**Step 6: Commit**

```bash
git add src/finances/apple/parser.py \
  tests/unit/test_apple/test_parser_utilities.py \
  tests/fixtures/apple/
git commit -m "refactor(apple): rename receipt formats to descriptive names

- legacy_aapl → table_format (2020-2023 table-based receipts)
- modern_custom → modern_format (2025+ CSS-in-JS receipts)
- Update format detection logic and all test fixtures
- Names now describe HTML structure, not arbitrary legacy status"
```

---

## Task 4: Implement Table Format Parser

**Files:**
- Modify: `src/finances/apple/parser.py:300-600`

**Step 1: Analyze table format HTML structure**

Read: `data/apple/emails/20201024_084743_Your_receipt_from_Apple._d6f911bd-formatted-simple.html`

Document selector strategy:

```
Table Format Structure (2020-era):
- Main container: table.aapl-desktop-tbl
- Metadata section: table with border-collapse style
  - Apple ID: td containing <span>APPLE ID</span>, next td has value
  - Date: td containing <span>DATE</span>, next td has value like "Oct 23, 2020"
  - Order ID: td containing <span>ORDER ID</span>, next td has link with order ID
  - Document: td containing <span>DOCUMENT NO.</span>, next td has document number
- Items section: table.aapl-desktop-tbl with section-header row
  - Each item: tr with .artwork-cell, .item-cell, .price-cell
  - Title: span.title
  - Price: table > tr > td with font-weight:600 and whitespace:nowrap
- Total: td with "TOTAL" text (all caps), next non-empty td sibling has total amount
```

**Step 2: Write test for table format date extraction**

Add to `tests/unit/test_apple/test_parser_utilities.py`:

```python
def test_table_format_extract_date():
    """Extract date from table format 'Oct 23, 2020' → FinancialDate."""
    html = """
    <table>
      <tr>
        <td colspan="2"><span style="color:rgb(102,102,102);font-size:10px;">DATE</span><br>Oct 23, 2020</td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AppleReceiptParser()

    date = parser._extract_table_format_date(soup)
    assert date is not None
    assert date == FinancialDate.from_string("2020-10-23")
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py::test_table_format_extract_date -v`

Expected: FAIL with "AttributeError: 'AppleReceiptParser' object has no attribute '_extract_table_format_date'"

**Step 4: Implement table format extraction methods**

Add to `src/finances/apple/parser.py` after utility methods:

```python
def _extract_table_format_date(self, soup: BeautifulSoup) -> FinancialDate | None:
    """
    Extract receipt date from table format HTML.

    Table format has: <span>DATE</span><br>Oct 23, 2020
    """
    # Find td containing "DATE" label
    date_cells = soup.find_all("td")
    for cell in date_cells:
        text = cell.get_text()
        if "DATE" in text and "Oct" in text or "Jan" in text or "Feb" in text:
            # Extract date portion (after the DATE label)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            for line in lines:
                if line == "DATE":
                    continue
                # Try to parse date like "Oct 23, 2020"
                try:
                    # Convert "Oct 23, 2020" to "2020-10-23"
                    from datetime import datetime
                    date_obj = datetime.strptime(line, "%b %d, %Y")
                    return FinancialDate(date=date_obj.date())
                except ValueError:
                    continue

    return None


def _extract_table_format_apple_id(self, soup: BeautifulSoup) -> str | None:
    """
    Extract Apple ID from table format HTML.

    Table format has: <span>APPLE ID</span><br>email@example.com
    """
    # Find td containing "APPLE ID" label
    id_cells = soup.find_all("td")
    for cell in id_cells:
        text = cell.get_text()
        if "APPLE ID" in text and "@" in text:
            # Extract email portion
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            for line in lines:
                if "@" in line and "APPLE ID" not in line:
                    return line

    return None


def _extract_table_format_order_id(self, soup: BeautifulSoup) -> str | None:
    """
    Extract order ID from table format HTML.

    Table format has: <span>ORDER ID</span><br><a>ORDER123</a>
    """
    # Find td containing "ORDER ID" label
    id_cells = soup.find_all("td")
    for cell in id_cells:
        if "ORDER ID" in cell.get_text():
            # Look for link or text after label
            link = cell.find("a")
            if link:
                order_id = link.get_text().strip()
                if order_id and len(order_id) >= 8:
                    return order_id

    return None


def _extract_table_format_items(self, soup: BeautifulSoup) -> list:
    """
    Extract items from table format HTML.

    Table format has item rows with:
    - td.artwork-cell: product image
    - td.item-cell: title, artist, type, device
    - td.price-cell: price in nested table
    """
    items = []

    # Find all item rows (have artwork-cell, item-cell, price-cell)
    item_rows = soup.find_all("tr", {"style": "max-height:114px;"})

    for row in item_rows:
        # Extract title
        title_span = row.select_one("span.title")
        if not title_span:
            continue

        title = title_span.get_text().strip()

        # Extract price from nested table
        price_cell = row.select_one("td.price-cell")
        if not price_cell:
            continue

        price_text = None
        price_spans = price_cell.find_all("span", {"style": "font-weight:600;white-space:nowrap;"})
        if price_spans:
            price_text = price_spans[0].get_text().strip()

        if not price_text:
            continue

        # Parse price to Money
        cost_cents = self._parse_currency(price_text)
        if cost_cents is None:
            continue

        cost = Money.from_cents(cost_cents)

        # Determine if subscription (not available in table format)
        subscription = False

        items.append(
            ParsedItem(
                title=title,
                cost=cost,
                quantity=1,
                subscription=subscription,
                item_type=None,
                metadata={"extraction_method": "table_format_targeted"},
            )
        )

    return items


def _parse_table_format(self, soup: BeautifulSoup) -> ParsedReceipt:
    """
    Parse table format (2020-2023) Apple receipt.

    Uses targeted selectors for table-based HTML structure.
    """
    apple_id = self._extract_table_format_apple_id(soup)
    receipt_date = self._extract_table_format_date(soup)
    order_id = self._extract_table_format_order_id(soup)

    # Document number (similar pattern to order ID)
    document_number = None
    doc_cells = soup.find_all("td")
    for cell in doc_cells:
        if "DOCUMENT NO." in cell.get_text():
            text_lines = [l.strip() for l in cell.get_text().split("\n") if l.strip()]
            for line in text_lines:
                if line.isdigit() and len(line) >= 10:
                    document_number = line
                    break

    # Extract total (TOTAL label, next td sibling)
    total = None
    total_cells = soup.find_all("td", string=lambda s: s and "TOTAL" in s.upper())
    for cell in total_cells:
        if cell.get_text().strip() == "TOTAL":
            # Get next non-empty sibling
            sibling = cell.find_next_sibling("td")
            while sibling and not sibling.get_text().strip():
                sibling = sibling.find_next_sibling("td")

            if sibling:
                price_text = sibling.get_text().strip()
                total_cents = self._parse_currency(price_text)
                if total_cents is not None:
                    total = Money.from_cents(total_cents)
                    break

    # Extract items
    items = self._extract_table_format_items(soup)

    # Subtotal and tax not shown separately in table format single-item receipts
    subtotal = None
    tax = None

    return ParsedReceipt(
        format_detected="table_format",
        apple_id=apple_id,
        receipt_date=receipt_date,
        order_id=order_id,
        document_number=document_number,
        subtotal=subtotal,
        tax=tax,
        total=total,
        currency="USD",
        payment_method=None,
        billed_to=None,
        items=items,
        parsing_metadata={
            "extraction_method": "table_format_parser",
        },
    )
```

**Step 5: Update main parse method to route to format-specific parsers**

Find `parse()` method in `src/finances/apple/parser.py` (around line 150):

```python
def parse(self, html_content: str) -> ParsedReceipt:
    """
    Parse Apple receipt HTML to extract structured data.

    Routes to format-specific parser based on HTML structure.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    format_detected = self._detect_format(soup)

    if format_detected == "table_format":
        return self._parse_table_format(soup)
    elif format_detected == "modern_format":
        return self._parse_modern_format(soup)
    else:
        raise ValueError(f"Unknown format: {format_detected}")
```

**Step 6: Run unit test to verify date extraction**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py::test_table_format_extract_date -v`

Expected: PASS

**Step 7: Run integration tests to check progress**

Run: `uv run pytest tests/integration/test_apple_parser_production.py::test_table_format_parsing -v`

Expected: Fewer failures (date, apple_id, order_id, items should pass now)

**Step 8: Commit**

```bash
git add src/finances/apple/parser.py tests/unit/test_apple/test_parser_utilities.py
git commit -m "feat(apple): implement table_format parser with targeted selectors

- Add format-specific parser methods for table format
- Extract date, Apple ID, order ID using targeted selectors
- Extract items from item rows with artwork/title/price cells
- No more wildcard selectors like 'span, div, td'
- Integration tests show progress on table format parsing"
```

---

## Task 5: Implement Modern Format Parser

**Files:**
- Modify: `src/finances/apple/parser.py:600-800`

**Step 1: Analyze modern format HTML structure**

Read: `data/apple/emails/20251014_130109_Your_receipt_from_Apple._42f10feb-formatted-simple.html`

Document selector strategy:

```
Modern Format Structure (2025+):
- Main container: div.custom-hzv07h (CSS-in-JS classes)
- Metadata: Direct <p> tags with labels
  - Date: <p class="custom-18w16cf">October 11, 2025</p>
  - Order ID: <p class="custom-f41j3e">Order ID:</p> followed by <p class="custom-zresjj">ID123</p>
  - Document: Similar pattern with "Document:" label
  - Apple Account: Similar pattern with "Apple Account:" label
- Items: table.subscription-lockup__container
  - Each item: tr.subscription-lockup
  - Title: p.custom-gzadzy
  - Subscription details: p.custom-wogfc8 with "Renews" text
  - Price: p.custom-137u684
- Billing section: div.payment-information
  - Subtotal: p.custom-4tra68 containing "Subtotal", sibling div with amount
  - Tax: p.custom-4tra68 containing "Tax", sibling div with amount
  - Total: p.custom-15zbox7 (payment method), sibling div with total amount
```

**Step 2: Write test for modern format date extraction**

Add to `tests/unit/test_apple/test_parser_utilities.py`:

```python
def test_modern_format_extract_date():
    """Extract date from modern format 'October 11, 2025' → FinancialDate."""
    html = """
    <div><p class="custom-18w16cf">October 11, 2025</p></div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AppleReceiptParser()

    date = parser._extract_modern_format_date(soup)
    assert date is not None
    assert date == FinancialDate.from_string("2025-10-11")
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py::test_modern_format_extract_date -v`

Expected: FAIL with "AttributeError"

**Step 4: Implement modern format extraction methods**

Add to `src/finances/apple/parser.py`:

```python
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


def _extract_modern_format_field(
    self, soup: BeautifulSoup, label: str
) -> str | None:
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
        if value_tag:
            value = value_tag.get_text().strip()
            if value and value != label:
                return value

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


def _parse_modern_format(self, soup: BeautifulSoup) -> ParsedReceipt:
    """
    Parse modern format (2025+) Apple receipt.

    Uses targeted selectors for CSS-in-JS HTML structure.
    """
    receipt_date = self._extract_modern_format_date(soup)
    apple_id = self._extract_modern_format_field(soup, "Apple Account:")
    order_id = self._extract_modern_format_field(soup, "Order ID:")
    document_number = self._extract_modern_format_field(soup, "Document:")

    # Extract billing amounts from payment information section
    subtotal = None
    tax = None
    total = None

    billing_section = soup.find("div", class_=lambda c: c and "payment-information" in c)
    if billing_section:
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

    # Extract items
    items = self._extract_modern_format_items(soup)

    return ParsedReceipt(
        format_detected="modern_format",
        apple_id=apple_id,
        receipt_date=receipt_date,
        order_id=order_id,
        document_number=document_number,
        subtotal=subtotal,
        tax=tax,
        total=total,
        currency="USD",
        payment_method=None,
        billed_to=None,
        items=items,
        parsing_metadata={
            "extraction_method": "modern_format_parser",
        },
    )
```

**Step 5: Run unit test to verify date extraction**

Run: `uv run pytest tests/unit/test_apple/test_parser_utilities.py::test_modern_format_extract_date -v`

Expected: PASS

**Step 6: Run integration tests to check progress**

Run: `uv run pytest tests/integration/test_apple_parser_production.py::test_modern_format_parsing -v`

Expected: Most/all fields should pass now

**Step 7: Commit**

```bash
git add src/finances/apple/parser.py tests/unit/test_apple/test_parser_utilities.py
git commit -m "feat(apple): implement modern_format parser with targeted selectors

- Add format-specific parser methods for modern format
- Extract date, Apple Account, order ID using label patterns
- Extract subscription items with renewal information
- Extract subtotal, tax, total from billing section
- All selectors use specific class patterns, no wildcards"
```

---

## Task 6: Remove Old Parser Code and Wildcard Selectors

**Files:**
- Modify: `src/finances/apple/parser.py:300-900`

**Step 1: Identify dead code to remove**

Search for:
- Old selector lists with wildcard patterns
- Methods like `_extract_apple_id`, `_extract_date`, etc. (replaced by format-specific methods)
- Pattern-based extraction methods that are no longer called

Run: `grep -n "span, div, td" src/finances/apple/parser.py`

List all lines with wildcard selectors.

**Step 2: Run full test suite before removal**

Run: `uv run pytest tests/ -k apple -v`

Expected: All tests pass (or known failures documented)

**Step 3: Remove old extraction methods**

Delete methods:
- `_extract_apple_id` (replaced by format-specific)
- `_extract_date` (replaced by format-specific)
- `_extract_order_id` (replaced by format-specific)
- `_extract_total` (replaced by format-specific)
- `_extract_items` (replaced by format-specific)
- Any selector lists containing `"span, div, td"`

**Step 4: Run tests to verify no regressions**

Run: `uv run pytest tests/ -k apple -v`

Expected: All tests still pass

**Step 5: Run grep to verify no wildcard selectors remain**

Run: `grep "span, div, td" src/finances/apple/parser.py`

Expected: No matches found

**Step 6: Check test coverage**

Run: `uv run pytest --cov=src/finances/apple/parser --cov-report=term-missing tests/ -k apple`

Review coverage report. If any methods are uncovered, either:
- Add tests for them, OR
- Remove them as dead code

**Step 7: Commit**

```bash
git add src/finances/apple/parser.py
git commit -m "refactor(apple): remove old parser code and wildcard selectors

- Remove old extraction methods replaced by format-specific parsers
- Delete all selector lists containing 'span, div, td'
- Verify no wildcard selectors remain in codebase
- All tests passing, no dead code remaining"
```

---

## Task 7: Add More Test Samples and Edge Cases

**Files:**
- Modify: `tests/fixtures/apple/table_format_samples.py`
- Modify: `tests/fixtures/apple/modern_format_samples.py`

**Step 1: Identify diverse samples**

Find receipts with different characteristics:
- Multi-item purchases (table format)
- Different subscription types (modern format)
- Different years (to test date parsing edge cases)

Run:
```bash
# Find multi-item receipts (large file sizes)
ls -lh data/apple/emails/*.html | sort -k5 -hr | head -10

# Find different years
ls -1 data/apple/emails/ | cut -d'_' -f1 | sort -u
```

**Step 2: Add 2 more table format samples**

Edit `tests/fixtures/apple/table_format_samples.py`:

Add 2 more sample dictionaries to `TABLE_SAMPLES` list:
- One from 2021
- One from 2022

Manually inspect HTML and determine expected values.

**Step 3: Add 2 more modern format samples**

Edit `tests/fixtures/apple/modern_format_samples.py`:

Add 2 more sample dictionaries to `MODERN_SAMPLES` list:
- One with different subscription types
- One from different month (test date parsing)

**Step 4: Run integration tests**

Run: `uv run pytest tests/integration/test_apple_parser_production.py -v`

Expected: All parameterized test cases pass

**Step 5: Commit**

```bash
git add tests/fixtures/apple/
git commit -m "test(apple): add additional test samples for both formats

- Add 2 more table_format samples (2021, 2022)
- Add 2 more modern_format samples (diverse subscriptions)
- All parameterized tests passing with 3 samples per format"
```

---

## Task 8: Update Existing Test Fixtures

**Files:**
- Modify: `tests/fixtures/apple/legacy_aapl_receipt.html`
- Create: `tests/fixtures/apple/table_format_receipt.html`
- Create: `tests/fixtures/apple/modern_format_receipt.html`

**Step 1: Rename legacy test fixture**

```bash
mv tests/fixtures/apple/legacy_aapl_receipt.html \
   tests/fixtures/apple/table_format_receipt.html
```

**Step 2: Copy modern format sample to fixtures**

```bash
cp data/apple/emails/20251014_130109_Your_receipt_from_Apple._42f10feb-formatted-simple.html \
   tests/fixtures/apple/modern_format_receipt.html
```

**Step 3: Update test imports**

Find all references to `legacy_aapl_receipt.html` in tests:

Run: `grep -r "legacy_aapl_receipt" tests/`

Update to use `table_format_receipt.html`.

**Step 4: Add test for modern format fixture**

Add to `tests/integration/test_apple_parser.py`:

```python
def test_parse_modern_format_complete(self):
    """Test complete modern format receipt parsing."""
    fixture_path = Path("tests/fixtures/apple/modern_format_receipt.html")
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    parser = AppleReceiptParser()
    receipt = parser.parse(html_content)

    # Format detection
    assert receipt.format_detected == "modern_format"

    # Metadata - EXACT values from fixture
    assert receipt.apple_id == "karl_apple@justdavis.com"
    assert receipt.receipt_date == FinancialDate.from_string("2025-10-11")
    assert receipt.order_id == "MSD3B7XL1D"
    assert receipt.document_number == "776034761448"

    # Financial data - EXACT values
    assert receipt.subtotal == Money.from_cents(2498)
    assert receipt.tax == Money.from_cents(150)
    assert receipt.total == Money.from_cents(2648)

    # Items
    assert len(receipt.items) == 2
    assert "RISE" in receipt.items[0].title
    assert receipt.items[0].cost == Money.from_cents(999)
    assert receipt.items[0].subscription is True
    assert "YNAB" in receipt.items[1].title
    assert receipt.items[1].cost == Money.from_cents(1499)
    assert receipt.items[1].subscription is True
```

**Step 5: Run updated tests**

Run: `uv run pytest tests/integration/test_apple_parser.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add tests/fixtures/apple/ tests/integration/test_apple_parser.py
git commit -m "test(apple): update test fixtures to use new format names

- Rename legacy_aapl_receipt.html → table_format_receipt.html
- Add modern_format_receipt.html fixture
- Add comprehensive test for modern format
- Update all test imports to use new fixture names"
```

---

## Task 9: Verify and Document Success

**Files:**
- Create: `docs/plans/2025-10-25-parser-overhaul-results.md`

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`

Expected: All tests pass

**Step 2: Check for wildcard selectors**

Run: `grep -r "span, div, td" src/finances/apple/`

Expected: No matches

**Step 3: Check test coverage**

Run: `uv run pytest --cov=src/finances/apple/parser --cov-report=term-missing tests/ -k apple`

Expected: >90% coverage, no uncovered critical code

**Step 4: Re-parse production receipts**

Run: `uv run finances apple parse-receipts --input-dir data/apple/emails/ --output-dir data/apple/exports/`

Check logs for:
- Number of successful parses
- Number of receipts with valid date and total
- No ValueErrors about oversized selectors

**Step 5: Document results**

Create: `docs/plans/2025-10-25-parser-overhaul-results.md`

```markdown
# Apple Parser Overhaul Results

## Summary

Successfully replaced wildcard-selector-based parser with robust, format-specific parsers.

## Metrics

**Test Coverage:**
- Unit tests: X tests, 100% pass rate
- Integration tests: Y parameterized tests (3 table format, 3 modern format), 100% pass rate
- Coverage: Z% of parser.py

**Code Quality:**
- Zero wildcard selectors remaining (`grep "span, div, td"` returns 0 matches)
- All selectors have size validation (200/80/80 char limits)
- Format detection accuracy: 100% on 870 production receipts

**Production Parsing:**
- Before: 0 receipts with valid date/total (0%)
- After: X receipts with valid date/total (Y%)
- Table format: A/B successful (C%)
- Modern format: D/E successful (F%)

## Architecture

**Format Detection:**
- `table_format`: 2020-2023 table-based receipts (96% of corpus)
- `modern_format`: 2025+ CSS-in-JS receipts (4% of corpus)

**Selector Utilities:**
- `_select_large_container()`: 200 char limit for sections
- `_select_small_container()`: 80 char limit for labels
- `_select_value()`: 80 char limit for extracted values

**Format-Specific Parsers:**
- `_parse_table_format()`: Targeted selectors for table structure
- `_parse_modern_format()`: Targeted selectors for CSS-in-JS structure

## Files Changed

- `src/finances/apple/parser.py`: Complete overhaul (removed ~500 lines, added ~300)
- `tests/integration/test_apple_parser_production.py`: New comprehensive tests
- `tests/unit/test_apple/test_parser_utilities.py`: New utility method tests
- `tests/fixtures/apple/`: New format-specific fixtures and samples

## Next Steps

- Monitor production parsing results
- Add more test samples if edge cases discovered
- Consider tuning size limits if legitimate long titles/values encountered
```

**Step 6: Commit**

```bash
git add docs/plans/2025-10-25-parser-overhaul-results.md
git commit -m "docs: document Apple parser overhaul results

- Comprehensive metrics on test coverage and parsing accuracy
- Architecture summary of new format-specific parsers
- Zero wildcard selectors remaining
- Production parsing validation complete"
```

---

## Execution Instructions

**This plan should be executed using the `superpowers:executing-plans` skill.**

The plan is designed for task-by-task execution with reviews between tasks.

**Estimated Time:**
- Task 1 (Selector utilities): 20 minutes
- Task 2 (Parameterized tests): 30 minutes
- Task 3 (Format renaming): 15 minutes
- Task 4 (Table format parser): 45 minutes
- Task 5 (Modern format parser): 45 minutes
- Task 6 (Remove dead code): 20 minutes
- Task 7 (More test samples): 30 minutes
- Task 8 (Update fixtures): 20 minutes
- Task 9 (Verify and document): 15 minutes

**Total: ~4 hours**

**Critical Success Criteria:**
1. ☐ No wildcard selectors (`"span, div, td"`) remain in codebase
2. ☐ All selectors have size validation (ValueError on oversized captures)
3. ☐ Parameterized tests cover both formats with real production HTML
4. ☐ Tests report ALL failures, not just first failure
5. ☐ Production parsing shows >80% valid receipt rate (have date and total)
6. ☐ Test coverage >90% for parser.py
7. ☐ Zero dead code remaining (all methods covered by tests)
8. ☐ Format names are descriptive (`table_format`, `modern_format`)
