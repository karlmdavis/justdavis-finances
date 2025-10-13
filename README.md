# Davis Family Finances

[![Code Quality](https://github.com/karlmdavis/justdavis-finances/actions/workflows/quality.yml/badge.svg)](https://github.com/karlmdavis/justdavis-finances/actions/workflows/quality.yml)
[![codecov](https://codecov.io/gh/karlmdavis/justdavis-finances/branch/main/graph/badge.svg)](https://codecov.io/gh/karlmdavis/justdavis-finances)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Professional personal finance management system with automated transaction matching,
  receipt processing, and financial analysis.

## Overview

A comprehensive Python package for automated financial data processing with YNAB integration.
Features high-accuracy transaction matching for Amazon and Apple purchases, cash flow analysis,
  and professional CLI tools.

**Key Features:**
- **Financial Flow System**: Single-command orchestration with dependency management and change detection.
- **Amazon Transaction Matching**: 94.7% accuracy with 3-strategy matching system.
- **Apple Receipt Processing**: 85.1% match rate with email integration.
- **Cash Flow Analysis**: Multi-timeframe analysis with statistical modeling.
- **YNAB Integration**: Secure transaction updates with audit trails.
- **Retirement Account Tracking**: Interactive balance management with YNAB integration.
- **Professional CLI**: Unified command-line interface for all operations.

## For Developers

See [CONTRIBUTING.md](CONTRIBUTING.md) for comprehensive development documentation including project
  architecture, testing framework, code quality standards, and development workflow.

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

# Install pre-commit hooks (for developers)
uv run pre-commit install
```

### Basic Usage

```bash
# View available commands
finances --help

# Execute complete financial update pipeline (recommended, interactive)
finances flow

# Individual commands (for specific tasks)
finances amazon match --start 2024-07-01 --end 2024-07-31
finances apple fetch-emails --days-back 30
finances cashflow analyze --start 2024-01-01 --end 2024-12-31
finances retirement update
```


## Core Features

### Financial Flow System

Intelligent orchestration of the complete financial data pipeline with dependency management,
  change detection, and transactional consistency.

**Benefits:**
- **Single Command**: Replaces 10+ manual commands with `finances flow`.
- **Dependency Management**: Automatic execution ordering based on data dependencies.
- **Change Detection**: Only processes data that has actually changed.
- **Transactional Integrity**: Pre-execution archiving ensures data consistency.
- **Interactive Execution**: Guided prompts walk you through each step.
- **Smart Orchestration**: Detects which nodes need to run based on data changes.

**Key Nodes and Dependencies:**
- **YNAB Sync** → Amazon/Apple Matching → Split Generation → YNAB Apply.
- **Amazon Unzip** → Amazon Matching (when new ZIP files detected).
- **Apple Email Fetch** → Apple Receipt Parsing → Apple Matching.
- **Retirement Updates** → YNAB Account Updates (independent).
- **Cash Flow Analysis** (triggered by YNAB data changes).

**Usage:**
```bash
# Execute complete pipeline with interactive prompts and change detection
finances flow

# The flow system will:
# 1. Detect which nodes have data changes
# 2. Show you a preview of what will execute
# 3. Ask for confirmation before proceeding
# 4. Create pre-execution archives for rollback
# 5. Execute nodes in dependency order
# 6. Show summary of results
```

**Archive Management:**
The flow system automatically creates compressed archives before execution:
- **Location**: `data/{domain}/archive/YYYY-MM-DD-NNN.tar.gz`.
- **Purpose**: Rollback capability and audit trails.
- **Retention**: All archives preserved indefinitely.
- **Metadata**: Complete execution context and trigger reasons.

### Amazon Transaction Matching

Automated matching of YNAB transactions to Amazon order data with industry-leading accuracy.

**Features:**
- **Multi-account support**: Handles household Amazon accounts automatically.
- **Exact amount matching**: 94.7% accuracy with precision currency handling.
- **Multi-day shipping**: Handles orders spanning multiple shipping dates.
- **Split payment detection**: Identifies partial order matches.
- **Confidence scoring**: 0.0-1.0 scoring for match quality assessment.

**Usage:**
```bash
# Extract downloaded Amazon order history ZIP files
finances amazon unzip --download-dir ~/Downloads

# Extract specific accounts only
finances amazon unzip --download-dir ~/Downloads --accounts karl erica

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
- **Email integration**: IMAP-based receipt fetching with security.
- **Multi-format parsing**: Supports legacy and modern Apple receipt formats.
- **85.1% match rate**: High-accuracy transaction matching.
- **Multi-Apple ID support**: Handles family accounts with attribution.
- **1:1 transaction model**: Optimized for Apple's direct billing.

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
- **Multi-timeframe analysis**: 7-day, 30-day, and 90-day moving averages.
- **Trend detection**: Statistical confidence intervals and projections.
- **Account composition**: Track balance changes across accounts.
- **Volatility analysis**: Measure cash flow stability.
- **Professional dashboards**: 6-panel visualization with export options.

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
- **Three-phase workflow**: Generate → Review → Apply for safety.
- **Transaction splitting**: Intelligent item-level categorization.
- **Audit trails**: Complete change tracking with reversibility.
- **Confidence thresholds**: Automatic approval for high-confidence matches.
- **Dry-run mode**: Test edits before applying.

**Usage:**
```bash
# Generate splits from Amazon matches
finances ynab generate-splits \
  --input-file data/amazon/transaction_matches/2024-07-15_results.json

# Apply edits to YNAB
finances ynab apply-edits \
  --edit-file data/ynab/edits/2024-07-15_amazon_edits.json

# Sync YNAB data to local cache
finances ynab sync-cache --days 30
```

### Retirement Account Management

Interactive retirement account balance tracking with YNAB integration for keeping investment
  accounts in sync.

**Features:**
- **Account tracking**: Manage multiple retirement accounts (401k, 403b, IRA, Roth IRA).
- **Balance history**: Track balance changes over time with adjustments.
- **YNAB integration**: Generate adjustment transactions for balance changes.
- **Interactive workflow**: Guided prompts for balance updates.
- **Multi-provider support**: Works with any retirement account provider.

**Usage:**
```bash
# List tracked retirement accounts with current balances
finances retirement list-accounts

# Update account balances interactively
finances retirement update

# Update specific accounts only
finances retirement update --account karl_401k --account erica_403b

# Update with specific date
finances retirement update --date 2024-07-31

# Save YNAB transactions to file for review
finances retirement update --output-file retirement_updates.yaml

# View balance history
finances retirement history --account karl_401k --limit 10
```

**Account Configuration:**
The system tracks accounts in `data/retirement/accounts.yaml` with default accounts:
- **karl_401k**: 401k account with Fidelity.
- **erica_403b**: 403b account with TIAA.
- **karl_ira**: IRA account with Vanguard.

**Balance History:**
All balance updates are stored in `data/retirement/balance_history.yaml` with:
- Date and timestamp of each update.
- Previous and new balance amounts.
- Calculated adjustments.
- Optional notes for each update.

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

- `data/amazon/raw/`: Amazon order history files.
- `data/amazon/archive/`: Transaction archives before processing.
- `data/apple/emails/`: Apple receipt emails.
- `data/apple/exports/`: Parsed Apple receipt data.
- `data/ynab/cache/`: Cached YNAB data.
- `data/ynab/edits/`: Generated transaction updates.
- `data/retirement/`: Retirement account balance history.
- `data/cash_flow/charts/`: Generated analysis dashboards.
- `data/cache/flow/`: Flow system change detection metadata.

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

**Flow execution issues:**
```bash
# Run the flow command interactively
finances flow

# The flow system will automatically:
# - Detect changed data
# - Show preview of execution plan
# - Prompt for confirmation
# - Execute nodes in dependency order

# Check flow cache state
ls -la data/cache/flow/

# Clear cache to force re-detection
rm -rf data/cache/flow/*
```

**Flow reports no changes to execute:**
```bash
# This is normal - the system only processes changed data
# The flow system compares timestamps to detect changes

# To trigger processing, update source data:
# - Download new Amazon ZIP files to ~/Downloads
# - Fetch new Apple receipt emails
# - Manually touch files to update timestamps if needed:
touch data/ynab/cache/transactions.json
```

## License

This project is for personal use and contains family financial management tools.
See LICENSE file for details.
