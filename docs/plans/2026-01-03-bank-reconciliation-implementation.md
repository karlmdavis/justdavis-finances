# Bank Account Reconciliation System - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement bank account reconciliation system to detect and import missing transactions from bank exports.

**Architecture:** Three-node flow (retrieve → parse → reconcile) with format handler plugins, domain models (Money/FinancialDate primitives), and unified YNAB operations output.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, csv, regex (OFX/QIF parsing), difflib (fuzzy matching)

---

## Task 1: Package Structure and Base Models

**Files:**
- Create: `src/finances/bank_accounts/__init__.py`
- Create: `src/finances/bank_accounts/models.py`
- Create: `tests/unit/test_bank_accounts/__init__.py`
- Create: `tests/unit/test_bank_accounts/test_models.py`

**Step 1: Write failing tests for BankTransaction model**

```python
# tests/unit/test_bank_accounts/test_models.py

from finances.bank_accounts.models import BankTransaction
from finances.core import Money, FinancialDate


def test_bank_transaction_creation_required_fields():
    """Test creating BankTransaction with only required fields."""
    tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363)
    )

    assert tx.posted_date == FinancialDate.from_string("2024-12-15")
    assert tx.description == "SAFEWAY 1616"
    assert tx.amount == Money.from_cents(-1363)
    assert tx.merchant is None
    assert tx.transaction_date is None


def test_bank_transaction_immutability():
    """Test that BankTransaction is immutable."""
    tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363)
    )

    with pytest.raises(FrozenInstanceError):
        tx.amount = Money.from_cents(-5000)


def test_bank_transaction_to_dict():
    """Test serialization to dict."""
    tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363),
        merchant="Safeway"
    )

    result = tx.to_dict()

    assert result["posted_date"] == "2024-12-15"
    assert result["description"] == "SAFEWAY 1616"
    assert result["amount_milliunits"] == -13630
    assert result["merchant"] == "Safeway"


def test_bank_transaction_from_dict():
    """Test deserialization from dict."""
    data = {
        "posted_date": "2024-12-15",
        "description": "SAFEWAY 1616",
        "amount_milliunits": -13630,
        "merchant": "Safeway"
    }

    tx = BankTransaction.from_dict(data)

    assert tx.posted_date == FinancialDate.from_string("2024-12-15")
    assert tx.description == "SAFEWAY 1616"
    assert tx.amount == Money.from_cents(-1363)
    assert tx.merchant == "Safeway"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_models.py::test_bank_transaction_creation_required_fields -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'finances.bank_accounts'"

**Step 3: Implement BankTransaction model**

```python
# src/finances/bank_accounts/__init__.py

"""Bank account reconciliation package."""

# src/finances/bank_accounts/models.py

from dataclasses import dataclass
from finances.core import Money, FinancialDate


@dataclass(frozen=True)
class BankTransaction:
    """Immutable bank transaction from normalized format."""

    # Required fields
    posted_date: FinancialDate
    description: str
    amount: Money  # Negative for expenses, positive for income

    # Optional fields (account-specific)
    transaction_date: FinancialDate | None = None
    merchant: str | None = None
    type: str | None = None
    category: str | None = None
    memo: str | None = None
    purchased_by: str | None = None
    running_balance: Money | None = None
    cleared_status: str | None = None
    check_number: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        result = {
            "posted_date": str(self.posted_date),
            "description": self.description,
            "amount_milliunits": self.amount.to_milliunits(),
        }

        # Add optional fields if present
        if self.transaction_date is not None:
            result["transaction_date"] = str(self.transaction_date)
        if self.merchant is not None:
            result["merchant"] = self.merchant
        if self.type is not None:
            result["type"] = self.type
        if self.category is not None:
            result["category"] = self.category
        if self.memo is not None:
            result["memo"] = self.memo
        if self.purchased_by is not None:
            result["purchased_by"] = self.purchased_by
        if self.running_balance is not None:
            result["running_balance_milliunits"] = self.running_balance.to_milliunits()
        if self.cleared_status is not None:
            result["cleared_status"] = self.cleared_status
        if self.check_number is not None:
            result["check_number"] = self.check_number

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BankTransaction":
        """Deserialize from normalized format dict."""
        return cls(
            posted_date=FinancialDate.from_string(data["posted_date"]),
            description=data["description"],
            amount=Money.from_milliunits(data["amount_milliunits"]),
            transaction_date=FinancialDate.from_string(data["transaction_date"])
                if "transaction_date" in data else None,
            merchant=data.get("merchant"),
            type=data.get("type"),
            category=data.get("category"),
            memo=data.get("memo"),
            purchased_by=data.get("purchased_by"),
            running_balance=Money.from_milliunits(data["running_balance_milliunits"])
                if "running_balance_milliunits" in data else None,
            cleared_status=data.get("cleared_status"),
            check_number=data.get("check_number"),
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_models.py -v`

Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add src/finances/bank_accounts/ tests/unit/test_bank_accounts/
git commit -m "feat(bank): add BankTransaction domain model

- Immutable dataclass with Money/FinancialDate primitives
- Required fields: posted_date, description, amount
- Optional fields for account-specific data
- to_dict/from_dict for JSON serialization
- Comprehensive unit tests for creation, immutability, serialization"
```

---

## Task 2: BalancePoint and BalanceReconciliation Models

**Files:**
- Modify: `src/finances/bank_accounts/models.py`
- Modify: `tests/unit/test_bank_accounts/test_models.py`

**Step 1: Write failing tests for BalancePoint**

```python
# tests/unit/test_bank_accounts/test_models.py (add to existing file)

from finances.bank_accounts.models import BalancePoint


def test_balance_point_creation():
    """Test creating BalancePoint with required fields."""
    balance = BalancePoint(
        date=FinancialDate.from_string("2024-12-31"),
        amount=Money.from_cents(-18283090)
    )

    assert balance.date == FinancialDate.from_string("2024-12-31")
    assert balance.amount == Money.from_cents(-18283090)
    assert balance.available is None


def test_balance_point_with_available():
    """Test BalancePoint with available balance (credit accounts)."""
    balance = BalancePoint(
        date=FinancialDate.from_string("2024-12-31"),
        amount=Money.from_cents(-18283090),
        available=Money.from_cents(21716910)
    )

    assert balance.available == Money.from_cents(21716910)


def test_balance_point_serialization():
    """Test to_dict and from_dict."""
    balance = BalancePoint(
        date=FinancialDate.from_string("2024-12-31"),
        amount=Money.from_cents(-18283090),
        available=Money.from_cents(21716910)
    )

    data = balance.to_dict()
    assert data["date"] == "2024-12-31"
    assert data["amount_milliunits"] == -182830900
    assert data["available_milliunits"] == 217169100

    restored = BalancePoint.from_dict(data)
    assert restored == balance
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_models.py::test_balance_point_creation -v`

Expected: FAIL with "ImportError: cannot import name 'BalancePoint'"

**Step 3: Implement BalancePoint model**

```python
# src/finances/bank_accounts/models.py (add to existing file)

@dataclass(frozen=True)
class BalancePoint:
    """Immutable balance snapshot from bank data."""

    date: FinancialDate
    amount: Money  # Ledger balance
    available: Money | None = None  # Available balance (credit accounts)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        result = {
            "date": str(self.date),
            "amount_milliunits": self.amount.to_milliunits(),
        }

        if self.available is not None:
            result["available_milliunits"] = self.available.to_milliunits()

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BalancePoint":
        """Deserialize from normalized format dict."""
        return cls(
            date=FinancialDate.from_string(data["date"]),
            amount=Money.from_milliunits(data["amount_milliunits"]),
            available=Money.from_milliunits(data["available_milliunits"])
                if "available_milliunits" in data else None,
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_models.py::test_balance_point -k balance_point -v`

Expected: PASS (all 3 balance_point tests)

**Step 5: Write failing tests for BalanceReconciliationPoint**

```python
# tests/unit/test_bank_accounts/test_models.py (add to existing file)

from finances.bank_accounts.models import BalanceReconciliationPoint


def test_balance_reconciliation_point_reconciled():
    """Test BalanceReconciliationPoint when balances match."""
    point = BalanceReconciliationPoint(
        date=FinancialDate.from_string("2024-11-30"),
        bank_balance=Money.from_cents(-1523456),
        ynab_balance=Money.from_cents(-1523456),
        bank_txs_not_in_ynab=Money.from_cents(0),
        ynab_txs_not_in_bank=Money.from_cents(0),
        adjusted_bank_balance=Money.from_cents(-1523456),
        adjusted_ynab_balance=Money.from_cents(-1523456),
        is_reconciled=True,
        difference=Money.from_cents(0)
    )

    assert point.is_reconciled is True
    assert point.difference == Money.from_cents(0)


def test_balance_reconciliation_point_diverged():
    """Test BalanceReconciliationPoint when balances differ."""
    point = BalanceReconciliationPoint(
        date=FinancialDate.from_string("2024-12-31"),
        bank_balance=Money.from_cents(-1828309),
        ynab_balance=Money.from_cents(-1814606),
        bank_txs_not_in_ynab=Money.from_cents(-13703),
        ynab_txs_not_in_bank=Money.from_cents(0),
        adjusted_bank_balance=Money.from_cents(-1814606),
        adjusted_ynab_balance=Money.from_cents(-1814606),
        is_reconciled=True,
        difference=Money.from_cents(0)
    )

    # Even though raw balances differ, adjusted balances match
    assert point.is_reconciled is True
```

**Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_models.py::test_balance_reconciliation_point_reconciled -v`

Expected: FAIL with "ImportError: cannot import name 'BalanceReconciliationPoint'"

**Step 7: Implement BalanceReconciliationPoint**

```python
# src/finances/bank_accounts/models.py (add to existing file)

@dataclass(frozen=True)
class BalanceReconciliationPoint:
    """Balance reconciliation at a single date."""

    date: FinancialDate
    bank_balance: Money
    ynab_balance: Money
    bank_txs_not_in_ynab: Money  # Sum of unmatched bank transactions
    ynab_txs_not_in_bank: Money  # Sum of unmatched YNAB transactions
    adjusted_bank_balance: Money
    adjusted_ynab_balance: Money
    is_reconciled: bool  # True if adjusted balances match exactly
    difference: Money  # adjusted_bank - adjusted_ynab

    def to_dict(self) -> dict:
        """Serialize for output."""
        return {
            "date": str(self.date),
            "bank_balance": self.bank_balance.to_milliunits(),
            "ynab_balance": self.ynab_balance.to_milliunits(),
            "bank_txs_not_in_ynab": self.bank_txs_not_in_ynab.to_milliunits(),
            "ynab_txs_not_in_bank": self.ynab_txs_not_in_bank.to_milliunits(),
            "adjusted_bank_balance": self.adjusted_bank_balance.to_milliunits(),
            "adjusted_ynab_balance": self.adjusted_ynab_balance.to_milliunits(),
            "is_reconciled": self.is_reconciled,
            "difference": self.difference.to_milliunits(),
        }
```

**Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_models.py -k reconciliation_point -v`

Expected: PASS (all reconciliation_point tests)

**Step 9: Commit**

```bash
git add src/finances/bank_accounts/models.py tests/unit/test_bank_accounts/test_models.py
git commit -m "feat(bank): add BalancePoint and BalanceReconciliationPoint models

- BalancePoint: immutable balance snapshot with optional available balance
- BalanceReconciliationPoint: reconciliation state at single date
- Both use Money/FinancialDate primitives
- Comprehensive unit tests for creation and serialization"
```

---

## Task 3: Format Handler Base and Registry

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/__init__.py`
- Create: `src/finances/bank_accounts/format_handlers/base.py`
- Create: `src/finances/bank_accounts/format_handlers/registry.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/__init__.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_registry.py`

**Step 1: Write failing test for handler registry**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_registry.py

import pytest
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from pathlib import Path


class MockHandler(BankExportFormatHandler):
    """Mock handler for testing."""

    @property
    def format_name(self) -> str:
        return "mock_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path):
        pass


def test_register_handler():
    """Test registering a format handler."""
    registry = FormatHandlerRegistry()
    registry.register(MockHandler)

    assert "mock_csv" in registry.list_formats()


def test_get_handler():
    """Test retrieving a registered handler."""
    registry = FormatHandlerRegistry()
    registry.register(MockHandler)

    handler = registry.get("mock_csv")
    assert isinstance(handler, MockHandler)


def test_get_unknown_handler_raises():
    """Test that getting unknown handler raises KeyError."""
    registry = FormatHandlerRegistry()

    with pytest.raises(KeyError, match="Unknown format handler: unknown"):
        registry.get("unknown")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_registry.py::test_register_handler -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'finances.bank_accounts.format_handlers'"

**Step 3: Implement format handler base class**

```python
# src/finances/bank_accounts/format_handlers/__init__.py

"""Format handlers for parsing bank export files."""

# src/finances/bank_accounts/format_handlers/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass
from finances.bank_accounts.models import BankTransaction, BalancePoint
from finances.core import FinancialDate


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing a bank export file."""

    transactions: tuple[BankTransaction, ...]  # Immutable sequence
    balance_points: tuple[BalancePoint, ...]  # Immutable sequence
    statement_date: FinancialDate | None = None  # For statement-based exports (OFX/QIF)

    @classmethod
    def create(
        cls,
        transactions: list[BankTransaction],
        balance_points: list[BalancePoint] | None = None,
        statement_date: FinancialDate | None = None
    ) -> "ParseResult":
        """Create ParseResult from lists (converts to immutable tuples)."""
        return cls(
            transactions=tuple(transactions),
            balance_points=tuple(balance_points or []),
            statement_date=statement_date
        )


class BankExportFormatHandler(ABC):
    """Base class for all bank export format parsers."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Unique identifier for this format (e.g., 'apple_card_csv')."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this handler can process (e.g., ('.csv',))."""
        pass

    @abstractmethod
    def validate_file(self, file_path: Path) -> bool:
        """
        Quick validation that file matches expected format.

        Check:
        - File extension
        - Header structure (for CSV)
        - Root elements (for XML/OFX)
        - Required fields present
        """
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse bank export file and return transactions and balance data.

        Responsibilities:
        1. Read format-specific file structure
        2. Normalize signs to accounting standard:
           - Expenses (purchases, debits) → NEGATIVE
           - Income (payments, credits) → POSITIVE
        3. Extract all available fields
        4. Extract balance data if available
        5. Return immutable ParseResult

        Raises:
            ValueError: If file is malformed or missing required fields
        """
        pass
```

**Step 4: Implement registry**

```python
# src/finances/bank_accounts/format_handlers/registry.py

from typing import Type
from .base import BankExportFormatHandler


class FormatHandlerRegistry:
    """Central registry for all bank export format handlers."""

    def __init__(self):
        self._handlers: dict[str, Type[BankExportFormatHandler]] = {}

    def register(self, handler_class: Type[BankExportFormatHandler]) -> None:
        """Register a format handler."""
        # Instantiate to get format_name
        instance = handler_class()
        self._handlers[instance.format_name] = handler_class

    def get(self, format_name: str) -> BankExportFormatHandler:
        """Get handler instance by format name."""
        if format_name not in self._handlers:
            raise KeyError(f"Unknown format handler: {format_name}")

        handler_class = self._handlers[format_name]
        return handler_class()

    def list_formats(self) -> list[str]:
        """List all registered format names."""
        return list(self._handlers.keys())
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_registry.py -v`

Expected: PASS (all 3 tests)

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/ tests/unit/test_bank_accounts/test_format_handlers/
git commit -m "feat(bank): add format handler architecture

- BankExportFormatHandler abstract base class
- ParseResult model for handler output
- FormatHandlerRegistry for plugin-style handler management
- Unit tests for registry registration and retrieval"
```

---

## Task 4: Apple Card CSV Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/apple_card_csv.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_csv.py`
- Create: `tests/fixtures/bank_accounts/raw/apple_card_sample.csv`

**Step 1: Create synthetic test fixture**

```csv
# tests/fixtures/bank_accounts/raw/apple_card_sample.csv

Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
12/30/2024,12/31/2024,"AMAZON MKTPL*ZP5WJ4KK2","Amazon Mktpl*zp5wj4kk2","Other","Purchase","94.52","Karl Davis"
12/29/2024,12/30/2024,"SAFEWAY 1616 444 WMC DRIVE","Safeway","Grocery","Purchase","42.99","Erica Davis"
12/28/2024,12/29/2024,"PAYMENT - THANK YOU","Apple Card","Payment","Payment","-150.00","Karl Davis"
```

**Step 2: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_csv.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.apple_card_csv import AppleCardCsvHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Apple Card CSV file."""
    csv_content = """Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
12/30/2024,12/31/2024,"AMAZON MKTPL*ZP5WJ4KK2","Amazon Mktpl*zp5wj4kk2","Other","Purchase","94.52","Karl Davis"
12/29/2024,12/30/2024,"SAFEWAY 1616 444 WMC DRIVE","Safeway","Grocery","Purchase","42.99","Erica Davis"
12/28/2024,12/29/2024,"PAYMENT - THANK YOU","Apple Card","Payment","Payment","-150.00","Karl Davis"
"""

    csv_file = tmp_path / "apple_card_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleCardCsvHandler()

    assert handler.format_name == "apple_card_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Apple Card CSV transactions."""
    handler = AppleCardCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (purchase - should be negative)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.transaction_date == FinancialDate.from_string("2024-12-30")
    assert tx1.description == "AMAZON MKTPL*ZP5WJ4KK2"
    assert tx1.merchant == "Amazon Mktpl*zp5wj4kk2"
    assert tx1.amount == Money.from_cents(-9452)  # Flipped sign
    assert tx1.type == "Purchase"
    assert tx1.category == "Other"
    assert tx1.purchased_by == "Karl Davis"

    # Third transaction (payment - should be positive)
    tx3 = result.transactions[2]
    assert tx3.amount == Money.from_cents(15000)  # Flipped sign


def test_parse_no_balances(sample_csv):
    """Test that CSV parsing returns no balance data."""
    handler = AppleCardCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.balance_points) == 0
    assert result.statement_date is None


def test_validate_file_success(sample_csv):
    """Test validating a correct Apple Card CSV file."""
    handler = AppleCardCsvHandler()

    assert handler.validate_file(sample_csv) is True


def test_validate_file_wrong_extension(tmp_path):
    """Test validation fails for wrong file extension."""
    handler = AppleCardCsvHandler()
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("test")

    assert handler.validate_file(txt_file) is False


def test_parse_invalid_amount_fails(tmp_path):
    """Test parsing fails with invalid amount format."""
    csv_content = """Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
12/30/2024,12/31/2024,"TEST","Test","Other","Purchase","---","Karl Davis"
"""

    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content)

    handler = AppleCardCsvHandler()

    with pytest.raises(ValueError, match="Invalid amount format"):
        handler.parse(csv_file)
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_csv.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'finances.bank_accounts.format_handlers.apple_card_csv'"

**Step 4: Implement Apple Card CSV handler**

```python
# src/finances/bank_accounts/format_handlers/apple_card_csv.py

import csv
from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import Money, FinancialDate


class AppleCardCsvHandler(BankExportFormatHandler):
    """
    Apple Card CSV format handler.

    Sign Convention: Consumer perspective (purchases positive, payments negative)
    Normalization: Flip all signs (consumer → accounting)
    Balance Data: None (CSV doesn't include balance)
    """

    EXPECTED_HEADERS = [
        "Transaction Date", "Clearing Date", "Description", "Merchant",
        "Category", "Type", "Amount (USD)", "Purchased By"
    ]

    @property
    def format_name(self) -> str:
        return "apple_card_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is an Apple Card CSV."""
        if file_path.suffix.lower() != ".csv":
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                return headers == self.EXPECTED_HEADERS
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Card CSV file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Apple Card CSV file: {file_path}")

        transactions = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Parse amount and flip sign (consumer → accounting)
                    amount_str = row["Amount (USD)"].strip()
                    if not amount_str or amount_str == "---":
                        raise ValueError(f"Invalid amount format at line {row_num}: '{amount_str}'")

                    amount_decimal = Decimal(amount_str)
                    # Flip sign: consumer perspective → accounting standard
                    amount_cents = int(amount_decimal * -100)

                    tx = BankTransaction(
                        posted_date=self._parse_date(row["Clearing Date"]),
                        transaction_date=self._parse_date(row["Transaction Date"]),
                        description=row["Description"],
                        merchant=row["Merchant"],
                        amount=Money.from_cents(amount_cents),
                        type=row["Type"],
                        category=row["Category"],
                        purchased_by=row["Purchased By"]
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}")

        return ParseResult.create(transactions=transactions)

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        # Apple Card CSV uses MM/DD/YYYY format
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_csv.py -v`

Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/apple_card_csv.py tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_csv.py tests/fixtures/bank_accounts/
git commit -m "feat(bank): add Apple Card CSV format handler

- Parses Apple Card CSV export format
- Normalizes consumer perspective to accounting standard (flip signs)
- Extracts merchant, category, purchased_by fields
- No balance data (CSV doesn't include it)
- Comprehensive unit tests with synthetic fixture"
```

---

## Task 5: Apple Card OFX Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/apple_card_ofx.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_ofx.py`
- Create: `tests/fixtures/bank_accounts/raw/apple_card_sample.ofx`

**Step 1: Create synthetic OFX fixture**

```ofx
# tests/fixtures/bank_accounts/raw/apple_card_sample.ofx

<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0</CODE>
<SEVERITY>INFO</SEVERITY>
</STATUS>
<DTSERVER>20241231120000</DTSERVER>
</SONRS>
</SIGNONMSGSRSV1>
<CREDITCARDMSGSRSV1>
<CCSTMTTRNRS>
<TRNUID>1</TRNUID>
<STATUS>
<CODE>0</CODE>
<SEVERITY>INFO</SEVERITY>
</STATUS>
<CCSTMTRS>
<CURDEF>USD</CURDEF>
<CCACCTFROM>
<ACCTID>1234567890</ACCTID>
</CCACCTFROM>
<BANKTRANLIST>
<DTSTART>20241201000000</DTSTART>
<DTEND>20241231235959</DTEND>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20241231</DTPOSTED>
<TRNAMT>-94.52</TRNAMT>
<FITID>20241231-1</FITID>
<NAME>AMAZON MKTPL*ZP5WJ4KK2</NAME>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20241230</DTPOSTED>
<TRNAMT>-42.99</TRNAMT>
<FITID>20241230-1</FITID>
<NAME>SAFEWAY 1616</NAME>
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20241229</DTPOSTED>
<TRNAMT>150.00</TRNAMT>
<FITID>20241229-1</FITID>
<NAME>PAYMENT - THANK YOU</NAME>
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>-182830.90</BALAMT>
<DTASOF>20241231</DTASOF>
</LEDGERBAL>
<AVAILBAL>
<BALAMT>217169.10</BALAMT>
<DTASOF>20241231</DTASOF>
</AVAILBAL>
</CCSTMTRS>
</CCSTMTTRNRS>
</CREDITCARDMSGSRSV1>
</OFX>
```

**Step 2: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_ofx.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.apple_card_ofx import AppleCardOfxHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_ofx(tmp_path):
    """Create a temporary Apple Card OFX file."""
    ofx_content = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<OFX>
<CREDITCARDMSGSRSV1>
<CCSTMTTRNRS>
<CCSTMTRS>
<CURDEF>USD</CURDEF>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20241231</DTPOSTED>
<TRNAMT>-94.52</TRNAMT>
<FITID>20241231-1</FITID>
<NAME>AMAZON MKTPL*ZP5WJ4KK2</NAME>
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20241229</DTPOSTED>
<TRNAMT>150.00</TRNAMT>
<FITID>20241229-1</FITID>
<NAME>PAYMENT - THANK YOU</NAME>
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>-182830.90</BALAMT>
<DTASOF>20241231</DTASOF>
</LEDGERBAL>
<AVAILBAL>
<BALAMT>217169.10</BALAMT>
<DTASOF>20241231</DTASOF>
</AVAILBAL>
</CCSTMTRS>
</CCSTMTTRNRS>
</CREDITCARDMSGSRSV1>
</OFX>
"""

    ofx_file = tmp_path / "apple_card_sample.ofx"
    ofx_file.write_text(ofx_content)
    return ofx_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleCardOfxHandler()

    assert handler.format_name == "apple_card_ofx"
    assert handler.supported_extensions == (".ofx",)


def test_parse_transactions(sample_ofx):
    """Test parsing OFX transactions."""
    handler = AppleCardOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.transactions) == 2

    # First transaction (debit - already negative in OFX)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.description == "AMAZON MKTPL*ZP5WJ4KK2"
    assert tx1.amount == Money.from_cents(-9452)  # Use as-is (already accounting standard)

    # Second transaction (credit - positive in OFX)
    tx2 = result.transactions[1]
    assert tx2.posted_date == FinancialDate.from_string("2024-12-29")
    assert tx2.amount == Money.from_cents(15000)  # Use as-is


def test_parse_balance(sample_ofx):
    """Test parsing balance data from OFX."""
    handler = AppleCardOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.balance_points) == 1

    balance = result.balance_points[0]
    assert balance.date == FinancialDate.from_string("2024-12-31")
    assert balance.amount == Money.from_cents(-18283090)
    assert balance.available == Money.from_cents(21716910)


def test_parse_statement_date(sample_ofx):
    """Test extracting statement date from OFX."""
    handler = AppleCardOfxHandler()
    result = handler.parse(sample_ofx)

    # Statement date should be the balance date
    assert result.statement_date == FinancialDate.from_string("2024-12-31")
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_ofx.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement OFX handler**

```python
# src/finances/bank_accounts/format_handlers/apple_card_ofx.py

import re
from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction, BalancePoint
from finances.core import Money, FinancialDate


class AppleCardOfxHandler(BankExportFormatHandler):
    """
    Apple Card OFX format handler.

    Sign Convention: Accounting standard (purchases negative, balance negative)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Statement balance from LEDGERBAL tag
    """

    @property
    def format_name(self) -> str:
        return "apple_card_ofx"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is an OFX file."""
        if file_path.suffix.lower() != ".ofx":
            return False

        try:
            content = file_path.read_text(encoding='utf-8')
            return '<OFX>' in content and '<STMTTRN>' in content
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Card OFX file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Apple Card OFX file: {file_path}")

        content = file_path.read_text(encoding='utf-8')

        transactions = self._parse_transactions(content)
        balance_points = self._parse_balances(content)
        statement_date = balance_points[0].date if balance_points else None

        return ParseResult.create(
            transactions=transactions,
            balance_points=balance_points,
            statement_date=statement_date
        )

    def _parse_transactions(self, content: str) -> list[BankTransaction]:
        """Extract transactions from OFX content."""
        transactions = []

        # Find all STMTTRN blocks
        stmttrn_pattern = r'<STMTTRN>(.*?)</STMTTRN>'
        for match in re.finditer(stmttrn_pattern, content, re.DOTALL):
            trn_block = match.group(1)

            # Extract fields
            posted_date = self._extract_tag(trn_block, 'DTPOSTED')
            amount = self._extract_tag(trn_block, 'TRNAMT')
            name = self._extract_tag(trn_block, 'NAME')

            if not all([posted_date, amount, name]):
                raise ValueError("Missing required transaction fields in OFX")

            # Parse amount (already accounting standard - use as-is)
            amount_decimal = Decimal(amount)
            amount_cents = int(amount_decimal * 100)

            tx = BankTransaction(
                posted_date=self._parse_ofx_date(posted_date),
                description=name,
                amount=Money.from_cents(amount_cents)
            )

            transactions.append(tx)

        return transactions

    def _parse_balances(self, content: str) -> list[BalancePoint]:
        """Extract balance from OFX content."""
        # Extract LEDGERBAL
        ledger_bal = self._extract_tag(content, 'BALAMT', parent='LEDGERBAL')
        ledger_date = self._extract_tag(content, 'DTASOF', parent='LEDGERBAL')

        if not ledger_bal or not ledger_date:
            return []  # No balance data

        # Extract AVAILBAL (optional)
        avail_bal = self._extract_tag(content, 'BALAMT', parent='AVAILBAL')

        # Parse amounts
        ledger_decimal = Decimal(ledger_bal)
        ledger_cents = int(ledger_decimal * 100)

        available = None
        if avail_bal:
            avail_decimal = Decimal(avail_bal)
            available = Money.from_cents(int(avail_decimal * 100))

        balance = BalancePoint(
            date=self._parse_ofx_date(ledger_date),
            amount=Money.from_cents(ledger_cents),
            available=available
        )

        return [balance]

    def _extract_tag(self, content: str, tag: str, parent: str = None) -> str | None:
        """Extract value from OFX tag."""
        if parent:
            # Find parent block first
            parent_pattern = f'<{parent}>(.*?)</{parent}>'
            parent_match = re.search(parent_pattern, content, re.DOTALL)
            if not parent_match:
                return None
            content = parent_match.group(1)

        # Extract tag value
        pattern = f'<{tag}>(.*?)<'
        match = re.search(pattern, content)
        return match.group(1).strip() if match else None

    def _parse_ofx_date(self, date_str: str) -> FinancialDate:
        """Parse OFX date format (YYYYMMDD)."""
        # OFX date format: YYYYMMDD (may have timestamp suffix)
        date_part = date_str[:8]  # Take first 8 characters
        year = date_part[:4]
        month = date_part[4:6]
        day = date_part[6:8]
        return FinancialDate.from_string(f"{year}-{month}-{day}")
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_ofx.py -v`

Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/apple_card_ofx.py tests/unit/test_bank_accounts/test_format_handlers/test_apple_card_ofx.py tests/fixtures/bank_accounts/raw/
git commit -m "feat(bank): add Apple Card OFX format handler

- Parses OFX SGML format with regex-based extraction
- Amounts already in accounting standard (use as-is)
- Extracts LEDGERBAL and AVAILBAL for statement balance
- Statement date from balance DTASOF field
- Comprehensive unit tests with synthetic OFX fixture"
```

---

## Task 6: Chase Checking CSV Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/chase_checking_csv.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_chase_checking_csv.py`
- Create: `tests/fixtures/bank_accounts/raw/chase_checking_sample.csv`

**Step 1: Create synthetic Chase checking CSV fixture**

```csv
# tests/fixtures/bank_accounts/raw/chase_checking_sample.csv

Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,12/24/2024,"PROTECTIVE LIFE INS. PREM...",-103.83,ACH_DEBIT,40559.83,
CREDIT,12/23/2024,"PAYCHECK DEPOSIT",2500.00,ACH_CREDIT,40663.66,
DEBIT,12/22/2024,"SAFEWAY 1616",-42.99,DEBIT,38163.66,
```

**Step 2: Write failing tests** (similar pattern as Apple handlers)

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_chase_checking_csv.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.chase_checking_csv import ChaseCheckingCsvHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Chase checking CSV file."""
    csv_content = """Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,12/24/2024,"PROTECTIVE LIFE INS. PREM...",-103.83,ACH_DEBIT,40559.83,
CREDIT,12/23/2024,"PAYCHECK DEPOSIT",2500.00,ACH_CREDIT,40663.66,
DEBIT,12/22/2024,"SAFEWAY 1616",-42.99,DEBIT,38163.66,
"""

    csv_file = tmp_path / "chase_checking_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = ChaseCheckingCsvHandler()

    assert handler.format_name == "chase_checking_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Chase checking CSV transactions."""
    handler = ChaseCheckingCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (debit - negative)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-24")
    assert tx1.description == "PROTECTIVE LIFE INS. PREM..."
    assert tx1.amount == Money.from_cents(-10383)  # Already accounting standard
    assert tx1.type == "ACH_DEBIT"
    assert tx1.running_balance == Money.from_cents(4055983)

    # Second transaction (credit - positive)
    tx2 = result.transactions[1]
    assert tx2.amount == Money.from_cents(250000)
    assert tx2.type == "ACH_CREDIT"


def test_parse_running_balances(sample_csv):
    """Test parsing running balance data."""
    handler = ChaseCheckingCsvHandler()
    result = handler.parse(sample_csv)

    # Should have balance points from running balance column
    assert len(result.balance_points) == 3

    balance1 = result.balance_points[0]
    assert balance1.date == FinancialDate.from_string("2024-12-24")
    assert balance1.amount == Money.from_cents(4055983)
    assert balance1.available is None  # Checking accounts don't have available balance
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_chase_checking_csv.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement Chase checking CSV handler**

```python
# src/finances/bank_accounts/format_handlers/chase_checking_csv.py

import csv
from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction, BalancePoint
from finances.core import Money, FinancialDate


class ChaseCheckingCsvHandler(BankExportFormatHandler):
    """
    Chase Checking CSV format handler.

    Sign Convention: Accounting standard (debits negative, credits positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Running balance column (balance after each transaction)
    """

    EXPECTED_HEADERS = [
        "Details", "Posting Date", "Description", "Amount", "Type", "Balance", "Check or Slip #"
    ]

    @property
    def format_name(self) -> str:
        return "chase_checking_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is a Chase checking CSV."""
        if file_path.suffix.lower() != ".csv":
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                return headers == self.EXPECTED_HEADERS
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase checking CSV file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Chase checking CSV file: {file_path}")

        transactions = []
        balance_points = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Parse amount (already accounting standard - use as-is)
                    amount_str = row["Amount"].strip()
                    if not amount_str:
                        raise ValueError(f"Missing amount at line {row_num}")

                    amount_decimal = Decimal(amount_str)
                    amount_cents = int(amount_decimal * 100)

                    # Parse balance
                    balance_str = row["Balance"].strip()
                    balance_cents = None
                    if balance_str:
                        balance_decimal = Decimal(balance_str)
                        balance_cents = int(balance_decimal * 100)

                    # Parse date
                    posted_date = self._parse_date(row["Posting Date"])

                    tx = BankTransaction(
                        posted_date=posted_date,
                        description=row["Description"],
                        amount=Money.from_cents(amount_cents),
                        type=row["Type"],
                        running_balance=Money.from_cents(balance_cents) if balance_cents else None,
                        check_number=row["Check or Slip #"] if row["Check or Slip #"] else None
                    )

                    transactions.append(tx)

                    # Create balance point from running balance
                    if balance_cents is not None:
                        balance = BalancePoint(
                            date=posted_date,
                            amount=Money.from_cents(balance_cents)
                        )
                        balance_points.append(balance)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}")

        return ParseResult.create(
            transactions=transactions,
            balance_points=balance_points
        )

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_chase_checking_csv.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/chase_checking_csv.py tests/unit/test_bank_accounts/test_format_handlers/test_chase_checking_csv.py tests/fixtures/bank_accounts/raw/
git commit -m "feat(bank): add Chase Checking CSV format handler

- Parses Chase checking CSV export format
- Amounts already in accounting standard (use as-is)
- Extracts running balance from Balance column
- Creates balance point for each transaction
- Comprehensive unit tests with synthetic fixture"
```

---

## Task 7: Chase Credit CSV Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/chase_credit_csv.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_csv.py`
- Create: `tests/fixtures/bank_accounts/raw/chase_credit_sample.csv`

**Step 1: Create synthetic Chase credit CSV fixture**

```csv
# tests/fixtures/bank_accounts/raw/chase_credit_sample.csv

Transaction Date,Post Date,Description,Category,Type,Amount,Memo
12/26/2024,12/26/2024,COMCAST / XFINITY,Bills & Utilities,Sale,-219.53,
12/25/2024,12/25/2024,AMAZON.COM*ZE1234567,Shopping,Sale,-45.99,
12/24/2024,12/24/2024,PAYMENT - THANK YOU,Payment/Credit,Payment,500.00,
```

**Step 2: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_csv.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.chase_credit_csv import ChaseCreditCsvHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Chase credit CSV file."""
    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
12/26/2024,12/26/2024,COMCAST / XFINITY,Bills & Utilities,Sale,-219.53,
12/25/2024,12/25/2024,AMAZON.COM*ZE1234567,Shopping,Sale,-45.99,
12/24/2024,12/24/2024,PAYMENT - THANK YOU,Payment/Credit,Payment,500.00,
"""

    csv_file = tmp_path / "chase_credit_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = ChaseCreditCsvHandler()

    assert handler.format_name == "chase_credit_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Chase credit CSV transactions."""
    handler = ChaseCreditCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (sale - negative)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-26")
    assert tx1.transaction_date == FinancialDate.from_string("2024-12-26")
    assert tx1.description == "COMCAST / XFINITY"
    assert tx1.amount == Money.from_cents(-21953)  # Already accounting standard
    assert tx1.type == "Sale"
    assert tx1.category == "Bills & Utilities"

    # Third transaction (payment - positive)
    tx3 = result.transactions[2]
    assert tx3.amount == Money.from_cents(50000)
    assert tx3.type == "Payment"


def test_parse_no_balances(sample_csv):
    """Test that CSV parsing returns no balance data."""
    handler = ChaseCreditCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.balance_points) == 0
    assert result.statement_date is None
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_csv.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement Chase credit CSV handler**

```python
# src/finances/bank_accounts/format_handlers/chase_credit_csv.py

import csv
from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import Money, FinancialDate


class ChaseCreditCsvHandler(BankExportFormatHandler):
    """
    Chase Credit Card CSV format handler.

    Sign Convention: Accounting standard (purchases negative, payments positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: None (CSV doesn't include balance)
    """

    EXPECTED_HEADERS = [
        "Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"
    ]

    @property
    def format_name(self) -> str:
        return "chase_credit_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is a Chase credit CSV."""
        if file_path.suffix.lower() != ".csv":
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                return headers == self.EXPECTED_HEADERS
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase credit CSV file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Chase credit CSV file: {file_path}")

        transactions = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Parse amount (already accounting standard - use as-is)
                    amount_str = row["Amount"].strip()
                    if not amount_str:
                        raise ValueError(f"Missing amount at line {row_num}")

                    amount_decimal = Decimal(amount_str)
                    amount_cents = int(amount_decimal * 100)

                    tx = BankTransaction(
                        posted_date=self._parse_date(row["Post Date"]),
                        transaction_date=self._parse_date(row["Transaction Date"]),
                        description=row["Description"],
                        amount=Money.from_cents(amount_cents),
                        type=row["Type"],
                        category=row["Category"],
                        memo=row["Memo"] if row["Memo"] else None
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}")

        return ParseResult.create(transactions=transactions)

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_csv.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/chase_credit_csv.py tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_csv.py tests/fixtures/bank_accounts/raw/
git commit -m "feat(bank): add Chase Credit CSV format handler

- Parses Chase credit card CSV export format
- Amounts already in accounting standard (use as-is)
- No balance data (CSV doesn't include it)
- Extracts category and memo fields
- Comprehensive unit tests with synthetic fixture"
```

---

## Task 8: Chase Credit QIF Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/chase_credit_qif.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_qif.py`
- Create: `tests/fixtures/bank_accounts/raw/chase_credit_sample.qif`

**Step 1: Create synthetic QIF fixture**

```qif
# tests/fixtures/bank_accounts/raw/chase_credit_sample.qif

!Type:CCard
D12/26/2024
NN/A
PCOMCAST / XFINITY
T-219.53
^
D12/25/2024
NN/A
PAMAZON.COM*ZE1234567
T-45.99
^
D12/24/2024
NN/A
PPAYMENT - THANK YOU
T500.00
^
```

**Step 2: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_qif.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.chase_credit_qif import ChaseCreditQifHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_qif(tmp_path):
    """Create a temporary Chase credit QIF file."""
    qif_content = """!Type:CCard
D12/26/2024
NN/A
PCOMCAST / XFINITY
T-219.53
^
D12/25/2024
NN/A
PAMAZON.COM*ZE1234567
T-45.99
^
D12/24/2024
NN/A
PPAYMENT - THANK YOU
T500.00
^
"""

    qif_file = tmp_path / "chase_credit_sample.qif"
    qif_file.write_text(qif_content)
    return qif_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = ChaseCreditQifHandler()

    assert handler.format_name == "chase_credit_qif"
    assert handler.supported_extensions == (".qif",)


def test_parse_transactions(sample_qif):
    """Test parsing QIF transactions."""
    handler = ChaseCreditQifHandler()
    result = handler.parse(sample_qif)

    assert len(result.transactions) == 3

    # First transaction (sale - negative)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-26")
    assert tx1.description == "COMCAST / XFINITY"
    assert tx1.amount == Money.from_cents(-21953)  # Already accounting standard

    # Third transaction (payment - positive)
    tx3 = result.transactions[2]
    assert tx3.amount == Money.from_cents(50000)


def test_parse_no_balances(sample_qif):
    """Test that QIF parsing returns no balance data."""
    handler = ChaseCreditQifHandler()
    result = handler.parse(sample_qif)

    # QIF files don't contain balance data for Chase credit
    assert len(result.balance_points) == 0
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_qif.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement QIF handler**

```python
# src/finances/bank_accounts/format_handlers/chase_credit_qif.py

from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import Money, FinancialDate


class ChaseCreditQifHandler(BankExportFormatHandler):
    """
    Chase Credit Card QIF format handler.

    Sign Convention: Accounting standard (purchases negative, payments positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: None (QIF doesn't include balance for Chase credit)
    """

    @property
    def format_name(self) -> str:
        return "chase_credit_qif"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".qif",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is a QIF file."""
        if file_path.suffix.lower() != ".qif":
            return False

        try:
            content = file_path.read_text(encoding='utf-8')
            return content.startswith("!Type:CCard") or content.startswith("!Type:Bank")
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Chase credit QIF file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Chase credit QIF file: {file_path}")

        content = file_path.read_text(encoding='utf-8')
        transactions = self._parse_transactions(content)

        return ParseResult.create(transactions=transactions)

    def _parse_transactions(self, content: str) -> list[BankTransaction]:
        """Parse QIF transactions from content."""
        transactions = []
        current_tx = {}

        for line_num, line in enumerate(content.split('\n'), start=1):
            line = line.strip()

            if not line:
                continue

            if line.startswith('!Type:'):
                continue  # Skip header

            if line == '^':
                # End of transaction - create BankTransaction
                if current_tx:
                    try:
                        tx = self._create_transaction(current_tx)
                        transactions.append(tx)
                    except Exception as e:
                        raise ValueError(f"Failed to create transaction at line {line_num}: {e}")
                    current_tx = {}
                continue

            # Parse field
            if len(line) < 2:
                continue

            field_code = line[0]
            field_value = line[1:]

            if field_code == 'D':  # Date
                current_tx['date'] = field_value
            elif field_code == 'T':  # Amount
                current_tx['amount'] = field_value
            elif field_code == 'P':  # Payee
                current_tx['payee'] = field_value
            elif field_code == 'M':  # Memo
                current_tx['memo'] = field_value
            elif field_code == 'C':  # Cleared status
                current_tx['cleared'] = field_value

        return transactions

    def _create_transaction(self, tx_data: dict) -> BankTransaction:
        """Create BankTransaction from QIF transaction data."""
        if 'date' not in tx_data or 'amount' not in tx_data:
            raise ValueError("Missing required fields (date or amount)")

        # Parse amount (already accounting standard - use as-is)
        amount_decimal = Decimal(tx_data['amount'])
        amount_cents = int(amount_decimal * 100)

        # Parse date
        date_parts = tx_data['date'].split('/')
        month, day, year = date_parts[0], date_parts[1], date_parts[2]
        posted_date = FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")

        return BankTransaction(
            posted_date=posted_date,
            description=tx_data.get('payee', 'Unknown'),
            amount=Money.from_cents(amount_cents),
            memo=tx_data.get('memo'),
            cleared_status=tx_data.get('cleared')
        )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_qif.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/chase_credit_qif.py tests/unit/test_bank_accounts/test_format_handlers/test_chase_credit_qif.py tests/fixtures/bank_accounts/raw/
git commit -m "feat(bank): add Chase Credit QIF format handler

- Parses QIF text format with line-by-line parser
- Amounts already in accounting standard (use as-is)
- No balance data for Chase credit QIF files
- Extracts cleared status and memo fields
- Comprehensive unit tests with synthetic fixture"
```

---

## Task 9: Apple Savings CSV Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/apple_savings_csv.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_csv.py`
- Create: `tests/fixtures/bank_accounts/raw/apple_savings_sample.csv`

**Step 1: Create synthetic Apple Savings CSV fixture**

```csv
# tests/fixtures/bank_accounts/raw/apple_savings_sample.csv

Transaction Date,Clearing Date,Description,Amount (USD),Transaction Type,Balance (USD)
12/30/2024,12/31/2024,"Interest Earned","1.25","Interest",42053.56
12/29/2024,12/30/2024,"Withdrawal to Apple Card","-500.00","Transfer",42052.31
12/28/2024,12/29/2024,"Deposit from Checking","1000.00","Transfer",42552.31
```

**Step 2: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_csv.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.apple_savings_csv import AppleSavingsCsvHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Apple Savings CSV file."""
    csv_content = """Transaction Date,Clearing Date,Description,Amount (USD),Transaction Type,Balance (USD)
12/30/2024,12/31/2024,"Interest Earned","1.25","Interest",42053.56
12/29/2024,12/30/2024,"Withdrawal to Apple Card","-500.00","Transfer",42052.31
12/28/2024,12/29/2024,"Deposit from Checking","1000.00","Transfer",42552.31
"""

    csv_file = tmp_path / "apple_savings_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleSavingsCsvHandler()

    assert handler.format_name == "apple_savings_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Apple Savings CSV transactions."""
    handler = AppleSavingsCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (interest - positive, should flip to positive)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.transaction_date == FinancialDate.from_string("2024-12-30")
    assert tx1.description == "Interest Earned"
    assert tx1.amount == Money.from_cents(-125)  # Flipped sign (consumer → accounting)
    assert tx1.type == "Interest"

    # Second transaction (withdrawal - negative in CSV, should flip to positive)
    tx2 = result.transactions[1]
    assert tx2.amount == Money.from_cents(50000)  # Flipped sign

    # Third transaction (deposit - positive in CSV, should flip to negative)
    tx3 = result.transactions[2]
    assert tx3.amount == Money.from_cents(-100000)  # Flipped sign
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_csv.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement Apple Savings CSV handler**

```python
# src/finances/bank_accounts/format_handlers/apple_savings_csv.py

import csv
from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import Money, FinancialDate


class AppleSavingsCsvHandler(BankExportFormatHandler):
    """
    Apple Savings CSV format handler.

    Sign Convention: Consumer perspective (deposits positive, withdrawals negative)
    Normalization: Flip all signs (consumer → accounting)
    Balance Data: None (balance column not used - running balance unreliable)
    """

    EXPECTED_HEADERS = [
        "Transaction Date", "Clearing Date", "Description", "Amount (USD)", "Transaction Type", "Balance (USD)"
    ]

    @property
    def format_name(self) -> str:
        return "apple_savings_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is an Apple Savings CSV."""
        if file_path.suffix.lower() != ".csv":
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                return headers == self.EXPECTED_HEADERS
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Savings CSV file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Apple Savings CSV file: {file_path}")

        transactions = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Parse amount and flip sign (consumer → accounting)
                    amount_str = row["Amount (USD)"].strip()
                    if not amount_str or amount_str == "---":
                        raise ValueError(f"Invalid amount format at line {row_num}: '{amount_str}'")

                    amount_decimal = Decimal(amount_str)
                    # Flip sign: consumer perspective → accounting standard
                    amount_cents = int(amount_decimal * -100)

                    tx = BankTransaction(
                        posted_date=self._parse_date(row["Clearing Date"]),
                        transaction_date=self._parse_date(row["Transaction Date"]),
                        description=row["Description"],
                        amount=Money.from_cents(amount_cents),
                        type=row["Transaction Type"]
                    )

                    transactions.append(tx)

                except (ValueError, KeyError) as e:
                    raise ValueError(f"Parse error at line {row_num}: {e}")

        return ParseResult.create(transactions=transactions)

    def _parse_date(self, date_str: str) -> FinancialDate:
        """Parse MM/DD/YYYY format date."""
        month, day, year = date_str.split("/")
        return FinancialDate.from_string(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_csv.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/apple_savings_csv.py tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_csv.py tests/fixtures/bank_accounts/raw/
git commit -m "feat(bank): add Apple Savings CSV format handler

- Parses Apple Savings CSV export format
- Normalizes consumer perspective to accounting standard (flip signs)
- No balance data (running balance column unreliable)
- Extracts transaction type field
- Comprehensive unit tests with synthetic fixture"
```

---

## Task 10: Apple Savings OFX Handler

**Files:**
- Create: `src/finances/bank_accounts/format_handlers/apple_savings_ofx.py`
- Create: `tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_ofx.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_ofx.py

import pytest
from pathlib import Path
from finances.bank_accounts.format_handlers.apple_savings_ofx import AppleSavingsOfxHandler
from finances.core import Money, FinancialDate


@pytest.fixture
def sample_ofx(tmp_path):
    """Create a temporary Apple Savings OFX file."""
    ofx_content = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD</CURDEF>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>INT</TRNTYPE>
<DTPOSTED>20241231</DTPOSTED>
<TRNAMT>1.25</TRNAMT>
<FITID>20241231-1</FITID>
<NAME>Interest Earned</NAME>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20241230</DTPOSTED>
<TRNAMT>-500.00</TRNAMT>
<FITID>20241230-1</FITID>
<NAME>Withdrawal to Apple Card</NAME>
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>42053.56</BALAMT>
<DTASOF>20241231</DTASOF>
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

    ofx_file = tmp_path / "apple_savings_sample.ofx"
    ofx_file.write_text(ofx_content)
    return ofx_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleSavingsOfxHandler()

    assert handler.format_name == "apple_savings_ofx"
    assert handler.supported_extensions == (".ofx",)


def test_parse_transactions(sample_ofx):
    """Test parsing OFX transactions."""
    handler = AppleSavingsOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.transactions) == 2

    # First transaction (interest - positive)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.description == "Interest Earned"
    assert tx1.amount == Money.from_cents(125)  # Use as-is (already accounting standard)

    # Second transaction (withdrawal - negative)
    tx2 = result.transactions[1]
    assert tx2.amount == Money.from_cents(-50000)  # Use as-is


def test_parse_balance(sample_ofx):
    """Test parsing balance data from OFX."""
    handler = AppleSavingsOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.balance_points) == 1

    balance = result.balance_points[0]
    assert balance.date == FinancialDate.from_string("2024-12-31")
    assert balance.amount == Money.from_cents(4205356)
    assert balance.available is None  # Savings accounts don't have available balance
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_ofx.py::test_handler_properties -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement Apple Savings OFX handler**

```python
# src/finances/bank_accounts/format_handlers/apple_savings_ofx.py

import re
from pathlib import Path
from decimal import Decimal
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.models import BankTransaction, BalancePoint
from finances.core import Money, FinancialDate


class AppleSavingsOfxHandler(BankExportFormatHandler):
    """
    Apple Savings OFX format handler.

    Sign Convention: Accounting standard (withdrawals negative, deposits positive)
    Normalization: Use as-is (already accounting standard)
    Balance Data: Statement balance from LEDGERBAL tag
    """

    @property
    def format_name(self) -> str:
        return "apple_savings_ofx"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate that file is an OFX file."""
        if file_path.suffix.lower() != ".ofx":
            return False

        try:
            content = file_path.read_text(encoding='utf-8')
            return '<OFX>' in content and '<STMTTRN>' in content
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Apple Savings OFX file."""
        if not self.validate_file(file_path):
            raise ValueError(f"Invalid Apple Savings OFX file: {file_path}")

        content = file_path.read_text(encoding='utf-8')

        transactions = self._parse_transactions(content)
        balance_points = self._parse_balances(content)
        statement_date = balance_points[0].date if balance_points else None

        return ParseResult.create(
            transactions=transactions,
            balance_points=balance_points,
            statement_date=statement_date
        )

    def _parse_transactions(self, content: str) -> list[BankTransaction]:
        """Extract transactions from OFX content."""
        transactions = []

        # Find all STMTTRN blocks
        stmttrn_pattern = r'<STMTTRN>(.*?)</STMTTRN>'
        for match in re.finditer(stmttrn_pattern, content, re.DOTALL):
            trn_block = match.group(1)

            # Extract fields
            posted_date = self._extract_tag(trn_block, 'DTPOSTED')
            amount = self._extract_tag(trn_block, 'TRNAMT')
            name = self._extract_tag(trn_block, 'NAME')

            if not all([posted_date, amount, name]):
                raise ValueError("Missing required transaction fields in OFX")

            # Parse amount (already accounting standard - use as-is)
            amount_decimal = Decimal(amount)
            amount_cents = int(amount_decimal * 100)

            tx = BankTransaction(
                posted_date=self._parse_ofx_date(posted_date),
                description=name,
                amount=Money.from_cents(amount_cents)
            )

            transactions.append(tx)

        return transactions

    def _parse_balances(self, content: str) -> list[BalancePoint]:
        """Extract balance from OFX content."""
        # Extract LEDGERBAL
        ledger_bal = self._extract_tag(content, 'BALAMT', parent='LEDGERBAL')
        ledger_date = self._extract_tag(content, 'DTASOF', parent='LEDGERBAL')

        if not ledger_bal or not ledger_date:
            return []  # No balance data

        # Parse amounts
        ledger_decimal = Decimal(ledger_bal)
        ledger_cents = int(ledger_decimal * 100)

        balance = BalancePoint(
            date=self._parse_ofx_date(ledger_date),
            amount=Money.from_cents(ledger_cents)
        )

        return [balance]

    def _extract_tag(self, content: str, tag: str, parent: str = None) -> str | None:
        """Extract value from OFX tag."""
        if parent:
            # Find parent block first
            parent_pattern = f'<{parent}>(.*?)</{parent}>'
            parent_match = re.search(parent_pattern, content, re.DOTALL)
            if not parent_match:
                return None
            content = parent_match.group(1)

        # Extract tag value
        pattern = f'<{tag}>(.*?)<'
        match = re.search(pattern, content)
        return match.group(1).strip() if match else None

    def _parse_ofx_date(self, date_str: str) -> FinancialDate:
        """Parse OFX date format (YYYYMMDD)."""
        date_part = date_str[:8]  # Take first 8 characters
        year = date_part[:4]
        month = date_part[4:6]
        day = date_part[6:8]
        return FinancialDate.from_string(f"{year}-{month}-{day}")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_ofx.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/finances/bank_accounts/format_handlers/apple_savings_ofx.py tests/unit/test_bank_accounts/test_format_handlers/test_apple_savings_ofx.py
git commit -m "feat(bank): add Apple Savings OFX format handler

- Parses OFX SGML format with regex-based extraction
- Amounts already in accounting standard (use as-is)
- Extracts LEDGERBAL for statement balance
- No available balance (savings accounts)
- Comprehensive unit tests with synthetic OFX fixture"
```

---

**Continuing with remaining tasks...**
