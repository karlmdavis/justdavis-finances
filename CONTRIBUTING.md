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
from finances.core.currency import milliunits_to_cents

@pytest.mark.unit
@pytest.mark.currency
def test_milliunits_conversion():
    """Test YNAB milliunits to cents conversion."""
    assert milliunits_to_cents(123456) == 12345
    assert milliunits_to_cents(-123456) == 12345  # Always positive
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
from typing import Any, Optional, Protocol

def milliunits_to_cents(milliunits: int) -> int:
    """Convert YNAB milliunits to integer cents."""
    return abs(milliunits // 10)

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

#### Required Patterns
```python
# CORRECT: Integer arithmetic only
def add_amounts(amount1_cents: int, amount2_cents: int) -> int:
    return amount1_cents + amount2_cents

def format_currency(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"

# INCORRECT: Never use float for currency
def bad_currency_math(dollars: float) -> float:  # DON'T DO THIS
    return dollars * 1.0825  # Floating-point errors!
```

#### Currency Conversion Functions
```python
from finances.core.currency import (
    milliunits_to_cents,    # YNAB milliunits -> integer cents
    cents_to_milliunits,    # Integer cents -> YNAB milliunits
    format_cents,           # Integer cents -> display string
    parse_currency_string   # String -> integer cents
)

# Always use these centralized functions
ynab_amount = -123456  # YNAB milliunits
cents = milliunits_to_cents(ynab_amount)  # 12345 cents
display = format_cents(cents)  # "$123.45"
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
uv run pytest tests/unit/core/test_currency.py::test_milliunits_conversion -v

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
