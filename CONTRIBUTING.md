# Contributors Guide

Welcome to the Davis Family Finances project.
This guide provides comprehensive information for developers contributing to this professional
  personal finance management system.

## Table of Contents

- [Project Architecture](#project-architecture)
- [Directory Structure](#directory-structure)
- [Development Setup](#development-setup)
- [Testing Framework](#testing-framework)
- [Code Quality Standards](#code-quality-standards)
- [Development Workflow](#development-workflow)
- [Package Development](#package-development)
- [Domain-Specific Guidelines](#domain-specific-guidelines)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Project Architecture

### Design Principles

The project follows a **domain-driven design** approach with strict architectural guidelines:

- **Domain separation**: Each financial data source (Amazon, Apple, YNAB) has its own package.
- **Integer arithmetic**: All currency calculations use integer arithmetic to prevent
  floating-point errors.
- **Configuration management**: Environment-based settings with comprehensive validation.
- **Security-first**: No sensitive data in source code, comprehensive audit trails.
- **Professional CLI**: Unified command-line interface with consistent patterns.

### Package Structure

```
src/finances/
├── core/                    # Shared business logic and utilities
│   ├── currency.py         # Integer-based currency handling (CRITICAL)
│   ├── models.py           # Common data models and validation
│   ├── config.py           # Environment-based configuration management
│   └── __init__.py         # Core module exports
├── amazon/                 # Amazon transaction processing domain
│   ├── matcher.py          # 3-strategy transaction matching system
│   ├── grouper.py          # Order grouping logic (complete/shipment/daily)
│   ├── scorer.py           # Confidence scoring algorithms
│   ├── split_matcher.py    # Split payment handling
│   ├── loader.py           # Amazon data loading and normalization
│   └── __init__.py         # Amazon package exports
├── apple/                  # Apple receipt processing domain
│   ├── matcher.py          # 2-strategy matching (exact + date window)
│   ├── parser.py           # Multi-format HTML receipt parsing
│   ├── loader.py           # Apple receipt data loading
│   ├── email_fetcher.py    # IMAP email integration
│   └── __init__.py         # Apple package exports
├── ynab/                   # YNAB integration domain
│   ├── split_calculator.py # Transaction splitting logic
│   └── __init__.py         # YNAB package exports
├── analysis/               # Financial analysis tools
│   ├── cash_flow.py        # Multi-timeframe cash flow analysis
│   └── __init__.py         # Analysis package exports
├── cli/                    # Command-line interfaces
│   ├── main.py             # Main CLI entry point and configuration
│   ├── amazon.py           # Amazon-specific commands
│   ├── apple.py            # Apple-specific commands
│   ├── ynab.py             # YNAB-specific commands
│   ├── cashflow.py         # Cash flow analysis commands
│   └── __init__.py         # CLI package exports
└── __init__.py             # Main package exports and version
```

### Domain Architecture Patterns

Each domain package follows consistent internal organization:

1. **Data Layer**: Models and validation (`models.py`, data classes).
2. **Processing Layer**: Business logic and algorithms (`matcher.py`, `parser.py`).
3. **Integration Layer**: External service interfaces (`loader.py`, `email_fetcher.py`).
4. **Interface Layer**: CLI commands and API endpoints (`cli/`).

## Directory Structure

### Repository Layout

```
finances/                           # Repository root
├── src/finances/                   # Python package source (see above)
├── tests/                          # Comprehensive test suite
│   ├── unit/                       # Unit tests by domain
│   │   ├── core/                   # Core utility tests
│   │   ├── amazon/                 # Amazon domain tests
│   │   ├── apple/                  # Apple domain tests
│   │   ├── ynab/                   # YNAB domain tests
│   │   ├── analysis/               # Analysis tool tests
│   │   └── cli/                    # CLI interface tests
│   ├── integration/                # End-to-end workflow tests
│   │   ├── amazon_workflow/        # Complete Amazon matching workflows
│   │   ├── apple_workflow/         # Complete Apple processing workflows
│   │   └── ynab_workflow/          # YNAB integration workflows
│   ├── fixtures/                   # Shared test data and utilities
│   │   ├── amazon_data/            # Sample Amazon order data
│   │   ├── apple_data/             # Sample Apple receipt data
│   │   └── ynab_data/              # Sample YNAB transaction data
│   └── conftest.py                 # Pytest configuration and shared fixtures
├── data/                           # Unified data directory (gitignored)
│   ├── amazon/                     # Amazon data and processing results
│   │   ├── raw/                    # Order history files (CSV format)
│   │   └── transaction_matches/    # Matching results (JSON format)
│   ├── apple/                      # Apple data and processing results
│   │   ├── emails/                 # Receipt emails (HTML/EML format)
│   │   ├── exports/                # Parsed receipt data (JSON format)
│   │   └── transaction_matches/    # Matching results (JSON format)
│   ├── ynab/                       # YNAB data and edits
│   │   ├── cache/                  # Cached YNAB data (JSON format)
│   │   └── edits/                  # Transaction updates (JSON format)
│   └── cash_flow/                  # Cash flow analysis results
│       └── charts/                 # Generated dashboards (PNG/PDF format)
├── dev/                            # Development documentation and specifications
│   ├── specs/                      # Technical specifications
│   └── todos.md                    # Development task tracking
├── pyproject.toml                  # Package configuration and dependencies
├── uv.lock                         # Dependency lock file
├── README.md                       # User-facing documentation
├── CONTRIBUTING.md                 # This file - developer documentation
├── CLAUDE.md                       # Claude Code guidance
├── .env.template                   # Environment variable template
├── .gitignore                      # Git ignore patterns
└── YNAB_DATA_WORKFLOW.md          # YNAB data extraction documentation
```

### Data Directory Management

The `data/` directory is automatically created and managed by the package:

- **Gitignored**: All financial data is excluded from version control for security.
- **Auto-creation**: Directories created automatically when needed.
- **Timestamped outputs**: All generated files include timestamps for tracking.
- **Organized by domain**: Clear separation between Amazon, Apple, YNAB, and analysis data.

## Development Setup

### Prerequisites

- **Python 3.13+**: Required for modern type annotations and language features.
- **uv**: Package manager for dependency management and virtual environments.
- **Git**: Version control system.

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd finances

# Install dependencies and development tools
uv sync --dev

# Install package in development mode
uv pip install -e .

# Install pre-commit hooks for automatic code quality checks
uv run pre-commit install

# Verify installation
finances --help
```

### Environment Configuration

Create `.env` file for configuration (copy from `.env.template`):

```bash
# Required for YNAB integration
YNAB_API_TOKEN=your_ynab_token_here

# Required for Apple email fetching
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Optional configuration
FINANCES_ENV=development          # development, test, production
FINANCES_DATA_DIR=./data         # Override data directory
EMAIL_IMAP_SERVER=imap.gmail.com # IMAP server
EMAIL_IMAP_PORT=993              # IMAP port
```

### Development Dependencies

The project includes comprehensive development tooling:

- **Testing**: pytest, pytest-cov for test execution and coverage.
- **Code Quality**: black, ruff, mypy for formatting, linting, and type checking.
- **Pre-commit**: Automated quality gates for git commits.
- **Documentation**: Tools for generating and maintaining documentation.

## Testing Framework

### Test Organization

Tests are organized by type and domain:

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest -m unit           # Unit tests only
uv run pytest -m integration    # Integration tests only
uv run pytest -m currency       # Currency handling tests
uv run pytest -m amazon         # Amazon domain tests
uv run pytest -m apple          # Apple domain tests
uv run pytest -m ynab           # YNAB integration tests

# Run with coverage reporting
uv run pytest --cov=src/finances --cov-report=html
```

### Test Categories

Tests are marked with pytest markers for selective execution:

- **unit**: Unit tests for individual components and functions.
- **integration**: End-to-end workflow tests with realistic data.
- **currency**: Tests specifically for currency handling and precision.
- **amazon**: Amazon transaction matching system tests.
- **apple**: Apple receipt processing system tests.
- **ynab**: YNAB integration and API tests.
- **slow**: Tests that take significant time to run.

### Writing Tests

#### Test Structure
```python
import pytest
from finances.core import Money

@pytest.mark.unit
@pytest.mark.currency
def test_money_from_milliunits():
    """Test Money creation from YNAB milliunits."""
    income = Money.from_milliunits(123456)
    assert income.to_cents() == 12345

    expense = Money.from_milliunits(-123456)
    assert expense.to_cents() == -12345  # Sign preserved
```

#### Using Fixtures
```python
def test_amazon_matching(sample_amazon_orders, sample_ynab_transactions):
    """Test Amazon transaction matching with sample data."""
    matcher = SimplifiedMatcher()
    results = matcher.match_transactions(
        sample_ynab_transactions,
        sample_amazon_orders
    )
    assert len(results) > 0
```

### Test Coverage Requirements

- **Minimum coverage**: 60% line coverage with quality over quantity philosophy.
- **Critical paths**: Comprehensive testing for financial calculations and user workflows.
- **Integration coverage**: End-to-end workflow testing with realistic data.
- **Performance testing**: Regression testing for critical performance paths.

## Code Quality Standards

### Overview

The project enforces comprehensive code quality standards through automated tooling:

- **Zero tolerance**: All quality checks must pass in CI/CD pipeline.
- **Pre-commit validation**: Lightweight hooks (<2s) for immediate feedback.
- **Strategic pragmatism**: Type checking with industry-standard ignore patterns for known
  library limitations.

### Automated Formatting

#### Black Configuration
```bash
# Format all code
uv run black src/ tests/

# Check formatting without changes
uv run black --check src/ tests/
```

Configuration in `pyproject.toml`:
- **Line length**: 110 characters (optimized for modern displays).
- **Target Python**: 3.13+ for compatibility.
- **Consistent style**: Automatic quote normalization and formatting.

#### Import Organization
```bash
# Organize imports (included in Ruff)
uv run ruff check --select I --fix src/ tests/
```

### Comprehensive Linting

#### Ruff Configuration
```bash
# Run all linting checks
uv run ruff check src/ tests/

# Auto-fix simple issues
uv run ruff check --fix src/ tests/
```

**Enabled rule categories:**
- **E, W**: pycodestyle errors and warnings.
- **F**: pyflakes for logical errors.
- **I**: isort for import organization.
- **B**: flake8-bugbear for likely bugs.
- **C4**: flake8-comprehensions for better comprehensions.
- **UP**: pyupgrade for modern Python patterns.
- **S**: Security checks for common vulnerabilities.
- **PERF**: Performance anti-pattern detection.
- **SIM**: Code simplification suggestions.

**Pragmatic ignore rules:**
- `E722`: Bare except allowed with proper logging.
- `S108`: Hardcoded temp directory paths allowed.
- `S112`: try-except-continue patterns allowed.
- `PERF203`: try-except in loops allowed (financial data processing).

### Type Safety with MyPy

#### Configuration and Usage
```bash
# Type check all code (strict mode)
uv run mypy src/

# Type check specific module
uv run mypy src/finances/amazon/
```

**Type checking requirements:**
- **Strict mode enabled**: Comprehensive checks with zero errors tolerance.
- **Public API coverage**: All public functions require type annotations.
- **Strategic ignores**: Documented type: ignore for known library limitations.
- **Type stubs**: pandas-stubs, types-PyYAML, types-beautifulsoup4.

#### Strategic Type Ignore Patterns

When third-party library type stubs have limitations (especially pandas), use strategic
  `# type: ignore[specific-code]` with documentation:

```python
# pandas-stubs limitation: groupby iterator returns overly broad Union type
for order_id, order_group in orders_df.groupby("Order ID"):  # type: ignore[index]
    # Process group...
    pass
```

**Best practices:**
- Always use specific error codes: `# type: ignore[union-attr]` not `# type: ignore`.
- Add explanatory comments explaining why the ignore is necessary.
- Document known library limitations at module level.
- Prefer type guards and explicit annotations over ignores when possible.

#### Type Annotation Examples
```python
from typing import Any, Protocol
from finances.core import Money

def calculate_total(amounts: list[Money]) -> Money:
    """Calculate total from Money amounts with sign preservation."""
    return Money.from_cents(sum(m.to_cents() for m in amounts))

class Matcher(Protocol):
    """Protocol for transaction matching implementations."""

    def match_transactions(
        self,
        transactions: list[dict[str, Any]],
        orders: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        ...
```

### Pre-Commit Hooks

Lightweight pre-commit hooks (<2 seconds) provide immediate feedback:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks on all files
uv run pre-commit run --all-files

# Skip hooks for emergency commits (use sparingly)
git commit --no-verify
```

**Hook configuration:**
- **File formatting**: Trailing whitespace, EOF normalization, YAML/JSON validation.
- **Code formatting**: Black formatting (fast check mode).
- **Linting**: Ruff auto-fixable checks only.
- **Performance**: Optimized for <2s execution on typical commits.

**Note**: Heavy checks (mypy, pytest) run in CI/CD only to maintain fast commit workflow.

### Continuous Integration (GitHub Actions)

The `.github/workflows/quality.yml` workflow enforces all quality standards:

```yaml
# Runs on every push and pull request
jobs:
  format-check:   # Black formatting verification
  lint:           # Ruff comprehensive linting
  type-check:     # MyPy strict type checking (zero errors)
  test-coverage:  # Pytest with 60% coverage threshold
```

**Quality gates:**
- All formatting must match Black 110-character style.
- Zero Ruff linting errors allowed.
- Zero MyPy type checking errors allowed.
- Minimum 60% test coverage required.

**Viewing results:**
```bash
# Check workflow status locally before pushing
uv run black --check src/ tests/
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest --cov=src/finances --cov-report=term

# View CI results in GitHub
gh pr checks  # When in PR branch
```

## Development Workflow

### Git Workflow

1. **Feature Branches**: Create feature branches from main.
2. **Quality Gates**: All commits must pass pre-commit hooks.
3. **Pull Requests**: Code review required for all changes.
4. **Testing**: All tests must pass before merging.

### Code Review Guidelines

- **Functionality**: Does the code solve the intended problem?
- **Architecture**: Does it follow domain-driven design principles?
- **Quality**: Does it meet code quality standards?
- **Testing**: Are there appropriate tests with good coverage?
- **Documentation**: Are public APIs properly documented?
- **Security**: Are financial data and credentials handled securely?

### Coding Standards

#### Markdown Formatting Guidelines

All markdown files in this repository follow consistent formatting standards for improved
  readability and maintainability.

##### Core Formatting Rules

1. **One Sentence Per Line**: Each sentence should be on its own line for better version
  control and readability.

2. **110-Character Line Limit**: Lines should be wrapped when they exceed 110 characters,
  breaking at natural points for optimal readability.

3. **Two-Space Indentation for Wrapped Lines**: When a sentence is wrapped, indent
  continuation lines with exactly two spaces beyond the start of the sentence on the
  preceding line.

4. **Natural Break Points**: When wrapping long lines, break at natural points such as:
   - Commas and conjunctions
   - Clause boundaries
   - Before prepositions in long phrases
   - After colons or semicolons

5. **Sentence Completion**: Every sentence, list item, or other full sentence-like line
  should end with a period.

6. **Trailing Whitespace Removal**: Remove trailing whitespace from all lines, except when
  required by Markdown's formatting rules (such as for code blocks inside lists).

7. **POSIX Line Endings**: Files should end with a line break, per POSIX standards.

##### Examples

**Good formatting (110-character limit with 2-space indentation):**
```markdown
The Amazon Transaction Matching System creates automated linkage between Amazon order
  history data and corresponding YNAB credit card transactions.
This solves the challenge of understanding what Amazon purchases comprise each consolidated
  charge, enabling accurate categorization.

1. The quick brown fox jumps over the lazy dog and continues running through the forest
     until it reaches the river.

> The comprehensive financial analysis tool provides multi-timeframe insights including
>   statistical modeling, trend detection, and professional dashboard generation.
```

**Avoid (long lines without proper wrapping):**
```markdown
The Amazon Transaction Matching System creates automated linkage between Amazon order history data and
  corresponding YNAB credit card transactions. This solves the challenge of understanding what Amazon
  purchases comprise each consolidated charge.
```

**Avoid (missing periods on sentence-like lines):**
```markdown
- Feature request for improved matching accuracy
- Bug fix for currency conversion errors
```

**Good (periods on sentence-like lines):**
```markdown
- Feature request for improved matching accuracy.
- Bug fix for currency conversion errors.
```

##### Code Blocks and Lists

- Preserve existing code block formatting.
- Maintain proper indentation for nested lists.
- Keep inline code spans on single lines when possible.

##### Cross-References

When referencing this formatting standard in other documentation, use:
```markdown
See [Markdown Formatting Guidelines](CONTRIBUTING.md#markdown-formatting-guidelines) for details.
```

#### Documentation Requirements
```python
def calculate_confidence_score(
    amount_match: bool,
    date_proximity: int,
    merchant_match: bool
) -> float:
    """Calculate confidence score for transaction match.

    Args:
        amount_match: True if transaction amounts match exactly
        date_proximity: Days between transaction and order dates
        merchant_match: True if merchant names match

    Returns:
        Confidence score between 0.0 and 1.0

    Example:
        >>> calculate_confidence_score(True, 0, True)
        1.0
        >>> calculate_confidence_score(True, 2, False)
        0.75
    """
```

#### Error Handling Patterns
```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def safe_currency_conversion(value: str) -> Optional[int]:
    """Safely convert string currency to integer cents."""
    try:
        # Parse currency with proper validation
        decimal_value = Decimal(value.replace('$', '').replace(',', ''))
        return int(decimal_value * 100)
    except (ValueError, InvalidOperation) as e:
        logger.warning(f"Failed to convert currency '{value}': {e}")
        return None
```

### Commit Message Format

Use conventional commit format:

```
type(scope): brief description

Detailed explanation of changes, including:
- What was changed and why
- Any breaking changes
- References to issues or specifications

Examples:
feat(amazon): add multi-day order support for split shipments
fix(currency): prevent floating-point errors in milliunits conversion
docs(api): update Amazon matcher documentation
test(apple): add integration tests for email fetching
```

## Package Development

### Building and Distribution

```bash
# Build package
uv build

# Test package installation
uv pip install dist/finances-*.whl

# Verify CLI works from installed package
finances --version
```

### Version Management

Version is managed in `pyproject.toml`:
- Follow semantic versioning (MAJOR.MINOR.PATCH).
- Update version for releases.
- Tag releases in git.

### CLI Development

The unified CLI is built with Click and follows consistent patterns:

```python
import click
from typing import Optional

@click.group()
def domain():
    """Domain-specific commands."""
    pass

@domain.command()
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def process(ctx: click.Context, start: str, end: str, verbose: bool) -> None:
    """Process data for date range."""
    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"Processing {start} to {end}")

    # Implementation here
```

## Domain-Specific Guidelines

### Currency Handling (CRITICAL)

**NEVER use floating-point arithmetic for currency calculations.**
**ALWAYS use the Money type for all financial operations.**

#### Required Patterns
```python
from finances.core import Money

# CORRECT: Use Money type for all currency operations
def add_amounts(amount1: Money, amount2: Money) -> Money:
    return amount1 + amount2  # Money supports arithmetic

def format_currency(amount: Money) -> str:
    return str(amount)  # Money handles formatting

# INCORRECT: Never use float for currency
def bad_currency_math(dollars: float) -> float:  # DON'T DO THIS
    return dollars * 1.0825  # Floating-point errors!
```

#### Money Type Usage
```python
from finances.core import Money

# Creating Money from different sources
income = Money.from_milliunits(123456)    # YNAB income (positive)
expense = Money.from_milliunits(-123456)  # YNAB expense (negative)
amount = Money.from_dollars("$12.34")     # String parsing
cents_amount = Money.from_cents(1234)     # Direct cents

# Sign preservation (critical for expenses)
ynab_expense = -123456  # YNAB milliunits (negative = expense)
money_expense = Money.from_milliunits(ynab_expense)
assert money_expense.to_cents() == -12345  # Sign preserved

# Conversions
cents = money_expense.to_cents()          # -12345
milliunits = money_expense.to_milliunits()  # -123450
display = str(money_expense)              # "$-123.45"
absolute = money_expense.abs()            # Money(cents=12345)

# Arithmetic preserves sign
net = income + expense  # Correct addition
```

### Amazon Domain Guidelines

- **Multi-account support**: Handle multiple Amazon accounts automatically.
- **Multi-day orders**: Support orders shipping across multiple days.
- **Split payments**: Handle partial order matches with item tracking.
- **Confidence scoring**: Use 3-strategy system (Complete, Split, Fuzzy).

### Apple Domain Guidelines

- **1:1 transaction model**: Leverage Apple's direct billing approach.
- **Multi-format parsing**: Support legacy and modern receipt formats.
- **Email integration**: IMAP-based receipt fetching with security.
- **Family accounts**: Handle multiple Apple IDs with proper attribution.

### YNAB Integration Guidelines

- **Three-phase workflow**: Generate → Review → Apply for safety.
- **Audit trails**: Complete change tracking with reversibility.
- **Batch operations**: Efficient bulk transaction updates.
- **Error recovery**: Graceful handling of API failures.

## Extension Guides

### Adding a New Flow Node

Flow nodes are the building blocks of the financial processing system.
Each node represents a distinct operation (data fetching, matching, analysis) with explicit
  dependencies on other nodes.

#### Step-by-Step Guide

**1. Create the flow function** in the appropriate domain's `flow.py` module:

```python
# In src/finances/newdomain/flow.py
from finances.core.flow import FlowContext, FlowResult

def new_operation_flow(context: FlowContext) -> FlowResult:
    """
    Execute new domain operation.

    Args:
        context: Flow execution context with shared state

    Returns:
        FlowResult with execution details and outputs
    """
    from finances.newdomain.datastore import NewDomainDataStore

    # Initialize datastore
    datastore = NewDomainDataStore(base_path=Path("data/newdomain"))

    # Load input data
    input_data = datastore.load()

    # Process data (implement your business logic here)
    results = process_data(input_data)

    # Save results
    datastore.save(results)

    # Return structured result
    return FlowResult(
        success=True,
        items_processed=len(results),
        new_items=len([r for r in results if r.is_new]),
        outputs=[datastore.output_path],
        execution_time_seconds=2.5
    )
```

**2. Register the node** in `src/finances/cli/flow.py` via `setup_flow_nodes()`:

```python
# In src/finances/cli/flow.py
from finances.newdomain.flow import new_operation_flow
from finances.newdomain.datastore import NewDomainDataStore

def setup_flow_nodes(registry: FlowNodeRegistry) -> None:
    # ... existing registrations ...

    # Initialize datastore for change detection
    new_datastore = NewDomainDataStore(base_path=Path("data/newdomain"))

    # Register new flow node
    registry.register_function_node(
        name="new_operation",  # Unique node identifier
        func=new_operation_flow,
        dependencies=["ynab_sync"],  # Depends on YNAB data
        change_detector=lambda ctx: check_new_operation_changes(ctx, new_datastore),
        data_summary_func=lambda ctx: new_datastore.to_node_data_summary()
    )
```

**3. Implement change detection logic**:

```python
# In src/finances/cli/flow.py or domain-specific module
def check_new_operation_changes(
    context: FlowContext,
    datastore: NewDomainDataStore
) -> tuple[bool, list[str]]:
    """
    Determine if new_operation node needs to execute.

    Args:
        context: Flow execution context
        datastore: Domain-specific datastore

    Returns:
        Tuple of (needs_execution, list_of_change_reasons)
    """
    reasons = []

    # Check if input data exists
    if not datastore.exists():
        reasons.append("No input data found")
        return True, reasons

    # Check if upstream dependencies have new outputs
    if "ynab_sync" in context.archive_manifest:
        ynab_file = context.archive_manifest["ynab_sync"]
        if datastore.last_modified() < ynab_file.stat().st_mtime:
            reasons.append("YNAB data updated")
            return True, reasons

    # No changes detected
    return False, ["No changes detected"]
```

**4. Test the flow node**:

```python
# In tests/integration/test_newdomain_flow.py
import pytest
from finances.core.flow import FlowContext
from finances.newdomain.flow import new_operation_flow

def test_new_operation_flow_success(tmp_path):
    """Test new operation flow executes successfully."""
    # Setup test data
    context = FlowContext(start_time=datetime.now())

    # Execute flow node
    result = new_operation_flow(context)

    # Verify results
    assert result.success
    assert result.items_processed > 0
    assert len(result.outputs) > 0
```

**5. Verify in complete flow**:

```bash
# List all flow nodes to verify registration
finances flow list-nodes

# Show flow graph with new node
finances flow show-graph

# Execute complete flow
finances flow go
```

#### Best Practices

- **Single responsibility**: Each node should do one thing well.
- **Idempotent execution**: Running a node multiple times with same inputs produces same outputs.
- **Change detection**: Only execute when upstream data or dependencies change.
- **Structured results**: Always return FlowResult with meaningful metadata.
- **Error handling**: Catch exceptions and return `FlowResult(success=False, error_message=str(e))`.

### Creating a New DataStore

DataStores abstract data persistence from business logic, providing consistent interface for
  loading, saving, and querying data.

#### Implementation Pattern

```python
# In src/finances/newdomain/datastore.py
from datetime import datetime
from pathlib import Path
from typing import Optional

from finances.core.datastore import DataStore
from finances.core.flow import NodeDataSummary
from finances.newdomain.models import NewDomainData

class NewDomainDataStore:
    """DataStore for new domain data persistence and metadata queries."""

    def __init__(self, base_path: Path):
        """
        Initialize datastore.

        Args:
            base_path: Root directory for data storage
        """
        self.base_path = base_path
        self.output_path = base_path / "results.json"

    def exists(self) -> bool:
        """Check if data exists in storage."""
        return self.output_path.exists()

    def load(self) -> list[NewDomainData]:
        """
        Load data from storage.

        Returns:
            List of NewDomainData domain models

        Raises:
            FileNotFoundError: If data doesn't exist
            ValueError: If data is invalid/corrupted
        """
        if not self.exists():
            raise FileNotFoundError(f"Data not found: {self.output_path}")

        # Load JSON and convert to domain models
        from finances.core.json_utils import read_json
        data_dicts = read_json(self.output_path)
        return [NewDomainData.from_dict(d) for d in data_dicts]

    def save(self, data: list[NewDomainData]) -> None:
        """
        Save data to storage.

        Args:
            data: List of NewDomainData to persist
        """
        # Create directory if needed
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Convert domain models to dicts and save
        from finances.core.json_utils import write_json
        data_dicts = [d.to_dict() for d in data]
        write_json(self.output_path, data_dicts)

    def last_modified(self) -> Optional[datetime]:
        """Get timestamp of most recent data modification."""
        if not self.exists():
            return None
        timestamp = self.output_path.stat().st_mtime
        return datetime.fromtimestamp(timestamp)

    def age_days(self) -> Optional[int]:
        """Get age of data in days since last modification."""
        last_mod = self.last_modified()
        if not last_mod:
            return None
        age = datetime.now() - last_mod
        return age.days

    def item_count(self) -> Optional[int]:
        """Get count of items in stored data."""
        if not self.exists():
            return None
        data = self.load()
        return len(data)

    def size_bytes(self) -> Optional[int]:
        """Get total storage size in bytes."""
        if not self.exists():
            return None
        return self.output_path.stat().st_size

    def summary_text(self) -> str:
        """Get human-readable summary of current data state."""
        if not self.exists():
            return "No data found"

        count = self.item_count()
        age = self.age_days()

        if age == 0:
            age_str = "today"
        elif age == 1:
            age_str = "yesterday"
        else:
            age_str = f"{age} days ago"

        return f"{count} items (updated {age_str})"

    def to_node_data_summary(self) -> NodeDataSummary:
        """Convert DataStore state to NodeDataSummary for FlowNode integration."""
        return NodeDataSummary(
            exists=self.exists(),
            last_updated=self.last_modified(),
            age_days=self.age_days(),
            item_count=self.item_count(),
            size_bytes=self.size_bytes(),
            summary_text=self.summary_text()
        )
```

#### DataStore Best Practices

- **Domain models only**: Never return dicts or DataFrames from `load()`.
- **Graceful errors**: Raise FileNotFoundError if data missing, ValueError if corrupted.
- **Metadata efficiency**: Cache metadata queries to avoid repeated file I/O.
- **Directory creation**: Use `mkdir(parents=True, exist_ok=True)` in `save()`.
- **JSON formatting**: Always use `finances.core.json_utils` for consistent formatting.

### Working with Domain Models

Domain models are typed dataclasses that represent business entities (transactions, orders,
  receipts).
They use Money and FinancialDate primitives for type safety.

#### Creating Domain Models

```python
# In src/finances/newdomain/models.py
from dataclasses import dataclass
from typing import Optional

from finances.core import Money, FinancialDate

@dataclass(frozen=True)
class NewDomainModel:
    """
    Domain model for new entity type.

    Attributes:
        id: Unique identifier
        amount: Transaction amount (use Money for type safety)
        transaction_date: Date of transaction (use FinancialDate)
        description: Human-readable description
        metadata: Optional additional data
    """
    id: str
    amount: Money
    transaction_date: FinancialDate
    description: str
    metadata: Optional[dict[str, str]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "NewDomainModel":
        """
        Deserialize from dictionary (JSON loading).

        Args:
            data: Dictionary with model fields

        Returns:
            NewDomainModel instance

        Raises:
            KeyError: If required fields missing
            ValueError: If data invalid
        """
        return cls(
            id=data["id"],
            amount=Money.from_milliunits(data["amount_milliunits"]),
            transaction_date=FinancialDate.from_string(data["transaction_date"]),
            description=data["description"],
            metadata=data.get("metadata")  # Optional field
        )

    def to_dict(self) -> dict:
        """
        Serialize to dictionary (JSON saving).

        Returns:
            Dictionary representation for JSON serialization
        """
        result = {
            "id": self.id,
            "amount_milliunits": self.amount.to_milliunits(),
            "transaction_date": str(self.transaction_date),
            "description": self.description
        }

        # Include optional fields only if present
        if self.metadata:
            result["metadata"] = self.metadata

        return result
```

#### Domain Model Best Practices

- **Frozen dataclasses**: Always use `@dataclass(frozen=True)` for immutability.
- **Money for currency**: Use Money type for all currency amounts (never int or float).
- **FinancialDate for dates**: Use FinancialDate for all date fields (never string or datetime).
- **Required serialization**: Always implement `from_dict()` and `to_dict()` methods.
- **Type hints**: Use full type annotations on all fields.
- **Comprehensive tests**: Test construction, conversion, edge cases, validation.

#### Using Domain Models in Business Logic

```python
from finances.newdomain.models import NewDomainModel

def process_transactions(
    transactions: list[NewDomainModel]
) -> list[NewDomainModel]:
    """
    Process transactions with domain model operations.

    Args:
        transactions: List of NewDomainModel instances

    Returns:
        Filtered and transformed transactions
    """
    # Filter using domain model fields (type-safe)
    filtered = [
        t for t in transactions
        if t.amount.to_cents() > 1000  # $10.00 minimum
        and t.transaction_date.to_date() >= date(2024, 1, 1)
    ]

    # Transform using domain model operations
    results = []
    for transaction in filtered:
        # Money arithmetic is type-safe
        adjusted_amount = transaction.amount + Money.from_cents(50)

        # Create new immutable instance with changes
        results.append(
            NewDomainModel(
                id=transaction.id,
                amount=adjusted_amount,
                transaction_date=transaction.transaction_date,
                description=f"Adjusted: {transaction.description}",
                metadata=transaction.metadata
            )
        )

    return results
```

### Writing Tests

The project follows an inverted test pyramid: E2E → Integration → Unit (priority order).

See `tests/README.md` for complete testing philosophy.

#### E2E Tests (Priority 1)

E2E tests execute complete CLI workflows via subprocess, catching integration bugs that unit tests
  miss.

```python
# In tests/e2e/test_newdomain_workflow.py
import subprocess
import pytest
from pathlib import Path

def test_newdomain_complete_workflow(tmp_path):
    """Test complete new domain workflow from end to end."""
    # Setup test environment
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create test input data
    input_file = data_dir / "input.json"
    input_file.write_text('{"test": "data"}')

    # Execute CLI command via subprocess (real user workflow)
    result = subprocess.run(
        ["finances", "newdomain", "process", "--input-file", str(input_file)],
        capture_output=True,
        text=True
    )

    # Verify command succeeded
    assert result.returncode == 0
    assert "Processing complete" in result.stdout

    # Verify output files created
    output_file = data_dir / "newdomain" / "results.json"
    assert output_file.exists()

    # Verify output data is correct
    from finances.core.json_utils import read_json
    results = read_json(output_file)
    assert len(results) > 0
```

#### Integration Tests (Priority 2)

Integration tests use CliRunner (faster than subprocess) and test multiple components with real
  file system operations.

```python
# In tests/integration/test_newdomain_integration.py
from click.testing import CliRunner
from finances.cli.main import cli

def test_newdomain_integration_with_datastore(tmp_path, monkeypatch):
    """Test new domain with DataStore integration."""
    # Setup test data directory
    data_dir = tmp_path / "data"
    monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))

    # Create input data
    input_path = data_dir / "input.json"
    from finances.core.json_utils import write_json
    write_json(input_path, [{"id": "1", "amount_milliunits": 12345}])

    # Execute via CliRunner (faster than subprocess)
    runner = CliRunner()
    result = runner.invoke(cli, ["newdomain", "process", "--input-file", str(input_path)])

    # Verify execution
    assert result.exit_code == 0

    # Verify DataStore saved results
    from finances.newdomain.datastore import NewDomainDataStore
    datastore = NewDomainDataStore(base_path=data_dir / "newdomain")
    assert datastore.exists()
    results = datastore.load()
    assert len(results) == 1
```

#### Unit Tests (Priority 3)

Unit tests isolate complex business logic for focused testing.

```python
# In tests/unit/test_newdomain/test_processor.py
import pytest
from finances.core import Money, FinancialDate
from finances.newdomain.models import NewDomainModel
from finances.newdomain.processor import process_transactions

def test_processor_filters_by_amount():
    """Test processor filters transactions by minimum amount."""
    # Create test data with domain models
    transactions = [
        NewDomainModel(
            id="1",
            amount=Money.from_cents(500),  # $5.00 - below minimum
            transaction_date=FinancialDate.from_string("2024-10-15"),
            description="Small transaction"
        ),
        NewDomainModel(
            id="2",
            amount=Money.from_cents(1500),  # $15.00 - above minimum
            transaction_date=FinancialDate.from_string("2024-10-15"),
            description="Large transaction"
        )
    ]

    # Execute business logic
    results = process_transactions(transactions)

    # Verify filtering
    assert len(results) == 1
    assert results[0].id == "2"
    assert results[0].amount.to_cents() == 1500
```

#### Test Data Guidelines

**NEVER use real financial data or PII in tests.**

Use synthetic data generators from `tests/fixtures/synthetic_data.py`:

```python
from tests.fixtures.synthetic_data import (
    generate_synthetic_ynab_transactions,
    generate_synthetic_amazon_orders,
    generate_synthetic_apple_receipts
)

def test_with_synthetic_data():
    """Test with realistic synthetic data."""
    transactions = generate_synthetic_ynab_transactions(count=10)
    orders = generate_synthetic_amazon_orders(count=5)

    # Test with realistic but fake data
    results = match_transactions(transactions, orders)
    assert len(results) > 0
```

### Debugging the Flow System

Common issues when working with flow nodes and execution.

#### Issue: Flow Node Not Executing

**Symptoms**: Node skipped in `finances flow go` output.

**Causes**:
1. Change detection returns `(False, ...)` - no changes detected.
2. Dependency failed - node blocked by failed upstream dependency.
3. Node excluded via `--nodes-excluded` flag.

**Debugging**:
```bash
# Force execution of all nodes
finances flow go --force-all

# Show detailed change detection reasoning
finances flow go --verbose

# List all registered nodes
finances flow list-nodes

# Show dependency graph
finances flow show-graph
```

**Fix change detection**:
```python
# Add debug logging to change detector
def check_changes(context: FlowContext) -> tuple[bool, list[str]]:
    import logging
    logger = logging.getLogger(__name__)

    if not datastore.exists():
        logger.info("No data found - triggering execution")
        return True, ["No data found"]

    # Add more debug logging for each check
    logger.info(f"Data age: {datastore.age_days()} days")
    # ...
```

#### Issue: Flow Node Fails Silently

**Symptoms**: Node reports success but doesn't produce expected output.

**Causes**:
1. Exception caught and logged but not propagated to FlowResult.
2. FlowResult returned with `success=True` despite internal errors.
3. Output paths not added to FlowResult.

**Debugging**:
```python
def problematic_flow(context: FlowContext) -> FlowResult:
    try:
        # Process data
        results = process_data()

        # WRONG: Exception caught but success=True
        return FlowResult(success=True, items_processed=0)

    except Exception as e:
        # Log error but return success
        logger.error(f"Error: {e}")
        return FlowResult(success=True)  # BUG: Should be success=False

# FIXED VERSION:
def fixed_flow(context: FlowContext) -> FlowResult:
    try:
        results = process_data()

        if not results:
            return FlowResult(
                success=False,
                error_message="No results produced"
            )

        return FlowResult(
            success=True,
            items_processed=len(results),
            outputs=[output_path]  # Include outputs for downstream change detection
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return FlowResult(
            success=False,
            error_message=str(e)
        )
```

#### Issue: Change Detection Too Aggressive

**Symptoms**: Nodes re-execute even when no changes occurred.

**Causes**:
1. Change detector always returns `True`.
2. Timestamp comparison includes seconds (files touched by unrelated operations).
3. Upstream dependency always produces new outputs (timestamp changes on every run).

**Debugging**:
```python
# Add detailed logging to change detector
def check_changes(context: FlowContext) -> tuple[bool, list[str]]:
    reasons = []

    output_time = datastore.last_modified()
    input_time = input_datastore.last_modified()

    logger.info(f"Output time: {output_time}")
    logger.info(f"Input time: {input_time}")

    if output_time < input_time:
        reasons.append(f"Input newer ({input_time}) than output ({output_time})")
        return True, reasons

    return False, ["No changes detected"]
```

**Fix timestamp precision issues**:
```python
from datetime import timedelta

# Use minute-level precision instead of seconds
if output_time < input_time - timedelta(seconds=30):
    # Allow 30-second window for file system delays
    reasons.append("Input significantly newer than output")
    return True, reasons
```

### YNAB Development Workflow

Specific guidelines for working with YNAB integration.

#### Local Development Setup

**1. Get YNAB Personal Access Token**:
- Go to https://app.ynab.com/settings/developer
- Generate new Personal Access Token
- Copy token to `.env` file:
  ```bash
  YNAB_API_TOKEN=your_token_here
  ```

**2. Verify authentication**:
```bash
# Test YNAB API connection
finances ynab sync-cache

# Verify cache files created
ls -la data/ynab/cache/
# Should see: accounts.json, categories.json, transactions.json
```

#### Testing YNAB Integration

**Use test mode to avoid affecting real budget**:

```python
# In tests/integration/test_ynab_integration.py
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_ynab_client():
    """Mock YNAB API client for testing."""
    with patch("finances.ynab.ynab_client.YNABClient") as mock:
        # Setup mock responses
        mock.return_value.get_accounts.return_value = [
            {"id": "account_1", "name": "Checking", "balance": 100000}
        ]
        yield mock

def test_ynab_sync_with_mock(mock_ynab_client, tmp_path, monkeypatch):
    """Test YNAB sync without real API calls."""
    monkeypatch.setenv("FINANCES_DATA_DIR", str(tmp_path))

    # Execute sync
    from finances.ynab.flow import ynab_sync_flow
    result = ynab_sync_flow(FlowContext(start_time=datetime.now()))

    # Verify mock called
    mock_ynab_client.return_value.get_accounts.assert_called_once()

    # Verify cache created
    assert result.success
```

#### Debugging YNAB Sync Issues

**Check API rate limits**:
```python
# YNAB API allows 200 requests per hour
# Check rate limit status in response headers
import requests

response = requests.get(
    "https://api.ynab.com/v1/budgets",
    headers={"Authorization": f"Bearer {api_token}"}
)

print(f"Rate limit: {response.headers.get('X-Rate-Limit')}")
print(f"Remaining: {response.headers.get('X-Rate-Limit-Remaining')}")
```

**Verify cache structure**:
```bash
# Check JSON structure
jq '.accounts | length' data/ynab/cache/accounts.json
jq '.category_groups | length' data/ynab/cache/categories.json
jq 'length' data/ynab/cache/transactions.json

# Validate JSON format
jq empty data/ynab/cache/*.json && echo "All valid JSON"
```

**Test with small date range**:
```bash
# Fetch only recent transactions for faster testing
finances ynab sync-cache --since-date 2024-10-01
```

## Security Considerations

### Data Protection

- **No sensitive data in code**: All financial data excluded from version control.
- **Environment variables**: Use `.env` file for sensitive configuration.
- **Local processing**: All analysis performed locally (no cloud services).
- **Encrypted communication**: HTTPS/IMAPS for all external connections.

### Best Practices

```python
import os
from typing import Optional

def get_api_token() -> Optional[str]:
    """Safely retrieve API token from environment."""
    token = os.getenv('YNAB_API_TOKEN')
    if not token:
        logger.error("YNAB_API_TOKEN not found in environment")
        return None

    # Never log the actual token
    logger.info(f"Retrieved API token (length: {len(token)})")
    return token
```

### Credential Management

- **API tokens**: Use YNAB personal access tokens (never passwords).
- **Email security**: Use app-specific passwords for email access.
- **No hardcoded secrets**: All credentials via environment variables.
- **Audit trails**: Log access patterns without exposing secrets.

## Troubleshooting

### Common Development Issues

#### Import Errors After Installation
```bash
# Reinstall in development mode
uv pip install -e .

# Verify package location
python -c "import finances; print(finances.__file__)"
```

#### Test Failures
```bash
# Run specific failing test with verbose output
uv run pytest tests/unit/core/test_money.py::test_negative_from_milliunits -v

# Clear pytest cache
rm -rf .pytest_cache __pycache__ src/finances/__pycache__

# Reinstall package and rerun
uv pip install -e . && uv run pytest
```

#### Type Checking Errors
```bash
# Check specific file
uv run mypy src/finances/amazon/matcher.py

# Install type stubs for dependencies
uv add --dev types-requests pandas-stubs

# Ignore specific lines (use sparingly)
result = api_call()  # type: ignore[no-untyped-call]
```

#### Pre-commit Hook Issues
```bash
# Update hook versions
uv run pre-commit autoupdate

# Run specific hook
uv run pre-commit run black

# Bypass hooks for emergency (use sparingly)
git commit --no-verify -m "emergency fix"
```

### Performance Issues

#### Slow Tests
```bash
# Run tests with profiling
uv run pytest --durations=10

# Skip slow tests during development
uv run pytest -m "not slow"

# Parallel test execution
uv run pytest -n auto
```

#### CLI Responsiveness
```bash
# Profile CLI startup time
time finances --help

# Check for expensive imports
python -c "import sys; import time; start=time.time(); import finances; \
  print(f'Import time: {time.time()-start:.3f}s')"
```

### Getting Help

1. **Check existing issues**: Review troubleshooting sections in documentation.
2. **Run diagnostics**: Use verbose flags for detailed error information.
3. **Verify environment**: Ensure all dependencies and configuration are correct.
4. **Test isolation**: Reproduce issues with minimal test cases.
5. **Documentation**: Update this guide when discovering new solutions.

## Contributing Workflow Summary

1. **Setup**: Clone repository, install dependencies, configure environment.
2. **Development**: Create feature branch, write code following standards.
3. **Testing**: Write comprehensive tests, ensure coverage requirements.
4. **Quality**: Run formatting, linting, and type checking.
5. **Review**: Submit pull request with clear description.
6. **Integration**: Address feedback, ensure all checks pass.
7. **Documentation**: Update relevant documentation for changes.

This guide is a living document.
Please update it as the project evolves and new patterns emerge.
