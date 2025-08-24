# Davis Family Finances

This project/directory contains notes, reports, and automation useful for tracking and managing our family finances.

## Overview

Most of our cash flow is managed in YNAB, though we typically don't make much use of its budgeting features;
  we use it mostly for tracking, categorizing, and reporting on transactions.
Our retirement accounts, unfortunately, don't generally support automatic transaction sync,
  so while we track that in YNAB,
  for many of them it's just us manually updating the account balances every once in a while.

One of the most important (and time-consuming) financial management activities we do
  is regularly going through new transactions in YNAB and properly categorizing them.
Oftentimes, this involves a **lot** of manually looking through receipts, order histories, etc. 
  to determine what items and categories each transaction is comprised of.
This is a particular challenge for amazon.com purchases and for Apple App Store purchases,
  as those transactions are often composed of many separate and unrelated items.

## Project Structure

```
finances/
├── analysis/                           # Analysis tools and outputs
│   ├── amazon_transaction_matching/    # Amazon-YNAB transaction matching system
│   │   ├── match_single_transaction.py # Single transaction matcher
│   │   ├── match_transactions_batch.py # Batch processing tool
│   │   ├── results/                    # Match results (gitignored)
│   │   └── README.md                   # Matching system documentation
│   ├── cash_flow/                      # Cash flow analysis tools
│   │   ├── cash_flow_analysis.py       # Main analysis script
│   │   └── results/                    # Generated reports (gitignored)
│   └── csv-tools/                      # CSV analysis utilities
│       ├── open.nu                     # Nushell CSV wrapper
│       └── README.md                   # CSV tools documentation
├── amazon/                             # Amazon data extraction
│   ├── data/                          # Amazon order history (gitignored)
│   ├── extract_amazon_data.sh         # Data extraction script
│   └── README.md                      # Amazon data workflow
├── ynab-data/                         # Cached YNAB data (gitignored)
├── ynab-exports/                      # YNAB export files
├── README.md                          # This file
├── CLAUDE.md                          # AI assistant guidance
├── YNAB_DATA_WORKFLOW.md             # YNAB data extraction workflow
└── pyproject.toml                     # Python dependencies (managed with uv)
```

## Data Management

### YNAB Data Extraction

We maintain local cached copies of YNAB data for analysis and reporting. See [YNAB_DATA_WORKFLOW.md](YNAB_DATA_WORKFLOW.md) for detailed instructions on:

- Setting up authentication with the YNAB CLI tool
- Extracting account, category, and transaction data
- Maintaining cached JSON files in `ynab-data/`
- Scheduling automated updates
- Troubleshooting common issues

Quick refresh command:
```bash
# Extract all current YNAB data to local cache
ynab --output json list accounts > ynab-data/accounts.json
ynab --output json list categories > ynab-data/categories.json
ynab --output json list transactions > ynab-data/transactions.json
```

## Analysis Tools

### Cash Flow Analysis (`analysis/cash_flow/cash_flow_analysis.py`)

A comprehensive Python script that analyzes cash flow patterns using various financial visualization techniques:

**Features:**
- Multiple moving averages (7-day, 30-day, 90-day) to smooth daily volatility
- Monthly net cash flow tracking (income vs expenses)
- Trend analysis with statistical confidence
- Cash flow velocity (30-day rolling changes)
- Account composition breakdown over time
- Detailed financial health metrics

**Usage:**
```bash
# Ensure dependencies are installed
uv sync

# Run the analysis
uv run python analysis/cash_flow/cash_flow_analysis.py
```

The script generates a timestamped dashboard image in `analysis/cash_flow/results/` with:
- Cash flow trends with smoothed averages
- Monthly spending patterns
- Volatility analysis
- Statistical summaries
- Burn rate calculations

**Note:** The analysis excludes data before May 2024 due to incomplete transaction history.

### Amazon Transaction Matching (`analysis/amazon_transaction_matching/`)

An advanced system for automatically matching YNAB transactions to Amazon order data across multiple accounts:

**Key Features:**
- **Multi-account support** - Handles household Amazon accounts (karl, erica, etc.)
- **Exact amount matching** - Finds perfect matches with 94.7% accuracy
- **Multi-day shipping** - Handles orders that ship across multiple days
- **Precision currency handling** - Uses integer cents to avoid floating-point errors
- **Confidence scoring** - Rates match quality from 0.0 to 1.0
- **Batch processing** - Process months of transactions efficiently

**Usage:**
```bash
# Process a single transaction
uv run python analysis/amazon_transaction_matching/match_single_transaction.py \
  --transaction-id "abc123" --date "2024-07-07" --amount -227320 \
  --payee-name "Amazon.com" --account-name "Chase Credit Card"

# Process a date range (e.g., July 2024)
uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31 --verbose

# Process specific accounts only
uv run python analysis/amazon_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31 --accounts karl erica
```

**Results:** Generates timestamped JSON files in `analysis/amazon_transaction_matching/results/` with:
- Complete match details and confidence scores
- Unmatched transaction analysis
- Summary statistics and match rates
- Account attribution for multi-household setups

See `analysis/amazon_transaction_matching/README.md` for detailed documentation.

### CSV Analysis Tools (`analysis/csv-tools/`)

Utilities for safe exploration and analysis of CSV data using nushell:

**Tools:**
- `open.nu` - Generic CSV opener with pipeline support
- Filtering, sorting, and basic aggregation capabilities
- Safe read-only operations

**Usage:**
```bash
# View first few rows
analysis/csv-tools/open.nu "amazon/data/account_data/file.csv" "first 5"

# Filter and select columns  
analysis/csv-tools/open.nu "amazon/data/account_data/file.csv" \
  "where 'Product Name' =~ 'Guitar' | select 'Product Name' 'Total Owed'"
```

See `analysis/csv-tools/README.md` for complete documentation and examples.

## Amazon Data Integration

The system integrates with Amazon order history data for transaction matching:

**Setup:** See `amazon/README.md` for complete data extraction workflow including:
- Requesting your Amazon data export
- Extracting and organizing order history files  
- Setting up multi-account directory structure
- Scheduling regular data updates

**Directory structure:** Amazon data is organized by account and date:
```
amazon/data/
├── 2025-08-24_karl_amazon_data/     # Karl's Amazon data (Aug 24, 2025)
├── 2025-08-24_erica_amazon_data/    # Erica's Amazon data (Aug 24, 2025)  
└── YYYY-MM-DD_account_amazon_data/  # Pattern for future extracts
```

## Dependencies

This project uses `uv` for Python dependency management. Dependencies are defined in `pyproject.toml`:

- `pandas` - Data manipulation and time series analysis
- `matplotlib` - Visualization and charting
- `scipy` - Statistical analysis and trend calculations
- **External:** `nushell` - CSV analysis and data exploration (install via Homebrew)

To install dependencies:
```bash
# Install Python dependencies
uv sync

# Install nushell (macOS)
brew install nushell
```

## Security Notes

- The `ynab-data/` directory contains sensitive financial data and is gitignored
- The `amazon/data/` directory contains personal order history and is gitignored
- All `analysis/*/results/` directories contain reports and are gitignored
- Never commit API tokens, access credentials, or personal financial data
- Use `.ynab.env` for YNAB authentication (not tracked in git)
