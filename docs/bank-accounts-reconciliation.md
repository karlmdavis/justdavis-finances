# Bank Account Reconciliation

This document describes the bank account reconciliation system for automatically
  matching bank transactions with YNAB.

## Overview

The bank reconciliation system provides automated transaction matching and balance
  verification for bank accounts.
Key features:

- **Automated file retrieval** - Copies bank export files from download locations
- **Multi-format parsing** - Supports CSV, OFX, and QIF formats from multiple banks
- **Transaction matching** - Matches bank transactions with YNAB using fuzzy matching
- **Balance reconciliation** - Verifies balances match after accounting for unmatched
    transactions
- **Operation generation** - Creates YNAB import operations for missing transactions

## Supported Banks and Formats

### Apple Card
- **CSV Format**: Transaction history with merchant, category, and amount
- **OFX Format**: Standard financial data interchange format
- **Sign Convention**: Consumer perspective (purchases positive, payments negative)
- **Normalization**: All signs flipped to accounting standard (expenses negative, income
    positive)

### Apple Savings
- **CSV Format**: Transaction history with balance data
- **OFX Format**: Includes transaction and balance information
- **Sign Convention**: Accounting standard (deposits positive, withdrawals negative)
- **Normalization**: No sign flip required

### Chase Credit Card
- **CSV Format**: Transaction history with merchant details
- **QIF Format**: Quicken Interchange Format
- **Sign Convention**: Consumer perspective (purchases positive, payments negative)
- **Normalization**: All signs flipped to accounting standard

### Chase Checking
- **CSV Format**: Transaction history with balance data
- **Sign Convention**: Accounting standard (deposits positive, withdrawals negative)
- **Normalization**: No sign flip required

## Configuration

Configuration file location: `~/.finances/bank_accounts_config.json`

### Configuration Structure

```json
{
  "accounts": [
    {
      "ynab_account_id": "abc-123-def",
      "ynab_account_name": "Apple Card",
      "slug": "apple-card",
      "bank_name": "Apple Card",
      "account_type": "credit",
      "statement_frequency": "monthly",
      "source_directory": "~/Downloads",
      "download_instructions": "Download from wallet.apple.com",
      "import_patterns": [
        {
          "pattern": "Apple Card Statement - *.csv",
          "format_handler": "apple_card_csv"
        },
        {
          "pattern": "*.ofx",
          "format_handler": "apple_card_ofx"
        }
      ]
    }
  ]
}
```

### Configuration Fields

**Account-level fields:**
- `ynab_account_id`: YNAB account ID (must exist in YNAB)
- `ynab_account_name`: Display name from YNAB
- `slug`: Short identifier for this account (used in directory names)
- `bank_name`: Name of the bank or financial institution
- `account_type`: One of: `credit`, `checking`, `savings`
- `statement_frequency`: Either `monthly` or `daily`
- `source_directory`: Path to directory containing downloaded bank files
- `download_instructions`: Human-readable instructions for obtaining bank exports
- `import_patterns`: List of file patterns and their format handlers

**Import pattern fields:**
- `pattern`: Glob pattern for matching files (e.g., `*.csv`, `Statement_*.ofx`)
- `format_handler`: Name of the format handler to use for this file type

### Available Format Handlers

- `apple_card_csv` - Apple Card CSV format
- `apple_card_ofx` - Apple Card OFX format
- `apple_savings_csv` - Apple Savings CSV format
- `apple_savings_ofx` - Apple Savings OFX format
- `chase_checking_csv` - Chase Checking CSV format
- `chase_credit_csv` - Chase Credit Card CSV format
- `chase_credit_qif` - Chase Credit Card QIF format

## CLI Commands

The bank reconciliation system provides three main commands:

### finances bank retrieve

Copies bank export files from download locations to the raw data directory.

```bash
finances bank retrieve
```

**What it does:**
1. Reads configuration from `~/.finances/bank_accounts_config.json`
2. For each configured account:
   - Expands paths (handles `~` in source_directory)
   - Finds files matching import_patterns in source_directory
   - Copies new files to `data/bank_accounts/raw/{slug}/`
   - Skips files that already exist (based on name and size)
3. Displays summary of files copied and skipped per account

**Options:**
- `--config PATH` - Path to configuration file (default: `~/.finances/bank_accounts_config.json`)
- `--base-dir PATH` - Base directory for bank data (default: `data/bank_accounts`)

**Example output:**
```
Loading configuration from ~/.finances/bank_accounts_config.json...
  Found 2 accounts

Retrieving bank export files...

Retrieval Summary:
  apple-card:
    Files copied: 3
    Files skipped: 5
  chase-checking:
    Files copied: 1
    Files skipped: 2

Total: 4 copied, 7 skipped

Done! account_data_retrieve completed
```

### finances bank parse

Parses raw bank files into normalized JSON format.

```bash
finances bank parse
```

**What it does:**
1. Reads configuration from `~/.finances/bank_accounts_config.json`
2. Creates format handler registry with all available parsers
3. For each configured account:
   - Reads files from `data/bank_accounts/raw/{slug}/`
   - Matches files against import_patterns to determine format handler
   - Parses each file using the appropriate handler
   - De-duplicates overlapping transactions (by transaction_id or date+amount+description)
   - De-duplicates balance points (uses most recent file for each date)
   - Auto-detects date range from transaction dates
   - Writes normalized JSON to `data/bank_accounts/normalized/{slug}.json`
4. Displays summary with transaction counts and date ranges

**Options:**
- `--config PATH` - Path to configuration file (default: `~/.finances/bank_accounts_config.json`)
- `--base-dir PATH` - Base directory for bank data (default: `data/bank_accounts`)

**Example output:**
```
Loading configuration from ~/.finances/bank_accounts_config.json...
  Found 2 accounts

Registered 7 format handlers

Parsing bank export files...

Parsing Summary:
  apple-card:
    Transactions: 156
    Date range: 2024-01-01 to 2024-12-31
  chase-checking:
    Transactions: 89
    Date range: 2024-06-01 to 2024-12-31

Total transactions parsed: 245

Done! account_data_parse completed
```

**Normalized JSON structure:**
```json
{
  "account_id": "apple-card",
  "account_name": "Apple Card",
  "account_type": "credit",
  "data_period": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  },
  "balances": [
    {
      "date": "2024-12-31",
      "balance_cents": -125000,
      "available_cents": 25000
    }
  ],
  "transactions": [
    {
      "posted_date": "2024-12-15",
      "transaction_date": "2024-12-14",
      "description": "Amazon.com",
      "merchant": "Amazon",
      "amount_cents": -5999,
      "type": "Purchase",
      "category": "Shopping"
    }
  ]
}
```

### finances bank reconcile

Reconciles bank data with YNAB transactions and generates operations.

```bash
finances bank reconcile
```

**What it does:**
1. Reads configuration from `~/.finances/bank_accounts_config.json`
2. Loads YNAB transactions (not yet implemented - uses empty list)
3. For each configured account:
   - Loads normalized bank data from `data/bank_accounts/normalized/{slug}.json`
   - Filters YNAB transactions for this account
   - Matches each bank transaction against YNAB transactions using fuzzy matching
   - Generates operations for unmatched transactions
   - Flags ambiguous matches for manual review
   - Builds balance reconciliation report
4. Writes operations JSON to `data/bank_accounts/reconciliation/{timestamp}_reconciliation.json`
5. Displays path to operations file

**Options:**
- `--config PATH` - Path to configuration file (default: `~/.finances/bank_accounts_config.json`)
- `--base-dir PATH` - Base directory for bank data (default: `data/bank_accounts`)

**Example output:**
```
Loading configuration from ~/.finances/bank_accounts_config.json...
  Found 2 accounts

Loading YNAB transactions...
  Note: YNAB transaction loading not yet implemented
  Using empty YNAB transaction list (all bank txs will be unmatched)

Reconciling bank data with YNAB...

Reconciliation complete!
Operations file: data/bank_accounts/reconciliation/2026-01-04_17-30-45_reconciliation.json

Next steps:
  1. Review the operations file
  2. Import missing transactions into YNAB
  3. Resolve flagged discrepancies

Done! account_data_reconcile completed
```

**Operations JSON structure:**
```json
{
  "version": "1.0",
  "metadata": {
    "generated_at": "2026-01-04T17:30:45.123456",
    "source_system": "bank_reconciliation"
  },
  "accounts": [
    {
      "account_id": "apple-card",
      "operations": [
        {
          "type": "create_transaction",
          "source": "bank",
          "transaction": {
            "posted_date": "2024-12-15",
            "amount_cents": -5999,
            "description": "Amazon.com"
          },
          "account_id": "abc-123-def"
        },
        {
          "type": "flag_discrepancy",
          "source": "bank",
          "transaction": {...},
          "candidates": [
            {
              "date": "2024-12-15",
              "amount_milliunits": -59990,
              "payee_name": "Amazon"
            }
          ],
          "message": "Multiple possible matches - manual review required"
        }
      ],
      "balance_reconciliation": {
        "account_id": "apple-card",
        "reconciliation_points": [...]
      }
    }
  ],
  "summary": {
    "total_operations": 156,
    "operations_by_type": {
      "create_transaction": 145,
      "flag_discrepancy": 11
    }
  }
}
```

## Workflow

### Initial Setup

1. **Create configuration file:**
   ```bash
   mkdir -p ~/.finances
   # Create bank_accounts_config.json with your account details
   ```

2. **Download bank export files:**
   - Log into each bank's website
   - Export transaction history (CSV, OFX, or QIF format)
   - Save files to source_directory specified in config

### Regular Reconciliation Workflow

1. **Retrieve new bank files:**
   ```bash
   finances bank retrieve
   ```
   This copies new export files from your download locations.

2. **Parse bank data:**
   ```bash
   finances bank parse
   ```
   This converts raw bank files into normalized JSON format.

3. **Reconcile with YNAB:**
   ```bash
   finances bank reconcile
   ```
   This matches bank transactions with YNAB and generates operations.

4. **Review operations file:**
   - Open the generated reconciliation JSON
   - Review create_transaction operations (missing from YNAB)
   - Review flag_discrepancy operations (ambiguous matches)

5. **Import transactions into YNAB:**
   - For transactions missing from YNAB, manually create them
   - For ambiguous matches, review and resolve manually
   - Update YNAB with any corrections

### Best Practices

1. **Regular updates**: Run the workflow weekly or monthly to keep YNAB in sync
2. **Review before applying**: Always review reconciliation output before making YNAB changes
3. **Keep exports organized**: Let retrieve command manage file copies (don't manually move
     files)
4. **Monitor balance reconciliation**: Check balance_reconciliation in output to ensure bank
     and YNAB balances match
5. **Document discrepancies**: When you find and fix issues, document them for future
     reference

## Transaction Matching Algorithm

The reconciliation system uses a multi-strategy fuzzy matching algorithm:

### Match Types

1. **Exact Match**: Same date, same amount (within 1 cent), similar description
   - Confidence: High
   - Action: Automatically linked

2. **Near Match**: Date within 2 days, amount exact, description similar
   - Confidence: Medium
   - Action: Automatically linked

3. **Fuzzy Match**: Date within 5 days, amount within $1, description contains key terms
   - Confidence: Low
   - Action: Flagged for review

4. **Ambiguous**: Multiple possible matches found
   - Confidence: N/A
   - Action: Flagged with all candidates for manual review

5. **No Match**: No similar YNAB transaction found
   - Confidence: N/A
   - Action: Generate create_transaction operation

### Matching Criteria

- **Date tolerance**: ±5 days (configurable)
- **Amount tolerance**: $1.00 or 1 cent depending on match type
- **Description similarity**: Uses fuzzy string matching (Levenshtein distance)
- **Merchant matching**: Extracts and matches merchant names when available

## Balance Reconciliation

The system performs balance reconciliation to verify data integrity:

### Reconciliation Points

For each balance point from the bank:
1. Start with bank balance
2. Add unmatched bank transactions (pending in bank, not yet in YNAB)
3. Subtract unmatched YNAB transactions (cleared in YNAB, not yet in bank)
4. Compare with YNAB balance for that date

### Expected Balance Formula

```
Expected YNAB Balance = Bank Balance + Unmatched Bank Txs - Unmatched YNAB Txs
```

### Balance Discrepancy Types

- **Matched**: Expected YNAB balance matches actual YNAB balance (within 1 cent)
- **Unmatched**: Balance differs by more than 1 cent
  - Possible causes: Missing transactions, incorrect categorization, data entry errors

### Reconciliation Output

Each reconciliation point includes:
- Date of balance check
- Bank balance (from export file)
- Unmatched transaction adjustments
- Expected YNAB balance
- Actual YNAB balance (when available)
- Difference amount (if discrepancy exists)

## Data Directory Structure

```
data/bank_accounts/
├── raw/                      # Raw bank export files
│   ├── apple-card/
│   │   ├── Statement_2024-01.csv
│   │   ├── Statement_2024-02.csv
│   │   └── ...
│   ├── chase-checking/
│   │   └── ...
│   └── ...
├── normalized/               # Parsed and normalized JSON
│   ├── apple-card.json
│   ├── chase-checking.json
│   └── ...
└── reconciliation/           # Reconciliation operations
    ├── 2026-01-04_17-30-45_reconciliation.json
    └── ...
```

## Future Enhancements

### Planned Features

1. **YNAB Integration**: Automatically load YNAB transactions for matching
2. **Automatic Import**: Apply operations directly to YNAB via API
3. **Confidence Tuning**: Allow per-account matching threshold configuration
4. **Balance Alerts**: Notify when balance discrepancies exceed threshold
5. **Historical Analysis**: Track matching accuracy over time
6. **Custom Rules**: User-defined matching rules for specific merchants or patterns

### Extensibility

The system is designed for easy extension:

- **New Format Handlers**: Add support for additional bank export formats
- **Custom Matchers**: Implement domain-specific matching logic
- **Alternative Outputs**: Export to other financial management systems
- **Validation Rules**: Add account-specific validation and business rules

## Troubleshooting

### Common Issues

**Issue**: "Configuration file not found"
- **Solution**: Create config file at `~/.finances/bank_accounts_config.json`

**Issue**: "Source directory does not exist"
- **Solution**: Verify source_directory path in config and ensure it exists

**Issue**: "Unknown format handler"
- **Solution**: Check format_handler name in config matches available handlers

**Issue**: "Parse error at line N"
- **Solution**: Verify bank export file format matches expected format for handler

**Issue**: "No files copied during retrieve"
- **Solution**: Check import_patterns match your bank's export file naming

**Issue**: "All transactions unmatched"
- **Solution**: This is expected currently - YNAB transaction loading not yet implemented

### Getting Help

For issues not covered here:
1. Check configuration file syntax
2. Verify bank export file formats
3. Review error messages in CLI output
4. Check file permissions on source and destination directories

## Technical Details

### Sign Convention

Different banks use different sign conventions for reporting transactions:

**Consumer Perspective** (used by credit cards):
- Purchases: Positive (money you owe)
- Payments: Negative (money you paid)

**Accounting Standard** (used by YNAB and most checking accounts):
- Expenses: Negative (money out)
- Income: Positive (money in)

The system automatically normalizes all transactions to accounting standard:
- Credit card handlers flip signs (consumer → accounting)
- Checking/savings handlers preserve signs (already accounting standard)

### Amount Precision

All amounts are stored as integers in cents to avoid floating-point errors:
- Bank amounts: Parsed to integer cents
- YNAB amounts: Use milliunits (tenths of cents) for API compatibility
- Conversions: Use integer arithmetic only (no floating-point)

### Date Handling

- All dates use ISO 8601 format (YYYY-MM-DD)
- Transaction dates and posted dates tracked separately when available
- Matching uses posted_date for primary comparison
- Balance points use statement date or transaction date as appropriate
