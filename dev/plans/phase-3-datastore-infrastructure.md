# Phase 3: DataStore Infrastructure

## Goal

Create consistent data persistence API across all domains with integrated archival support.

## Problem Statement

Current state:
- Each domain has ad-hoc file reading/writing
- No consistent pattern for checking data age or existence
- Archive system separate from normal persistence
- Difficult to implement "data summary" consistently

Target state:
- `DataStore` protocol defines standard interface
- Each domain implements its own DataStore
- Archive system integrates seamlessly
- Easy to query data state (age, existence, size)

## Key Changes

### 1. DataStore Protocol

**File:** `src/finances/core/datastore.py` (NEW)

```python
class DataStore(Protocol[T]):
    """Protocol for domain data persistence."""

    def exists(self) -> bool:
        """Check if data exists."""
        ...

    def load(self) -> T:
        """Load data from storage."""
        ...

    def save(self, data: T) -> None:
        """Save data to storage."""
        ...

    def age(self) -> timedelta | None:
        """Get age of data (None if doesn't exist)."""
        ...

    def last_modified(self) -> datetime | None:
        """Get last modification time."""
        ...

    def size_bytes(self) -> int | None:
        """Get size in bytes."""
        ...

    def summary(self) -> str:
        """Get human-readable summary."""
        ...
```

### 2. Domain-Specific Implementations

Each domain gets its own DataStore:

- **YnabDataStore**: Manages YNAB cache files (accounts, transactions, categories)
- **AmazonDataStore**: Manages Amazon raw data and match results
- **AppleDataStore**: Manages Apple receipts and match results
- **YnabEditsDataStore**: Manages YNAB edit files
- **CashFlowDataStore**: Manages cash flow analysis outputs

### 3. Integration with Archive System

Update `src/finances/core/archive.py` to work with DataStores:

```python
def create_domain_archive(store: DataStore, reason: str) -> ArchiveManifest:
    """Archive data from a DataStore."""
    # Seamless integration
```

## Benefits

1. **Consistency**: All domains follow same patterns
2. **Testability**: Easy to mock for testing
3. **Discoverability**: Clear interface for new developers
4. **Feature Support**: Easy to add features like compression, validation

## Testing Strategy

- Unit tests for base DataStore utilities
- Integration tests for each domain's DataStore
- E2E tests verify archiving works with new system

## Definition of Done

- [ ] DataStore protocol defined
- [ ] All 5 domain DataStores implemented
- [ ] Archive system integrated with DataStores
- [ ] Flow system uses DataStores for data summary
- [ ] All tests passing

## Estimated Effort

- **Design & Protocol**: 2-3 hours
- **Implementations**: 8-10 hours (5 domains × 2 hours)
- **Integration**: 4-6 hours
- **Testing**: 4-6 hours
- **Total**: 18-25 hours (3-4 work days)

## Dependencies

- Phase 1 complete (CLI simplified)
- Phase 2 complete (types make DataStore implementations cleaner)
