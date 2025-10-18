# Phase 4.5: Domain Model Completion - Eliminate Dict/DataFrame Usage

**Status:** ✅ **COMPLETE** (PR #14 merged 2025-10-18)
**Branch:** `feature/phase-4.5-domain-models`
**Complexity:** High
**Actual Effort:** ~16 hours (within estimates)

## Executive Summary

Complete the domain model migration started in Phase 4 by eliminating all dict and DataFrame usage
  for complex data structures throughout the codebase.
Every major data transformation should use type-safe domain models.
This refactoring uses a bottom-up approach (Loaders → Calculators → Matchers → Flow) with strong
  TDD focus to ensure zero regressions.

**Approach:** Bottom-Up (Layer by layer, type safety propagates upward)

## Success Criteria

1. ✅ All loaders return domain models (no dicts/DataFrames for complex structures).
2. ✅ All calculators accept domain models as parameters.
3. ✅ All matchers use domain models internally and in return values.
4. ✅ All flow nodes load and pass domain models directly.
5. ✅ No `transform_*` functions remaining (e.g., `transform_apple_receipt_data`).
6. ✅ No temporary adapter code (e.g., `orders_to_dataframe`) remaining.
7. ✅ Merge `todos.md` into `dev/todos.md` and mark completed items.
8. ✅ Zero deprecated/legacy code or backward compatibility shims.
9. ✅ Zero stubs or incomplete implementations.
10. ✅ Minimal changes to E2E tests (only if fixing discovered bugs).
11. ✅ All existing tests pass without modification (pure refactoring).

## Context

### Problem Statement

Current codebase has partially completed domain model migration:
- **Done:** Amazon/Apple/YNAB domain models exist (`AmazonOrderItem`, `ParsedReceipt`,
    `YnabTransaction`).
- **Done:** Type-safe primitives (`Money`, `FinancialDate`) exist.
- **Not Done:** Many components still use dicts/DataFrames:
  - Apple loader returns dicts instead of `ParsedReceipt` objects.
  - Split calculators accept dict lists instead of domain models.
  - Matchers pass around dicts for transactions and results.
  - Flow nodes load JSON dicts and manually transform data.
  - Manual transform functions like `transform_apple_receipt_data()` exist.

### Why This Matters

**Type Safety:** Catch errors at development time, not runtime.

**Maintainability:** Clear interfaces make code easier to understand and modify.

**Testing:** Domain models make unit tests simpler (no dict mocking).

**Consistency:** All domains (Amazon/Apple/YNAB) use same patterns.

**Future-Proof:** Foundation for future features like validation, serialization, migrations.

## Architecture Overview

### Bottom-Up Refactoring Layers

```
┌─────────────────────────────────────────────────┐
│  Layer 4: Flow Nodes                            │
│  - Load domain models from JSON/DataStore       │
│  - Pass models to matchers/calculators          │
│  - No dict transformations                      │
└─────────────────┬───────────────────────────────┘
                  │ Uses
┌─────────────────▼───────────────────────────────┐
│  Layer 3: Matchers                              │
│  - Accept YnabTransaction (not dict)            │
│  - Internal processing uses domain models       │
│  - Return structured MatchResult objects        │
└─────────────────┬───────────────────────────────┘
                  │ Uses
┌─────────────────▼───────────────────────────────┐
│  Layer 2: Calculators (Split Generation)        │
│  - Accept domain models (AmazonOrderItem, etc.) │
│  - Return structured split results              │
│  - No transform functions needed                │
└─────────────────┬───────────────────────────────┘
                  │ Uses
┌─────────────────▼───────────────────────────────┐
│  Layer 1: Loaders (Data Access)                 │
│  - Load JSON and return domain models           │
│  - No DataFrame output for complex data         │
│  - YNAB: list[YnabTransaction] ✅               │
│  - Amazon: list[AmazonOrderItem] ✅             │
│  - Apple: list[ParsedReceipt] ❌ (needs work)   │
└─────────────────────────────────────────────────┘
```

### Current State Analysis

| Component | Current Return Type | Target Return Type | Status |
|-----------|---------------------|-------------------|---------|
| **Loaders** | | | |
| `ynab.loader.load_transactions()` | `list[YnabTransaction]` | ✅ No change | Done |
| `amazon.loader.load_orders()` | `dict[str, list[AmazonOrderItem]]` | ✅ No change | Done |
| `amazon.loader.orders_to_dataframe()` | `pd.DataFrame` | ❌ Remove | Temp adapter |
| `apple.loader.load_apple_receipts()` | `list[dict]` | `list[ParsedReceipt]` | Needs work |
| `apple.loader.normalize_apple_receipt_data()` | `pd.DataFrame` | ❌ Remove | Temp adapter |
| **Calculators** | | | |
| `split_calculator.calculate_amazon_splits()` | `list[dict]` (splits) | `list[dict]` (splits) | Params need work |
| `split_calculator.calculate_apple_splits()` | `list[dict]` (splits) | `list[dict]` (splits) | Params need work |
| `split_generation_flow.transform_apple_receipt_data()` | `tuple` | ❌ Remove entirely | Legacy |
| **Matchers** | | | |
| `amazon.matcher.match_transaction()` | `dict` (result) | Structured result | Needs work |
| `apple.matcher.match_single_transaction()` | `MatchResult` | ✅ No change | Done |
| **Flow Nodes** | | | |
| `split_generation_flow.execute()` | Uses dicts | Use domain models | Needs work |
| `amazon/apple matching flow` | Uses DataFrames | Use domain models | Needs work |

## Implementation Plan

### Layer 1: Loaders (Data Access) - 3-4 hours

**Goal:** All loaders return domain models, eliminate temporary DataFrame adapters.

#### 1.1: Apple Loader Refactoring

**File:** `src/finances/apple/loader.py`

**Changes:**
1. Update `load_apple_receipts()` to return `list[ParsedReceipt]`:
   - Load JSON files.
   - Use `ParsedReceipt` constructor or factory method.
   - Return fully typed objects.
2. Remove `normalize_apple_receipt_data()` function (DataFrame adapter).
3. Add helper: `receipts_to_dataframe()` as temporary adapter if needed by existing code.

**TDD Approach:**
```python
# Test: test_apple_loader_returns_domain_models
def test_load_apple_receipts_returns_parsed_receipt_objects():
    receipts = load_apple_receipts(test_export_path)
    assert all(isinstance(r, ParsedReceipt) for r in receipts)
    assert receipts[0].total.to_cents() > 0
    assert isinstance(receipts[0].receipt_date, FinancialDate)
```

**Success Criteria:**
- `load_apple_receipts()` returns `list[ParsedReceipt]`.
- All receipt fields are properly typed (`Money`, `FinancialDate`, `ParsedItem`).
- Unit tests for loader pass.
- E2E tests still pass (may need adapter temporarily).

#### 1.2: Amazon Loader Cleanup

**File:** `src/finances/amazon/loader.py`

**Changes:**
1. Remove `orders_to_dataframe()` adapter function entirely.
2. Update any internal code using it to work with `list[AmazonOrderItem]` directly.

**TDD Approach:**
```python
# Test: test_amazon_loader_no_dataframe_adapter
def test_load_orders_returns_domain_models_only():
    orders = load_orders()
    for account_orders in orders.values():
        assert all(isinstance(item, AmazonOrderItem) for item in account_orders)
```

**Success Criteria:**
- No DataFrame conversion functions remain.
- Matchers/groupers work directly with domain models or have their own adapters.
- Tests pass.

### Layer 2: Calculators (Split Generation) - 4-5 hours

**Goal:** Split calculators accept domain models and return type-safe split models.

#### 2.0: Create Split Generation Domain Models (NEW)

**File:** `src/finances/ynab/models.py`

**Goal:** Standardize split generation data structures with type-safe domain models instead of dicts.

**New Domain Models:**

1. **YnabSplit** - Individual split/subtransaction

```python
@dataclass
class YnabSplit:
    """
    Individual split (subtransaction) for YNAB transaction edits.

    Represents one line item in a split transaction that will be
    sent to YNAB for application.
    """
    amount: Money  # Split amount (negative for expenses)
    memo: str
    category_id: str | None = None
    payee_id: str | None = None

    def to_ynab_dict(self) -> dict[str, Any]:
        """Convert to YNAB API format (milliunits dict)."""
        result: dict[str, Any] = {
            "amount": self.amount.to_milliunits(),
            "memo": self.memo,
        }
        if self.category_id:
            result["category_id"] = self.category_id
        if self.payee_id:
            result["payee_id"] = self.payee_id
        return result
```

2. **TransactionSplitEdit** - Edit for a single transaction

```python
@dataclass
class TransactionSplitEdit:
    """
    Split edit for a single YNAB transaction.

    Contains the transaction ID and list of splits to apply,
    along with source information for audit trail.
    """
    transaction_id: str
    transaction: YnabTransaction  # Full transaction context
    splits: list[YnabSplit]
    source: str  # "amazon" or "apple"
    confidence: float | None = None  # Match confidence
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "transaction_id": self.transaction_id,
            "splits": [s.to_ynab_dict() for s in self.splits],
            "source": self.source,
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.metadata:
            result["metadata"] = self.metadata
        return result
```

3. **SplitEditBatch** - Collection of edits for file output

```python
@dataclass
class SplitEditBatch:
    """
    Batch of split edits for writing to file.

    Contains multiple transaction edits along with metadata
    about the batch generation process.
    """
    edits: list[TransactionSplitEdit]
    timestamp: str
    amazon_count: int = 0
    apple_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for file output."""
        return {
            "metadata": {
                "timestamp": self.timestamp,
                "amazon_matches_processed": self.amazon_count,
                "apple_matches_processed": self.apple_count,
                "total_edits": len(self.edits),
            },
            "edits": [edit.to_dict() for edit in self.edits],
        }
```

**TDD Approach:**

```python
# Test: test_ynab_split_domain_model
def test_ynab_split_to_dict():
    split = YnabSplit(
        amount=Money.from_dollars("-$12.99"),
        memo="Item 1",
        category_id="cat_123"
    )

    ynab_dict = split.to_ynab_dict()

    assert ynab_dict["amount"] == -12990  # milliunits
    assert ynab_dict["memo"] == "Item 1"
    assert ynab_dict["category_id"] == "cat_123"
    assert "payee_id" not in ynab_dict  # Not included if None

# Test: test_transaction_split_edit_domain_model
def test_transaction_split_edit_to_dict():
    transaction = YnabTransaction(
        id="tx1",
        date=FinancialDate.today(),
        amount=Money.from_dollars("-$15.99"),
        ...
    )
    splits = [
        YnabSplit(amount=Money.from_dollars("-$10.00"), memo="Item 1"),
        YnabSplit(amount=Money.from_dollars("-$5.99"), memo="Item 2"),
    ]
    edit = TransactionSplitEdit(
        transaction_id="tx1",
        transaction=transaction,
        splits=splits,
        source="amazon",
        confidence=0.95
    )

    edit_dict = edit.to_dict()

    assert edit_dict["transaction_id"] == "tx1"
    assert len(edit_dict["splits"]) == 2
    assert edit_dict["splits"][0]["amount"] == -10000
    assert edit_dict["source"] == "amazon"
    assert edit_dict["confidence"] == 0.95

# Test: test_split_edit_batch_domain_model
def test_split_edit_batch_to_dict():
    tx1 = YnabTransaction(id="tx1", ...)
    tx2 = YnabTransaction(id="tx2", ...)

    edits = [
        TransactionSplitEdit(
            transaction_id="tx1",
            transaction=tx1,
            splits=[YnabSplit(...)],
            source="amazon"
        ),
        TransactionSplitEdit(
            transaction_id="tx2",
            transaction=tx2,
            splits=[YnabSplit(...)],
            source="apple"
        ),
    ]
    batch = SplitEditBatch(
        edits=edits,
        timestamp="2025-10-16_14-30-00",
        amazon_count=1,
        apple_count=1
    )

    batch_dict = batch.to_dict()

    assert batch_dict["metadata"]["total_edits"] == 2
    assert batch_dict["metadata"]["amazon_matches_processed"] == 1
    assert len(batch_dict["edits"]) == 2
```

**Success Criteria:**

- ✅ Domain models created in `src/finances/ynab/models.py`
- ✅ Models have proper type hints (`Money`, `YnabTransaction`, etc.)
- ✅ `to_dict()` / `to_ynab_dict()` methods for JSON serialization
- ✅ Unit tests for all models pass
- ✅ JSON output format unchanged (backward compatible)

**Benefits:**

- **Type safety at boundaries**: Clear interfaces between components
- **Better testing**: Domain models are easier to test than dicts
- **Clear edit file format**: Structured batch output with audit trail
- **Consistency**: Matches pattern used elsewhere in codebase

#### 2.1: Update Split Calculator Signatures

**File:** `src/finances/ynab/split_calculator.py`

**Changes:**
1. Update `calculate_amazon_splits()`:
   ```python
   # Before:
   def calculate_amazon_splits(
       transaction_amount: int | Money,
       amazon_items: list[dict[str, Any]]
   ) -> list[dict[str, Any]]:

   # After:
   def calculate_amazon_splits(
       transaction: YnabTransaction,  # Full transaction context
       amazon_items: list[AmazonOrderItem]  # Domain models
   ) -> list[YnabSplit]:  # Return domain models
   ```

2. Update `calculate_apple_splits()`:
   ```python
   # Before:
   def calculate_apple_splits(
       transaction_amount: int,
       apple_items: list[dict[str, Any]],
       receipt_subtotal: int | None = None,
       receipt_tax: int | None = None,
   ) -> list[dict[str, Any]]:

   # After:
   def calculate_apple_splits(
       transaction: YnabTransaction,
       receipt: ParsedReceipt  # Full receipt with items, subtotal, tax
   ) -> list[YnabSplit]:  # Return domain models
   ```

**TDD Approach:**
```python
# Test: test_amazon_split_calculator_with_domain_models
def test_calculate_amazon_splits_accepts_domain_models():
    transaction = YnabTransaction(
        id="tx1", date=FinancialDate.today(),
        amount=Money.from_dollars("-$45.99"), ...
    )
    items = [
        AmazonOrderItem(
            order_id="123", product_name="Item 1",
            total_owed=Money.from_dollars("$25.00"), ...
        ),
        AmazonOrderItem(
            order_id="123", product_name="Item 2",
            total_owed=Money.from_dollars("$20.99"), ...
        ),
    ]

    splits = calculate_amazon_splits(transaction, items)

    assert len(splits) == 2
    assert all(isinstance(s, YnabSplit) for s in splits)
    assert sum(s.amount.to_milliunits() for s in splits) == transaction.amount.to_milliunits()

# Test: test_apple_split_calculator_with_domain_models
def test_calculate_apple_splits_accepts_parsed_receipt():
    transaction = YnabTransaction(...)
    receipt = ParsedReceipt(
        total=Money.from_dollars("$12.99"),
        subtotal=Money.from_dollars("$11.97"),
        tax=Money.from_dollars("$1.02"),
        items=[
            ParsedItem(title="App 1", cost=Money.from_dollars("$5.99")),
            ParsedItem(title="App 2", cost=Money.from_dollars("$5.98")),
        ]
    )

    splits = calculate_apple_splits(transaction, receipt)

    assert len(splits) == 2
    assert all(isinstance(s, YnabSplit) for s in splits)
    assert sum(s.amount.to_milliunits() for s in splits) == transaction.amount.to_milliunits()
```

**Success Criteria:**
- Calculators accept domain models as parameters.
- Calculators return `list[YnabSplit]` instead of `list[dict]`.
- No dict transformations needed before calling.
- All unit tests for calculators pass.
- Split generation math remains correct (penny-perfect).

#### 2.2: Remove Transform Functions

**File:** `src/finances/ynab/split_generation_flow.py`

**Changes:**
1. Delete `transform_apple_receipt_data()` function entirely (lines 14-61).
2. Update any call sites to use domain models directly.

**TDD Approach:**
```python
# Test: test_no_transform_functions_exist
def test_split_generation_has_no_transform_functions():
    import inspect
    from finances.ynab import split_generation_flow

    functions = [name for name, obj in inspect.getmembers(split_generation_flow)
                 if inspect.isfunction(obj) and name.startswith("transform_")]

    assert len(functions) == 0, f"Found transform functions: {functions}"
```

**Success Criteria:**
- No `transform_*` functions exist in split generation module.
- Flow node loads domain models and passes them directly to calculators.

### Layer 3: Matchers (Transaction Matching) - 3-4 hours

**Goal:** Matchers accept domain models, return structured results, no internal dict usage.

#### 3.1: Amazon Matcher Refactoring

**File:** `src/finances/amazon/matcher.py`

**Changes:**
1. Update `match_transaction()` signature:
   ```python
   # Before:
   def match_transaction(
       self,
       ynab_tx: dict[str, Any],
       account_data: dict[str, tuple[pd.DataFrame, pd.DataFrame]]
   ) -> dict[str, Any]:

   # After:
   def match_transaction(
       self,
       ynab_tx: YnabTransaction,
       account_data: dict[str, list[AmazonOrderItem]]
   ) -> AmazonMatchResult:  # New structured result class
   ```

2. Update internal methods to work with `YnabTransaction` directly (no dict access).

3. Create `AmazonMatchResult` dataclass:
   ```python
   @dataclass
   class AmazonMatchResult:
       transaction: YnabTransaction
       matches: list[AmazonMatch]  # Structured match info
       best_match: AmazonMatch | None
       match_method: str | None
       confidence: float
   ```

4. Remove DataFrame dependencies:
   - Update `_find_complete_matches()` to work with `list[AmazonOrderItem]`.
   - Update grouper/scorer if needed to accept domain models.

**TDD Approach:**
```python
# Test: test_amazon_matcher_with_domain_models
def test_match_transaction_accepts_ynab_transaction():
    matcher = SimplifiedMatcher()
    transaction = YnabTransaction(
        id="tx1", payee_name="Amazon",
        amount=Money.from_dollars("-$45.99"), ...
    )
    account_data = {
        "karl": [AmazonOrderItem(...), AmazonOrderItem(...)]
    }

    result = matcher.match_transaction(transaction, account_data)

    assert isinstance(result, AmazonMatchResult)
    assert result.transaction.id == "tx1"
    if result.best_match:
        assert isinstance(result.best_match.orders[0], AmazonOrderItem)
```

**Success Criteria:**
- `match_transaction()` accepts `YnabTransaction`.
- No DataFrame creation inside matcher (work with lists directly).
- Returns structured `AmazonMatchResult`.
- Matching logic unchanged (same results as before).
- Unit tests pass.

#### 3.2: Apple Matcher Verification

**File:** `src/finances/apple/matcher.py`

**Changes:**
1. Verify `match_single_transaction()` already returns `MatchResult` ✅.
2. Update to accept `YnabTransaction` instead of dict:
   ```python
   # Before:
   def match_single_transaction(
       self,
       ynab_transaction: dict[str, Any],
       apple_receipts_df: pd.DataFrame
   ) -> MatchResult:

   # After:
   def match_single_transaction(
       self,
       ynab_transaction: YnabTransaction,
       apple_receipts: list[ParsedReceipt]
   ) -> MatchResult:
   ```

3. Remove DataFrame dependency:
   - Work with `list[ParsedReceipt]` directly.
   - Update internal filtering/matching to use list operations.

**TDD Approach:**
```python
# Test: test_apple_matcher_with_domain_models
def test_match_single_transaction_accepts_domain_models():
    matcher = AppleMatcher()
    transaction = YnabTransaction(
        id="tx1", payee_name="Apple",
        amount=Money.from_dollars("-$5.99"), ...
    )
    receipts = [
        ParsedReceipt(
            order_id="R1", receipt_date=FinancialDate.today(),
            total=Money.from_dollars("$5.99"), ...
        )
    ]

    result = matcher.match_single_transaction(transaction, receipts)

    assert isinstance(result, MatchResult)
    assert result.transaction.id == "tx1"
    if result.receipts:
        assert isinstance(result.receipts[0], Receipt)
```

**Success Criteria:**
- Matcher accepts `YnabTransaction` and `list[ParsedReceipt]`.
- No DataFrame usage internally.
- Returns `MatchResult` with proper domain models.
- Tests pass.

### Layer 4: Flow Nodes (Orchestration) - 3-4 hours

**Goal:** Flow nodes load domain models from storage and pass them to lower layers.

#### 4.1: Split Generation Flow Node

**File:** `src/finances/ynab/split_generation_flow.py`

**Changes:**
1. Load domain models directly in `execute()`:
   ```python
   # Load YNAB transactions as domain models
   from ..ynab.loader import load_transactions
   from ..ynab.datastore import YnabDataStore

   # Load Amazon orders as domain models
   from ..amazon.loader import load_orders

   # Load Apple receipts as domain models
   from ..apple.loader import load_apple_receipts
   ```

2. Remove all dict-based loading and transformation.

3. Pass domain models to calculators:
   ```python
   # Before:
   tx_amount_milliunits = ynab_tx.get("amount")
   items = amazon_order.get("items", [])
   splits = calculate_amazon_splits(tx_amount_milliunits, items)

   # After:
   splits = calculate_amazon_splits(ynab_transaction, amazon_items)
   ```

4. For Apple receipts:
   ```python
   # Before:
   receipt_data = read_json(receipt_file)
   items, subtotal, tax = transform_apple_receipt_data(receipt_data)
   splits = calculate_apple_splits(tx_amount_milliunits, items, subtotal, tax)

   # After:
   receipt = next(r for r in apple_receipts if r.order_id == receipt_id)
   splits = calculate_apple_splits(ynab_transaction, receipt)
   ```

**TDD Approach:**
```python
# Test: test_split_generation_flow_uses_domain_models
def test_split_generation_flow_loads_domain_models(flow_test_env):
    node = SplitGenerationFlowNode(data_dir=flow_test_env.data_dir)
    context = FlowContext(data_dir=flow_test_env.data_dir)

    result = node.execute(context)

    assert result.success
    # Verify splits were generated without transform functions
```

**Success Criteria:**
- Flow node loads domain models using loaders.
- No JSON dict manipulation.
- No transform functions called.
- Passes domain models to calculators.
- E2E tests pass.

#### 4.2: Amazon Matching Flow Node

**File:** `src/finances/amazon/flow.py`

**Changes:**
1. Load `list[YnabTransaction]` instead of dicts.
2. Load `dict[str, list[AmazonOrderItem]]` (already done by loader).
3. Remove DataFrame conversion:
   ```python
   # Before:
   from ..amazon.loader import load_orders, orders_to_dataframe
   orders = load_orders()
   account_data = {
       account: (orders_to_dataframe(items), pd.DataFrame())
       for account, items in orders.items()
   }

   # After:
   from ..amazon.loader import load_orders
   orders = load_orders()  # Returns dict[str, list[AmazonOrderItem]]
   # Pass directly to matcher
   ```

4. Update matcher calls to pass domain models.

**TDD Approach:**
```python
# Test: test_amazon_matching_flow_no_dataframes
def test_amazon_matching_flow_uses_domain_models(flow_test_env):
    node = AmazonMatchingFlowNode(data_dir=flow_test_env.data_dir)
    context = FlowContext(data_dir=flow_test_env.data_dir)

    result = node.execute(context)

    assert result.success
    # Verify no DataFrame adapters were used
```

**Success Criteria:**
- No `orders_to_dataframe()` calls.
- Matcher receives domain models directly.
- Tests pass.

#### 4.3: Apple Matching Flow Node

**File:** `src/finances/apple/flow.py`

**Changes:**
1. Load `list[ParsedReceipt]` using updated loader.
2. Remove `normalize_apple_receipt_data()` call.
3. Pass `list[ParsedReceipt]` to matcher:
   ```python
   # Before:
   receipts = load_apple_receipts()
   receipts_df = normalize_apple_receipt_data(receipts)
   result = matcher.match_single_transaction(tx_dict, receipts_df)

   # After:
   receipts = load_apple_receipts()  # Returns list[ParsedReceipt]
   result = matcher.match_single_transaction(transaction, receipts)
   ```

**TDD Approach:**
```python
# Test: test_apple_matching_flow_no_dataframes
def test_apple_matching_flow_uses_domain_models(flow_test_env):
    node = AppleMatchingFlowNode(data_dir=flow_test_env.data_dir)
    context = FlowContext(data_dir=flow_test_env.data_dir)

    result = node.execute(context)

    assert result.success
    # Verify no DataFrame normalization was used
```

**Success Criteria:**
- No DataFrame adapter calls.
- Matcher receives `list[ParsedReceipt]`.
- Tests pass.

### Phase Completion Tasks - 1-2 hours

#### 1. Documentation Consolidation

**Files:**
- `todos.md` (root)
- `dev/todos.md`

**Changes:**
1. Merge `todos.md` content into `dev/todos.md`.
2. Mark Phase 4.5 items as completed:
   ```markdown
   ### Split Generation Flow - Domain Model Migration

   **Status:** ✅ Completed (Phase 4.5)
   **Completed:** 2025-10-16

   **Implementation:**
   - All loaders return domain models
   - All calculators accept domain models
   - All matchers use domain models
   - All flow nodes eliminated dict transformations
   - Removed transform_apple_receipt_data()
   - Removed orders_to_dataframe() adapter
   - Removed normalize_apple_receipt_data() adapter
   ```

3. Delete `todos.md` from root (everything now in `dev/todos.md`).

**Success Criteria:**
- Single source of truth for todos: `dev/todos.md`.
- Phase 4.5 work marked complete.
- No duplicate todo lists.

#### 2. Legacy Code Verification

**Task:** Comprehensive search for any remaining legacy patterns.

**Verification Checklist:**
```bash
# 1. No transform functions
grep -r "def transform_" src/finances/

# 2. No DataFrame adapters for domain data
grep -r "to_dataframe\|normalize_.*_data" src/finances/ | grep -v test | grep -v "# "

# 3. No dict-based matcher signatures
grep -r "def match.*ynab_tx: dict" src/finances/

# 4. No deprecated functions
grep -r "@deprecated\|# DEPRECATED\|# TODO.*remove" src/finances/

# 5. No incomplete implementations
grep -r "raise NotImplementedError\|pass  # TODO\|# STUB" src/finances/
```

**Success Criteria:**
- Zero matches for legacy patterns.
- All functions fully implemented.
- No deprecated code markers.

#### 3. E2E Test Verification

**File:** `tests/e2e/test_flow_system.py`

**Task:** Run full E2E test suite and verify zero changes needed.

```bash
uv run pytest tests/e2e/ -v
```

**Success Criteria:**
- All E2E tests pass without modification.
- If tests fail, fix root cause (not test).
- If bug found and fixed, document in PR.

#### 4. Test Coverage Verification

**Task:** Ensure test coverage remains ≥60% (target: 74%+).

```bash
uv run pytest --cov=src/finances --cov-report=term-missing --cov-report=html
```

**Success Criteria:**
- Coverage ≥60% maintained.
- New code has unit tests.
- Critical paths (calculators, matchers) have high coverage.

## Testing Strategy

### Test Pyramid for Phase 4.5

**Priority 1: Unit Tests (Write First)**
- Layer 1 (Loaders): Test domain model construction from JSON/CSV.
- Layer 2 (Calculators): Test split generation with domain models.
- Layer 3 (Matchers): Test matching logic with domain models.

**Priority 2: Integration Tests (Write During)**
- Loader → Calculator integration.
- Loader → Matcher integration.
- Matcher → Calculator → Flow integration.

**Priority 3: E2E Tests (Verify After)**
- Run existing E2E tests without modification.
- Verify end-to-end workflows unchanged.
- Only modify E2E tests if fixing bugs.

### TDD Workflow for Each Layer

```
1. RED:   Write failing unit test for new signature/behavior
2. GREEN: Implement minimal change to pass test
3. REFACTOR: Clean up implementation
4. INTEGRATION: Write integration test
5. VERIFY: Run E2E tests (should still pass)
```

### Example: Layer 1 TDD Cycle

```python
# 1. RED - Write failing test
def test_load_apple_receipts_returns_domain_models():
    receipts = load_apple_receipts(test_export_path)
    assert isinstance(receipts[0], ParsedReceipt)  # FAILS: returns dict

# 2. GREEN - Implement
def load_apple_receipts(export_path: str) -> list[ParsedReceipt]:
    data = read_json(...)
    return [ParsedReceipt.from_dict(d) for d in data]

# 3. REFACTOR - Clean up
def load_apple_receipts(export_path: str) -> list[ParsedReceipt]:
    receipts_file = Path(export_path) / "all_receipts_combined.json"
    data = read_json(receipts_file)
    return [ParsedReceipt.from_dict(receipt) for receipt in data]

# 4. INTEGRATION - Test with next layer
def test_loader_to_matcher_integration():
    receipts = load_apple_receipts(test_path)
    matcher = AppleMatcher()
    result = matcher.match_single_transaction(test_tx, receipts)
    assert result.receipts  # Verify works end-to-end

# 5. VERIFY - Run E2E
pytest tests/e2e/test_flow_system.py  # Should pass unchanged
```

## Risks and Mitigations

### Risk 1: Breaking E2E Tests

**Probability:** Medium

**Impact:** High

**Mitigation:**
- Run E2E tests after each layer completion.
- Keep temporary adapters until all layers complete.
- Roll back if E2E tests fail unexpectedly.

### Risk 2: Performance Regression

**Probability:** Low

**Impact:** Medium

**Mitigation:**
- Domain models are lightweight (dataclasses).
- Avoid unnecessary conversions.
- Profile before/after if concerned.

### Risk 3: Incomplete Migration

**Probability:** Low

**Impact:** High

**Mitigation:**
- Use verification checklist (grep for legacy patterns).
- Code review for completeness.
- Success criteria explicitly require zero legacy code.

### Risk 4: Scope Creep

**Probability:** Medium

**Impact:** Medium

**Mitigation:**
- Strict adherence to layer-by-layer plan.
- Defer unrelated improvements to future phases.
- Document discovered issues for future work.

## Dependencies

### Prerequisites

- Phase 4 completed (domain models exist).
- Phase 3 completed (DataStore infrastructure).
- Phase 2 completed (Money/FinancialDate primitives).
- All tests passing on main branch.

### Blocks

None - this is pure refactoring.

### Blocked By

None - all prerequisites met.

## Deliverables

### Code Artifacts

1. **Updated Loaders**
   - `src/finances/apple/loader.py` - Returns `list[ParsedReceipt]`.
   - `src/finances/amazon/loader.py` - Removes DataFrame adapter.

2. **Updated Calculators**
   - `src/finances/ynab/split_calculator.py` - Accepts domain models.

3. **Updated Matchers**
   - `src/finances/amazon/matcher.py` - Accepts `YnabTransaction`, returns structured result.
   - `src/finances/apple/matcher.py` - Accepts domain models, no DataFrames.

4. **Updated Flow Nodes**
   - `src/finances/ynab/split_generation_flow.py` - No transform functions.
   - `src/finances/amazon/flow.py` - No DataFrame adapters.
   - `src/finances/apple/flow.py` - No DataFrame adapters.

5. **New Domain Models**
   - `src/finances/ynab/models.py` - `YnabSplit`, `TransactionSplitEdit`, `SplitEditBatch`.
   - `src/finances/amazon/models.py` - `AmazonMatchResult` dataclass.

6. **Deleted Code**
   - `transform_apple_receipt_data()` function.
   - `orders_to_dataframe()` adapter.
   - `normalize_apple_receipt_data()` adapter.

### Documentation

1. **Updated Plan**
   - `dev/plans/consolidation-2024/phase-4.5-domain-model-completion.md` (this document).

2. **Consolidated Todos**
   - `dev/todos.md` - Merged and marked complete.
   - `todos.md` - Deleted.

3. **PR Description**
   - Summary of changes.
   - Test plan.
   - Verification steps.

### Testing Artifacts

1. **Unit Tests**
   - `tests/unit/test_apple_loader.py` - Domain model tests.
   - `tests/unit/test_split_calculator.py` - Updated signatures.
   - `tests/unit/test_amazon_matcher.py` - Domain model tests.
   - `tests/unit/test_apple_matcher.py` - Domain model tests.

2. **Integration Tests**
   - `tests/integration/test_loader_to_calculator.py`.
   - `tests/integration/test_loader_to_matcher.py`.

3. **E2E Tests**
   - `tests/e2e/test_flow_system.py` - Should pass unchanged.

## Success Metrics

### Quantitative

- ✅ Zero grep matches for `def transform_`.
- ✅ Zero grep matches for `to_dataframe` in non-test code.
- ✅ Zero grep matches for `dict[str, Any]` in matcher signatures.
- ✅ Test coverage ≥60% (maintain or improve).
- ✅ All 100+ existing tests pass.

### Qualitative

- ✅ Code review approval.
- ✅ No merge conflicts with main.
- ✅ Clear type hints throughout.
- ✅ Consistent domain model usage across all domains.
- ✅ Easy to understand (reduced cognitive load).

## Timeline

### Estimated Breakdown

- **Layer 1 (Loaders):** 3-4 hours
- **Layer 2 (Calculators + Split Models):** 4-5 hours
- **Layer 3 (Matchers):** 3-4 hours
- **Layer 4 (Flow Nodes):** 3-4 hours
- **Completion Tasks:** 1-2 hours

**Total:** 14-19 hours

### Milestones

1. **Layer 1 Complete:** All loaders return domain models, unit tests pass.
2. **Layer 2 Complete:** Calculators accept domain models, unit tests pass.
3. **Layer 3 Complete:** Matchers use domain models, integration tests pass.
4. **Layer 4 Complete:** Flow nodes refactored, E2E tests pass.
5. **Phase Complete:** All verification checks pass, PR ready.

## Related Work

### Previous Phases

- **Phase 1:** CLI Simplification - Unified flow system.
- **Phase 2:** Type-Safe Primitives - Money & FinancialDate.
- **Phase 3:** DataStore Infrastructure - Persistent storage.
- **Phase 4:** Domain Model Migrations - Created models, partial adoption.

### Future Phases

- **Phase 5:** Matcher Refactoring - Eliminate DataFrame usage in matching algorithms.
- **Phase 6:** Validation Layer - Add domain model validation.
- **Phase 7:** Serialization - Standardize JSON serialization across models.

## Notes

### Design Decisions

**Why Bottom-Up?**
Type safety propagates cleanly upward.
Lower layers can't break higher layers during refactoring.
Unit tests guide implementation at each layer.

**Why Keep Split Return Type as dict?**
YNAB API expects specific dict format for splits.
Changing this would require YNAB API wrapper layer.
Out of scope for Phase 4.5 (defer to future phase).

**Why Not Remove All DataFrame Usage?**
Some components (grouper, scorer) use DataFrames for algorithmic efficiency.
Refactoring those is Phase 5 (matcher internals).
Phase 4.5 focuses on data boundaries (loaders, calculators, flow).

### Open Questions

1. Should we create `AmazonMatchResult` dataclass or keep dict for now?
   - **Decision:** Create dataclass for consistency with `MatchResult`.

2. Do we need temporary adapters during migration?
   - **Decision:** Minimize adapters; remove as soon as consumer updated.

## Approval

**Status:** ✅ Approved for Implementation

**Next Steps:**
1. Create feature branch: `feature/phase-4.5-domain-models`.
2. Execute Layer 1 (Loaders) with TDD.
3. Execute Layer 2 (Calculators) with TDD.
4. Execute Layer 3 (Matchers) with TDD.
5. Execute Layer 4 (Flow Nodes) with TDD.
6. Complete verification and documentation tasks.
7. Create pull request with comprehensive summary.
