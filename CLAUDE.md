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
    See [Markdown Formatting Guidelines](CONTRIBUTORS.md#markdown-formatting-guidelines) for
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
