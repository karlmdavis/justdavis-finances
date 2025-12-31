# Bank Account Reconciliation - Design Document

**Date:** 2025-12-29
**Status:** Design Phase
**Author:** Claude Code (with Karl Davis)

## Overview

This design document describes a system for reconciling bank account data with YNAB transactions.
The primary goal is to detect and import missing transactions from authoritative bank exports,
using bank data as the source of truth to identify gaps in YNAB caused by failed bank link syncs.

### Goals

1. **One-way reconciliation:** Bank exports are authoritative, YNAB data may have gaps
2. **Find missing transactions:** Identify bank transactions not present in YNAB
3. **Balance reconciliation:** Use ending balances to detect systematic gaps
4. **Unified operations format:** Consistent format across all YNAB operations (bank, Amazon, Apple)
5. **Manual review workflow:** Generate operations for user review before applying

### Non-Goals

- Automatic bank data downloads (no APIs available)
- Correcting YNAB transaction amounts/dates (bank data issues are rare)
- Real-time syncing (batch processing only)
- Bidirectional sync (YNAB → bank)

## Data Sources

### Bank Accounts

Four accounts require reconciliation:

1. **Apple Card** (credit) - Monthly statements (CSV + OFX)
2. **Apple Savings** (savings) - Monthly statements (CSV + OFX)
3. **Chase Checking (...1503)** (checking) - Daily/range exports (CSV only)
4. **Chase Credit (...9579)** (credit) - Daily/range exports (CSV + QIF)

### Export Formats

#### Apple Card CSV
```csv
Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
12/30/2024,12/31/2024,"AMAZON MKTPL*ZP5WJ4KK2...","Amazon Mktpl*zp5wj4kk2","Other","Purchase","94.52","Karl Davis"
```

#### Apple Card/Savings OFX
- SGML format with `<OFX>` structure
- Contains: `FITID` (unique ID), `TRNTYPE`, `DTPOSTED`, `TRNAMT`, `NAME`
- Balance data: `LEDGERBAL`, `AVAILBAL`, `DTASOF`

#### Chase Checking CSV
```csv
Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,12/24/2025,"PROTECTIVE LIFE INS. PREM...",-103.83,ACH_DEBIT,40559.83,
```

#### Chase Credit CSV
```csv
Transaction Date,Post Date,Description,Category,Type,Amount,Memo
12/26/2025,12/26/2025,COMCAST / XFINITY,Bills & Utilities,Sale,-219.53,
```

#### Chase Credit QIF
```
!Type:CCard
C*
D12/26/2025
NN/A
PCOMCAST / XFINITY
T-219.53
```

### Format Usage Strategy

- **CSV files:** Authoritative source for transaction data
- **OFX/QIF files:** Used ONLY for ending balance data
- **Reason:** CSV has all transaction details, OFX/QIF balance data complements it

## Architecture

### Data Flow

```
Bank Exports (CSV/OFX/QIF)
    ↓
[account_data_retrieve] - Guide user to download missing data
    ↓
[account_data_parse] - Parse to normalized JSON, de-duplicate
    ↓
[account_data_reconcile] - Match to YNAB, generate operations
    ↓
Unified Operations JSON
    ↓
[ynab_apply] - Manual review and apply
```

### Directory Structure

```
data/
└── bank_accounts/
    ├── config.json                          # Account configuration (git-ignored)
    ├── raw/                                 # User-downloaded exports
    │   ├── apple_card/
    │   │   ├── 2024-11.csv
    │   │   ├── 2024-11.ofx
    │   │   ├── 2024-12.csv
    │   │   └── 2024-12.ofx
    │   ├── apple_savings/
    │   ├── chase_checking/
    │   │   └── 2024-12-01_to_2024-12-27.csv
    │   └── chase_credit/
    │       ├── 2024-01-01_to_2024-12-31.csv
    │       └── 2024-01-01_to_2024-12-31.qif
    ├── normalized/                          # Parsed, de-duplicated data
    │   ├── apple_card.json                 # One file per account (all data)
    │   ├── apple_savings.json
    │   ├── chase_checking.json
    │   └── chase_credit.json
    └── reconciliation/                      # Generated operations
        └── 2025-12-27_20-30-45_reconciliation.json
```

## Configuration Format

### Account Configuration

**File:** `data/bank_accounts/config.json` (git-ignored, user-maintained)

```json
{
  "accounts": [
    {
      "ynab_account_id": "uuid-from-ynab-api",
      "ynab_account_name": "Apple Card",
      "slug": "apple_card",
      "bank_name": "Apple",
      "account_type": "credit",
      "statement_frequency": "monthly",
      "download_instructions": "1. Go to wallet.apple.com\n2. Click Apple Card → Statements\n3. Download CSV + OFX for {month}\n4. Place in data/bank_accounts/raw/apple_card/{YYYY-MM}.csv and {YYYY-MM}.ofx"
    },
    {
      "ynab_account_id": "uuid-from-ynab-api",
      "ynab_account_name": "Chase Checking (...1503)",
      "slug": "chase_checking",
      "bank_name": "Chase",
      "account_type": "checking",
      "statement_frequency": "daily",
      "download_instructions": "1. Go to chase.com → Transactions\n2. Select date range\n3. Download CSV\n4. Place in data/bank_accounts/raw/chase_checking/{YYYY-MM-DD}_to_{YYYY-MM-DD}.csv"
    }
  ]
}
```

### Configuration Workflow

1. **Missing config:** Node creates stub from YNAB cache, fails with instructions
2. **User edits:** Add slugs, bank info, download instructions
3. **Empty accounts array:** Valid state, nodes skip gracefully
4. **Invalid config:** Fail with validation errors

### Config Stub Generation

When `config.json` is missing, the node generates a stub from YNAB cache and fails with instructions:

**Generated stub** (`data/bank_accounts/config.json`):
```json
{
  "accounts": [
    {
      "ynab_account_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "ynab_account_name": "Apple Card",
      "slug": "TODO_REQUIRED",
      "bank_name": "TODO_REQUIRED",
      "account_type": "credit",
      "statement_frequency": "TODO_REQUIRED",
      "download_instructions": "TODO_REQUIRED"
    },
    {
      "ynab_account_id": "b2c3d4e5-6789-01bc-def0-234567890abc",
      "ynab_account_name": "Apple Savings",
      "slug": "TODO_REQUIRED",
      "bank_name": "TODO_REQUIRED",
      "account_type": "savings",
      "statement_frequency": "TODO_REQUIRED",
      "download_instructions": "TODO_REQUIRED"
    },
    {
      "ynab_account_id": "c3d4e5f6-7890-12cd-ef01-34567890abcd",
      "ynab_account_name": "Chase Checking (...1503)",
      "slug": "TODO_REQUIRED",
      "bank_name": "TODO_REQUIRED",
      "account_type": "checking",
      "statement_frequency": "TODO_REQUIRED",
      "download_instructions": "TODO_REQUIRED"
    },
    {
      "ynab_account_id": "d4e5f6a7-8901-23de-f012-4567890abcde",
      "ynab_account_name": "Chase Credit (...9579)",
      "slug": "TODO_REQUIRED",
      "bank_name": "TODO_REQUIRED",
      "account_type": "credit",
      "statement_frequency": "TODO_REQUIRED",
      "download_instructions": "TODO_REQUIRED"
    }
  ]
}
```

**Auto-filled fields** (from YNAB cache):
- `ynab_account_id` - Account UUID from YNAB API
- `ynab_account_name` - Account name from YNAB
- `account_type` - Inferred from YNAB account type (credit_card → credit, checking → checking, savings → savings)

**Manual fields** (user must complete):
- `slug` - Short identifier for directory naming (e.g., "apple_card", "chase_checking")
  - Recommendation: lowercase, underscores, descriptive
  - Used in: `data/bank_accounts/raw/{slug}/`, `normalized/{slug}.json`
- `bank_name` - Financial institution name (e.g., "Apple", "Chase")
- `statement_frequency` - Export frequency: "monthly" or "daily"
  - Use "monthly" for statement-based (Apple Card/Savings)
  - Use "daily" for transaction exports (Chase Checking/Credit)
- `download_instructions` - Step-by-step guide for downloading bank data
  - Include: URL, navigation steps, date range selection, file format
  - Template placeholders: `{month}` for monthly, `{start_date}` / `{end_date}` for daily

**Error message when stub is created:**
```
❌ account_data_retrieve failed

Configuration file not found. Created stub at:
  data/bank_accounts/config.json

Next steps:
  1. Edit config.json and replace all "TODO_REQUIRED" values
  2. Set slug (e.g., "apple_card", "chase_checking")
  3. Set bank_name (e.g., "Apple", "Chase")
  4. Set statement_frequency ("monthly" or "daily")
  5. Add download_instructions for each account
  6. Re-run this node

Flow execution aborted.
```

## Normalized Bank Account Format

**Purpose:** Consistent format across all bank sources, optimized for reconciliation

**File:** `data/bank_accounts/normalized/{slug}.json`

```json
{
  "account_id": "apple_card",
  "account_name": "Apple Card",
  "account_type": "credit",
  "data_period": {
    "start_date": "2024-11-01",
    "end_date": "2024-12-31"
  },
  "balances": [
    {
      "date": "2024-11-30",
      "amount_milliunits": -15234560,
      "available_milliunits": 24765440
    },
    {
      "date": "2024-12-31",
      "amount_milliunits": -18283090,
      "available_milliunits": 21716910
    }
  ],
  "transactions": [
    {
      "posted_date": "2024-11-01",
      "transaction_date": "2024-10-31",
      "description": "SAFEWAY 1616...",
      "merchant": "Safeway",
      "amount_milliunits": -13636,
      "type": "Purchase",
      "category": "Grocery",
      "purchased_by": "Erica Davis",
      "running_balance_milliunits": null,
      "cleared_status": null,
      "check_number": null,
      "memo": null
    }
  ],
  "source_metadata": {
    "parsed_at": "2025-12-27T20:30:00Z",
    "transaction_count": 243,
    "balance_count": 2,
    "deduplication_summary": {
      "total_raw_transactions": 243,
      "duplicates_removed": 0
    }
  }
}
```

### Field Specifications

**Required fields (all transactions):**
- `posted_date` - The official posted/clearing date
- `description` - Full transaction description
- `amount_milliunits` - Amount in YNAB format (negative = expense)

**Optional fields (account-specific):**
- `transaction_date` - If different from posted_date
- `merchant` - Extracted merchant name (Apple Card only)
- `type` - Bank's transaction type
- `category` - Bank's category
- `memo` - Additional memo field
- `purchased_by` - Apple Card specific
- `running_balance_milliunits` - Chase Checking only
- `cleared_status` - QIF only
- `check_number` - Chase Checking only

**Balance fields:**
- `date` - Balance as-of date
- `amount_milliunits` - Account balance
- `available_milliunits` - Available balance (credit accounts)

### De-duplication Strategy

**Problem:** Multiple export files with overlapping date ranges contain duplicate transactions.

**Solution:** For each date, use transactions from the most recent export file.

**Algorithm:**
1. Load all files (CSV and OFX) with export timestamps
2. Group transactions by (posted_date, source_file)
3. For each date, select transactions from file with latest export timestamp
4. Preserve original file ordering within each date's transactions
5. Result: Chronological transaction list with no duplicates

**Key principle:** Identical transactions within the SAME file are NOT duplicates
(bank is authoritative - if they reported it, it happened).

**Note:** OFX FITID (Financial Institution Transaction ID) is not extracted or used. All transaction identification is based on date, amount, and description fields.

## Unified YNAB Operations Format

**Purpose:** Consistent format for all YNAB operations (bank reconciliation, Amazon splits, Apple splits)

**File:** `data/bank_accounts/reconciliation/{timestamp}_reconciliation.json`

```json
{
  "version": "1.0",
  "metadata": {
    "generated_at": "2025-12-27T20:30:45Z",
    "source_system": "bank_reconciliation"
  },
  "operations": [
    {
      "operation_type": "create_transaction",
      "confidence": 1.0,
      "target": {
        "ynab_transaction": {
          "account_id": "uuid-ynab-account",
          "date": "2024-12-25",
          "amount_milliunits": -13636,
          "payee_name": "Safeway",
          "memo": "SAFEWAY 1616 444 WMC DRIVE...",
          "cleared": "cleared",
          "approved": false
        }
      },
      "source": {
        "bank_transaction": {
          "posted_date": "2024-12-25",
          "transaction_date": "2024-12-24",
          "description": "SAFEWAY 1616 444 WMC DRIVE...",
          "merchant": "Safeway",
          "amount_milliunits": -13636,
          "type": "Purchase",
          "category": "Grocery",
          "purchased_by": "Erica Davis"
        },
        "reason": "missing_from_ynab"
      }
    },
    {
      "operation_type": "update_transaction_splits",
      "confidence": 0.95,
      "target": {
        "ynab_transaction": {
          "account_id": "uuid-ynab-account",
          "transaction_id": "tx_xyz789",
          "date": "2024-10-15",
          "amount_milliunits": -45990,
          "payee_name": "Amazon",
          "memo": "AMAZON.COM*ZE1234567"
        }
      },
      "source": {
        "amazon_order": {
          "order_id": "112-7856341-1234567",
          "order_date": "2024-10-13",
          "ship_date": "2024-10-15",
          "total_amount_milliunits": -45990,
          "item_count": 2,
          "items": [
            {
              "title": "Arduino Starter Kit",
              "amount_milliunits": -12340,
              "quantity": 1
            }
          ]
        }
      },
      "splits": [
        {
          "amount_milliunits": -12340,
          "memo": "Arduino Starter Kit (qty: 1)",
          "category_id": "cat_abc123",
          "payee_id": null
        }
      ]
    },
    {
      "operation_type": "flag_discrepancy",
      "confidence": null,
      "target": {
        "ynab_transactions": [
          {
            "account_id": "uuid-ynab-account",
            "transaction_id": "tx_abc123",
            "date": "2024-12-20",
            "amount_milliunits": -5000,
            "payee_name": "Amazon",
            "memo": "AMAZON.COM ORDER 123"
          },
          {
            "account_id": "uuid-ynab-account",
            "transaction_id": "tx_def456",
            "date": "2024-12-20",
            "amount_milliunits": -5000,
            "payee_name": "Amazon",
            "memo": "AMAZON PRIME SUBSCRIPTION"
          }
        ]
      },
      "source": {
        "bank_transaction": {
          "posted_date": "2024-12-20",
          "description": "AMAZON MKTPL*ZE1234567 AMZN.COM/BILL",
          "amount_milliunits": -5000,
          "type": "Sale"
        }
      },
      "discrepancy": {
        "issue_type": "ambiguous_match",
        "candidate_count": 2,
        "description_similarity_scores": [0.65, 0.42],
        "recommended_action": "review_and_match",
        "explanation": "Bank transaction matches 2 YNAB transactions by date and amount, but descriptions don't match well enough."
      }
    }
  ],
  "summary": {
    "total_operations": 3,
    "by_type": {
      "create_transaction": 1,
      "update_transaction_splits": 1,
      "flag_discrepancy": 1
    },
    "by_confidence": {
      "1.0": 1,
      "0.95-0.99": 1,
      "null": 1
    },
    "balance_reconciliation": {
      "apple_card": {
        "bank_ending_balance_milliunits": -18283090,
        "bank_balance_date": "2024-12-31",
        "ynab_ending_balance_milliunits": -18420120,
        "difference_milliunits": -137030,
        "status": "mismatch",
        "explanation": "Mismatch explained by 15 missing transactions"
      }
    }
  }
}
```

### Operation Types

1. **create_transaction** - Add new transaction to YNAB (bank reconciliation)
2. **update_transaction_splits** - Break existing transaction into splits (Amazon/Apple)
3. **flag_discrepancy** - Mark ambiguous match for manual review

### Source Data Principles

- **Passthrough only** - No transformation or generation
- **Complete context** - Full source object for reviewer
- **No extraction** - Use data as provided by source system

## Domain Models

**Purpose:** Type-safe dataclasses for all bank reconciliation operations using Money and FinancialDate primitives.

**Location:** `src/finances/bank_accounts/models.py`

### BankTransaction

Represents a transaction from normalized bank account data.

```python
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
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "BankTransaction":
        """Deserialize from normalized format dict."""
        ...
```

### BalancePoint

Represents a balance snapshot at a specific date.

```python
@dataclass(frozen=True)
class BalancePoint:
    """Immutable balance snapshot from bank data."""

    date: FinancialDate
    amount: Money  # Ledger balance
    available: Money | None = None  # Available balance (credit accounts)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "BalancePoint":
        """Deserialize from normalized format dict."""
        ...
```

### BankAccount

Represents normalized bank account data.

```python
@dataclass(frozen=True)
class BankAccount:
    """Immutable normalized bank account data."""

    account_id: str  # Slug from config
    account_name: str
    account_type: str  # credit, checking, savings
    data_period_start: FinancialDate
    data_period_end: FinancialDate
    transactions: tuple[BankTransaction, ...]  # Immutable sequence
    balances: tuple[BalancePoint, ...]  # Immutable sequence

    @classmethod
    def from_normalized_file(cls, filepath: Path) -> "BankAccount":
        """Load from normalized JSON file."""
        ...

    def to_normalized_file(self, filepath: Path) -> None:
        """Write to normalized JSON file."""
        ...
```

### ReconciliationOperation

Represents a single YNAB operation to apply.

```python
from enum import Enum

class OperationType(Enum):
    """Type of YNAB operation."""
    CREATE_TRANSACTION = "create_transaction"
    UPDATE_TRANSACTION_SPLITS = "update_transaction_splits"
    FLAG_DISCREPANCY = "flag_discrepancy"

@dataclass(frozen=True)
class ReconciliationOperation:
    """Immutable YNAB operation from reconciliation."""

    operation_type: OperationType
    confidence: float  # 0.0 to 1.0
    target: dict  # YNAB transaction data
    source: dict  # Bank transaction data or match context

    # Optional for flag_discrepancy
    discrepancy: dict | None = None

    # Optional for update_transaction_splits
    splits: list[dict] | None = None

    def to_dict(self) -> dict:
        """Serialize to unified operations format."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "ReconciliationOperation":
        """Deserialize from unified operations format."""
        ...
```

### BalanceReconciliation

Represents balance reconciliation results for an account.

```python
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
        ...

@dataclass(frozen=True)
class BalanceReconciliation:
    """Complete balance reconciliation history for an account."""

    account_id: str
    points: tuple[BalanceReconciliationPoint, ...]  # Chronological
    last_reconciled_date: FinancialDate | None  # Last date with exact match
    first_diverged_date: FinancialDate | None  # First date with mismatch

    @property
    def current_status(self) -> BalanceReconciliationPoint:
        """Most recent balance point."""
        return self.points[-1] if self.points else None

    def to_dict(self) -> dict:
        """Serialize for output with filtered history."""
        ...
```

### ReconciliationResult

Represents complete reconciliation results for an account.

```python
@dataclass(frozen=True)
class ReconciliationResult:
    """Immutable reconciliation results for one account."""

    account_id: str
    bank_transactions_count: int
    ynab_transactions_count: int
    matched_count: int
    missing_from_ynab_count: int
    in_ynab_not_bank_count: int
    ambiguous_count: int
    operations: tuple[ReconciliationOperation, ...]
    balance_reconciliation: BalanceReconciliation | None

    def to_dict(self) -> dict:
        """Serialize for output."""
        ...
```

### Key Principles

1. **Immutability**: All models use `@dataclass(frozen=True)` to prevent accidental mutation
2. **Type safety**: Use `Money` for amounts, `FinancialDate` for dates, never raw integers or strings
3. **No floating point**: Money handles all currency arithmetic with integer milliunits
4. **Validation**: Dataclass `__post_init__` validates constraints (e.g., confidence 0.0-1.0)
5. **Serialization**: All models have `to_dict()` and `from_dict()` for JSON I/O
6. **Tuple sequences**: Use `tuple[T, ...]` for immutable collections instead of `list[T]`

## Flow Node Designs

### Node 1: account_data_retrieve

**Purpose:** Check data freshness and guide user to download missing/stale data

**Dependencies:** `ynab_sync` (for config stub generation)

**Inputs:**
- `data/bank_accounts/config.json`
- `data/bank_accounts/raw/{slug}/` (existing files)

**Outputs:** None (console output only)

**Behavior:**

1. Load config (create stub + fail if missing)
2. If config has no accounts → skip gracefully
3. For each account:
   - Scan raw/{slug}/ for latest file
   - Parse date/range from filename
   - Calculate staleness:
     - Monthly: Stale if >3 business days past month-end and missing that month
     - Daily: Stale if >2 days old
   - Determine if download needed (always suggest up to today)
4. Display status + download instructions (from config)
5. Prompt: "Run this node? [y/N]"
6. If yes → validate required files exist → fail if missing

**Pre-execution:**
```
[account_data_retrieve]
  Current date: 2025-12-27 (Friday)
  Status: 4 accounts configured, 2 stale
  Run this node? [y/N]
```

**Post-execution:**
```
✅ account_data_retrieve completed

Download status:
  apple_card: ✅ Current (2024-12.ofx, 1 day old)
  chase_checking: ⚠️  Stale (2024-12-20_to_2024-12-25.csv, 3 days old)

Download needed: chase_checking
  Required: data/bank_accounts/raw/chase_checking/2024-12-26_to_2024-12-27.csv

Instructions for chase_checking:
  1. Go to chase.com → Transactions
  2. Select date range: 12/26/2024 - 12/27/2024
  3. Download CSV
  4. Place in path above

Files validated and ready for parsing.
```

### Node 2: account_data_parse

**Purpose:** Parse raw bank files into normalized JSON format

**Dependencies:** `account_data_retrieve`

**Inputs:**
- `data/bank_accounts/config.json`
- `data/bank_accounts/raw/{slug}/*.{csv,ofx,qif}`

**Outputs:**
- `data/bank_accounts/normalized/{slug}.json` (one per account)

**Parser Implementation Strategy:**

This implementation uses custom parsers for OFX and QIF formats rather than external libraries for the following reasons:

1. **Unmaintained libraries**: The two major Python OFX libraries (ofxparse and ofxtools) have been abandoned since 2021-2022 with no releases in the past 3+ years, creating ongoing security and Python version compatibility risks.

2. **Limited scope**: This system only needs balance extraction from OFX/QIF files (not full transaction parsing), which is a small subset of functionality that external libraries provide.

3. **Simple formats**: QIF is a text-based format (~50 lines of regex-based parsing), and OFX balance extraction requires only matching specific SGML tags (`<LEDGERBAL>`, `<AVAILBAL>`, `<DTASOF>`).

4. **Lower TCO**: Custom parsing (one-time 2-3 hour implementation) has lower total cost of ownership than maintaining dependencies on abandoned libraries that may break with Python version updates.

5. **Consistency**: CSV formats already require custom parsers with validation; keeping all parsers in the same codebase simplifies maintenance.

Implementation approach:
- OFX: Regex-based extraction of balance tags from SGML format (~50 lines)
- QIF: Line-by-line text parser with state machine (~30 lines)
- CSV: Python `csv.DictReader` with custom validation (existing pattern)

**Parsing Strategy:**

For each configured account:

1. **Load all CSV files** with export timestamp metadata
2. **Group transactions** by (posted_date, source_file)
3. **De-duplicate:** For each date, select transactions from most recent export file
4. **Load OFX/QIF** for balance data ONLY (don't extract transactions)
5. **De-duplicate balances:** For each date, select balance from most recent file
6. **Auto-detect date range** from transaction content (min/max posted_date)
7. **Write normalized JSON** to `normalized/{slug}.json`

**Format Parsers:**

- Apple Card CSV → Extract merchant, category, purchased_by
- Apple Card/Savings OFX → Extract balances only (LEDGERBAL, AVAILBAL)
- Chase Checking CSV → Extract running_balance
- Chase Credit CSV → Standard format
- Chase Credit QIF → Extract cleared_status, check_number
- All formats → Parse to common normalized structure

**Error Handling:**

- Unparseable file → Fail fast with line number and error
- Invalid CSV headers → Fail with expected vs. found
- Invalid date/amount format → Fail with specific error
- Empty file → Warning, continue with others
- OFX parse error → Fail with element name

**Pre-execution:**
```
[account_data_parse]
  Status: 4 accounts configured, 0 normalized files exist
  Run this node? [y/N]
```

**Post-execution:**
```
✅ account_data_parse completed

apple_card:
  Transactions: 243 (0 duplicates removed)
  Date range: 2024-11-01 to 2024-12-31
  Latest balance: -$182,830.90 as of 2024-12-31
  → normalized/apple_card.json

apple_savings:
  Transactions: 156 (0 duplicates removed)
  Date range: 2024-11-01 to 2024-12-31
  Latest balance: $42,053.56 as of 2024-12-31
  → normalized/apple_savings.json

chase_checking:
  Transactions: 42 (12 duplicates removed)
  Date range: 2024-12-01 to 2024-12-27
  Latest balance: $40,559.83 as of 2024-12-27
  → normalized/chase_checking.json

chase_credit:
  Transactions: 468 (0 duplicates removed)
  Date range: 2024-01-01 to 2025-12-27
  Latest balance: (none)
  → normalized/chase_credit.json

Summary: 4 accounts, 909 transactions, 12 duplicates removed
```

### Node 3: account_data_reconcile

**Purpose:** Compare normalized bank data to YNAB transactions and generate reconciliation operations

**Dependencies:** `account_data_parse`, `ynab_sync`

**Inputs:**
- `data/bank_accounts/config.json`
- `data/bank_accounts/normalized/{slug}.json`
- `data/ynab/cache/transactions.json`
- `data/ynab/cache/accounts.json`

**Outputs:**
- `data/bank_accounts/reconciliation/{timestamp}_reconciliation.json`

**Transaction Reconciliation (Bidirectional):**

For each configured account, match transactions in both directions:

1. **Load data:**
   - Bank transactions from normalized file
   - YNAB transactions for account from cache

2. **Filter pending:**
   - Bank: Exclude if cleared_status == "pending"
   - YNAB: Exclude if cleared == "uncleared"

3. **Bank → YNAB matching** (find missing transactions):
   - For each bank transaction:
     - Search for YNAB transaction with same date + exact amount
     - If unique match: Mark as reconciled
     - If no match: Generate `create_transaction` operation
     - If multiple YNAB matches: Try fuzzy description matching
       - Normalize descriptions (lowercase, remove numbers, normalize spaces)
       - Calculate similarity score (SequenceMatcher) against payee_name and memo
       - If score > 0.8: Mark as reconciled
       - If score <= 0.8: Generate `flag_discrepancy` operation (ambiguous match)

4. **YNAB → Bank matching** (find extra transactions):
   - For each YNAB transaction not matched above:
     - Generate `flag_discrepancy` operation
     - Reason: "Transaction in YNAB but not in bank statement"
     - Possible causes: Duplicate entry, incorrect date, pending reversal

**Balance Reconciliation (Validation Only):**

After transaction matching, verify arithmetic using traditional accounting reconciliation format:

1. **Collect all balance points chronologically:**
   - Extract all dates where bank has balance data
   - For each date, calculate YNAB balance as of that date (sum of cleared/reconciled transactions)
   - Sort chronologically (earliest first)

2. **Calculate adjusted balances for each date:**
   ```
   Adjusted Bank Balance = Bank_Balance
                         + sum(bank_txs_not_in_ynab where date <= balance_date)

   Adjusted YNAB Balance = YNAB_Balance
                         + sum(ynab_txs_not_in_bank where date <= balance_date)
   ```

3. **Track reconciliation history:**
   - Work chronologically through all balance points
   - For each date: reconciled (exact match) or diverged (calculate difference)
   - Identify last reconciled date and first diverged date
   - Filter output: show starting/ending balances, changes in divergence, and one entry before each change

4. **Exact match requirement:**
   - Reconciled: `Adjusted_Bank == Adjusted_YNAB` (exact, no tolerance)
   - Mismatch: `Adjusted_Bank != Adjusted_YNAB` → investigation required

**Note:** Balance reconciliation is arithmetic validation only. All substantive work happens in transaction matching. If transactions are fully matched, balances will reconcile exactly.

**Operation Generation:**

1. **create_transaction** for each unmatched bank transaction:
   - payee_name: Use merchant field if present, else description
   - memo: Full description
   - No payee extraction/parsing

2. **flag_discrepancy** for ambiguous matches:
   - Type: "ambiguous_match"
   - Include all YNAB candidate transactions
   - Include similarity scores
   - Recommend manual review

3. **flag_discrepancy** for YNAB transactions not in bank:
   - Type: "ynab_not_in_bank"
   - Include YNAB transaction details
   - Possible causes: Duplicate entry, incorrect date, pending reversal
   - Recommend manual review

**Pre-execution:**
```
[account_data_reconcile]
  Status: 4 normalized files ready, YNAB cache 1 day old
  Run this node? [y/N]
```

**Post-execution:**
```
✅ account_data_reconcile completed

apple_card:
  Transaction Reconciliation:
    Bank transactions: 243
    YNAB transactions: 228
    Matched: 228
    Missing from YNAB: 15
    In YNAB but not bank: 0
    Ambiguous: 0

  Balance Reconciliation History:
    2024-11-01: ✅ Reconciled (exact match: -$14,523.45)  [starting balance]
    2024-11-30: ✅ Reconciled (exact match: -$15,234.56)  [before divergence]
    2024-12-01: ⚠️  Diverged (difference: -$42.99, bank: -$15,277.55, adjusted YNAB: -$15,234.56)
    2024-12-19: ⚠️  Diverged (difference: -$42.99, bank: -$17,150.00, adjusted YNAB: -$17,107.01)  [before change]
    2024-12-20: ⚠️  Diverged (difference: -$85.50, bank: -$17,234.56, adjusted YNAB: -$17,149.06)
    2024-12-31: ⚠️  Diverged (difference: -$137.03, bank: -$18,283.09, adjusted YNAB: -$18,146.06)  [ending balance]

  Summary:
    Last reconciled: 2024-11-30 (balances agreed: -$15,234.56)
    First diverged:  2024-12-01 (difference appeared: -$42.99)
    Divergence grew: 2024-12-20 (-$42.99 → -$85.50), 2024-12-31 (-$85.50 → -$137.03)
    Action: Review transactions between 2024-11-30 and 2024-12-01

  Current Status (as of 2024-12-31):
    Bank balance:              -$18,283.09
    + Bank TXs not in YNAB:       -$137.03  (15 transactions)
    - YNAB TXs not in bank:         $0.00  (0 transactions)
    = Adjusted bank balance:   -$18,146.06

    YNAB balance:              -$18,146.06
    = Adjusted YNAB balance:   -$18,146.06

    Status: ⚠️  Mismatch ($137.03 discrepancy after adjustments)

chase_credit:
  Transaction Reconciliation:
    Bank transactions: 468
    YNAB transactions: 465
    Matched: 459
    Missing from YNAB: 6
    In YNAB but not bank: 3
    Ambiguous: 3 (multiple YNAB txs with same date/amount)

  Balance Reconciliation:
    Status: No balance data available

Overall Summary:
  21 operations generated:
    - 15 create_transaction (apple_card)
    - 6 create_transaction (chase_credit)
    - 6 flag_discrepancy (3 ambiguous + 3 ynab_not_in_bank)

  Balance reconciliation:
    - 1 account with divergence (apple_card: -$137.03)
    - 1 account without balance data (chase_credit)

  → reconciliation/2025-12-27_20-30-45_reconciliation.json

Next: Review reconciliation file, then run ynab_apply
```

## Error Handling

### Principles

1. **Fail fast and loudly** - Stop immediately on error
2. **Actionable messages** - Tell user exactly what's wrong and how to fix
3. **Context in errors** - Include file names, line numbers, field names
4. **No silent failures** - Every error should halt execution
5. **Validate early** - Check inputs before processing

### Error Categories

**Configuration Errors:**
- Missing config → Create stub, fail with instructions
- Invalid JSON → Fail with parse error and line number
- Invalid fields → Fail with validation errors
- YNAB account not found → Fail with available accounts list

**Parse Errors:**
- Invalid CSV headers → Fail with expected vs. found
- Invalid amount format → Fail with line number and value
- Invalid date format → Fail with line number and value
- Empty file → Warning, continue
- OFX malformed → Fail with specific element error

**Dependency Errors:**
- Missing normalized files → Fail with dependency message
- Missing YNAB cache → Fail with dependency message

**Balance Errors:**
- Balance calculation fails → Warning, continue without balance

### Example Error Messages

**Parse Error:**
```
❌ account_data_parse failed

Failed to parse: data/bank_accounts/raw/apple_card/2024-12.csv

Parse error at line 45, column 7 (Amount field):
  Invalid amount format: "---"
  Expected: Decimal number (e.g., "123.45" or "-50.00")

Full line (line 45):
  12/15/2024,12/16/2024,"REFUND","Amazon","Other","Refund","---","Karl Davis"

Please fix the file and re-run.

Flow execution aborted.
```

**Config Error:**
```
❌ account_data_reconcile failed

Configuration error in data/bank_accounts/config.json:

Account "apple_card":
  YNAB account ID not found: "uuid-that-doesnt-exist"

Available YNAB accounts:
  - Apple Card (uuid-correct-one)
  - Apple Savings (uuid-savings)
  - Chase Checking (...1503) (uuid-checking)

Please update config.json with correct account ID.

Flow execution aborted.
```

## Migration Plan

### Phase 1: Bank Reconciliation (This Design)

**Scope:**
- Implement 3 new flow nodes with unified operations format
- Create normalized bank account format
- Output reconciliation operations for manual review

**Deliverables:**
- `finances.bank_accounts` package
- Flow nodes: account_data_retrieve, account_data_parse, account_data_reconcile
- Configuration management
- Comprehensive error handling
- E2E tests with synthetic data

**Timeline:** 2-3 weeks

### Phase 2: Migrate Amazon Matcher (REQUIRED)

**Scope:**
- Update `finances.amazon.matcher` to output unified operations format
- Convert from `TransactionSplitEdit` → `update_transaction_splits` operations
- Map metadata → `source.amazon_order` with full order details

**Changes:**
- Output directory: `data/amazon/operations/` (instead of `data/ynab/edits/`)
- Format version: `"version": "1.0"` field
- Operation structure: Matches unified format spec
- Preserve all existing Amazon matching logic

**Testing:**
- Convert historical Amazon split files using conversion helper
- Verify manual review workflow still works
- E2E test with real Amazon data

**Timeline:** 1 week

### Phase 3: Migrate Apple Matcher (REQUIRED)

**Scope:**
- Update `finances.apple.matcher` to output unified operations format
- Convert to `update_transaction_splits` operations
- Map to `source.apple_receipt` with full receipt details

**Changes:**
- Output directory: `data/apple/operations/`
- Format version: `"version": "1.0"` field
- Operation structure: Matches unified format spec
- Preserve all existing Apple matching logic

**Testing:**
- Convert historical Apple split files using conversion helper
- Verify manual review workflow still works
- E2E test with real Apple data

**Timeline:** 1 week

### Phase 4: Automated Apply (Future, Optional)

**Scope:**
- Implement actual YNAB API integration in `ynab_apply` node
- Parse unified operations format
- Execute operations via YNAB API
- Handle errors and rollback

**Benefits:**
- One format to support (unified)
- Consistent behavior across all operation types
- Automated application with review checkpoints

**Timeline:** TBD (not part of initial scope)

### Migration Helpers

**Format Conversion Tool:**

```python
def convert_legacy_to_unified(legacy_file: Path, output_file: Path):
    """
    Convert old SplitEditBatch format to new unified operations format.

    Reads legacy format and outputs unified format with proper structure.
    Useful for migrating historical split files.
    """
    # Implementation details in migration code
```

## Testing Strategy

### Test Pyramid

1. **E2E Tests** (Highest Priority)
   - Execute actual `finances` CLI commands via subprocess
   - Test complete user workflows from raw files to operations
   - Use synthetic bank data (no real PII)

2. **Integration Tests**
   - Test parsers with various file formats
   - Test de-duplication logic with overlapping files
   - Test matching algorithm with edge cases

3. **Unit Tests**
   - Test fuzzy description matching
   - Test date range detection
   - Test balance reconciliation logic
   - Test configuration validation

### Test Data

- All test data MUST be synthetic (no real financial data)
- Create representative samples for each bank format
- Include edge cases: overlapping dates, duplicates, missing balances
- Store in `tests/fixtures/bank_accounts/`

### Test Scenarios

**Critical edge cases to test:**

**De-duplication:**
- Overlapping date ranges with 3+ files (ensure most recent wins)
- Same date in multiple files with different transaction counts
- Transactions with identical date/amount/description in same file (not duplicates)
- Empty export files
- Single-day export vs. multi-month export overlap

**Transaction Matching:**
- Exact match: same date + amount (unique)
- No match: transaction in bank but not YNAB
- Multiple matches: 2+ YNAB transactions with same date + amount
  - High similarity description (score > 0.8) → match
  - Low similarity description (score <= 0.8) → flag discrepancy
- Pending transactions (excluded from matching)
- Same amount on same date, different descriptions
- Unicode in descriptions (emoji, accented characters)
- Very long descriptions (>200 characters)

**Balance Reconciliation:**
- Exact match: adjusted balances equal
- Divergence: balances differ by missing transactions
- First divergence: balances match initially, then diverge
- Multiple divergences: difference grows over time
- No balance data available (OFX/QIF missing)
- Balance date in future (should fail)
- Rounding: amounts differing by $0.01 (should NOT reconcile - exact match required)

**Parser Edge Cases:**
- CSV with missing required columns (should fail)
- CSV with extra columns (should fail - unexpected input)
- CSV with columns in wrong order (should fail - exact header match required)
- CSV with malformed amounts ("---", "N/A", empty) (should fail)
- CSV with malformed dates ("00/00/0000", "Invalid") (should fail)
- CSV with newlines in description field (quoted) (should parse correctly)
- OFX with missing balance tags (should fail)
- OFX with malformed SGML (unclosed tags) (should fail)
- QIF with missing required fields (!Type, D, T) (should fail)
- Empty files (warning, continue with other files)
- Files with BOM (byte order mark) (should handle gracefully or fail clearly)
- Files with different line endings (CRLF, LF, CR) (should handle all formats)
- Files with unexpected format (e.g., HTML error page saved as .csv) (should fail)

**Configuration:**
- Missing config.json (generate stub)
- Empty accounts array (skip gracefully)
- Invalid YNAB account ID (fail with available accounts)
- Duplicate slugs (fail with validation error)
- Invalid statement_frequency value (fail)

**Date Handling:**
- Leap year dates (2024-02-29)
- Year boundaries (12/31 → 01/01)
- Daylight saving time transitions (not applicable for dates, but test date parsing)
- Invalid dates (2024-02-30, 2024-13-01)

**Amount Handling:**
- Zero amounts ($0.00)
- Very large amounts (>$1,000,000)
- Negative amounts (credits for credit cards, debits for checking)
- Amounts with many decimal places (should fail - milliunits only)

**File Timestamp Detection:**
- Filename with date range (2024-12-01_to_2024-12-31.csv)
- Filename with single date (2024-12.csv)
- Filename without date (should use file modification time)
- Multiple files with same date (undefined behavior - should fail or pick deterministically)

**Key principle:** Unexpected input should fail fast with clear error message. Only valid, expected formats should parse successfully.

### Coverage Goals

- 60%+ overall coverage with quality over quantity
- 100% coverage of error handling paths
- E2E tests for all three flow nodes
- Integration tests for parsers and matchers

## Success Criteria

### General Criteria

- ☐ All CI checks pass (tests, mypy, ruff, black)
- ☐ E2E tests cover main workflows
- ☐ No stubbed/incomplete code
- ☐ No legacy/backward compatibility code
- ☐ Work committed with descriptive messages
- ☐ PR description includes summary, test plan, success criteria

### Bank Reconciliation Specific

- ☐ All 3 flow nodes implemented and tested
- ☐ Config file workflow tested (stub creation, validation)
- ☐ All 4 bank account formats parsed correctly
- ☐ De-duplication working for overlapping files
- ☐ Matching strategy correctly identifies missing transactions
- ☐ Balance reconciliation accurate
- ☐ Unified operations format generated correctly
- ☐ Error handling comprehensive and tested
- ☐ Documentation complete

### Migration Specific (Phases 2-3)

- ☐ Amazon matcher outputs unified format
- ☐ Apple matcher outputs unified format
- ☐ Historical split files converted or deprecated
- ☐ No code supports old format
- ☐ All tests pass with new format

## Open Questions

None - design is complete.

## References

- CLAUDE.md - Repository documentation
- Unified YNAB Operations Format (designed in this document)
- Existing Amazon/Apple matchers for pattern reference
