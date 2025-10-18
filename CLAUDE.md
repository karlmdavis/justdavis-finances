# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
  repository.

## Repository Purpose

This is a personal finance management repository for the Davis family.
The primary focus is on:
- Tracking and managing family finances.
- Creating automation for financial data processing.
- Managing transaction categorization from various sources.
- Analyzing cash flow patterns and financial trends.

## Key Context

### Professional Python Package (September 2024)

This repository is a complete professional Python package for financial management:

- **Package Structure**: `src/finances/` - Modern Python package with domain separation.
- **Professional CLI**: Unified `finances` command-line interface for all operations.
- **Core Modules**: Currency, models, and configuration in `src/finances/core/`.
- **Domain Packages**: Amazon (`finances.amazon`), Apple (`finances.apple`), YNAB
  (`finances.ynab`), Analysis (`finances.analysis`).

**Import Examples:**
```python
from finances.amazon import SimplifiedMatcher, batch_match_transactions
from finances.apple import AppleMatcher, AppleReceiptParser, AppleEmailFetcher
from finances.core import Money, FinancialDate  # Type-safe primitives
from finances.core.currency import format_cents
from finances.ynab import SplitCalculator
from finances.analysis import CashFlowAnalyzer
```

**CLI Examples:**
```bash
# View available commands
finances --help

# Amazon transaction matching
finances amazon match --start 2024-07-01 --end 2024-07-31

# Apple receipt processing
finances apple fetch-emails --days-back 30
finances apple parse-receipts --input-dir data/apple/emails/

# Cash flow analysis
finances cashflow analyze --start 2024-01-01 --end 2024-12-31

# YNAB integration
finances ynab generate-splits --input-file data/amazon/transaction_matches/results.json
```

### Financial Management Tools
- **Primary Tool**: YNAB (You Need A Budget) - used for transaction tracking, categorization,
  and reporting.
- **YNAB CLI**: Command-line tool for extracting YNAB data (`ynab` command).
- **Main Challenge**: Manual categorization of transactions, especially for:
  - Amazon.com purchases (multiple items per transaction).
  - Apple App Store purchases (bundled transactions).
  - Retirement account balance updates (no automatic sync).

### Core Financial Workflows

#### 1. YNAB Data Integration
- **Package module**: `finances.ynab` - Professional YNAB integration with caching.
- **CLI commands**: `finances ynab sync-cache`, `finances ynab generate-splits`.
- **Data storage**: `data/ynab/cache/` - Cached YNAB data (accounts, categories, transactions).
- **Features**: Three-phase workflow (Generate → Review → Apply), audit trails, confidence
  thresholds.

#### 2. Amazon Transaction Matching
- **Package module**: `finances.amazon` - Complete Amazon transaction processing.
- **CLI commands**: `finances amazon match`, `finances amazon match-single`.
- **Data sources**: `data/amazon/raw/` - Amazon order history files.
- **Output**: `data/amazon/transaction_matches/` - Matching results with confidence scoring.
- **Features**: 3-strategy matching system, multi-account support, split payment detection.
- **Performance**: 94.7% accuracy with 0.1 seconds per transaction.

#### 3. Apple Receipt Processing
- **Package modules**: `finances.apple` - Complete Apple ecosystem integration.
- **CLI commands**: `finances apple fetch-emails`, `finances apple parse-receipts`,
  `finances apple match`.
- **Data flow**: Email fetching → HTML parsing → Transaction matching.
- **Features**: IMAP email integration, multi-format parsing, 1:1 transaction model.
- **Performance**: 85.1% match rate with HTML-only parsing system.

#### 4. Cash Flow Analysis
- **Package module**: `finances.analysis.cash_flow` - Professional financial analysis.
- **CLI commands**: `finances cashflow analyze` - Multi-timeframe analysis and dashboards.
- **Output**: `data/cash_flow/charts/` - Professional 6-panel dashboards.
- **Features**: Statistical modeling, trend detection, volatility analysis, export options.

### Domain Model Usage Examples (Phase 4.5 - October 2024)

The codebase uses domain models throughout for type safety and eliminating DataFrame dependencies.
All financial processing now uses pure Python domain models.

#### YNAB Split Generation Models

**YnabSplit** - Individual split (subtransaction) for transaction edits:
```python
from finances.ynab.models import YnabSplit
from finances.core import Money

# Create a split for an Amazon item
split = YnabSplit(
    amount=Money.from_milliunits(-12340),  # -$12.34 (negative for expenses)
    memo="Arduino Starter Kit (qty: 1)",
    category_id="cat_abc123",  # Optional category assignment
    payee_id=None  # Optional payee override
)

# Convert to YNAB API format
split_dict = split.to_ynab_dict()
# Result: {"amount": -12340, "memo": "Arduino Starter Kit (qty: 1)", "category_id": "cat_abc123"}
```

**TransactionSplitEdit** - Split edit for a single transaction:
```python
from finances.ynab.models import TransactionSplitEdit, YnabTransaction

# Create edit batch for a transaction
edit = TransactionSplitEdit(
    transaction_id="tx_xyz789",
    transaction=transaction_obj,  # Full YnabTransaction context
    splits=[split1, split2, split3],  # List of YnabSplit objects
    source="amazon",  # "amazon" or "apple"
    confidence=0.95,  # Match confidence score
    metadata={"order_id": "123-456"}  # Additional context
)

# Serialize for JSON output
edit_dict = edit.to_dict()
```

**SplitEditBatch** - Batch of splits for file output:
```python
from finances.ynab.models import SplitEditBatch

# Create batch of edits
batch = SplitEditBatch(
    edits=[edit1, edit2, edit3],
    timestamp="2024-10-17_15-30-45",
    amazon_count=2,
    apple_count=1
)

# Write to JSON file
batch_dict = batch.to_dict()
# Structure: {"metadata": {...}, "edits": [...]}
```

#### Amazon Match Models

**MatchedOrderItem** - Order item with allocated tax/shipping:
```python
from finances.amazon.models import MatchedOrderItem, AmazonOrderItem
from finances.core import Money, FinancialDate

# Convert raw order item to match-layer model
order_item = AmazonOrderItem(...)  # From CSV loader
matched_item = MatchedOrderItem.from_order_item(
    order_item=order_item,
    allocated_tax=Money.from_cents(127),  # Proportionally allocated tax
    allocated_shipping=Money.from_cents(599)  # Proportionally allocated shipping
)

# Access total amount (item cost + allocated tax + shipping)
total = matched_item.amount  # Money object with full allocated amount
```

**OrderGroup** - Grouped orders for matching strategies:
```python
from finances.amazon.models import OrderGroup

# Group created by grouping logic
group = OrderGroup(
    order_id="123-456",
    ship_date=FinancialDate.from_string("2024-10-15"),
    items=[matched_item1, matched_item2],
    total_amount=Money.from_cents(4599)
)

# Access group properties
print(f"Order {group.order_id}: {group.total_amount} ({len(group.items)} items)")
```

#### Apple Receipt Models

**ParsedReceipt** - Parsed Apple receipt with typed fields:
```python
from finances.apple.parser import ParsedReceipt, ParsedItem

# Create receipt from parser
receipt = ParsedReceipt(
    order_id="M123456789",
    receipt_date=FinancialDate.from_string("2024-10-15"),
    apple_id="user@example.com",
    total=Money.from_cents(3299),  # $32.99
    subtotal=Money.from_cents(2999),
    tax=Money.from_cents(300),
    items=[
        ParsedItem(
            title="App Subscription",
            cost=Money.from_cents(999),
            quantity=1,
            subscription=True
        ),
        ParsedItem(
            title="In-App Purchase",
            cost=Money.from_cents(2000),
            quantity=1,
            subscription=False
        )
    ],
    format_detected="modern_custom"
)

# All fields are typed (Money, FinancialDate)
assert isinstance(receipt.total, Money)
assert isinstance(receipt.receipt_date, FinancialDate)
```

#### Working with Domain Models

**Type Safety Benefits:**
```python
# OLD (Phase 4.0 - dict-based):
tx_amount = transaction["amount"]  # int? float? milliunits? cents? Unknown!
if tx_amount < 0:  # Direct comparison with raw int
    ...

# NEW (Phase 4.5 - domain models):
tx_amount = transaction.amount  # Money object - type is clear!
if tx_amount.to_cents() < 0:  # Explicit unit conversion
    ...

# Money enforces integer-only arithmetic
split_amount = Money.from_milliunits(-12340)
assert split_amount.to_cents() == -1234  # Automatic conversion
assert str(split_amount) == "-$12.34"  # Pretty formatting
```

**DataFrame Elimination:**
```python
# OLD (Phase 4.0 - DataFrame-based):
orders_df = pd.DataFrame(orders_data)
filtered = orders_df[orders_df["ship_date"] == target_date]
result = filtered.to_dict("records")  # Convert back to dicts

# NEW (Phase 4.5 - domain models):
orders = [AmazonOrderItem.from_dict(d) for d in orders_data]
filtered = [o for o in orders if o.ship_date == target_date]
# Result is already list[AmazonOrderItem] - no conversion needed!
```


### Data Structure Notes

**accounts.json structure:**
```json
{
  "accounts": [...],
  "server_knowledge": ...
}
```

**categories.json structure:**
```json
{
  "category_groups": [...],
  "server_knowledge": ...
}
```

**transactions.json structure:**
```json
[...] // Direct array of transactions
```

### Development Focus Areas
When developing automation or tools for this repository, prioritize:
1. Transaction categorization assistance (Amazon ✅ solved, Apple ✅ solved).
2. Receipt and order history parsing (Amazon ✅ solved, Apple ✅ solved).
3. Data import/export utilities for YNAB.
4. Reporting and analysis tools.
5. Cash flow trend analysis and projections.

### Directory Conventions
- `data/` - Unified data directory (gitignored).
  - `data/amazon/raw/` - Amazon order history files.
  - `data/amazon/transaction_matches/` - Amazon matching results.
  - `data/apple/emails/` - Apple receipt emails.
  - `data/apple/exports/` - Parsed Apple receipt data.
  - `data/apple/transaction_matches/` - Apple matching results.
  - `data/ynab/cache/` - Cached YNAB data.
  - `data/ynab/edits/` - Transaction updates.
  - `data/cash_flow/charts/` - Generated analysis dashboards.
- `src/finances/` - Python package source code.
- `tests/` - Comprehensive test suite with fixtures.

### Python Environment
- **Package manager**: `uv` for dependency management and virtual environments.
- **Package configuration**: `pyproject.toml` with full packaging metadata.
- **Installation**: `uv pip install -e .` for development mode.
- **CLI execution**: `finances --help` (installed command) or `uv run finances --help`.
- **Testing**: `uv run pytest` with comprehensive test suite.
- **Code quality**: `uv run black src/ tests/`, `uv run ruff src/ tests/`, `uv run mypy src/`.

### Development Workflow

This repository uses a **PR-based workflow** with branch protection rules enforced on main.

**Core principles:**
- **ALL changes** must go through pull requests - direct commits to main are blocked.
- **ALWAYS** create a feature branch before making any code changes.
- **NEVER** attempt to commit directly to the main branch.

**Branch naming conventions:**
- `feature/descriptive-name` - New features or enhancements.
- `fix/descriptive-name` - Bug fixes.
- `refactor/descriptive-name` - Code refactoring without functional changes.
- `docs/descriptive-name` - Documentation updates.

**PR workflow using gh CLI:**
1. Create and checkout a feature branch: `git checkout -b feature/your-feature-name`.
2. Make changes and commit to the feature branch.
3. Push branch: `git push -u origin feature/your-feature-name`.
4. Create PR: `gh pr create --title "Title" --body "Description"`.
5. Review and approve PR (self-review for solo project).
6. Merge PR: `gh pr merge --squash` or `gh pr merge --merge`.
7. Branches are automatically deleted after merge (GitHub setting).

**PR management commands:**
- `gh pr create` - Create a new pull request.
- `gh pr view` - View PR details.
- `gh pr list` - List open pull requests.
- `gh pr merge` - Merge an approved pull request.
- `gh pr checks` - View CI/CD check status.

**PR description requirements:**
- **Summary**: 1-3 bullet points explaining what changed and why.
- **Test plan**: How the changes were tested (commands run, test coverage, manual verification).
- **Context**: Link to related issues or provide background for the change.

### Testing Philosophy and Strategy

This repository prioritizes **quality over quantity** in test coverage, focusing on tests that catch
  real bugs in user workflows.

#### Test Pyramid (Inverted Priority)

Traditional test pyramids emphasize unit tests.
This repository inverts that priority:

**Priority 1: E2E Tests** (Highest Value)
- Execute actual `finances` CLI commands via subprocess
- Test complete user workflows from start to finish
- Catch integration bugs that unit tests miss
- Tell clear, complete stories about functionality
- Located in `tests/e2e/`

**Priority 2: Integration Tests** (Fill Coverage Gaps)
- Test multiple components working together with real file system operations
- Use CliRunner for CLI commands (faster than subprocess)
- Minimal mocking (only for external services like YNAB API)
- Located in `tests/integration/`

**Priority 3: Unit Tests** (Complex Business Logic Only)
- Test isolated components in pure business logic
- Avoid testing implementation details or trivial code
- Use only when behavior is too complex for integration testing alone
- Located in `tests/unit/`

#### Writing Testable Code

When implementing new features, design code to be testable without excessive mocking:

**DO:**
- ✅ Separate I/O from business logic
- ✅ Design CLI commands with testable parameter behavior
- ✅ Make implementations complete, not placeholders
- ✅ Return meaningful results that can be verified
- ✅ Use dependency injection for external services
- ✅ Write integration tests before unit tests

**DON'T:**
- ❌ Tightly couple business logic to external APIs
- ❌ Mix presentation logic with computation
- ❌ Create complex dependencies that require extensive mocking
- ❌ Write placeholder implementations without test placeholders
- ❌ Test private methods or implementation details
- ❌ Write tests just to increase coverage percentage

#### Test Development Workflow

**For New Features:**
1.
Start with E2E test for the main user workflow
2.
If E2E test doesn't cover edge cases, add integration tests
3.
Only add unit tests if complex business logic needs isolation
4.
Ensure all tests use synthetic data (see `tests/fixtures/synthetic_data.py`)

**For Bug Fixes:**
1.
Write failing E2E or integration test reproducing the bug
2.
Fix the bug
3.
Verify test passes
4.
Consider if additional edge case tests are needed

**Test Quality Indicators:**
- ✅ Test catches real bugs in user workflows
- ✅ Test fails when functionality breaks
- ✅ Test name clearly describes what it verifies
- ✅ Test is fast enough to run frequently
- ✅ Test uses minimal mocking
- ❌ Test requires extensive setup/mocking (consider refactoring code)
- ❌ Test breaks when implementation changes but behavior doesn't
- ❌ Test covers trivial code or implementation details

#### Coverage Philosophy

**Target Coverage**: 60%+ with quality over quantity

**What to Test:**
- ✅ CLI command parameter handling and workflows
- ✅ Core business logic (matchers, calculators, parsers)
- ✅ Error handling and edge cases
- ✅ Data transformation and validation
- ✅ File I/O with real temporary files

**What NOT to Test:**
- ❌ Simple getters/setters or property accessors
- ❌ Trivial dataclass definitions
- ❌ Implementation details (algorithms, private methods)
- ❌ Third-party library behavior
- ❌ Code requiring excessive mocking (refactor instead)

#### Anti-Patterns to Avoid

**Over-Mocking:**
```python
# BAD: Excessive mocking defeats integration test purpose
def test_amazon_match():
    mock_loader = Mock()
    mock_matcher = Mock()
    mock_ynab = Mock()
    mock_writer = Mock()
    # ...20 more mocks...
    # This tests nothing real!
```

**Testing Implementation Details:**
```python
# BAD: Tests private method implementation
def test_internal_algorithm_step_3():
    result = matcher._internal_sort_by_confidence(items)
    assert result[0].confidence > result[1].confidence

# GOOD: Tests public behavior
def test_matcher_returns_best_match_first():
    matches = matcher.match_transaction(transaction)
    assert matches[0].confidence >= matches[1].confidence
```

**Low-Value Algorithmic Tests:**
```python
# BAD: Tests obvious sorting implementation
def test_sort_orders_by_date():
    orders = [order_b, order_a]
    sorted_orders = sort_by_date(orders)
    assert sorted_orders == [order_a, order_b]

# GOOD: Tests business logic using sorting
def test_matcher_prioritizes_recent_orders():
    matches = matcher.match_transaction(transaction)
    assert matches[0].order_date > matches[1].order_date
```

#### Test Data Management

**Synthetic Data Only:**
- All test data MUST be synthetic (never real PII or financial data)
- Use `tests/fixtures/synthetic_data.py` generators
- See `tests/README.md` for detailed guidelines

**Temporary Files:**
- Always use `tempfile.mkdtemp()` for test file operations
- Clean up in `teardown_method()` or use pytest fixtures
- Never write to actual `data/` directory in tests

#### Running Tests

```bash
# All tests
uv run pytest tests/

# Fast tests (skip E2E subprocess tests)
uv run pytest -m "not e2e"

# Integration + Unit only
uv run pytest tests/integration/ tests/unit/

# With coverage
uv run pytest --cov=src/finances --cov-report=term-missing

# Specific domain
uv run pytest -m amazon
uv run pytest -m apple
uv run pytest -m ynab
```

See `tests/README.md` for complete testing documentation.

### Important Implementation Notes

#### Critical: Currency Handling - ZERO Floating Point Tolerance
**NEVER use floating point math for currency** - not even for display formatting.
This repository maintains strict integer-only arithmetic for all financial calculations
  to ensure precision.

**Required patterns:**
- **ALL calculations**: Use integer arithmetic only (cents or milliunits).
- **Display formatting**: Use integer division and modulo: `f"{cents//100}.{cents%100:02d}"`.
- **Currency parsing**: Parse directly to integer cents without float intermediate.
  - Example: "$12.34" → 1234 cents (parse as `int(dollars)*100 + int(cents_part)`).
- **Confidence scores**: Use integer basis points (0-10000) instead of floats (0.0-1.0).
- **NO float() calls**: Never use `float()` for currency amounts, even temporarily.
- **NO division for display**: Never use `cents / 100` even with `.2f` formatting.

**Safe patterns in package structure:**
- `src/finances/core/currency.py`: Centralized integer-based conversion functions.
- All domain modules use centralized currency utilities.
- Package-wide enforcement of integer-only arithmetic.

1. **Type-safe primitives (October 2024)**:
   - **Money class**: Immutable type-safe currency wrapper (replaces raw cents/milliunits).
   - **FinancialDate class**: Immutable type-safe date wrapper (replaces raw date objects).
   - **Import**: `from finances.core import Money, FinancialDate`.
   - **Construction examples**:
     ```python
     # Money construction
     amount = Money.from_cents(1234)  # $12.34
     expense = Money.from_milliunits(-12340)  # -$12.34 (YNAB expense)
     amount = Money.from_dollars("$12.34")  # String parsing

     # FinancialDate construction
     date = FinancialDate.from_string("2024-10-13")
     date = FinancialDate.today()
     date = FinancialDate(date=datetime.date(2024, 10, 13))
     ```
   - **Sign preservation**: Money preserves sign from milliunits - negative for expenses, positive
     for income.
   - **Arithmetic**: Money supports +, -, <, >, ==, and other operators.
   - **Conversion**: Use `.to_cents()`, `.to_milliunits()`, `.to_dollars()`, `.abs()` for interop.
   - **No more backward compatibility**: All code now uses Money type directly (October 2024).
   - **Recommendation**: Always use Money/FinancialDate for all currency and date operations.
2. **Date handling**: Transaction dates before May 2024 may have incomplete data.
3. **JSON structures**: Use proper jq paths for nested structures
   (e.g., `.accounts[0]` not `.[0]`).
4. **Output organization**: Always create output directories if they don't exist.
5. **Timestamps**: Use format `YYYY-MM-DD_HH-MM-SS_filename` for all generated files.
6. **Path handling**: Use package-relative paths and configuration-based directory
   resolution.
7. **Multi-account support**: Amazon data uses `YYYY-MM-DD_accountname_amazon_data/`
   naming in `data/amazon/raw/`.
8. **Working directory**: Repository root (`personal/justdavis-finances/`) is the standard
   working directory.
9. **Package execution**: Use `finances` CLI or `uv run finances` for all operations.
10. **Development**: Use `uv run python -c ...` for ad-hoc Python with package imports.
11. **JSON formatting**: All JSON files must use pretty-printing with 2-space indentation.
    **Required practice**:
    - Import: `from finances.core.json_utils import write_json, read_json, format_json`.
    - File writing: Use `write_json(filepath, data)` instead of `json.dump()`.
    - File reading: Use `read_json(filepath)` instead of `json.load()`.
    - String formatting: Use `format_json(data)` instead of `json.dumps()`.
    - **Never use** direct `json.dump()` or `json.dumps()` calls without `indent=2`.
13. **Markdown formatting**: All markdown files follow standardized formatting rules.
    See [Markdown Formatting Guidelines](CONTRIBUTING.md#markdown-formatting-guidelines) for
      complete details:
    - One sentence per line for better version control
    - 110-character line wrap limit at natural break points
    - Two-space indentation for wrapped lines
    - Sentence completion with periods on all sentence-like lines
    - Trailing whitespace removal (except when required by Markdown)
    - POSIX line endings
    - Consistent formatting across all documentation files

## Security Considerations
- Never commit sensitive financial data, account numbers, or API credentials.
- Use environment variables (`.env` file) for API keys and email credentials.
- All financial data stored locally with no cloud dependencies.
- **Gitignored directories**:
  - `data/` (all financial data and generated outputs).
  - `.env` (environment variables and credentials).
  - Package maintains strict local-only processing for privacy.

## Recent Major Improvements

### Professional Python Package Migration (September 2024)
- **Complete package transformation**: Migrated from script-based system to professional
  Python package.
- **Unified CLI interface**: Single `finances` command with comprehensive subcommands for all
  operations.
- **Domain-driven architecture**: Clean separation into Amazon, Apple, YNAB, and Analysis
  packages.
- **Centralized configuration**: Environment-based configuration with validation and type
  safety.
- **Comprehensive testing**: Full pytest suite with fixtures, markers, and domain-specific
  test organization.
- **Professional tooling**: Integration with black, ruff, mypy for code quality and
  development workflow.

Key architectural achievements:
1. **Package structure**: `src/finances/` layout with proper imports, exports, and CLI
   integration.
2. **Legacy cleanup**: Removed 92 legacy Python files and 4 legacy directories while
   maintaining functionality.
3. **Unified data management**: Single `data/` directory with domain-specific subdirectories.
4. **Professional development**: Complete development tooling setup with pre-commit hooks and
   quality gates.

### Type-Safe Primitive Types - Money & FinancialDate (October 2024)
- **Immutable type wrappers**: Introduced Money and FinancialDate classes to replace raw
  integers and dates.
- **Zero floating-point errors**: Money class enforces integer-only arithmetic at type level.
- **Backward compatibility**: All core models (Transaction, Receipt) auto-sync between legacy
  and new fields.
- **Complete test coverage**: 33 unit tests covering construction, arithmetic, comparison,
  immutability.
- **Strict type checking**: All new code passes mypy --strict with zero errors.
- **Domain migrations**: Amazon, Apple, and YNAB modules updated to use new types with
  legacy support.

Key implementation details:
1. **Frozen dataclasses**: Immutable by design using `@dataclass(frozen=True)`.
2. **Multiple constructors**: `Money.from_cents()`, `Money.from_milliunits()`,
   `Money.from_dollars()`.
3. **Rich comparisons**: Full support for arithmetic (+, -) and comparison (<, >, ==)
   operators.
4. **Seamless migration**: Existing code continues to work unchanged while new code gains type
   safety.

### Apple Transaction Matching System Implementation (September 2024)
- **Complete Apple ecosystem**: Full receipt extraction and transaction matching with email
  integration.
- **Multi-format parsing**: HTML parser supporting legacy and modern Apple receipt formats.
- **IMAP email fetching**: Secure email integration with comprehensive filtering and search.
- **High performance**: 85.1% match rate with 1:1 transaction model optimization.
- **Professional CLI**: `finances apple` commands for email fetching, parsing, and matching.

### Amazon Transaction Matching System (August 2024)
- **3-strategy architecture**: Simplified from complex 5-strategy to maintainable 3-strategy
  system.
- **Integer arithmetic**: Eliminated floating-point errors with strict currency handling.
- **Multi-account support**: Household-level Amazon account management with automatic
  discovery.
- **94.7% accuracy**: Maintained high match rate with simplified, reliable architecture.
- **Professional CLI**: `finances amazon` commands for batch and single transaction
  processing.

### Phase 4.5: DataFrame Elimination & Domain Model Migration (October 2024)

Complete migration from DataFrame/dict-based code to pure domain models across all modules.

**Migration Strategy:**
1. **Bottom-up approach**: Loaders → Calculators → Matchers → Flow
2. **Domain model first**: Define typed models before updating consumers
3. **Test-driven**: Write domain model tests before migration
4. **Incremental rollout**: One module at a time to minimize risk

**Key Lessons Learned:**

1. **Type Safety Pays Off**
   - Money/FinancialDate primitives caught 10+ bugs during migration
   - mypy strict mode prevented incorrect unit conversions
   - Explicit type boundaries eliminated "is this cents or milliunits?" confusion

2. **DataFrames Add Complexity**
   - Eliminated 500+ lines of DataFrame conversion code
   - Reduced memory overhead by 40% (no intermediate DataFrames)
   - Simpler code: list comprehensions replace complex DataFrame operations

3. **Domain Models Enable Testing**
   - Can test business logic without mocking DataFrame operations
   - Test data is clearer: `Money.from_cents(1234)` vs `1234` (ambiguous)
   - Integration tests run 2x faster without DataFrame overhead

4. **Migration Order Matters**
   - **Bottom-up wins**: Start with loaders, work up to flow nodes
   - **Top-down fails**: Changing matchers first forces simultaneous changes across layers
   - **Test each layer**: Don't commit untested migration steps

5. **Avoid Premature Abstraction**
   - Don't create "universal" DataFrame adapters - commit to domain models
   - Temporary backward compatibility adds complexity - rip the band-aid off
   - If you need both dict and domain model signatures, you're not done migrating

**Common Pitfalls:**

❌ **Mixing DataFrames and Domain Models**
```python
# BAD: Half-migrated code
orders_df = load_orders()  # Returns DataFrame
orders = [AmazonOrderItem.from_dict(row.to_dict()) for _, row in orders_df.iterrows()]
# Just load domain models directly!
```

❌ **Lossy Type Conversions**
```python
# BAD: Losing type information
amount_cents = item.amount.to_cents()  # Money → int
amount_milliunits = cents_to_milliunits(amount_cents)  # int → int
# GOOD: Direct conversion
amount_milliunits = item.amount.to_milliunits()  # Money → int (one step)
```

❌ **Testing Implementation Details**
```python
# BAD: Testing dict structure
assert result["amount"] == 1234
# GOOD: Testing business behavior
assert result.amount.to_cents() == 1234
```

**Success Metrics (Phase 4.5):**
- ✅ Zero DataFrame usage outside CSV parsing
- ✅ Zero dict-based function signatures (except JSON serialization)
- ✅ 100% domain model coverage in matchers and calculators
- ✅ 473 tests passing with 73.60% coverage
- ✅ Zero mypy errors in strict mode
- ✅ Critical bug fix: Apple split unit conversion (10x error)

**Migration Checklist for Future Refactorings:**

1. ☐ **Define Domain Models**
   - Create typed dataclasses with Money/FinancialDate
   - Add `from_dict()` and `to_dict()` serialization methods
   - Write comprehensive unit tests for models

2. ☐ **Update Data Loaders**
   - Change loaders to return `list[DomainModel]` instead of DataFrame/dicts
   - Update integration tests to verify domain model output
   - Remove DataFrame conversion code

3. ☐ **Migrate Business Logic**
   - Update calculators and matchers to accept domain models
   - Remove dict access patterns (`obj["field"]` → `obj.field`)
   - Simplify logic with type-safe operations

4. ☐ **Update Flow Nodes**
   - Change CLI commands to use domain model signatures
   - Update E2E tests to verify end-to-end flow
   - Remove temporary adapters and backward compatibility code

5. ☐ **Verify & Clean Up**
   - Run full test suite (E2E, integration, unit)
   - Run mypy in strict mode
   - Search codebase for DataFrame usage: `rg "pd\.DataFrame|\.to_dict\(\"records\"\)"`
   - Remove unused imports (pandas, dict converters)

**Resources:**
- See `dev/plans/phase-4.5-domain-model-migration.md` for detailed plan
- Example PR: Phase 4.5 (#14) - Complete DataFrame elimination
- Test examples: `tests/unit/test_amazon/test_match_models.py`
