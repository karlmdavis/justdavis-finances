# Apple Receipt Transaction Matching System - Product Specification

## Executive Summary

The Apple Receipt Transaction Matching System creates automated linkage between Apple receipts
  (extracted from emails) and corresponding YNAB credit card transactions.
This solves the challenge of understanding what Apple purchases comprise each consolidated credit
  card charge, enabling accurate categorization and spending analysis across the Davis family's
  multiple Apple accounts.

## Problem Statement

### Current Pain Points
1. **Opaque Apple Charges**: YNAB shows consolidated Apple charges (e.g., "$19.99 from
     APPLE.COM/BILL") without details of what was purchased.
2. **Manual Investigation Required**: Each Apple transaction requires manual email searching to
     understand the underlying purchases.
3. **Multi-Account Complexity**: Four family Apple IDs (karl, erica, archer, mason) create
     charges that are difficult to attribute.
4. **Incomplete Categorization**: Apple purchases often remain in generic "Shopping" categories
     due to investigation overhead.
5. **Missing Purchase History**: Years of Apple transactions lack proper categorization and
     item-level detail.

### Business Impact
- **Time Cost**: 5-15 minutes per Apple transaction for manual matching and categorization.
- **Analysis Limitations**: Cannot track subscription costs, app spending patterns, or family
    member spending allocation.
- **Budget Accuracy**: Apple purchases (potentially $100+/month) are inadequately categorized.
- **Financial Insights**: Missing visibility into digital spending patterns and subscription
    management.

## Success Criteria

### Primary Goals
1. **100% Match Coverage**: Every Apple receipt finds its corresponding YNAB transaction, and
     vice versa.
2. **Automated Processing**: No manual intervention required for standard matching.
3. **Multi-Account Support**: Handle all four family Apple IDs seamlessly.
4. **Historical Coverage**: Process years of existing Apple receipts and transactions.

### Measurable Outcomes
- **Match Rate**: ≥95% of Apple transactions automatically matched with high confidence.
- **Processing Speed**: Complete monthly batch processing in <30 seconds.
- **Time Savings**: Reduce Apple transaction processing from 10 minutes to <1 minute per
    transaction.
- **Categorization Improvement**: Enable detailed item-level categorization for Apple
    purchases.

## Functional Requirements

### Input Requirements

#### Apple Receipt Data
- **Source**: Parsed Apple receipts from `apple/exports/` JSON files.
- **Coverage**: All receipts from all four Apple IDs (karl, erica, archer, mason).
- **Historical Scope**: Process all available receipt history.
- **Data Fields Required**:
  - Apple ID (purchaser email).
  - Receipt date and time.
  - Total amount charged.
  - Order ID/document number.
  - Individual items purchased.
  - Payment method indicators.

#### YNAB Transaction Data
- **Source**: YNAB transaction cache in `ynab-data/transactions.json`.
- **Filtering Criteria**: Transactions with Apple-related payee names.
- **Required Fields**:
  - Transaction ID, date, amount (in milliunits).
  - Payee name, account name.
  - Current categorization.

#### Expected Apple Payee Patterns
- "Apple.com", "APPLE.COM/BILL".
- "iTunes", "App Store".
- "Apple Services".
- Family of similar variants.

### Processing Requirements

#### Core Matching Logic
1. **Date Alignment**: Match receipt dates to transaction dates (allowing for processing
     delays).
2. **Amount Verification**: Confirm receipt totals match YNAB transaction amounts.
3. **Account Attribution**: Link receipts to correct Apple ID when multiple accounts exist.
4. **Confidence Scoring**: Assign reliability scores to matches.

#### Handling Edge Cases
- **Processing Delays**: Apple charges may appear 1-2 days after receipt date.
- **Refunds**: Handle refunded purchases and credits.
- **Subscription Renewals**: Identify recurring subscription charges.
- **Family Sharing**: Attribute purchases to correct family member.
- **Currency Conversions**: Handle any currency discrepancies.
- **Partial Refunds**: Match partial credits to original purchases.

### Output Requirements

#### Match Results Format
```json
{
  "ynab_transaction": {
    "id": "transaction-uuid",
    "date": "2024-11-15",
    "amount": -19.99,
    "payee_name": "APPLE.COM/BILL",
    "account_name": "Chase Credit Card"
  },
  "matched": true,
  "apple_receipts": [
    {
      "apple_id": "user@example.com",
      "receipt_date": "2024-11-15",
      "order_id": "MLYPH7KXN9",
      "total": 19.99,
      "items": [
        {
          "title": "ProApp Premium",
          "type": "in_app_purchase",
          "cost": 19.99
        }
      ]
    }
  ],
  "match_confidence": 1.0,
  "match_method": "exact_date_amount"
}
```

#### Batch Processing Results
- **Summary Statistics**: Total transactions processed, match rates, confidence distributions.
- **Unmatched Items**: Both YNAB transactions and Apple receipts without matches.
- **Processing Metadata**: Timestamps, data sources, performance metrics.
- **Match Quality Reports**: Confidence score analysis and potential issues.

#### Command-Line Interface

The Apple transaction matching system is integrated into the Financial Flow System.

```bash
# Execute the complete financial flow (includes Apple matching as AppleMatcherNode)
finances flow

# The flow system guides you through interactive prompts for:
# 1. YNAB data sync (YnabDataNode)
# 2. Amazon transaction matching (AmazonMatcherNode)
# 3. Apple receipt matching (AppleMatcherNode)
# 4. Cash flow analysis (CashFlowNode)
```

**Flow System Integration:**
- Apple matching runs as **AppleMatcherNode** in the dependency graph.
- Depends on YnabDataNode (requires YNAB transactions).
- Outputs match results to `data/apple/transaction_matches/`.
- All Apple IDs automatically discovered and processed.
- Item details included by default for YNAB transaction splitting integration.
- Configuration via environment variables or `.env` file.

## Non-Functional Requirements

### Performance
- **Processing Speed**: Handle 100+ transactions per minute.
- **Memory Efficiency**: Process large datasets without excessive memory usage.
- **Scalability**: Support years of historical data.

### Reliability
- **Error Handling**: Graceful failure for malformed data.
- **Data Integrity**: Preserve original data, no destructive operations.
- **Consistency**: Reproducible results across multiple runs.

### Usability
- **Clear Documentation**: Usage examples and troubleshooting guides.
- **Progress Indication**: Status updates for long-running operations.
- **Actionable Outputs**: Clear identification of items requiring manual review.

## Integration Requirements

### Existing System Compatibility
- **Apple Receipt System**: Consume JSON exports from `apple/exports/`.
- **YNAB Data Workflow**: Use existing transaction cache structure.
- **Amazon Matching System**: Follow similar architectural patterns for consistency.
- **Analysis Tools**: Support integration with broader financial analysis workflows.
- **YNAB Transaction Splitter**: Provide item-level details required for automated transaction
    splitting.

### Data Dependencies
- **Apple Receipt Availability**: Requires successful Apple email extraction and parsing.
- **YNAB Data Currency**: Results depend on up-to-date YNAB transaction cache.
- **Multi-Account Coordination**: Handle family member data privacy appropriately.

## Validation and Testing

### Test Scenarios
1. **Perfect Matches**: Recent transactions with clear 1:1 receipt correspondence.
2. **Processing Delays**: Receipts and charges with 1-2 day timing differences.
3. **Multiple Apple IDs**: Transactions from different family members on same dates.
4. **Edge Cases**: Refunds, subscription renewals, family sharing purchases.
5. **Historical Data**: Older transactions to validate retroactive matching.

### Success Validation
- **Match Rate Analysis**: Statistical analysis of matching success rates.
- **Manual Verification**: Spot-checking of high-confidence matches.
- **Edge Case Coverage**: Verification that special cases are handled appropriately.
- **Performance Benchmarking**: Timing analysis for various data volumes.

## Future Considerations

### Potential Enhancements
- **YNAB Integration**: Automatic memo updates with item details.
- **Subscription Tracking**: Dedicated recurring payment analysis.
- **Spending Analytics**: Apple-specific spending pattern reports.
- **Category Suggestions**: AI-powered categorization recommendations.

### Maintenance Requirements
- **Apple Format Changes**: Monitor for receipt format updates.
- **New Apple Services**: Support for additional Apple product lines.
- **Performance Optimization**: Ongoing efficiency improvements as data volume grows.

---

**Document Version**: 1.1.
**Created**: September 14, 2025.
**Last Updated**: September 20, 2025.
**Owner**: Karl Davis.
**Status**: Specification Complete.

### Changelog
- **v1.1 (2025-09-20)**: Updated default behavior to include item details by default for YNAB
    transaction splitter integration.
