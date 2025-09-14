# Viewing Unmatched Apple Transactions

This guide shows you multiple ways to analyze and explore unmatched transactions from the Apple receipt matching system.

## Quick Start

**Fastest way to see what's unmatched:**
```bash
# Show summary with categories
./unmatched_summary.sh

# Show detailed Python analysis
uv run python view_unmatched.py
```

## Available Tools

### 1. `unmatched_summary.sh` - Fast Command-Line Summaries

**Purpose**: Quick bash script using jq for instant summaries without Python dependencies.

**Basic Usage:**
```bash
# Basic summary (default)
./unmatched_summary.sh

# Show breakdown by payee
./unmatched_summary.sh --payee

# Show top 15 largest unmatched amounts
./unmatched_summary.sh --amounts 15

# Show monthly breakdown
./unmatched_summary.sh --monthly

# Show category details
./unmatched_summary.sh --details services
./unmatched_summary.sh --details icloud
./unmatched_summary.sh --details store

# Export to CSV
./unmatched_summary.sh --export my_unmatched.csv
```

**Advanced Usage:**
```bash
# Use specific results file
./unmatched_summary.sh --payee results/2025-09-14_17-49-10_apple_matching_results.json

# Multiple options
./unmatched_summary.sh --amounts 20 --categories
```

### 2. `view_unmatched.py` - Interactive Python Explorer

**Purpose**: Comprehensive analysis with pandas and interactive features.

**Basic Usage:**
```bash
# Show category summary (default)
uv run python view_unmatched.py

# Show detailed view of specific categories
uv run python view_unmatched.py --category services
uv run python view_unmatched.py --category icloud
uv run python view_unmatched.py --category store
uv run python view_unmatched.py --category other

# Show analysis by date or amount patterns
uv run python view_unmatched.py --analysis date
uv run python view_unmatched.py --analysis amount

# Export to CSV with detailed analysis
uv run python view_unmatched.py --export detailed_unmatched.csv
```

**Advanced Usage:**
```bash
# Show more details and limit results
uv run python view_unmatched.py --category services --details --limit 50

# Use specific results file
uv run python view_unmatched.py --file results/2025-09-14_17-49-10_apple_matching_results.json

# Full help
uv run python view_unmatched.py --help
```

## Direct jq Commands (Manual Exploration)

For custom analysis, you can use jq directly on the results files:

### Basic Queries

```bash
# Set the results file path
RESULTS="analysis/apple_transaction_matching/results/2025-09-14_17-49-10_apple_matching_results.json"

# Count total unmatched
jq '[.results[] | select(.matched == false)] | length' "$RESULTS"

# List all unmatched payee names
jq -r '.results[] | select(.matched == false) | .ynab_transaction.payee_name' "$RESULTS" | sort | uniq

# Show unmatched transactions over $100
jq '.results[] | select(.matched == false and .ynab_transaction.amount > 100) | {
  amount: .ynab_transaction.amount,
  payee: .ynab_transaction.payee_name,
  date: .ynab_transaction.date
}' "$RESULTS"
```

### Category-Specific Queries

```bash
# Apple Services subscriptions
jq '.results[] | select(.matched == false and .ynab_transaction.payee_name == "Apple Services") | {
  amount: .ynab_transaction.amount,
  date: .ynab_transaction.date,
  account: .ynab_transaction.account_name
}' "$RESULTS"

# APPLE.COM/BILL transactions (iCloud subscriptions)
jq '.results[] | select(.matched == false and (.ynab_transaction.payee_name | contains("APPLE.COM/BILL"))) | {
  amount: .ynab_transaction.amount,
  date: .ynab_transaction.date
}' "$RESULTS"

# Apple Store hardware purchases
jq '.results[] | select(.matched == false and (.ynab_transaction.payee_name | contains("Apple Store"))) | {
  amount: .ynab_transaction.amount,
  payee: .ynab_transaction.payee_name,
  date: .ynab_transaction.date
}' "$RESULTS"
```

### Export Queries

```bash
# Export unmatched to CSV format
echo "id,date,amount,payee_name,account_name" > unmatched.csv
jq -r '.results[] | select(.matched == false) | .ynab_transaction | 
  [.id, .date, .amount, .payee_name, .account_name] | @csv' "$RESULTS" >> unmatched.csv

# Export only high-value unmatched (over $50)
jq -r '.results[] | select(.matched == false and .ynab_transaction.amount > 50) | .ynab_transaction | 
  [.id, .date, .amount, .payee_name, .account_name] | @csv' "$RESULTS" > high_value_unmatched.csv
```

## Understanding Unmatched Categories

### Apple Services (Subscriptions)
- **What**: Monthly/annual subscription charges for Apple services
- **Examples**: App Store apps, Apple Music, Apple TV+, Apple Arcade
- **Why unmatched**: Many subscriptions don't generate email receipts
- **Expected**: Normal to have some unmatched here

### APPLE.COM/BILL (iCloud/Subscriptions)
- **What**: Regular billing for iCloud storage and other recurring services
- **Examples**: $9.99/month iCloud storage, Apple One bundles
- **Why unmatched**: Subscription billing often lacks detailed receipts
- **Expected**: Normal to have regular $9.99 charges unmatched

### Apple Store (Hardware)
- **What**: Physical Apple product purchases
- **Examples**: iPhones, MacBooks, accessories, AppleCare
- **Why unmatched**: In-store purchases may not email receipts, or receipts go to different email
- **Expected**: Some unmatched is normal, especially for in-store purchases

### Other Apple Transactions
- **What**: Miscellaneous Apple-related charges
- **Examples**: App Store purchases, iTunes purchases, Apple Pay transactions
- **Why unmatched**: Various reasons - different Apple ID emails, gift cards, etc.
- **Expected**: Should investigate these more closely

## Common Analysis Workflows

### 1. Monthly Review Workflow
```bash
# Quick monthly summary
./unmatched_summary.sh --monthly

# Detailed look at current month's unmatched
uv run python view_unmatched.py --analysis date

# Export for spreadsheet analysis
uv run python view_unmatched.py --export monthly_unmatched.csv
```

### 2. High-Value Investigation Workflow
```bash
# Show largest unmatched amounts
./unmatched_summary.sh --amounts 20

# Look for hardware purchases
./unmatched_summary.sh --details store

# Export high-value items for manual investigation
jq -r '.results[] | select(.matched == false and .ynab_transaction.amount > 200) | .ynab_transaction | 
  [.id, .date, .amount, .payee_name] | @csv' "$RESULTS" > investigate.csv
```

### 3. Subscription Analysis Workflow
```bash
# Look at all subscription-type charges
./unmatched_summary.sh --details services
./unmatched_summary.sh --details icloud

# Monthly subscription pattern analysis
uv run python view_unmatched.py --category services --analysis date
```

## Performance Notes

- **Bash script**: Fastest for quick summaries, uses minimal resources
- **Python script**: More detailed analysis, requires pandas but provides rich insights
- **Direct jq**: Most flexible for custom queries, good for specific investigations

## Results File Locations

Results files are stored in `analysis/apple_transaction_matching/results/` with timestamps:
- Format: `YYYY-MM-DD_HH-MM-SS_apple_matching_results.json`
- Both tools automatically find the latest file if no specific file is provided
- Use `--file` option to analyze specific historical results

## Tips for Analysis

1. **Start with the bash script** for a quick overview
2. **Use the Python script** for detailed monthly/category analysis  
3. **Export to CSV** for spreadsheet analysis and sharing
4. **Focus on high-value unmatched** items first
5. **Remember**: Some unmatched transactions are expected (subscriptions, in-store purchases)
6. **Look for patterns**: Regular amounts, specific payees, date patterns

## Troubleshooting

### "No results files found"
```bash
# Make sure you've run the batch matcher first
uv run python analysis/apple_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31
```

### "jq not found" 
```bash
# Install jq for the bash script
brew install jq
```

### "Permission denied"
```bash
# Make the bash script executable
chmod +x analysis/apple_transaction_matching/unmatched_summary.sh
```

---

**Quick Reference Commands:**
```bash
# Fastest overview
./unmatched_summary.sh

# Detailed analysis  
uv run python view_unmatched.py

# Export for Excel
uv run python view_unmatched.py --export analysis.csv

# Focus on subscriptions
./unmatched_summary.sh --details services

# Focus on hardware
./unmatched_summary.sh --details store
```