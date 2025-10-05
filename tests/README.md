# Test Suite Documentation

This document explains the test structure and how to run tests for the finances package.

## Test Organization

```
tests/
├── e2e/              # End-to-end tests (subprocess CLI execution)
├── integration/      # Integration tests (real components, no mocks)
├── unit/             # Unit tests (isolated component testing)
├── fixtures/         # Shared test fixtures and data generators
└── test_data/        # Synthetic test data (NEVER real PII)
```

## Test Categories

### End-to-End Tests (`tests/e2e/`)

**Purpose**: Test complete user workflows by executing actual CLI commands via subprocess.

**Characteristics**:
- No mocking - uses real subprocess execution
- Tests actual `finances` CLI commands
- Uses temporary directories with synthetic data
- Slower but highest confidence

**Example**:
```bash
uv run pytest tests/e2e/test_flow_system.py -v
```

**Known Issues**: May fail if `uv` is not in system PATH during subprocess execution.

### Integration Tests (`tests/integration/`)

**Purpose**: Test multiple components working together with real file system operations.

**Characteristics**:
- Minimal mocking (only for external services like YNAB API)
- Uses real components and file system
- Tests workflows across module boundaries
- Moderate speed, high confidence

**Example**:
```bash
uv run pytest tests/integration/ -v
```

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation.

**Characteristics**:
- Fast execution
- Focused on single components
- Pure business logic verification
- No I/O operations

**Example**:
```bash
uv run pytest tests/unit/test_amazon/ -v
```

## Running Tests

### Run All Tests
```bash
uv run pytest tests/
```

### Run by Category
```bash
# E2E tests only
uv run pytest -m e2e

# Integration tests only
uv run pytest -m integration

# Unit tests only
uv run pytest -m unit

# Skip E2E tests (faster, no subprocess issues)
uv run pytest -m "not e2e"
```

### Run by Domain
```bash
# Amazon tests
uv run pytest -m amazon

# Apple tests
uv run pytest -m apple

# YNAB tests
uv run pytest -m ynab

# Cash flow tests
uv run pytest tests/unit/test_analysis/
```

### Run with Coverage
```bash
uv run pytest --cov=src/finances --cov-report=term-missing
```

### Run Specific Test
```bash
uv run pytest tests/unit/test_amazon/test_matcher.py::TestAppleMatcher::test_exact_match -v
```

## Test Markers

Tests are marked with pytest markers for selective execution:

- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.amazon` - Amazon-related tests
- `@pytest.mark.apple` - Apple-related tests
- `@pytest.mark.ynab` - YNAB-related tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.requires_network` - Tests requiring network access
- `@pytest.mark.requires_credentials` - Tests requiring API credentials

## Synthetic Test Data

### Location
- `tests/test_data/` - Pre-generated synthetic data files
- `tests/fixtures/synthetic_data.py` - Data generation functions

### PII Protection

**CRITICAL**: All test data MUST be synthetic. Never commit real:
- Account balances or IDs
- Transaction details with personal information
- Email addresses or phone numbers
- Credit card or financial account numbers

### Generating Test Data

```python
from tests.fixtures.synthetic_data import (
    generate_synthetic_ynab_cache,
    generate_synthetic_amazon_orders,
    generate_synthetic_apple_receipt_html,
    save_synthetic_ynab_data,
)

# Generate YNAB data
ynab_data = generate_synthetic_ynab_cache(num_accounts=3, num_transactions=100)

# Generate Amazon orders
amazon_orders = generate_synthetic_amazon_orders(num_orders=10)

# Generate Apple receipt
html = generate_synthetic_apple_receipt_html()

# Save to directory
save_synthetic_ynab_data(Path("path/to/output"))
```

## Coverage Goals

**Current Target**: 55-60% coverage

**Philosophy**: Quality over quantity
- Meaningful E2E and integration tests preferred over unit tests
- Some code is acceptable to leave untested if it requires excessive mocking
- Focus on testing behavior, not implementation details

**Coverage by Module**:
- Core business logic: Aim for >80%
- CLI commands: Covered by E2E tests, unit coverage less critical
- Integration glue: Covered by integration tests

## Test Development Guidelines

### DO
- ✅ Use synthetic data from `tests/fixtures/synthetic_data.py`
- ✅ Use temporary directories for file operations
- ✅ Test actual behavior and error handling
- ✅ Clean up resources in teardown methods
- ✅ Write clear, descriptive test names
- ✅ Use appropriate test markers

### DON'T
- ❌ Use real PII or financial data in tests
- ❌ Test implementation details (private methods, algorithms)
- ❌ Over-mock integration tests (defeats the purpose)
- ❌ Write tests just for coverage percentage
- ❌ Commit test data with sensitive information
- ❌ Touch real YNAB account (always use --dry-run or mocks)

## Troubleshooting

### E2E Tests Failing with "uv: command not found"

**Problem**: Subprocess can't find `uv` executable

**Solution**:
```bash
# Ensure uv is in PATH
which uv

# Run with proper environment
uv run pytest tests/e2e/

# Or skip E2E tests
pytest -m "not e2e"
```

### Tests Failing After Code Changes

1. **Check if tests are too brittle**: Testing implementation details?
2. **Update tests**: If behavior changed intentionally
3. **Fix the code**: If tests caught a real bug
4. **Regenerate test data**: If test data format changed

### Slow Test Execution

```bash
# Run only fast tests
pytest -m "not slow and not e2e"

# Run tests in parallel
pytest -n auto

# Run specific subset
pytest tests/unit/
```

## Test Statistics

**Total Tests**: ~265 (as of test overhaul)
- E2E tests: 68
- Integration tests: ~50
- Unit tests: ~147

**Execution Time**:
- All tests: ~60 seconds
- Unit tests only: ~5 seconds
- E2E tests only: ~40 seconds

**Coverage**: ~55-60% (quality-focused)

---

**Last Updated**: 2025-10-05
**Maintained By**: Project maintainers
