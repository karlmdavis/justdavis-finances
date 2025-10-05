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
from finances.core.currency import milliunits_to_cents, format_cents
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

1. **Currency handling**:
   - YNAB amounts are in milliunits (1000 milliunits = $1.00).
   - All calculations use integer arithmetic (cents or milliunits).
   - **Required imports**:
     `from finances.core.currency import milliunits_to_cents, format_cents`.
   - Convert: `milliunits_to_cents(amount) = abs(milliunits // 10)`.
   - Display: `format_cents(cents) = f"${cents//100}.{cents%100:02d}"`.
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
12. **Markdown formatting**: All markdown files follow standardized formatting rules.
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
