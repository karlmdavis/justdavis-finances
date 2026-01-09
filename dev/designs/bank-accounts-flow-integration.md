# Bank Accounts Flow Integration Design

**Status**: Draft
**Created**: 2026-01-08
**Author**: Claude Code

## 1. Overview

This design formalizes the integration of bank account reconciliation nodes into the `finances flow` system.
The bank accounts domain currently has three standalone Python functions that need to be wrapped in FlowNode classes with proper DataStore integration.

### 1.1 Goals

1. **Flow System Integration**: Enable bank account nodes to run via `finances flow` command
2. **Directory Ownership**: Establish clear data ownership boundaries between nodes
3. **DataStore Patterns**: Apply consistent file management patterns from existing domains
4. **Change Detection**: Implement proper OutputInfo validation for incremental processing
5. **Type Safety**: Maintain Money/FinancialDate type safety throughout flow integration

### 1.2 Non-Goals

- Changing existing node business logic (retrieve, parse, reconcile functions work correctly)
- Adding archiving or file cleanup logic (not present in other domains)
- Modifying the multi-account configuration model

## 2. Architecture Overview

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Flow System Entry                         │
│                  finances flow [nodes]                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Node Registration                          │
│        src/finances/cli/flow.py::setup_flow_nodes()         │
│  Registers: BankDataRetrieveFlowNode                        │
│             BankDataParseFlowNode                           │
│             BankDataReconcileFlowNode                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Bank Accounts Flow Nodes                    │
│           src/finances/bank_accounts/flow.py                │
│                                                              │
│  ┌────────────────────────────────────────────────┐        │
│  │  BankDataRetrieveFlowNode                      │        │
│  │  - No dependencies                              │        │
│  │  - Wraps retrieve_account_data()               │        │
│  │  - Writes to: bank_accounts/raw/{slug}/       │        │
│  │  - No DataStore (raw files only)               │        │
│  └────────────────┬───────────────────────────────┘        │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────┐        │
│  │  BankDataParseFlowNode                         │        │
│  │  - Depends on: bank_data_retrieve              │        │
│  │  - Wraps parse_account_data()                  │        │
│  │  - Reads from: bank_accounts/raw/{slug}/      │        │
│  │  - Writes to: bank_accounts/normalized/       │        │
│  │  - DataStore: BankNormalizedDataStore (C)     │        │
│  └────────────────┬───────────────────────────────┘        │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────┐        │
│  │  BankDataReconcileFlowNode                     │        │
│  │  - Depends on: bank_data_parse, ynab_sync     │        │
│  │  - Wraps reconcile_account_balances()         │        │
│  │  - Reads from: bank_accounts/normalized/      │        │
│  │  -             ynab/cache/                     │        │
│  │  - Writes to: bank_accounts/reconciliation/   │        │
│  │  - DataStore: BankReconciliationStore (C)     │        │
│  └────────────────────────────────────────────────┘        │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Pattern Legend:
(C) = Pattern C: Timestamped Accumulation
```

### 2.2 Directory Structure and Ownership

```
data/bank_accounts/
├── raw/                          # OWNED BY: BankDataRetrieveFlowNode
│   ├── apple-card/               #   One subdirectory per account slug
│   │   └── 2024-12-statement.ofx #   Raw export files from banks
│   ├── apple-savings/
│   │   └── 2024-12-statement.ofx
│   └── chase-checking/
│       └── 2024-12-statement.csv
│
├── normalized/                   # OWNED BY: BankDataParseFlowNode
│   ├── 2024-01-08_14-23-45_apple-card.json      # Pattern C: Timestamped
│   ├── 2024-01-08_14-23-46_apple-savings.json   # One file per parse run
│   ├── 2024-01-08_14-23-47_chase-checking.json  # per account
│   └── ...                                       # Accumulates forever
│
└── reconciliation/               # OWNED BY: BankDataReconcileFlowNode
    ├── 2024-01-08_14-30-12_operations.json      # Pattern C: Timestamped
    ├── 2024-01-08_15-45-23_operations.json      # One file per reconcile run
    └── ...                                       # Accumulates forever

data/ynab/cache/                  # OWNED BY: YnabSyncFlowNode
├── transactions.json             # READ-ONLY for bank reconciliation
└── accounts.json
```

**Ownership Rules**:
1. Each node EXCLUSIVELY writes to its output directory
2. Nodes MAY read from upstream dependency directories (read-only access)
3. Raw files in `raw/{slug}/` are copied from external sources, not generated
4. No node deletes files from other nodes' directories

## 3. FlowNode Specifications

### 3.1 BankDataRetrieveFlowNode

**Purpose**: Copy raw bank export files from configured source paths to data directory.

**Node ID**: `bank_data_retrieve`

**Dependencies**: None (entry point node)

**Configuration**:
```python
# From src/finances/bank_accounts/config.py
accounts:
  - slug: "apple-card"
    name: "Apple Card"
    export_format: "apple_card_ofx"
    source_path: "/Users/karl/Downloads/AppleCard-*.ofx"
```

**Business Logic**: Wraps `retrieve_account_data()` from `src/finances/bank_accounts/nodes/retrieve.py`

**Input**: None (reads from filesystem paths in config)

**Output**:
- **Directory**: `data/bank_accounts/raw/{slug}/`
- **Files**: Copied export files (e.g., `2024-12-statement.ofx`)
- **Pattern**: Overwrite-on-copy (no accumulation, file manager maintains raw exports)

**OutputInfo Implementation**:
```python
class BankDataRetrieveOutputInfo(OutputInfo):
    """Validates that raw account data exists for configured accounts."""

    def __init__(self, output_dir: Path, config: BankAccountsConfig):
        super().__init__(output_dir)
        self.config = config

    def is_data_ready(self) -> bool:
        """Check if at least one configured account has raw data."""
        if not self.output_dir.exists():
            return False

        for account in self.config.accounts:
            account_dir = self.output_dir / account.slug
            if account_dir.exists() and len(list(account_dir.glob("*"))) > 0:
                return True

        return False

    def get_output_files(self) -> list[Path]:
        """Return all raw export files across all accounts."""
        files = []
        for account in self.config.accounts:
            account_dir = self.output_dir / account.slug
            if account_dir.exists():
                files.extend(account_dir.glob("*"))
        return files
```

**DataStore**: None (raw files managed manually)

**FlowResult**:
- **Status**: Success if any files copied/found, Warning if none found
- **Outputs**: All files in `raw/{slug}/` directories
- **Summary**: Count of copied/skipped files per account

### 3.2 BankDataParseFlowNode

**Purpose**: Parse raw bank exports into normalized transaction format.

**Node ID**: `bank_data_parse`

**Dependencies**: `bank_data_retrieve`

**Business Logic**: Wraps `parse_account_data()` from `src/finances/bank_accounts/nodes/parse.py`

**Input**:
- **Read from**: `data/bank_accounts/raw/{slug}/` (read-only)
- **Format**: Bank-specific exports (OFX, CSV)

**Output**:
- **Directory**: `data/bank_accounts/normalized/`
- **Files**: `{timestamp}_{slug}.json` (one per account per run)
- **Pattern**: Pattern C (Timestamped Accumulation)
- **Format**:
```json
{
  "account_slug": "apple-card",
  "parsed_at": "2024-01-08T14:23:45",
  "transactions": [
    {
      "posted_date": "2024-01-05",
      "description": "Amazon.com",
      "amount": {"cents": -5499},
      "transaction_date": "2024-01-04"
    }
  ],
  "balance_points": [
    {
      "date": "2024-01-05",
      "amount": {"cents": -125000},
      "available": null
    }
  ],
  "statement_date": "2024-01-31"
}
```

**OutputInfo Implementation**:
```python
class BankDataParseOutputInfo(OutputInfo):
    """Validates that normalized data exists."""

    def is_data_ready(self) -> bool:
        """Check if at least one normalized file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[Path]:
        """Return all normalized JSON files."""
        if not self.output_dir.exists():
            return []
        return list(self.output_dir.glob("*.json"))
```

**DataStore**:
```python
class BankNormalizedDataStore(DataStoreMixin):
    """Pattern C: Timestamped Accumulation for normalized account data."""

    def __init__(self, normalized_dir: Path):
        super().__init__()
        self.normalized_dir = normalized_dir

    def exists(self) -> bool:
        """Check if any normalized files exist."""
        return self.normalized_dir.exists() and len(self._get_files_cached(
            self.normalized_dir, "*.json"
        )) > 0

    def load(self) -> dict[str, Any]:
        """Load most recent normalized data (by mtime)."""
        files = self._get_files_cached(self.normalized_dir, "*.json")
        if not files:
            raise FileNotFoundError(f"No normalized data found in {self.normalized_dir}")

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return read_json(most_recent)

    def save(self, account_slug: str, data: dict[str, Any]) -> Path:
        """Save normalized data with timestamp and account slug."""
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.normalized_dir / f"{timestamp}_{account_slug}.json"

        write_json(output_file, data)
        self._invalidate_cache()

        return output_file

    def last_modified(self) -> datetime | None:
        """Return most recent file modification time."""
        files = self._get_files_cached(self.normalized_dir, "*.json")
        if not files:
            return None

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return datetime.fromtimestamp(most_recent.stat().st_mtime)

    def item_count(self) -> int | None:
        """Return count of normalized files."""
        return len(self._get_files_cached(self.normalized_dir, "*.json"))

    def summary_text(self) -> str:
        """Provide human-readable summary."""
        count = self.item_count() or 0
        age = self.age_days()
        age_str = f"{age}d old" if age is not None else "never"
        return f"{count} normalized files, last modified {age_str}"
```

**FlowResult**:
- **Status**: Success if all accounts parsed
- **Outputs**: All timestamped JSON files created in this run
- **Summary**: Count of transactions/balances parsed per account

### 3.3 BankDataReconcileFlowNode

**Purpose**: Reconcile bank balances with YNAB, identify discrepancies.

**Node ID**: `bank_data_reconcile`

**Dependencies**: `bank_data_parse`, `ynab_sync`

**Business Logic**: Wraps `reconcile_account_balances()` from `src/finances/bank_accounts/nodes/reconcile.py`

**Input**:
- **Read from**:
  - `data/bank_accounts/normalized/` (read-only)
  - `data/ynab/cache/transactions.json` (read-only)
  - `data/ynab/cache/accounts.json` (read-only)

**Output**:
- **Directory**: `data/bank_accounts/reconciliation/`
- **Files**: `{timestamp}_operations.json`
- **Pattern**: Pattern C (Timestamped Accumulation)
- **Format**:
```json
{
  "reconciled_at": "2024-01-08T14:30:12",
  "accounts": {
    "apple-card": {
      "reconciliation": {
        "account_id": "apple-card",
        "points": [
          {
            "date": "2024-01-31",
            "bank_balance": {"cents": -125000},
            "ynab_balance": {"cents": -125000},
            "bank_txs_not_in_ynab": {"cents": 0},
            "ynab_txs_not_in_bank": {"cents": 0},
            "adjusted_bank_balance": {"cents": -125000},
            "adjusted_ynab_balance": {"cents": -125000},
            "is_reconciled": true,
            "difference": {"cents": 0}
          }
        ],
        "last_reconciled_date": "2024-01-31",
        "first_diverged_date": null
      },
      "unmatched_bank_txs": [...],
      "unmatched_ynab_txs": [...]
    }
  }
}
```

**OutputInfo Implementation**:
```python
class BankDataReconcileOutputInfo(OutputInfo):
    """Validates that reconciliation operations exist."""

    def is_data_ready(self) -> bool:
        """Check if at least one operations file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[Path]:
        """Return all operations JSON files."""
        if not self.output_dir.exists():
            return []
        return list(self.output_dir.glob("*.json"))
```

**DataStore**:
```python
class BankReconciliationStore(DataStoreMixin):
    """Pattern C: Timestamped Accumulation for reconciliation operations."""

    def __init__(self, reconciliation_dir: Path):
        super().__init__()
        self.reconciliation_dir = reconciliation_dir

    def exists(self) -> bool:
        """Check if any operations files exist."""
        return self.reconciliation_dir.exists() and len(self._get_files_cached(
            self.reconciliation_dir, "*.json"
        )) > 0

    def load(self) -> dict[str, Any]:
        """Load most recent reconciliation (by mtime)."""
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        if not files:
            raise FileNotFoundError(
                f"No reconciliation data found in {self.reconciliation_dir}"
            )

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return read_json(most_recent)

    def save(self, data: dict[str, Any]) -> Path:
        """Save reconciliation with timestamp."""
        self.reconciliation_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.reconciliation_dir / f"{timestamp}_operations.json"

        write_json(output_file, data)
        self._invalidate_cache()

        return output_file

    def last_modified(self) -> datetime | None:
        """Return most recent file modification time."""
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        if not files:
            return None

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return datetime.fromtimestamp(most_recent.stat().st_mtime)

    def item_count(self) -> int | None:
        """Return count of operations files."""
        return len(self._get_files_cached(self.reconciliation_dir, "*.json"))

    def summary_text(self) -> str:
        """Provide human-readable summary."""
        count = self.item_count() or 0
        age = self.age_days()
        age_str = f"{age}d old" if age is not None else "never"
        return f"{count} reconciliation files, last modified {age_str}"
```

**FlowResult**:
- **Status**: Success if reconciliation completes, Warning if discrepancies found
- **Outputs**: Timestamped operations JSON file
- **Summary**: Per-account reconciliation status (reconciled vs diverged)

## 4. File Cleanup Strategy

The FlowEngine automatically removes files not in `FlowResult.outputs`.
To protect accumulated files:

**Protected Files**:
1. **Parse Node**: All generated `{timestamp}_{slug}.json` files in `normalized/`
2. **Reconcile Node**: All generated `{timestamp}_operations.json` files in `reconciliation/`

**Implementation**:
```python
# In execute() method
def execute(self, context: FlowContext) -> FlowResult:
    # ... node logic ...

    # Get ALL existing files in output directory
    existing_files = list(self.output_dir.glob("*.json"))

    # Add newly created file
    all_protected_files = existing_files + [new_output_file]

    return FlowResult.success(
        node_id=self.node_id,
        outputs=all_protected_files,  # Protects both old and new
        summary=summary
    )
```

**Why This Works**:
- Pattern C accumulates files naturally
- Each node run includes ALL files in its directory in `FlowResult.outputs`
- FlowEngine won't delete files explicitly listed in outputs
- No archiving logic needed (follows existing patterns)

## 5. Integration Points

### 5.1 Flow Registry Registration

**Location**: `src/finances/cli/flow.py`

**Changes Required**:
```python
def setup_flow_nodes() -> None:
    """Register all flow nodes with their dependencies."""
    config = get_config()

    # Existing imports...
    from ..amazon.flow import (...)
    from ..apple.flow import (...)

    # NEW: Import bank accounts nodes
    from ..bank_accounts.flow import (
        BankDataRetrieveFlowNode,
        BankDataParseFlowNode,
        BankDataReconcileFlowNode,
    )

    # Existing registrations...
    flow_registry.register_node(AmazonMatchingFlowNode(config.data_dir))
    # ...

    # NEW: Register bank accounts nodes
    bank_config = BankAccountsConfig.load()
    flow_registry.register_node(
        BankDataRetrieveFlowNode(config.data_dir, bank_config)
    )
    flow_registry.register_node(
        BankDataParseFlowNode(config.data_dir, bank_config)
    )
    flow_registry.register_node(
        BankDataReconcileFlowNode(config.data_dir, bank_config)
    )
```

### 5.2 Dependency Graph

```
┌──────────────────┐
│   ynab_sync      │────────┐
└──────────────────┘        │
                             │
┌──────────────────┐        │    ┌─────────────────────────┐
│ bank_data_       │        └───▶│  bank_data_reconcile    │
│   retrieve       │             └─────────────────────────┘
└────────┬─────────┘                        ▲
         │                                  │
         ▼                                  │
┌──────────────────┐                       │
│ bank_data_parse  │───────────────────────┘
└──────────────────┘
```

**Execution Order** (with `finances flow`):
1. `ynab_sync` (if stale)
2. `bank_data_retrieve` (if new exports available)
3. `bank_data_parse` (if retrieve ran or new raw files)
4. `bank_data_reconcile` (if parse or ynab_sync ran)

### 5.3 CLI Command Integration

**Existing Behavior** (standalone):
```bash
finances bank retrieve
finances bank parse
finances bank reconcile
```

**New Behavior** (via flow):
```bash
# Run all nodes
finances flow

# Run specific nodes
finances flow bank_data_retrieve bank_data_parse bank_data_reconcile

# Run with dependencies
finances flow bank_data_reconcile  # Auto-runs parse + retrieve if stale
```

**No CLI Changes Required**: Existing commands continue to work, flow integration is additive.

## 6. Type Safety and Domain Models

### 6.1 Type Preservation

All nodes maintain type-safe Money and FinancialDate usage:

```python
# Existing business logic already uses types correctly
def reconcile_account_balances(...) -> dict[str, ReconciliationResult]:
    # Money types preserved throughout
    bank_balance: Money = balance_point.amount
    ynab_balance: Money = ynab_balances.get(date, Money.from_cents(0))
    difference: Money = bank_balance - ynab_balance
```

**FlowNode wrappers don't change types**, they only:
- Call existing typed functions
- Serialize typed results to JSON (using `.to_dict()`)
- Deserialize JSON back to typed models (using `.from_dict()`)

### 6.2 JSON Serialization

```python
# In execute() methods
result = parse_account_data(config, base_dir)

# Serialize domain models to JSON
output_data = {
    "account_slug": account.slug,
    "parsed_at": datetime.now().isoformat(),
    "transactions": [tx.to_dict() for tx in result.transactions],
    "balance_points": [bp.to_dict() for bp in result.balance_points],
}

write_json(output_file, output_data)
```

## 7. Testing Strategy

### 7.1 Unit Tests

**File**: `tests/unit/bank_accounts/test_flow.py`

**Coverage**:
- OutputInfo validation logic
- DataStore save/load/exists methods
- File cleanup protection (verify all files in outputs)

### 7.2 Integration Tests

**File**: `tests/integration/bank_accounts/test_flow_integration.py`

**Coverage**:
- Each node's execute() method with real files
- DataStore operations with temporary directories
- FlowResult outputs include correct files

### 7.3 E2E Tests

**File**: `tests/e2e/test_bank_accounts_flow.py`

**Coverage**:
- `finances flow bank_data_retrieve bank_data_parse bank_data_reconcile`
- Verify files created in correct directories
- Verify flow system change detection (skip if no new data)

## 8. Implementation Checklist

- [ ] Create `src/finances/bank_accounts/flow.py` with 3 FlowNode classes
- [ ] Create `src/finances/bank_accounts/datastore.py` with 2 DataStore classes
- [ ] Update `src/finances/cli/flow.py` to register bank account nodes
- [ ] Write unit tests for OutputInfo and DataStore classes
- [ ] Write integration tests for node execute() methods
- [ ] Write E2E test for full flow command
- [ ] Update `dev/todos.md` to mark flow integration task complete
- [ ] Create PR with design document and implementation

## 9. Open Questions

None - design is complete and ready for implementation.

## 10. References

- **Existing Patterns**: Amazon flow (Pattern C for matching), Apple flow (Pattern C for matching)
- **DataStore Protocol**: `src/finances/core/datastore.py`
- **DataStoreMixin**: `src/finances/core/datastore_mixin.py`
- **Flow Registry**: `src/finances/cli/flow.py`
- **Bank Accounts Config**: `src/finances/bank_accounts/config.py`
- **Existing Nodes**: `src/finances/bank_accounts/nodes/`
