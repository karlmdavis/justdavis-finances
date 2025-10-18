# Phase 2: Primitive Types (Money & FinancialDate)

## Goal

Introduce type-safe wrapper classes for currency and dates to eliminate floating-point
errors and date format mismatches throughout the codebase.

## Problem Statement

Current state:
- Currency handled as raw ints (cents/milliunits) with manual conversion
- Date handling scattered across codebase with inconsistent formats
- No type-level enforcement preventing mistakes
- Easy to accidentally mix cents and milliunits

Target state:
- `Money` class wraps currency amounts with safe operations
- `FinancialDate` class wraps dates with consistent formatting
- Type system prevents mixing incompatible units
- Clear, self-documenting code

## Key Changes

### 1. Money Class

**File:** `src/finances/core/currency.py` (enhance existing)

```python
@dataclass(frozen=True)
class Money:
    """Immutable money value in cents (USD)."""
    cents: int

    @classmethod
    def from_cents(cls, cents: int) -> Money:
        return cls(cents=cents)

    @classmethod
    def from_milliunits(cls, milliunits: int) -> Money:
        """Create from YNAB milliunits with sign preservation."""
        return cls(cents=milliunits // 10)  # Sign preserved

    @classmethod
    def from_dollars(cls, dollars: str | int) -> Money:
        """Parse from dollar string like '$123.45' or integer dollars."""
        # Integer-only parsing
        pass

    def to_cents(self) -> int:
        return self.cents

    def to_milliunits(self) -> int:
        return self.cents * 10

    def __add__(self, other: Money) -> Money:
        return Money(cents=self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        return Money(cents=self.cents - other.cents)

    def __mul__(self, scalar: int) -> Money:
        return Money(cents=self.cents * scalar)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents == other.cents

    def __lt__(self, other: Money) -> bool:
        return self.cents < other.cents

    def __str__(self) -> str:
        return format_cents(self.cents)  # Use existing formatter

    def __repr__(self) -> str:
        return f"Money(cents={self.cents})"
```

### 2. FinancialDate Class

**File:** `src/finances/core/dates.py` (NEW)

```python
@dataclass(frozen=True)
class FinancialDate:
    """Immutable financial date wrapper with consistent formatting."""
    date: date

    @classmethod
    def from_string(cls, date_str: str, format: str = "%Y-%m-%d") -> FinancialDate:
        """Parse from string in specified format."""
        return cls(date=datetime.strptime(date_str, format).date())

    @classmethod
    def from_timestamp(cls, timestamp: float) -> FinancialDate:
        """Create from Unix timestamp."""
        return cls(date=datetime.fromtimestamp(timestamp).date())

    @classmethod
    def today(cls) -> FinancialDate:
        """Get today's date."""
        return cls(date=date.today())

    def to_iso_string(self) -> str:
        """Format as YYYY-MM-DD."""
        return self.date.isoformat()

    def to_ynab_format(self) -> str:
        """Format as YNAB expects."""
        return self.date.isoformat()

    def age_days(self, other: FinancialDate | None = None) -> int:
        """Calculate days between this date and another (or today)."""
        if other is None:
            other = FinancialDate.today()
        return (other.date - self.date).days

    def __str__(self) -> str:
        return self.to_iso_string()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FinancialDate):
            return NotImplemented
        return self.date == other.date

    def __lt__(self, other: FinancialDate) -> bool:
        return self.date < other.date
```

### 3. Migration Strategy

**Phase 2a: Core Infrastructure**
- Implement Money and FinancialDate classes
- Add comprehensive unit tests
- Add migration helper utilities

**Phase 2b: Domain Migrations**
- YNAB module: Replace int amounts with Money
- Amazon module: Replace int amounts with Money
- Apple module: Replace int amounts with Money
- All modules: Replace date operations with FinancialDate

**Phase 2c: Test Updates**
- Update all tests to use new types
- Remove old currency conversion utilities (deprecate carefully)

## Testing Strategy

### Unit Tests

```python
def test_money_addition():
    a = Money.from_cents(100)
    b = Money.from_cents(50)
    assert (a + b).to_cents() == 150

def test_money_from_milliunits():
    m = Money.from_milliunits(1250)  # $1.25
    assert m.to_cents() == 125

def test_financial_date_age():
    old = FinancialDate.from_string("2024-01-01")
    new = FinancialDate.from_string("2024-01-11")
    assert old.age_days(new) == 10
```

### Integration Tests

- Verify Money flows through entire pipeline without conversion errors
- Verify FinancialDate parsing from all source formats

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Widespread breaking changes | High | Migrate module-by-module with rollback points |
| Performance overhead | Low | Frozen dataclasses are very efficient |
| Type confusion during migration | Medium | Use mypy strict mode, catch errors early |

## Definition of Done

- [ ] Money and FinancialDate classes implemented with full test coverage
- [ ] All domain modules use Money instead of raw ints
- [ ] All date operations use FinancialDate
- [ ] Mypy strict mode passes
- [ ] All existing tests updated and passing
- [ ] No floating-point currency operations remain

## Estimated Effort

- **Implementation**: 8-12 hours
- **Testing**: 4-6 hours
- **Migration**: 6-8 hours
- **Total**: 18-26 hours (3-4 work days)

## Dependencies

- Phase 1 complete (simplified CLI reduces surface area)
