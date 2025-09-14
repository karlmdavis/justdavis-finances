# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a personal finance management repository for the Davis family. The primary focus is on:
- Tracking and managing family finances
- Creating automation for financial data processing
- Managing transaction categorization from various sources
- Analyzing cash flow patterns and financial trends

## Key Context

### Financial Management Tools
- **Primary Tool**: YNAB (You Need A Budget) - used for transaction tracking, categorization, and reporting
- **YNAB CLI**: Command-line tool for extracting YNAB data (`ynab` command)
- **Main Challenge**: Manual categorization of transactions, especially for:
  - Amazon.com purchases (multiple items per transaction)
  - Apple App Store purchases (bundled transactions)
  - Retirement account balance updates (no automatic sync)

### Available Workflows and Scripts

#### 1. YNAB Data Workflow (`YNAB_DATA_WORKFLOW.md`)
- Documents the process for extracting and caching YNAB data locally
- Uses `ynab` CLI tool with proper syntax: `ynab --output json list [resource]`
- Maintains three JSON files in `ynab-data/`:
  - `accounts.json` - Account information with nested structure
  - `categories.json` - Category groups with nested categories
  - `transactions.json` - Transaction array

#### 2. Amazon Data Workflow (`amazon/README.md`)
- Documents Amazon order history data extraction and management
- Supports multi-account household setups (karl, erica, etc.)
- Directory naming convention: `YYYY-MM-DD_accountname_amazon_data/`
- Automatic discovery of all account directories
- Used by Amazon transaction matching system

#### 3. Cash Flow Analysis (`analysis/cash_flow/cash_flow_analysis.py`)
- Python script for comprehensive financial analysis
- Generates timestamped dashboard images in `analysis/cash_flow/results/`
- Features multiple smoothing techniques (moving averages)
- Excludes unreliable data before May 2024
- Key accounts analyzed: Chase Checking, Chase Credit Card, Apple Card, Apple Cash, Apple Savings

#### 4. Amazon Transaction Matching System (`analysis/amazon_transaction_matching/`)
- **Primary purpose**: Automatically match YNAB transactions to Amazon orders
- **Architecture**: Simplified 3-strategy system for clean, maintainable code
- **Key scripts**:
  - `match_single_transaction.py` - Process individual transactions using SimplifiedMatcher
  - `match_transactions_batch.py` - Batch process date ranges with 3-strategy architecture
- **Supporting modules**:
  - `order_grouper.py` - Unified order grouping (complete orders, shipments, daily shipments)
  - `match_scorer.py` - Confidence scoring and match result creation
  - `split_payment_matcher.py` - Split payment handling for partial order matches
- **Multi-account support**: Automatically discovers and searches all Amazon accounts
- **Precision handling**: Uses integer cents arithmetic to avoid floating-point errors
- **Match strategies**: 3 clean strategies replacing complex 5-strategy system:
  1. **Complete Match** - Exact order/shipment matches (high confidence)
  2. **Split Payment** - Partial order matches with item tracking
  3. **Fuzzy Match** - Approximate matches with flexible tolerances
- **Output**: Timestamped JSON files in `analysis/amazon_transaction_matching/results/`
- **Current performance**: 94.7% match rate maintained with simplified architecture
- **Multi-day orders**: Handles orders that ship across multiple days
- **Usage patterns**:
  ```bash
  # Process a month of transactions
  uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
    --start 2024-07-01 --end 2024-07-31 --verbose
  
  # Process specific accounts only
  uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
    --start 2024-07-01 --end 2024-07-31 --accounts karl erica
    
  # Disable split payment matching if needed
  uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
    --start 2024-07-01 --end 2024-07-31 --disable-split
  ```

#### 5. Apple Transaction Matching System (`analysis/apple_transaction_matching/`)
- **Primary purpose**: Automatically match YNAB transactions to Apple receipt data
- **Architecture**: Simplified 2-strategy system for Apple's 1:1 transaction model
- **Key scripts**:
  - `match_single_transaction.py` - Process individual transactions
  - `match_transactions_batch.py` - Batch process date ranges
- **Supporting modules**:
  - `apple_matcher.py` - Core matching logic with exact and date window strategies
  - `match_scorer.py` - Confidence scoring adapted for Apple patterns
  - `apple_receipt_loader.py` - Apple receipt data loading and normalization
- **Multi-Apple ID support**: Automatically discovers and searches all family Apple accounts
- **Integration**: Works with Apple receipt extraction system (`apple/scripts/`)
- **Match strategies**: 2 clean strategies for Apple's simpler transaction model:
  1. **Exact Match** - Same date + exact amount match (confidence 1.0)
  2. **Date Window Match** - ±1-2 days with exact amount (confidence 0.75-0.90)
- **Output**: Timestamped JSON files in `analysis/apple_transaction_matching/results/`
- **Current performance**: 85.1% match rate with 0.871 average confidence
- **Processing speed**: ~0.005 seconds per transaction (faster than Amazon)
- **Usage patterns**:
  ```bash
  # Process a month of transactions
  uv run python analysis/apple_transaction_matching/match_transactions_batch.py \
    --start 2024-07-01 --end 2024-07-31 --verbose
  
  # Match specific transaction by ID
  uv run python analysis/apple_transaction_matching/match_single_transaction.py \
    --transaction-id "abc123-def456-..." --verbose
  ```

#### 6. CSV Analysis Tools (`analysis/csv-tools/`)
- **Purpose**: Safe exploration of CSV data using nushell
- **Main tool**: `open.nu` - Generic CSV wrapper with pipeline support
- **Safety features**: Read-only operations, path validation
- **Usage examples**:
  ```bash
  # Basic inspection
  analysis/csv-tools/open.nu "file.csv" "first 5"
  
  # Filtering and selection
  analysis/csv-tools/open.nu "file.csv" "where 'column' =~ 'pattern' | select 'col1' 'col2'"
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
1. Transaction categorization assistance (Amazon ✅ solved, Apple ✅ solved)
2. Receipt and order history parsing (Amazon ✅ solved, Apple ✅ solved)
3. Data import/export utilities for YNAB
4. Reporting and analysis tools
5. Cash flow trend analysis and projections

### Directory Conventions
- `ynab-data/` - Cached YNAB data (gitignored)
- `amazon/data/` - Amazon order history data (gitignored)
- `apple/data/` - Apple receipt emails (gitignored)
- `apple/exports/` - Parsed Apple receipt exports (gitignored)
- `analysis/*/results/` - All generated outputs with timestamps (gitignored)
- `ynab-exports/` - YNAB export files

### Python Environment
- Uses `uv` for dependency management
- Dependencies defined in `pyproject.toml`
- Run scripts with: `uv run python script.py`
- External dependency: `nushell` (install via Homebrew)

### Important Implementation Notes
1. **Currency handling**: 
   - YNAB amounts are in milliunits (1000 milliunits = $1.00)
   - Amazon matching system uses integer cents internally (avoid floating-point precision errors)
   - Convert: `milliunits_to_cents(amount) = abs(milliunits // 10)`
   - Display: `cents_to_dollars_str(cents) = f"{cents / 100:.2f}"`
2. **Date handling**: Transaction dates before May 2024 may have incomplete data
3. **JSON structures**: Use proper jq paths for nested structures (e.g., `.accounts[0]` not `.[0]`)
4. **Output organization**: Always create output directories if they don't exist
5. **Timestamps**: Use format `YYYY-MM-DD_HH-MM-SS_filename` for all generated files
6. **Path handling**: Use paths relative to script location, not working directory
7. **Multi-account support**: Amazon data uses `YYYY-MM-DD_accountname_amazon_data/` naming
8. **Working directory**: Stay in the personal/finances/ directory as much as possible, and run commands/scripts below it using their relative path. If you get a file or directory not found error, run `pwd` and try to navigate back to `personal/finances/` before retrying.
9. **Python execution**: Use `uv run python3 -c ...` instead of just `python3 -c ...` when trying to run ad-hoc Python.
10. **Markdown formatting**: When editing documentation files (README.md, CLAUDE.md), follow the existing line wrapping style:
    - Wrap long lines at approximately 80-120 characters for readability
    - Use 2-space indentation for continuation lines in paragraphs
    - Match the existing formatting patterns in each file
    - Example: "This is a long sentence that should be wrapped\n  to maintain consistency with existing formatting."

## Security Considerations
- Never commit sensitive financial data, account numbers, or API credentials
- Use environment variables or secure credential storage for any API keys
- Ensure all financial data remains private and encrypted where applicable
- **Gitignored directories**: 
  - `ynab-data/` (YNAB financial data)
  - `amazon/data/` (Amazon order history)
  - `apple/data/` (Apple receipt emails)
  - `apple/exports/` (parsed Apple receipt data)
  - `analysis/*/results/` (all generated reports and outputs)

## Recent Major Improvements

### Apple Transaction Matching System Implementation (September 2024)
- **Complete Apple ecosystem**: Implemented full Apple receipt extraction and transaction matching system
- **Email-based receipt parsing**: Extracts itemized purchase data from Apple receipt emails with 100% parsing success
- **1:1 transaction model**: Simplified matching logic leveraging Apple's direct transaction model
- **Multi-Apple ID support**: Handles all family Apple accounts automatically with account attribution
- **High match rate**: Achieved 85.1% match rate with 0.871 average confidence on production data
- **Enhanced email search**: IMAP fetcher searches all folders, discovering 87 additional archived receipts
- **HTML-only parsing**: Streamlined from 3-parser system to single robust HTML parser with 100% coverage

Key technical innovations:
1. **Simplified 2-strategy matching**: Exact match + date window strategies optimized for Apple's transaction patterns
2. **Receipt email integration**: Direct integration with Apple's receipt email system for complete purchase history
3. **HTML parser consolidation**: Single EnhancedHTMLParser handles both legacy (94.2%) and modern (5.8%) receipt formats

### Amazon Transaction Matching System Overhaul (August 2024)
- **Architecture simplification**: Replaced complex 5-strategy system with clean 3-strategy architecture
- **Code maintainability**: Modular design with separate files for grouping, scoring, and split payments
- **Precision fixes**: Eliminated floating-point currency errors using integer cents
- **Multi-day order support**: Now handles orders that ship across multiple days  
- **Performance improvement**: Maintained 94.7% match rate with simplified, more reliable code
- **Multi-account architecture**: Supports household with multiple Amazon accounts
- **Split payment enhancement**: Improved partial order matching with persistent item tracking

Key technical breakthroughs:
1. **Simplified Architecture**: 3 focused strategies (Complete Match, Split Payment, Fuzzy Match) replace complex 5-strategy system
2. **Modular Design**: Clean separation of concerns with `order_grouper.py`, `match_scorer.py`, and `split_payment_matcher.py`
3. **Multi-day Orders**: Fixed critical bug where exact amount matches failed due to single-day shipping restriction