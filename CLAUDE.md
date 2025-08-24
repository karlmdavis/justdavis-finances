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
- **Key scripts**:
  - `match_single_transaction.py` - Process individual transactions
  - `match_transactions_batch.py` - Batch process date ranges
- **Multi-account support**: Automatically discovers and searches all Amazon accounts
- **Precision handling**: Uses integer cents arithmetic to avoid floating-point errors
- **Match strategies**: 5 different algorithms (exact amount, shipment groups, date windows, etc.)
- **Output**: Timestamped JSON files in `analysis/amazon_transaction_matching/results/`
- **Current performance**: 94.7% match rate on July 2024 data
- **Multi-day orders**: Handles orders that ship across multiple days
- **Usage patterns**:
  ```bash
  # Process a month of transactions
  uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
    --start 2024-07-01 --end 2024-07-31 --verbose
  
  # Process specific accounts only
  uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
    --start 2024-07-01 --end 2024-07-31 --accounts karl erica
  ```

#### 5. CSV Analysis Tools (`analysis/csv-tools/`)
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
1. Transaction categorization assistance
2. Receipt and order history parsing
3. Data import/export utilities for YNAB
4. Reporting and analysis tools
5. Cash flow trend analysis and projections

### Directory Conventions
- `ynab-data/` - Cached YNAB data (gitignored)
- `amazon/data/` - Amazon order history data (gitignored)  
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

## Security Considerations
- Never commit sensitive financial data, account numbers, or API credentials
- Use environment variables or secure credential storage for any API keys
- Ensure all financial data remains private and encrypted where applicable
- **Gitignored directories**: 
  - `ynab-data/` (YNAB financial data)
  - `amazon/data/` (Amazon order history)
  - `analysis/*/results/` (all generated reports and outputs)

## Recent Major Improvements

### Amazon Transaction Matching System (August 2024)
- **Precision fixes**: Eliminated floating-point currency errors using integer cents
- **Multi-day order support**: Now handles orders that ship across multiple days  
- **Performance improvement**: Increased match rate from 84.2% to 94.7%
- **Multi-account architecture**: Supports household with multiple Amazon accounts
- **Algorithm enhancements**: 5 different matching strategies with confidence scoring

Key technical breakthrough: Fixed critical bug where exact amount matches failed due to single-day shipping restriction. Now supports complete multi-day orders using earliest ship date for matching.