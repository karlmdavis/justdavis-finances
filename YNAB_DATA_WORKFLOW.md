# YNAB Data Caching Workflow

This document describes the workflow for using the `ynab` command line tool to create and maintain
  local cached copies of YNAB data for the Davis Family Budget.

## Overview

The goal is to maintain three local JSON files that contain cached copies of all YNAB data:
- `ynab-data/accounts.json` - All account information
- `ynab-data/categories.json` - All category and category group information
- `ynab-data/transactions.json` - All transaction data

## Prerequisites

### 1. Authentication Setup
Ensure your YNAB CLI tool is properly authenticated:

```bash
# Verify authentication and budget access
ynab list budgets

# Should show: Davis Family Budget (6ad96df6-0bf6-45b4-b1ad-0d002bbfa739)
```

If authentication fails, check that your `.ynab.env` file contains a valid access token.

### 2. Directory Structure
Create the data directory if it doesn't exist:

```bash
mkdir -p ynab-data
```

## Data Extraction Commands

### Extract Accounts Data

```bash
# Get all accounts in JSON format
ynab --output json list accounts > ynab-data/accounts.json

# Verify the data was extracted successfully (accounts are nested in 'accounts' field)
echo "Accounts extracted: $(jq '.accounts | length' ynab-data/accounts.json)"
```

### Extract Categories Data

```bash
# Get all categories and category groups in JSON format
ynab --output json list categories > ynab-data/categories.json

# Verify the data was extracted successfully (categories are nested in 'category_groups' field)
echo "Category groups extracted: $(jq '.category_groups | length' ynab-data/categories.json)"
```

### Extract Transactions Data

```bash
# Get all transactions in JSON format (this may take a while for large datasets)
ynab --output json list transactions > ynab-data/transactions.json

# Verify the data was extracted successfully (transactions are in root array)
echo "Transactions extracted: $(jq length ynab-data/transactions.json)"
```

## Complete Workflow

### Option 1: Full Data Refresh

Use this when you want to completely refresh all cached data:

```bash
#!/bin/bash
# Full YNAB data refresh script

echo "Starting YNAB data refresh..."

# Create directory if needed
mkdir -p ynab-data

# Extract all data
echo "Extracting accounts..."
ynab --output json list accounts > ynab-data/accounts.json

echo "Extracting categories..."
ynab --output json list categories > ynab-data/categories.json

echo "Extracting transactions..."
ynab --output json list transactions > ynab-data/transactions.json

# Verify extraction
echo "Data extraction complete:"
echo "  Accounts: $(jq '.accounts | length' ynab-data/accounts.json 2>/dev/null || echo 'ERROR')"
echo "  Category groups: $(jq '.category_groups | length' ynab-data/categories.json 2>/dev/null || echo 'ERROR')"
echo "  Transactions: $(jq length ynab-data/transactions.json 2>/dev/null || echo 'ERROR')"

echo "Cached data updated: $(date)"
```

### Option 2: Incremental Transaction Updates

For regular updates focusing on recent transactions:

```bash
#!/bin/bash
# Incremental transaction update script

echo "Updating recent transactions..."

# Get transactions from the last 30 days
SINCE_DATE=$(date -d '30 days ago' '+%Y-%m-%d' 2>/dev/null || date -v-30d '+%Y-%m-%d')

# Extract recent transactions and merge with existing data
ynab --output json list transactions --since-date "$SINCE_DATE" > ynab-data/transactions_recent.json

# Note: This creates a separate file for recent transactions
# Manual merging may be needed for a complete dataset

echo "Recent transactions updated: $(jq length ynab-data/transactions_recent.json 2>/dev/null || echo 'ERROR')"
echo "Update completed: $(date)"
```

## Data Validation

After extracting data, validate the JSON format and content:

```bash
# Validate JSON format
jq empty ynab-data/accounts.json && echo "accounts.json: Valid JSON" || echo "accounts.json: Invalid JSON"
jq empty ynab-data/categories.json && echo "categories.json: Valid JSON" || echo "categories.json: Invalid JSON"
jq empty ynab-data/transactions.json && echo "transactions.json: Valid JSON" || echo "transactions.json: Invalid JSON"

# Check for expected data structure
echo "Sample account: $(jq '.accounts[0] | {id, name, type, balance}' ynab-data/accounts.json 2>/dev/null)"
echo "Sample category: $(jq '.category_groups[0] | {id, name}' ynab-data/categories.json 2>/dev/null)"
echo "Sample transaction: $(jq '.[0] | {id, date, amount, payee_name, category_name}' ynab-data/transactions.json 2>/dev/null)"
```

## Automation Recommendations

### Scheduled Updates

Consider scheduling regular data updates using cron:

```bash
# Edit crontab
crontab -e

# Add entry for daily updates at 6 AM
0 6 * * * cd /Users/karl/workspaces/justdavis/personal/justdavis-finances && /path/to/refresh-ynab-data.sh >> ynab-data/refresh.log 2>&1
```

### Rate Limiting Considerations

YNAB API has rate limits (200 requests per hour).
For large datasets:
- Extract accounts and categories less frequently (weekly)
- Focus regular updates on transactions only
- Add delays between requests if needed

```bash
# Add delays for large datasets
sleep 1  # Wait 1 second between API calls
```

## File Formats and Structure

### accounts.json
Contains a JSON object with:
- `accounts`: Array of account objects with properties:
  - `id`: Unique account identifier
  - `name`: Account name
  - `type`: Account type (checking, savings, etc.)
  - `balance`: Current balance in milliunits
  - `closed`: Whether account is closed
  - `deleted`: Whether account is deleted
- `server_knowledge`: Server synchronization information

### categories.json
Contains a JSON object with:
- `category_groups`: Array of category group objects with nested categories:
  - `id`: Category group ID
  - `name`: Category group name
  - `categories`: Array of category objects
    - `id`: Category ID
    - `name`: Category name
    - `budgeted`: Amount budgeted
    - `activity`: Activity amount
    - `balance`: Available balance
- `server_knowledge`: Server synchronization information

### transactions.json
Contains an array of transaction objects with properties:
- `id`: Transaction ID
- `date`: Transaction date (YYYY-MM-DD)
- `amount`: Amount in milliunits (negative = outflow)
- `payee_name`: Payee name
- `category_name`: Category name
- `memo`: Transaction memo
- `cleared`: Clearing status
- `approved`: Approval status
- `account_name`: Account name

## Troubleshooting

### Authentication Issues

```bash
# Test authentication
ynab get user

# If this fails, check:
# 1. .ynab.env file exists and contains valid token
# 2. Token has not expired
# 3. Network connectivity to YNAB API
```

### Empty or Invalid JSON Files

```bash
# Check file sizes
ls -la ynab-data/

# If files are empty (0 bytes), check API response:
ynab --verbose list accounts

# Look for error messages in the output
```

### Large Dataset Performance

For budgets with many transactions:

```bash
# Extract data in smaller chunks by date range
ynab --output json list transactions --since-date 2024-01-01 --until-date 2024-06-30 > ynab-data/transactions_h1_2024.json
ynab --output json list transactions --since-date 2024-07-01 --until-date 2024-12-31 > ynab-data/transactions_h2_2024.json

# Then combine files manually or with jq
jq -s 'add' ynab-data/transactions_*.json > ynab-data/transactions.json
```

### Data Consistency Checks

```bash
# Check for data consistency
echo "Unique accounts referenced in transactions: $(jq -r '.[].account_name' ynab-data/transactions.json | sort -u | wc -l)"
echo "Accounts in accounts.json: $(jq '.accounts | length' ynab-data/accounts.json)"

echo "Unique categories referenced in transactions: $(jq -r '.[].category_name' ynab-data/transactions.json | sort -u | wc -l)"
echo "Total categories in categories.json: $(jq '[.category_groups[].categories[]] | length' ynab-data/categories.json)"
```

## Security Considerations

1. **File Permissions**: Ensure cached data files have appropriate permissions
   ```bash
   chmod 600 ynab-data/*.json  # Owner read/write only
   ```

2. **Git Exclusion**: Add to `.gitignore` to prevent committing sensitive data
   ```bash
   echo "ynab-data/" >> .gitignore
   ```

3. **Backup Strategy**: Consider encrypted backups for sensitive financial data

## Usage Examples

### Find High-Value Transactions
```bash
# Find transactions over $500
jq '.[] | select(.amount < -500000) | {date, amount: (.amount/1000), payee_name, category_name}' ynab-data/transactions.json
```

### Category Spending Analysis
```bash
# Sum spending by category for current year
jq -r '.[] | select(.date >= "2024-01-01") | select(.amount < 0) | "\(.category_name),\(.amount)"' ynab-data/transactions.json | \
awk -F, '{sum[$1] += $2} END {for (cat in sum) printf "%s,%.2f\n", cat, sum[cat]/1000}' | \
sort -t, -k2 -n
```

### Account Balance Summary
```bash
# Show current balances for all accounts
jq '.accounts[] | select(.closed == false) | {name, balance: (.balance/1000)}' ynab-data/accounts.json
```

## Maintenance

- Review and update this workflow monthly
- Monitor YNAB API changes that might affect CLI tool
- Validate data integrity regularly
- Archive old transaction data as needed to manage file sizes

---

**Last Updated**: $(date)
**YNAB Budget**: Davis Family Budget
**CLI Tool Version**: Check with `ynab --version`
