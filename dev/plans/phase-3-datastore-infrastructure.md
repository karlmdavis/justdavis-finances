# Phase 3: DataStore Infrastructure

## Goal

Extract data management logic from FlowNodes into reusable DataStore components for better
separation of concerns and testability.

## Problem Statement

**Current state (post-Phase 1 & 2):**
- FlowNodes directly implement data checking and summary logic (see `*.flow.py` files)
- Data access patterns duplicated across similar nodes (e.g., checking file age, counting items)
- FlowNodes mix data persistence concerns with flow orchestration
- Hard to test data operations independently from flow logic
- Archive system separate from data access layer

**Example of current duplication** (from `amazon/flow.py` and `apple/flow.py`):
```python
# Both nodes have nearly identical file age checking logic
csv_files = list(raw_dir.glob("**/Retail.OrderHistory.*.csv"))
latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
age = (datetime.now() - mtime).days
```

**Target state:**
- `DataStore` protocol defines standard data access interface
- Each domain implements its own DataStore encapsulating data operations
- FlowNodes delegate to DataStores for data access and summary
- Archive system integrates with DataStores
- Easy to test data operations independently from flow orchestration

## Key Changes

### 1. DataStore Protocol

**File:** `src/finances/core/datastore.py` (NEW)

Define protocol matching `NodeDataSummary` output from existing FlowNodes:

```python
from pathlib import Path
from typing import Protocol, TypeVar, Generic
from datetime import datetime

T = TypeVar("T")

class DataStore(Protocol[T]):
    """Protocol for domain data persistence and metadata queries."""

    def exists(self) -> bool:
        """Check if data exists."""
        ...

    def load(self) -> T:
        """Load data from storage. Raises if data doesn't exist."""
        ...

    def save(self, data: T) -> None:
        """Save data to storage."""
        ...

    def last_modified(self) -> datetime | None:
        """Get last modification time (None if doesn't exist)."""
        ...

    def age_days(self) -> int | None:
        """Get age in days (None if doesn't exist)."""
        ...

    def item_count(self) -> int | None:
        """Get count of items/records (None if doesn't exist)."""
        ...

    def size_bytes(self) -> int | None:
        """Get total size in bytes (None if doesn't exist)."""
        ...

    def summary_text(self) -> str:
        """Get human-readable summary for display."""
        ...

    def to_node_data_summary(self) -> NodeDataSummary:
        """Convert to NodeDataSummary for FlowNode integration."""
        return NodeDataSummary(
            exists=self.exists(),
            last_updated=self.last_modified(),
            age_days=self.age_days(),
            item_count=self.item_count(),
            size_bytes=self.size_bytes(),
            summary_text=self.summary_text(),
        )
```

### 2. Domain-Specific Implementations

Extract existing logic from FlowNodes into DataStore implementations:

**Amazon Domain:**
- `AmazonRawDataStore`: Manages raw CSV files (extracted from ZIPs)
  - Extracted from `AmazonUnzipFlowNode.get_data_summary()`
  - Pattern: Glob for `**/Retail.OrderHistory.*.csv`, aggregate stats
- `AmazonMatchResultsStore`: Manages transaction match results
  - Extracted from `AmazonMatchingFlowNode.get_data_summary()`
  - Pattern: JSON files in `transaction_matches/`

**Apple Domain:**
- `AppleEmailStore`: Manages email files (`.eml` format)
  - Extracted from `AppleEmailFetchFlowNode.get_data_summary()`
  - Pattern: Count `.eml` files in `emails/` directory
- `AppleReceiptStore`: Manages parsed receipt JSON files
  - Extracted from `AppleReceiptParsingFlowNode.get_data_summary()`
  - Pattern: Count `.json` files in `exports/` directory
- `AppleMatchResultsStore`: Manages transaction match results
  - Extracted from `AppleMatchingFlowNode.get_data_summary()`
  - Pattern: JSON files in `transaction_matches/`

**YNAB Domain:**
- `YnabCacheStore`: Manages YNAB cache (transactions, accounts, categories)
  - Extracted from `YnabSyncFlowNode.get_data_summary()`
  - Pattern: Check `transactions.json` age and count
- `YnabEditsStore`: Manages YNAB edit files
  - Extracted from `RetirementUpdateFlowNode.get_data_summary()`
  - Pattern: Check retirement edit files in `edits/`

**Analysis Domain:**
- `CashFlowResultsStore`: Manages cash flow analysis outputs
  - Currently no dedicated FlowNode, but pattern exists
  - Pattern: Check for chart files in `cash_flow/charts/`

### 3. FlowNode Integration

Update existing FlowNodes to delegate to DataStores:

**Before (current):**
```python
class AmazonUnzipFlowNode(FlowNode):
    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        raw_dir = self.data_dir / "amazon" / "raw"
        if not raw_dir.exists():
            return NodeDataSummary(exists=False, ...)

        csv_files = list(raw_dir.glob("**/Retail.OrderHistory.*.csv"))
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        # ... more logic ...
```

**After (with DataStore):**
```python
class AmazonUnzipFlowNode(FlowNode):
    def __init__(self, data_dir: Path):
        super().__init__("amazon_unzip")
        self.store = AmazonRawDataStore(data_dir / "amazon" / "raw")

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        return self.store.to_node_data_summary()
```

### 4. Integration with Archive System

Update `src/finances/core/archive.py` to optionally work with DataStores:

```python
def archive_datastore(
    store: DataStore,
    archive_dir: Path,
    reason: str
) -> ArchiveManifest:
    """
    Archive data from a DataStore.

    Complements existing archive functions while working with new abstraction.
    """
    if not store.exists():
        raise ValueError("Cannot archive non-existent data")

    # Use existing archive infrastructure, but query through DataStore
    # This bridges new DataStore API with existing archive.py functions
    ...
```

## Benefits

1. **Separation of Concerns**: FlowNodes focus on orchestration, DataStores handle data access
2. **Testability**: Test data operations independently from flow logic
3. **Reusability**: DataStores can be used outside flow context (e.g., in scripts, analysis)
4. **Consistency**: Eliminates duplicated file age/count logic across domains
5. **Discoverability**: Clear interface for data access patterns
6. **Feature Support**: Easy to add caching, validation, compression at DataStore level

## Migration Strategy

This is a **refactoring phase** - extracting existing logic, not adding new features:

1. **Extract**: Create DataStore implementations by moving logic from FlowNode methods
2. **Integrate**: Update FlowNodes to use DataStores (constructor injection)
3. **Test**: Ensure behavior unchanged (existing tests should still pass)
4. **Clean up**: Remove duplicated code from FlowNodes

**Critical constraint**: All existing E2E and integration tests must pass without modification.
This is pure refactoring - same behavior, better structure.

## Testing Strategy

**Primary verification:**
- All existing tests continue to pass (no changes needed)
- This validates refactoring preserved behavior

**New tests (minimal):**
- Unit tests for DataStore implementations (test extracted logic in isolation)
- Integration tests showing DataStores work with real file system

**No changes needed:**
- E2E flow tests (behavior unchanged)
- FlowNode integration tests (contracts preserved)

## Definition of Done

**Phase completion checklist:**

- [ ] `DataStore` protocol defined in `src/finances/core/datastore.py`
- [ ] DataStore implementations for all domains:
  - [ ] Amazon: `AmazonRawDataStore`, `AmazonMatchResultsStore`
  - [ ] Apple: `AppleEmailStore`, `AppleReceiptStore`, `AppleMatchResultsStore`
  - [ ] YNAB: `YnabCacheStore`, `YnabEditsStore`
  - [ ] Analysis: `CashFlowResultsStore`
- [ ] FlowNodes updated to use DataStores:
  - [ ] `AmazonUnzipFlowNode` uses `AmazonRawDataStore`
  - [ ] `AmazonMatchingFlowNode` uses `AmazonMatchResultsStore`
  - [ ] `AppleEmailFetchFlowNode` uses `AppleEmailStore`
  - [ ] `AppleReceiptParsingFlowNode` uses `AppleReceiptStore`
  - [ ] `AppleMatchingFlowNode` uses `AppleMatchResultsStore`
  - [ ] `YnabSyncFlowNode` uses `YnabCacheStore`
  - [ ] `RetirementUpdateFlowNode` uses `YnabEditsStore`
- [ ] Archive system integration (optional helper function)
- [ ] All existing tests passing (317 tests, 69%+ coverage)
- [ ] No E2E or integration tests modified (behavior preserved)
- [ ] Code quality checks pass (Black, Ruff, Mypy)

## Estimated Effort

**Revised estimates (post-Phase 1 & 2):**

- **Protocol design**: 1-2 hours (simpler now that patterns exist)
- **DataStore implementations**: 6-8 hours
  - Amazon (2 stores): 1.5 hours
  - Apple (3 stores): 2 hours
  - YNAB (2 stores): 1.5 hours
  - Analysis (1 store): 1 hour
  - Testing extracted logic: 1-2 hours
- **FlowNode integration**: 3-4 hours (mostly mechanical updates)
- **Archive integration**: 1-2 hours (optional bridge function)
- **Testing & validation**: 2-3 hours (verify all tests pass)

**Total: 13-19 hours (2-3 work days)**

Reduced from original 18-25 hours because:
- Phase 1 already implemented data summary patterns
- Clear examples in existing FlowNodes to extract from
- No new features - pure refactoring

## Dependencies

- ✅ Phase 1 complete (CLI simplified, FlowNodes exist)
- ✅ Phase 2 complete (Money/FinancialDate types available)

## Post-Phase Benefits

**For Phase 4 (Domain Models):**
- DataStores provide clean abstraction for model persistence
- Easier to swap underlying storage formats

**For Phase 5 (Test Overhaul):**
- DataStore unit tests are naturally isolated
- Easier to mock DataStores in FlowNode tests

**For future development:**
- Add caching at DataStore level (transparent to FlowNodes)
- Add validation/schema checking at persistence boundary
- Support alternative storage backends (SQLite, remote API)
