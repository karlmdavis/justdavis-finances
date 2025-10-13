# Phase 4: Domain Model Refactoring

## Goal

Clean domain models true to their source formats, with split generator handling
normalization internally.

## Problem Statement

Current state:
- Amazon and Apple data prematurely normalized to common format
- Split generator expects normalized input
- Tight coupling between data sources and split generation
- Transformation logic scattered

Target state:
- Each domain has models true to source format (CSV, HTML, JSON)
- Split generator has internal normalizer components
- Clear transformation: Source Format → Domain Model → Normalized Model → Splits
- Loose coupling between domains

## Key Changes

### 1. YNAB Domain Models

**File:** `src/finances/ynab/models.py` (NEW)

True-to-API models:
```python
@dataclass
class YnabAccount:
    id: str
    name: str
    type: str
    on_budget: bool
    balance: Money  # Using Phase 2 Money type
    # ... all YNAB API fields ...

@dataclass
class YnabTransaction:
    id: str
    date: FinancialDate
    amount: Money
    payee_name: str | None
    category_name: str | None
    # ... all YNAB API fields ...
```

### 2. Amazon Domain Models

**File:** `src/finances/amazon/models.py` (REFACTOR)

True-to-CSV models:
```python
@dataclass
class AmazonOrder:
    """Represents one row from Amazon Order History Reports CSV."""
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
    purchase_order_number: str
    po_line_number: str
    ordering_customer_email: str
    shipment_date: FinancialDate | None
    shipping_address_street: str
    # ... all CSV columns ...

    @property
    def total_price(self) -> Money:
        """Calculate total for this line item."""
        return self.purchase_price_per_unit * self.quantity
```

**Remove**: Current normalized format, move to split generator

### 3. Apple Domain Models

**File:** `src/finances/apple/models.py` (REFACTOR)

True-to-HTML models:
```python
@dataclass
class AppleReceiptItem:
    """Single item from Apple email receipt."""
    name: str
    price: Money
    quantity: int
    # May have app-specific fields

@dataclass
class AppleReceipt:
    """Complete Apple receipt from email."""
    receipt_id: str
    date: FinancialDate
    email_subject: str
    items: list[AppleReceiptItem]
    subtotal: Money
    tax: Money | None
    total: Money
    # ... all fields from HTML ...
```

**Remove**: Current normalized format, move to split generator

### 4. Split Generator Refactoring

**File:** `src/finances/ynab/split_generator.py` (NEW architecture)

```python
@dataclass
class NormalizedTransaction:
    """Internal format for split generation."""
    date: FinancialDate
    amount: Money
    description: str
    line_items: list[NormalizedLineItem]
    source: str  # "amazon", "apple", "retirement"

class AmazonToNormalizedTransformer:
    """Transforms Amazon orders to normalized format."""
    def transform(self, orders: list[AmazonOrder], ynab_tx: YnabTransaction) -> NormalizedTransaction:
        # Transformation logic
        pass

class AppleToNormalizedTransformer:
    """Transforms Apple receipts to normalized format."""
    def transform(self, receipt: AppleReceipt, ynab_tx: YnabTransaction) -> NormalizedTransaction:
        # Transformation logic
        pass

class SplitCalculator:
    """Generates YNAB splits from normalized transactions."""
    def calculate_splits(self, normalized: NormalizedTransaction) -> list[YnabSplit]:
        # Business logic here
        pass
```

### 5. Migration Strategy

**Phase 4a: YNAB Models**
- Define clean YNAB models
- Update YNAB loader to produce models
- Update consumers (matchers, flow nodes)

**Phase 4b: Amazon Models**
- Define clean Amazon models
- Update Amazon loader/parser
- Create AmazonToNormalizedTransformer
- Update split generator to use transformer

**Phase 4c: Apple Models**
- Define clean Apple models
- Update Apple parser
- Create AppleToNormalizedTransformer
- Update split generator to use transformer

**Phase 4d: Split Generator**
- Implement NormalizedTransaction model
- Integrate transformers
- Remove normalization from domain modules

## Benefits

1. **Domain Integrity**: Each domain represents its source faithfully
2. **Clear Responsibilities**: Transformers handle normalization, not parsers
3. **Testability**: Can test parsing and transformation separately
4. **Flexibility**: Easy to add new sources (just add transformer)

## Testing Strategy

### Unit Tests
- Test each model's validation and properties
- Test transformers independently

### Integration Tests
- Test full pipeline: CSV → Model → Normalized → Splits
- Test full pipeline: HTML → Model → Normalized → Splits

### E2E Tests
- Verify entire flow works with new models

## Definition of Done

- [ ] All 3 domain models refactored (YNAB, Amazon, Apple)
- [ ] Transformers implemented and tested
- [ ] Split generator refactored to use normalized model
- [ ] All parsers/loaders updated
- [ ] All tests passing
- [ ] No premature normalization in domain modules

## Estimated Effort

- **YNAB Models**: 4-6 hours
- **Amazon Models & Transformer**: 6-8 hours
- **Apple Models & Transformer**: 6-8 hours
- **Split Generator Refactor**: 8-10 hours
- **Testing & Integration**: 8-10 hours
- **Total**: 32-42 hours (5-7 work days)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing integrations | High | Migrate one domain at a time, extensive testing |
| Transformation logic bugs | Medium | Thorough unit tests for transformers |
| Performance concerns | Low | Transformation is fast, profile if needed |

## Dependencies

- Phase 1 complete (simpler CLI)
- Phase 2 complete (Money and FinancialDate types)
- Phase 3 complete (DataStore for clean persistence)
