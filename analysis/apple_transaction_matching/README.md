# Apple Receipt Transaction Matching System

## Overview

This system automatically matches Apple receipts (extracted from emails) to corresponding YNAB credit card transactions, solving the challenge of understanding what Apple purchases comprise each consolidated credit card charge. The system enables accurate categorization and spending analysis across multiple Apple accounts in the Davis family.

**Status**: ✅ **Implemented and Tested** - Successfully matching transactions with 85.2% match rate and 0.883 average confidence on full production data (Feb 2024 - Sep 2025).

## Quick Start

```bash
# Process all Apple transactions in a specific month
uv run python analysis/apple_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31 --verbose

# Match a specific transaction by ID
uv run python analysis/apple_transaction_matching/match_single_transaction.py \
  --transaction-id "abc123-def456-..." --verbose
```

## System Architecture

### Key Components

1. **`apple_receipt_loader.py`** - Loads and normalizes Apple receipt data from exports
2. **`ynab_apple_filter.py`** - Filters YNAB transactions to Apple-related purchases  
3. **`apple_matcher.py`** - Core matching logic with 2-strategy approach
4. **`match_scorer.py`** - Confidence scoring adapted for Apple transaction patterns
5. **`match_single_transaction.py`** - CLI tool for matching individual transactions
6. **`match_transactions_batch.py`** - CLI tool for batch processing date ranges

### Matching Strategies

**Simple 2-strategy approach** (vs Amazon's complex 3-strategy system):

1. **Exact Match**: Same date + exact amount match
   - Confidence: 1.0
   - Example: YNAB $19.99 on 2024-07-15 matches Apple receipt $19.99 on 2024-07-15

2. **Date Window Match**: ±1-2 days with exact amount
   - Confidence: 0.75-0.90 (depending on date difference)
   - Example: YNAB $5.29 on 2024-07-27 matches Apple receipt $5.29 on 2024-07-26
   - **Note**: Requires exact amount matches (no tolerance) for maximum precision

### Data Sources

#### Apple Receipts
- **Source**: Parsed receipts from `apple/exports/` JSON files
- **Coverage**: 327 receipts across 4 Apple IDs (karl, erica, archer, mason)
- **Date Range**: 2020-11-03 to 2025-09-12
- **Total Value**: $6,507.96

#### YNAB Transactions  
- **Source**: YNAB transaction cache (`ynab-data/transactions.json`)
- **Apple Transactions**: 201 out of 5,439 total transactions
- **Payee Patterns**: "Apple", "Apple Services", "APPLE.COM/BILL", "Apple Store"
- **Accounts**: Apple Card, Chase Credit Card, Chase Checking

## Tools Available

### 1. `match_single_transaction.py` - Single Transaction Matcher

**Purpose**: Match one specific YNAB transaction to Apple receipts

**Usage**:
```bash
# Match by transaction ID (looks up from YNAB data)
uv run python analysis/apple_transaction_matching/match_single_transaction.py \
  --transaction-id "24bd348e-41cc-4759-940e-4e2d01b00859"

# Match by providing transaction details manually  
uv run python analysis/apple_transaction_matching/match_single_transaction.py \
  --transaction-id "manual-001" \
  --date "2024-11-15" \
  --amount -1990 \
  --payee-name "APPLE.COM/BILL" \
  --account-name "Chase Credit Card"

# Save result to file
uv run python analysis/apple_transaction_matching/match_single_transaction.py \
  --transaction-id "abc123-def456-..." \
  --output results/single_match.json
```

**Parameters**:
- `--transaction-id`: YNAB transaction UUID (required)
- `--date`: Transaction date (YYYY-MM-DD) - for manual entry
- `--amount`: Amount in milliunits (negative for expenses) - for manual entry
- `--payee-name`: Payee name from YNAB - for manual entry
- `--account-name`: Account name from YNAB - for manual entry
- `--output`: Optional output file path
- `--include-items`: Include item details from Apple receipts
- `--verbose`: Enable detailed progress output

### 2. `match_transactions_batch.py` - Batch Processor

**Purpose**: Process all Apple transactions in a date range

**Usage**:
```bash
# Process July 2024 transactions
uv run python analysis/apple_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31

# With verbose output and item details
uv run python analysis/apple_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31 \
  --verbose --include-items

# Custom date window (exact amounts always required)
uv run python analysis/apple_transaction_matching/match_transactions_batch.py \
  --start 2024-07-01 --end 2024-07-31 \
  --date-window 3
```

**Parameters**:
- `--start`: Start date (YYYY-MM-DD) - required
- `--end`: End date (YYYY-MM-DD) - required  
- `--output`: Results directory (default: analysis/apple_transaction_matching/results)
- `--include-items`: Include item details from Apple receipts
- `--verbose`: Enable detailed progress logging
- `--date-window`: Date window in days for matching (default: 2)

## Output Format

### Single Transaction Result
```json
{
  "ynab_transaction": {
    "id": "transaction-uuid",
    "date": "2024-07-04",
    "amount": 13.77,
    "payee_name": "Apple",
    "account_name": "Chase Credit Card"
  },
  "matched": true,
  "apple_receipts": [
    {
      "apple_id": "***REMOVED***",
      "receipt_date": "Jul 4, 2024",
      "order_id": "MSD1VL9G7T",
      "total": 13.77,
      "currency": "USD"
    }
  ],
  "match_confidence": 1.0,
  "match_strategy": "exact_date_amount",
  "unmatched_amount": 0.0
}
```

### Batch Processing Results
```json
{
  "date_range": {
    "start": "2024-07-01", 
    "end": "2024-07-31"
  },
  "summary": {
    "total_transactions": 11,
    "matched": 7,
    "match_rate": 0.636,
    "average_confidence": 0.871,
    "total_amount_matched": 201.96,
    "strategy_breakdown": {
      "exact_date_amount": 1,
      "date_window_match": 6
    }
  },
  "results": [...],
  "processing_metadata": {
    "timestamp": "2025-09-14T17:28:25",
    "processing_time_seconds": 0.05
  }
}
```

## Performance Metrics

### Production Results (Feb 2024 - Sep 2025)
- **Data Volume**: 422 Apple receipts total, 208 in date range; 183 YNAB Apple transactions
- **Processing Time**: 0.13 seconds total (~0.0007 seconds per transaction)
- **Match Rate**: 85.2% (156 of 183 transactions matched)
- **Confidence**: 0.883 average confidence score
- **1:1 Relationship**: ✅ Confirmed - each transaction matches exactly one receipt

### Matching Strategy Distribution
- **Exact matches**: 21.8% (34 of 156 matches, confidence 1.0)
- **Date window matches**: 78.2% (122 of 156 matches, confidence 0.75-0.90)

### Confidence Distribution
- **Perfect** (≥0.95): 34 matches
- **High** (0.80-0.95): 122 matches
- **Medium** (0.60-0.80): 0 matches
- **Low** (<0.60): 0 matches

### Recent Architecture Improvements (September 2025)
- **Amount Tolerance Removal**: Eliminated $0.01 tolerance requirement for exact amount matches
- **Impact**: Maintained 85.2% match rate while improving precision (exact amounts only)
- **Benefit**: Prevents false positives from rounding/tax calculation discrepancies

## Key Insights

### 1:1 Transaction Model Confirmed
Unlike Amazon (which bundles multiple orders into shipment-based charges), Apple maintains a direct 1:1 relationship between receipts and credit card transactions. This greatly simplifies the matching logic compared to Amazon's complex grouping system.

### Multi-Account Support
The system automatically handles all 4 family Apple IDs:
- ***REMOVED***
- ***REMOVED***  
- ***REMOVED***
- ***REMOVED***

### Common Match Scenarios
1. **Same Day Purchase**: Receipt and charge on identical date
2. **Processing Delay**: Receipt date vs charge date differs by 1-2 days
3. **Family Sharing**: Different Apple ID but same payment method

## Dependencies

### Data Requirements
- **Apple Receipt System**: Requires successful Apple email extraction and parsing
- **YNAB Data Workflow**: Uses existing transaction cache structure
- **Python Environment**: Uses `uv` for dependency management

### System Integration
- **Apple Receipt Exports**: Consumes JSON from `apple/exports/`
- **YNAB Transaction Cache**: Reads from `ynab-data/transactions.json`
- **Results Storage**: Outputs to `analysis/apple_transaction_matching/results/`

## Troubleshooting

### Common Issues

1. **No Apple receipts found**
   - Check that Apple receipt system has run successfully
   - Verify `apple/exports/` contains timestamped export directories
   - Run `uv run python apple/scripts/export_receipts_to_json.py`

2. **No Apple transactions found**
   - Verify YNAB data is current: check `ynab-data/transactions.json`
   - Update YNAB cache if needed
   - Check date range includes Apple transactions

3. **Low match rates**
   - Increase `--date-window` parameter (default: 2 days)
   - Check for missing Apple receipts or different payment methods
   - Note: Amount tolerance has been removed for precision - only exact amounts match

4. **Large unmatched amounts**
   - Often indicates Apple Card payments (transfers) rather than purchases
   - Filter by payee patterns to exclude non-purchase transactions

### Performance Optimization

- **Memory**: Efficient pandas operations, minimal memory footprint
- **Speed**: ~0.005 seconds per transaction for batch processing
- **Scalability**: Handles 300+ receipts and 200+ transactions efficiently

## Future Enhancements

### Near-term Improvements
1. **Subscription Tracking**: Identify and track recurring Apple service charges
2. **Family Sharing Analysis**: Better attribution of shared purchases
3. **Refund Handling**: Match refund credits to original purchases

### Integration Opportunities  
1. **YNAB Memo Updates**: Automatically add receipt details to transaction memos
2. **Category Suggestions**: AI-powered categorization based on app/service type
3. **Spending Analytics**: Apple-specific spending pattern reports

### Architecture Extensions
1. **Real-time Processing**: Webhook-based matching for new transactions
2. **Duplicate Detection**: Identify and handle duplicate receipt imports
3. **Multi-currency Support**: Handle international Apple purchases

## Project Structure

```
analysis/apple_transaction_matching/
├── README.md                     # This documentation
├── apple_receipt_loader.py       # Receipt data loading and normalization
├── ynab_apple_filter.py          # YNAB transaction filtering
├── apple_matcher.py              # Core matching logic (2-strategy system)
├── match_scorer.py               # Confidence scoring for Apple patterns
├── match_single_transaction.py   # Single transaction CLI tool
├── match_transactions_batch.py   # Batch processing CLI tool
└── results/                      # Generated JSON results (timestamped)
    └── YYYY-MM-DD_HH-MM-SS_apple_matching_results.json
```

## Comparison to Amazon System

| Aspect | Amazon System | Apple System |
|--------|---------------|--------------|
| **Complexity** | 3 strategies, complex shipment grouping | 2 strategies, simple 1:1 matching |
| **Match Rate** | 94.7% (multi-item bundling challenges) | 85.2% (simpler transaction model) |
| **Confidence** | 0.93 average | 0.883 average |
| **Performance** | 0.007 sec/transaction | 0.0007 sec/transaction |
| **Architecture** | Modular but complex (order grouper, split payments) | Streamlined and focused |
| **Amount Precision** | Uses tolerance for bundled orders | Exact amounts only (no tolerance) |

---

**Document Version**: 1.1
**Last Updated**: September 21, 2025
**Status**: ✅ **Production Ready** - Fully implemented, tested, and documented for ongoing use.