# Dict-to-Domain Model Migration Opportunities

**Analysis Date**: 2025-10-17
**Current Branch**: feature/phase-4.5-domain-models
**Purpose**: Identify dict usage that should be converted to proper domain models

## Executive Summary

The codebase has **3 major areas** where dicts are being used to represent structured domain data instead of proper domain models:

1. **Amazon Match Results** (HIGH PRIORITY) - Match candidates and match results
2. **Apple Match Results** (MEDIUM PRIORITY) - Similar pattern to Amazon
3. **Flow System Results** (LOW PRIORITY) - Generic result structures

## Priority 1: Amazon Match Results 🔴

### Current Problem

The Amazon matching system uses `dict[str, Any]` to represent match candidates and results throughout the matching pipeline, despite having an `AmazonMatch` domain model defined.

### Evidence

**Model Definition** (`src/finances/amazon/models.py:287-312`):
```python
@dataclass
class AmazonMatch:
    """Single Amazon match candidate for a YNAB transaction."""
    amazon_orders: list[AmazonOrderItem]
    match_method: str
    confidence: float
    account: str
    total_match_amount: Money
    unmatched_amount: Money = field(default_factory=lambda: Money.from_cents(0))
    matched_item_indices: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

**Actual Usage** (`src/finances/amazon/models.py:315-328`):
```python
@dataclass
class AmazonMatchResult:
    transaction: "YnabTransaction"
    matches: list[Any]  # TODO(Phase 5): Change to list[AmazonMatch]
    best_match: Any | None  # TODO(Phase 5): Change to AmazonMatch | None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Dict Structure Being Used

**Created by** `MatchScorer.create_match_result()` (`scorer.py:64-95`):
```python
{
    "account": str,                    # Amazon account name
    "amazon_orders": list[dict],       # List of order dicts
    "match_method": str,               # "complete_order", "split_payment"
    "confidence": float,               # 0.0 to 1.0
    "total_match_amount": int,         # Total in cents
    "unmatched_amount": int,           # For split payments
}
```

**Order dict structure** (from `OrderGroup.to_dict()`):
```python
{
    "order_id": str,
    "items": list[dict],               # MatchedOrderItem dicts
    "total": int,                      # Total in cents
    "order_date": str,                 # ISO format
    "ship_dates": list[str],           # ISO format dates
    "grouping_level": str,             # "order" or "shipment"
}
```

### Impact Analysis

**Files Using Dict Matches**:
1. `amazon/matcher.py` - Creates, sorts, selects best match from dicts
2. `amazon/scorer.py` - Creates match result dicts
3. `amazon/split_matcher.py` - Creates split payment match dicts
4. `amazon/flow.py` - Consumes match dicts, serializes to JSON
5. `amazon/datastore.py` - Reads/writes match dicts to JSON

**Operations on Dicts**:
- `matcher.py:193-214` - `_select_best_match()` sorts by confidence and method
- `matcher.py:216-255` - `convert_match_result_for_json()` deep copies and formats
- `flow.py:199-212` - Extracts match dict fields for serialization
- `split_matcher.py:222-240` - Constructs complex match dict structure

### Migration Strategy

**Phase 1: Create Proper AmazonMatch Instances**
1. Update `MatchScorer.create_match_result()` to return `AmazonMatch` instead of dict
2. Update `SplitPaymentMatcher.match_split_payment()` to return `AmazonMatch`
3. Change `AmazonMatchResult.matches` from `list[Any]` to `list[AmazonMatch]`
4. Change `AmazonMatchResult.best_match` from `Any | None` to `AmazonMatch | None`

**Phase 2: Add Domain Model Methods**
1. Add `AmazonMatch.to_dict()` for JSON serialization
2. Add `AmazonMatch.from_dict()` for JSON deserialization
3. Add `AmazonMatch.total_amount` property to replace dict access
4. Add comparison methods for sorting by confidence

**Phase 3: Update Consumers**
1. Update `SimplifiedMatcher._select_best_match()` to work with `AmazonMatch` objects
2. Update `SimplifiedMatcher.convert_match_result_for_json()` to call `.to_dict()`
3. Update flow nodes to call `.to_dict()` for serialization
4. Update datastore to deserialize from dict to `AmazonMatch`

**Benefits**:
- ✅ Type safety - mypy can catch field access errors
- ✅ IDE autocomplete - discover available fields
- ✅ Validation - ensure required fields are present
- ✅ Consistency - single source of truth for match structure
- ✅ Testability - easier to mock and test with proper types

**Risks**:
- ⚠️ Moderate refactoring effort across 5 files
- ⚠️ Need to preserve JSON serialization format for compatibility
- ⚠️ Split payment logic is complex and needs careful testing

### Estimated Effort

- **Lines of code**: ~200-300 lines changed across 5 files
- **Test updates**: ~50-100 lines in test files
- **Estimated time**: 4-6 hours
- **Risk level**: MEDIUM - Complex logic but well-tested

## Priority 2: Apple Match Results ⚠️

### Current Problem

Apple matching also uses dicts for match results, but with a simpler structure since Apple uses the core `MatchResult` model.

### Evidence

**Apple flow serialization** (`apple/flow.py:295-315`):
```python
"matches": [
    {
        "transaction_id": result.transaction.id if result.transaction else None,
        "transaction_date": result.transaction.date_obj.date.isoformat(),
        "transaction_amount": result.transaction.amount_money.to_milliunits(),
        "receipt_ids": [r.id for r in result.receipts],
        "matched": bool(result.receipts),
        "confidence": result.confidence,
        "match_method": result.match_method,
    }
    for result in results
]
```

**Apple matcher best_match** (`apple/matcher.py:193`):
```python
best_match = receipt.to_dict()  # Receipt dict for storage
```

### Impact Analysis

**Files Using Dict Structures**:
1. `apple/matcher.py` - Converts Receipt to dict for best_match
2. `apple/flow.py` - Creates inline dict structures for JSON serialization

**Operations**:
- Creating ad-hoc dicts for JSON output in flow nodes
- Using `Receipt.to_dict()` for single receipt storage

### Migration Strategy

**Lower Priority Because**:
- Apple uses proper `MatchResult` domain model for most operations
- Dict usage is mostly for JSON serialization in flow nodes
- No complex dict manipulation logic like Amazon

**Potential Improvements**:
1. Create `AppleMatchSummary` dataclass for flow serialization
2. Add `MatchResult.to_dict()` method to core model
3. Standardize JSON output format across domains

### Estimated Effort

- **Lines of code**: ~50-100 lines
- **Test updates**: ~20-30 lines
- **Estimated time**: 2-3 hours
- **Risk level**: LOW - Simple serialization logic

## Priority 3: Flow System Results 🟢

### Current Problem

The flow system uses `list[Any]` for generic result storage.

### Evidence

**Flow result field** (`core/models.py:258`):
```python
@dataclass
class FlowResult:
    # ... other fields ...
    results: list[Any] = field(default_factory=list)
```

### Impact Analysis

This is by design - flow results are intentionally generic to support different node types. The `list[Any]` is appropriate here because:

1. Different node types produce different result structures
2. Results are opaque to the flow engine
3. Each node is responsible for its own result structure

### Migration Strategy

**RECOMMENDATION: No action needed**

The generic `list[Any]` is the right choice for the flow system. Domain-specific nodes should handle their own type safety.

## Dict Usage Categories: Appropriate vs Needs Migration

### ✅ APPROPRIATE Dict Usage (No Action Needed)

**1. JSON/Config Loading** (`loader.py`, `config.py`)
- Purpose: Deserialize JSON to domain models
- Pattern: `dict[str, Any]` → domain model via `from_dict()`

**2. Generic Metadata** (`metadata: dict[str, Any]`)
- Purpose: Extensible key-value storage
- Pattern: Optional metadata fields in domain models

**3. Function Parameters** (`kwargs: Any`)
- Purpose: Flexible function arguments
- Pattern: Type-safe wrapper around dict arguments

**4. Grouping/Indexing** (`dict[str, DomainModel]`)
- Purpose: Efficient lookup by key
- Pattern: `dict[order_id, OrderGroup]`

**5. Serialization Output** (`to_dict()` methods)
- Purpose: Convert domain models to JSON-compatible format
- Pattern: Domain model → `dict[str, Any]` for JSON

### ❌ NEEDS MIGRATION (Domain Data as Dict)

**1. Amazon Match Results**
- Current: `dict[str, Any]` with match data
- Should be: `AmazonMatch` domain model
- Files: matcher.py, scorer.py, split_matcher.py

**2. Amazon Order Dicts in Matches**
- Current: `list[dict]` for amazon_orders
- Should be: `list[OrderGroup]` or keep as dict for JSON compat
- Note: OrderGroup already has `to_dict()`, just need to use it consistently

## Recommendations

### Immediate Next Steps

1. **Start with Amazon Match Results** (Phase 5 already has TODO comments)
   - Update `MatchScorer.create_match_result()` to return `AmazonMatch`
   - Update `AmazonMatchResult` type annotations
   - Add `AmazonMatch.to_dict()` / `from_dict()` methods

2. **Create Feature Branch** (`feature/phase-5-amazon-match-models`)
   - Keep separate from phase-4.5 to avoid conflicts
   - Focus only on Amazon domain models

3. **Write Tests First**
   - Test `AmazonMatch` construction and validation
   - Test serialization/deserialization round-trip
   - Test sorting and comparison methods

### Long-term Improvements

1. **Standardize Match Result Pattern**
   - Create common interface/base class for match results
   - Ensure Apple and Amazon use consistent patterns

2. **Type-Safe Matching Pipeline**
   - Full type annotations with no `Any` types
   - Strict mypy checking on matching code

3. **Domain Model Guidelines**
   - Document when to use domain models vs dicts
   - Add patterns to CONTRIBUTING.md

## Metrics

**Current State**:
- Domain models: Transaction, Receipt, AmazonOrderItem, OrderGroup, YnabTransaction
- Dict-based structures: Match results, order dicts in matches
- Files with `dict[str, Any]` return types: 24 files
- Files with `Any` type annotations: 6 files

**Target State** (After Phase 5):
- All match results: Proper domain models
- All match pipeline: Type-safe with no `Any`
- Dicts only for: Config loading, JSON I/O, metadata, indexing

## Conclusion

The highest-value migration is **Amazon Match Results** → `AmazonMatch` domain model.
This aligns with existing TODO comments in the code and provides immediate benefits:
- Type safety in matching logic
- Better IDE support
- Easier testing and validation
- Foundation for future domain model work

The code already has the `AmazonMatch` model defined - it just needs to be used!
