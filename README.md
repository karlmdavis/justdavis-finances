# Davis Family Finances

Professional personal finance management system with automated transaction matching, receipt processing, and financial analysis.

## Overview

A comprehensive Python package for automated financial data processing with YNAB integration. Features high-accuracy transaction matching for Amazon and Apple purchases, cash flow analysis, and professional CLI tools.

**Key Features:**
- **Amazon Transaction Matching**: 94.7% accuracy with 3-strategy matching system
- **Apple Receipt Processing**: 85.1% match rate with email integration
- **Cash Flow Analysis**: Multi-timeframe analysis with statistical modeling
- **YNAB Integration**: Secure transaction updates with audit trails
- **Professional CLI**: Unified command-line interface for all operations

## For Developers

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for comprehensive development documentation including project architecture, testing framework, code quality standards, and development workflow.

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd justdavis-finances

# Install dependencies
uv sync

# Install package in development mode
uv pip install -e .
```

### Basic Usage

```bash
# View available commands
finances --help

# Analyze cash flow
finances cashflow analyze --start 2024-01-01 --end 2024-12-31

# Match Amazon transactions
finances amazon match --start 2024-07-01 --end 2024-07-31

# Fetch and parse Apple receipts
finances apple fetch-emails --days-back 30
finances apple parse-receipts --input-dir data/apple/emails/

# Generate YNAB transaction splits
finances ynab generate-splits --input-file data/amazon/transaction_matches/results.json
```


## Core Features

### Amazon Transaction Matching

Automated matching of YNAB transactions to Amazon order data with industry-leading accuracy.

**Features:**
- **Multi-account support**: Handles household Amazon accounts automatically
- **Exact amount matching**: 94.7% accuracy with precision currency handling
- **Multi-day shipping**: Handles orders spanning multiple shipping dates
- **Split payment detection**: Identifies partial order matches
- **Confidence scoring**: 0.0-1.0 scoring for match quality assessment

**Usage:**
```bash
# Match transactions for a date range
finances amazon match --start 2024-07-01 --end 2024-07-31

# Match specific accounts only
finances amazon match --start 2024-07-01 --end 2024-07-31 --accounts karl erica

# Match single transaction
finances amazon match-single \
  --transaction-id "abc123" \
  --date "2024-07-07" \
  --amount -227320 \
  --payee-name "Amazon.com" \
  --account-name "Chase Credit Card"
```

### Apple Receipt Processing

Complete Apple receipt processing pipeline with email integration and multi-format parsing.

**Features:**
- **Email integration**: IMAP-based receipt fetching with security
- **Multi-format parsing**: Supports legacy and modern Apple receipt formats
- **85.1% match rate**: High-accuracy transaction matching
- **Multi-Apple ID support**: Handles family accounts with attribution
- **1:1 transaction model**: Optimized for Apple's direct billing

**Usage:**
```bash
# Fetch receipt emails (requires email configuration)
finances apple fetch-emails --days-back 90 --max-emails 200

# Parse fetched emails
finances apple parse-receipts --input-dir data/apple/emails/

# Match transactions to receipts
finances apple match --start 2024-07-01 --end 2024-07-31
```

### Cash Flow Analysis

Comprehensive financial analysis with statistical modeling and professional dashboards.

**Features:**
- **Multi-timeframe analysis**: 7-day, 30-day, and 90-day moving averages
- **Trend detection**: Statistical confidence intervals and projections
- **Account composition**: Track balance changes across accounts
- **Volatility analysis**: Measure cash flow stability
- **Professional dashboards**: 6-panel visualization with export options

**Usage:**
```bash
# Generate full analysis dashboard
finances cashflow analyze

# Custom date range
finances cashflow analyze --start 2024-01-01 --end 2024-06-30

# Specific accounts only
finances cashflow analyze --accounts "Chase Checking" "Apple Card"

# Different output format
finances cashflow analyze --format pdf --exclude-before 2024-05-01
```

### YNAB Integration

Secure YNAB integration with transaction splitting and audit trails.

**Features:**
- **Three-phase workflow**: Generate → Review → Apply for safety
- **Transaction splitting**: Intelligent item-level categorization
- **Audit trails**: Complete change tracking with reversibility
- **Confidence thresholds**: Automatic approval for high-confidence matches
- **Dry-run mode**: Test mutations before applying

**Usage:**
```bash
# Generate splits from Amazon matches
finances ynab generate-splits \
  --input-file data/amazon/transaction_matches/2024-07-15_results.json

# Apply mutations to YNAB
finances ynab apply-mutations \
  --mutation-file data/ynab/mutations/2024-07-15_amazon_mutations.json

# Sync YNAB data to local cache
finances ynab sync-cache --days 30
```

## Configuration

### Environment Variables

Create `.env` file for configuration:

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

### Data Directories

The system automatically creates and manages data directories:

- `data/amazon/raw/`: Amazon order history files
- `data/apple/emails/`: Apple receipt emails
- `data/ynab/cache/`: Cached YNAB data
- `data/cash_flow/charts/`: Generated analysis dashboards

All sensitive financial data is gitignored for security.

## Troubleshooting

### Common Issues

**Import errors after installation:**
```bash
# Reinstall in development mode
uv pip install -e .
```

**YNAB authentication errors:**
```bash
# Verify token in .env file
echo $YNAB_API_TOKEN

# Test token with YNAB CLI
ynab list budgets
```

**Email fetching fails:**
```bash
# Check credentials
echo $EMAIL_USERNAME
echo $EMAIL_PASSWORD

# Verify IMAP settings for your provider
# Gmail requires app-specific password
```

**No matches found:**
```bash
# Verify data directories exist and contain data
ls data/amazon/raw/
ls data/apple/exports/

# Check date ranges
finances amazon match --start 2024-07-01 --end 2024-07-31 --verbose
```

## License

This project is for personal use and contains family financial management tools. See LICENSE file for details.