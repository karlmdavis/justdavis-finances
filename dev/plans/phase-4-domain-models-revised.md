# Phase 4: Domain Model Refactoring (Revised)

**Status:** 🚧 **IN PROGRESS** (Started 2025-10-14)

## Goal

Create clean domain-specific models true to their source formats (CSV, HTML, JSON API), eliminating premature normalization and improving type safety.

## Current State Assessment (Post-Phase 3)

### What We Have

**Phase 2 primitives:**
- ✅ `Money` and `FinancialDate` types available
- ✅ Universal models in `src/finances/core/models.py` (Transaction, Receipt, Account, Category)
- ✅ These have backward compatibility with legacy int/str fields

**Phase 3 DataStores:**
- ✅ DataStore protocol for data persistence
- ✅ Domain-specific DataStores (Amazon, Apple, YNAB, Analysis)
- ✅ Clean separation between flow orchestration and data access

**Current domain implementations:**

1. **YNAB** (`src/finances/ynab/`):
   - ❌ `loader.py` returns raw `dict[str, Any]` from JSON
   - ❌ No domain models - uses universal `Transaction` model or raw dicts
   - ✅ Already has Money/FinancialDate in universal Transaction model

2. **Amazon** (`src/finances/amazon/`):
   - ❌ `loader.py` returns pandas `DataFrame` objects
   - ❌ No domain models - DataFrame columns accessed by string keys
   - ❌ Matching logic works directly with DataFrames
   - ✅ Already uses integer arithmetic for currency (no float issues)

3. **Apple** (`src/finances/apple/`):
   - ✅ `parser.py` has `ParsedReceipt` and `ParsedItem` dataclasses!
   - ⚠️ Uses `int` for cents (not `Money` type)
   - ⚠️ Uses `str` for dates (not `FinancialDate` type)
   - ✅ Good foundation - just needs type upgrades

### Problems to Solve

1. **YNAB**: No domain models, just raw dicts everywhere
2. **Amazon**: DataFrame-based processing loses type safety
3. **Apple**: Good models exist but don't use Money/FinancialDate
4. **All domains**: Premature conversion to universal models

## Revised Implementation Strategy

### Phase 4a: YNAB Domain Models

**Create:** `src/finances/ynab/models.py`

True-to-API models matching YNAB JSON structure:

```python
from dataclasses import dataclass
from finances.core import Money, FinancialDate

@dataclass
class YnabAccount:
    """YNAB account from API."""
    id: str
    name: str
    type: str
    on_budget: bool
    balance: Money
    closed: bool
    deleted: bool
    # Add other YNAB API fields as needed

@dataclass
class YnabCategory:
    """YNAB category from API."""
    id: str
    category_group_id: str
    name: str
    hidden: bool
    deleted: bool
    # Add budgeting fields

@dataclass
class YnabTransaction:
    """YNAB transaction from API."""
    id: str
    date: FinancialDate
    amount: Money
    memo: str | None
    cleared: str  # "cleared", "uncleared", "reconciled"
    approved: bool
    payee_id: str | None
    payee_name: str | None
    category_id: str | None
    category_name: str | None
    account_id: str
    account_name: str | None
    deleted: bool
    # Add subtransactions field if needed
```

**Update:** `src/finances/ynab/loader.py`

Change return types from `list[dict[str, Any]]` to domain models:

```python
def load_ynab_transactions(cache_dir: str | Path | None = None) -> list[YnabTransaction]:
    """Load YNAB transactions from cache as domain models."""
    # Load JSON, convert dicts to YnabTransaction objects
    pass

def load_ynab_accounts(cache_dir: str | Path | None = None) -> list[YnabAccount]:
    """Load YNAB accounts from cache as domain models."""
    pass

def load_ynab_categories(cache_dir: str | Path | None = None) -> list[YnabCategory]:
    """Load YNAB categories from cache as domain models."""
    pass
```

**Testing:**
- Unit tests for model construction and Money/FinancialDate handling
- Integration tests for loader (ensure existing JSON files still load)
- Update existing tests that expect dicts to work with models

**Estimated effort:** 4-6 hours

### Phase 4b: Amazon Domain Models

**Create:** `src/finances/amazon/models.py`

True-to-CSV models matching Amazon Order History Reports:

```python
from dataclasses import dataclass
from finances.core import Money, FinancialDate

@dataclass
class AmazonOrderItem:
    """Single line item from Amazon Order History CSV."""
    order_date: FinancialDate
    order_id: str
    title: str
    category: str
    asin: str
    unspsc_code: str
    website: str
    release_date: FinancialDate | None
    seller: str
    seller_credentials: str
    list_price_per_unit: Money
    purchase_price_per_unit: Money
    quantity: int
    payment_instrument_type: str
    purchase_order_number: str | None
    po_line_number: str | None
    ordering_customer_email: str
    shipment_date: FinancialDate | None
    shipping_address_name: str
    shipping_address_street1: str
    shipping_address_street2: str | None
    shipping_address_city: str
    shipping_address_state: str
    shipping_address_zip: str
    order_status: str
    carrier_name_tracking_number: str | None
    item_subtotal: Money
    item_subtotal_tax: Money
    item_total: Money
    tax_exemption_applied: str | None
    tax_exemption_type: str | None
    exemption_opt_out: str | None
    buyer_name: str
    currency: str
    group_name: str | None

    @property
    def total_price(self) -> Money:
        """Get total price for this line item."""
        return self.item_total
```

**Update:** `src/finances/amazon/loader.py`

Change from DataFrame to domain models:

```python
def load_amazon_data(
    data_dir: str | Path | None = None,
    accounts: tuple[str, ...] = ()
) -> dict[str, list[AmazonOrderItem]]:
    """
    Load Amazon order data as domain models.

    Returns:
        Dictionary mapping account names to lists of AmazonOrderItem objects
    """
    # Read CSVs, convert DataFrame rows to AmazonOrderItem objects
    pass
```

**Update consumers:**
- `src/finances/amazon/matcher.py`: Work with `list[AmazonOrderItem]` instead of DataFrame
- `src/finances/amazon/grouper.py`: Group AmazonOrderItem objects
- `src/finances/amazon/scorer.py`: Score matches using domain models

**Testing:**
- Unit tests for AmazonOrderItem with Money/FinancialDate
- Integration tests for loader (CSV → models)
- Update matcher tests to use models instead of DataFrames
- Ensure E2E tests still pass

**Estimated effort:** 8-10 hours (more complex due to DataFrame removal)

### Phase 4c: Apple Domain Models Enhancement

**Update:** `src/finances/apple/parser.py`

Upgrade existing models to use Money and FinancialDate:

```python
from finances.core import Money, FinancialDate

@dataclass
class ParsedItem:
    """Apple receipt line item."""
    title: str
    cost: Money  # Change from int cents
    quantity: int = 1
    subscription: bool = False
    item_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ParsedReceipt:
    """Apple email receipt."""
    format_detected: str | None = None
    apple_id: str | None = None
    receipt_date: FinancialDate | None = None  # Change from str
    order_id: str | None = None
    document_number: str | None = None

    # Financial data using Money
    subtotal: Money | None = None
    tax: Money | None = None
    total: Money | None = None
    currency: str = "USD"

    # ... rest of fields ...
```

**Update parser logic:**
- Change `_parse_currency()` to return Money objects instead of int cents
- Change `_normalize_date()` to return FinancialDate objects
- Update all field assignments to use new types

**Testing:**
- Unit tests for parser with Money/FinancialDate
- Integration tests for full parsing flow
- Ensure E2E tests still pass

**Estimated effort:** 4-6 hours (smaller scope - models already exist)

### Phase 4d: Rename to Domain-Specific Names

Optional cleanup to make models more discoverable:

- `ParsedReceipt` → `AppleReceipt`
- `ParsedItem` → `AppleReceiptItem`

This makes it clear these are Apple-specific models, not universal models.

**Estimated effort:** 1-2 hours

## Testing Strategy

### Per-Phase Testing

Each phase must pass all existing tests before moving to next phase:

1. **Unit tests**: Test new domain models in isolation
2. **Integration tests**: Test loaders/parsers produce correct models
3. **E2E tests**: Verify CLI commands still work end-to-end
4. **Migration validation**: All 317+ existing tests must pass

### New Tests

- Model construction with various input formats
- Money arithmetic in models
- FinancialDate handling and parsing
- Conversion helpers between domain and universal models

## Definition of Done

- [x] Phase 4a: YNAB domain models
  - [ ] `YnabAccount`, `YnabCategory`, `YnabTransaction` models created
  - [ ] YNAB loader returns domain models instead of dicts
  - [ ] All YNAB tests updated and passing
- [ ] Phase 4b: Amazon domain models
  - [ ] `AmazonOrderItem` model created
  - [ ] Amazon loader returns models instead of DataFrames
  - [ ] Matcher, grouper, scorer updated to use models
  - [ ] All Amazon tests updated and passing
- [ ] Phase 4c: Apple model enhancement
  - [ ] `ParsedReceipt` and `ParsedItem` use Money/FinancialDate
  - [ ] Parser logic updated
  - [ ] All Apple tests updated and passing
- [ ] Phase 4d: Optional rename (if time permits)
  - [ ] Models renamed to domain-specific names
  - [ ] All references updated
- [ ] All phases complete:
  - [ ] All 317+ tests passing
  - [ ] No breaking changes to CLI interface
  - [ ] Code quality checks pass (Black, Ruff, Mypy --strict)
  - [ ] Documentation updated

## Estimated Effort

**Revised based on current state:**

- **Phase 4a (YNAB Models)**: 4-6 hours
  - Model definitions: 2 hours
  - Loader updates: 2 hours
  - Test updates: 2 hours
- **Phase 4b (Amazon Models)**: 8-10 hours
  - Model definition: 2 hours
  - Loader DataFrame → model conversion: 3 hours
  - Matcher/grouper/scorer updates: 3 hours
  - Test updates: 2 hours
- **Phase 4c (Apple Enhancement)**: 4-6 hours
  - Model field updates: 1 hour
  - Parser logic updates: 2 hours
  - Test updates: 2 hours
- **Phase 4d (Rename - Optional)**: 1-2 hours

**Total: 17-24 hours (3-4 work days)**

Reduced from original estimate because:
- Apple models already exist (just need type upgrades)
- No split generator refactoring needed yet (that's future work)
- DataStore infrastructure makes persistence easier

## Dependencies

- ✅ Phase 1 complete (Unified CLI)
- ✅ Phase 2 complete (Money/FinancialDate types)
- ✅ Phase 3 complete (DataStore infrastructure)

## Post-Phase Benefits

**For immediate use:**
- Type-safe domain operations (no more DataFrame string keys!)
- Money arithmetic enforced at type level
- Better IDE support (autocomplete, type checking)
- Clearer data transformations

**For future phases:**
- Split generator can work with typed domain models
- Easier to add validation at model construction time
- DataStore can save/load typed objects instead of dicts
- Clear foundation for adding new data sources

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing integrations | High | Migrate one domain at a time, run full test suite after each |
| DataFrame removal breaks Amazon matching | High | Careful conversion, preserve all matching logic |
| Type errors in existing code | Medium | Fix with mypy --strict, ensure tests cover all code paths |
| Performance regression | Low | Models are lightweight, profile if concerned |

## Notes

- **Do NOT** refactor split generator in this phase - that's future work
- **Do NOT** add validation logic yet - just get types right first
- **Do** maintain backward compatibility where possible
- **Do** ensure all tests pass before considering phase complete
