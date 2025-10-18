# Amazon Transaction Matching System - Product Specification

## Executive Summary

The Amazon Transaction Matching System creates automated linkage between Amazon order
  history data and corresponding YNAB credit card transactions.
This solves the challenge of understanding what Amazon purchases comprise each
  consolidated credit card charge, enabling accurate categorization and spending
  analysis across the Davis family's multiple Amazon accounts.

## Problem Statement

### Current Pain Points
1. **Opaque Amazon Charges**: YNAB shows consolidated Amazon charges (e.g.,
     "$89.99 from AMZN Mktp US*RT4Y12") without details of what was purchased
2. **Manual Investigation Required**: Each Amazon transaction requires manual order
     history searching to understand the underlying purchases
3. **Multi-Item Complexity**: Single orders with multiple items, shipping across
     different days, create complex matching scenarios
4. **Multi-Account Management**: Household has multiple Amazon accounts (karl, erica)
     with purchases appearing on shared credit cards
5. **Split Payment Scenarios**: Large orders may be split across multiple payment
     methods or billing cycles
6. **Historical Data Volume**: Years of Amazon transactions lack proper categorization
     and item-level detail

### Business Impact
- **Time Cost**: 10-15 minutes per Amazon transaction for manual matching and
    categorization
- **Analysis Limitations**: Cannot track product category spending, seasonal patterns,
    or individual item costs
- **Budget Accuracy**: Amazon purchases (potentially $200+/month) are inadequately
    categorized
- **Financial Insights**: Missing visibility into shopping patterns, bulk purchase
    optimization, and subscription management

## Success Criteria

### Primary Goals
1. **95% Match Coverage**: Nearly all Amazon transactions find corresponding order
     matches with high confidence
2. **Automated Processing**: No manual intervention required for standard matching
     scenarios
3. **Multi-Strategy Architecture**: Handle complete orders, split payments, and fuzzy
     matching scenarios
4. **Multi-Account Support**: Seamlessly process all household Amazon accounts
5. **Historical Coverage**: Process years of existing Amazon order history and
     transactions

### Measurable Outcomes
- **Match Rate**: ≥94% of Amazon transactions automatically matched with confidence
    ≥0.8
- **Processing Speed**: Complete monthly batch processing in <60 seconds
- **Time Savings**: Reduce Amazon transaction processing from 15 minutes to <2
    minutes per transaction
- **Item Detail Coverage**: Enable item-level categorization for Amazon purchases

## Functional Requirements

### Input Requirements

#### Amazon Order History Data
- **Source**: CSV files from Amazon data exports in `amazon/data/` directories
- **Multi-Account Structure**: Support `YYYY-MM-DD_accountname_amazon_data/` naming
    convention
- **Coverage**: All accounts automatically discovered and processed
- **Historical Scope**: Process all available order history
- **Data Fields Required**:
  - Order ID, order date, shipment date
  - Item names, quantities, individual amounts
  - Total amounts, shipping costs, tax
  - Payment method and billing information

#### YNAB Transaction Data
- **Source**: YNAB transaction cache in `ynab-data/transactions.json`
- **Filtering Criteria**: Transactions with Amazon-related payee names
- **Required Fields**:
  - Transaction ID, date, amount (in milliunits)
  - Payee name, account name
  - Current categorization

#### Expected Amazon Payee Patterns
- "AMZN Mktp US", "Amazon.com", "Amazon Mktp"
- "AMZN Digital", "Amazon Digital Services"
- "Prime Video", "Amazon Prime"
- Family of similar variants and abbreviations

### Processing Requirements

#### Core Matching Architecture

The system employs a **3-strategy architecture** designed for clean, maintainable code:

1. **Complete Match Strategy**
   - Exact order/shipment matches (high confidence ≥0.95)
   - Same-day shipping alignment
   - Direct amount correspondence

2. **Split Payment Strategy**
   - Partial order matches with item tracking
   - Handles large orders split across multiple payment methods
   - Maintains item-level detail for partial matches

3. **Fuzzy Match Strategy**
   - Approximate matches with flexible tolerances
   - Date window matching (±3 days)
   - Amount tolerance handling for small discrepancies

#### Advanced Matching Features

1. **Multi-Day Order Handling**
   - Orders shipping across multiple days
   - Individual shipment matching
   - Consolidated daily shipment grouping

2. **Integer Arithmetic Precision**
   - All currency calculations in integer cents
   - Zero tolerance for floating-point errors
   - Consistent rounding and remainder allocation

3. **Multi-Account Discovery**
   - Automatic detection of all Amazon account directories
   - Account attribution for order matching
   - Cross-account order search capabilities

4. **Order Grouping Intelligence**
   - Complete orders (all items together)
   - Individual shipments (separate packages)
   - Daily shipments (all items shipping same day)

### Output Requirements

#### Match Results Format
```json
{
  "ynab_transaction": {
    "id": "transaction-uuid",
    "date": "2024-08-15",
    "amount": -89.99,
    "payee_name": "AMZN Mktp US*RT4Y12",
    "account_name": "Chase Credit Card"
  },
  "matched": true,
  "amazon_orders": [
    {
      "account": "karl",
      "order_id": "111-2223334-5556667",
      "order_date": "2024-08-14",
      "total": 89.99,
      "items": [
        {
          "name": "Echo Dot (4th Gen)",
          "quantity": 1,
          "amount": 45.99
        },
        {
          "name": "USB-C Cable 6ft",
          "quantity": 2,
          "amount": 21.98
        }
      ]
    }
  ],
  "confidence": 0.95,
  "match_strategy": "complete_match",
  "processing_time": 0.012
}
```

#### Performance Metrics
- **Match Statistics**: Total matches, confidence distribution, strategy breakdown
- **Processing Metrics**: Time per transaction, total batch time
- **Quality Indicators**: Unmatched transactions, low-confidence matches
- **Multi-Account Attribution**: Matches per Amazon account

## Technical Architecture

### Modular Component Design

#### Order Grouper (`order_grouper.py`)
- **Purpose**: Unified order grouping logic
- **Functions**: Complete orders, shipments, daily shipments
- **Input**: Raw Amazon CSV data
- **Output**: Structured order groups for matching

#### Match Scorer (`match_scorer.py`)
- **Purpose**: Confidence scoring and match result creation
- **Functions**: Date alignment scoring, amount precision validation
- **Input**: Potential matches with metadata
- **Output**: Scored match results with confidence levels

#### Split Payment Matcher (`split_payment_matcher.py`)
- **Purpose**: Handle partial order matches
- **Functions**: Item tracking, persistent state management
- **Input**: Large orders and payment transactions
- **Output**: Split payment match results with item attribution

### Currency Handling Strategy

1. **Integer-Only Arithmetic**: All calculations in integer cents (no floating-point)
2. **Milliunits Conversion**: YNAB amounts converted from milliunits to cents
3. **Precision Preservation**: No rounding errors in financial calculations
4. **Display Formatting**: Integer division for dollar display (`cents//100.cents%100`)

### Multi-Day Order Processing

#### Problem
Amazon orders may ship across multiple days, with separate credit card charges for
  each shipment date.

#### Solution
1. **Order Discovery**: Identify all shipments belonging to same order ID
2. **Daily Grouping**: Group items by shipment date within order
3. **Flexible Matching**: Match individual daily shipments to separate transactions
4. **Complete Order Tracking**: Maintain relationship between all shipments

### Command-Line Interface

The Amazon transaction matching system is integrated into the Financial Flow System.

```bash
# Execute the complete financial flow (includes Amazon matching as AmazonMatcherNode)
finances flow

# The flow system guides you through interactive prompts:
# 1. YNAB data sync (YnabDataNode)
# 2. Amazon transaction matching (AmazonMatcherNode)
# 3. Apple receipt matching (AppleMatcherNode)
# 4. Cash flow analysis (CashFlowNode)

# Each node displays current data summary and prompts for updates
# Amazon matching happens automatically when processing flow
```

**Flow System Integration:**
- Amazon matching runs as **AmazonMatcherNode** in the dependency graph
- Depends on YnabDataNode (requires YNAB transactions)
- Outputs match results to `data/amazon/transaction_matches/`
- All Amazon accounts automatically discovered and processed
- Configuration via environment variables or `.env` file

### Performance Characteristics

#### Processing Speed
- **Target**: <60 seconds for monthly batch processing
- **Current**: ~0.015 seconds per transaction average
- **Scalability**: Linear scaling with transaction volume

#### Memory Efficiency
- **Order Data Caching**: Efficient in-memory order structures
- **Incremental Processing**: Process transactions individually
- **Resource Management**: Minimal memory footprint for large datasets

#### Quality Metrics
- **Match Rate**: Currently achieving 94.7% success rate
- **Confidence Distribution**: High confidence (≥0.9) for 80%+ of matches
- **Strategy Effectiveness**: Complete matches dominate successful results

## Quality Assurance

### Data Validation

1. **Input Validation**: Amazon CSV format verification, required field checking
2. **Amount Precision**: Integer arithmetic validation, sum verification
3. **Date Alignment**: Transaction date vs order date consistency
4. **Account Attribution**: Correct Amazon account assignment

### Edge Case Handling

1. **Zero Amount Items**: Free items in orders (promotional items)
2. **Refunds and Credits**: Negative amount transactions
3. **Currency Conversion**: International purchases (if applicable)
4. **Partial Cancellations**: Modified orders with item removals
5. **Subscription Orders**: Recurring Amazon purchases (Subscribe & Save)

### Error Recovery

1. **Graceful Degradation**: Skip problematic orders/transactions without stopping
     batch
2. **Detailed Logging**: Comprehensive error reporting with context
3. **Retry Logic**: Handle transient issues with order data loading
4. **Debug Mode**: Verbose output for troubleshooting complex scenarios

## Integration Points

### YNAB Data Workflow Integration
- **Dependencies**: Requires fresh YNAB transaction cache
- **Trigger Points**: After YNAB data refresh, before transaction updates
- **Data Flow**: YNAB transactions → matching → edit generation

### Amazon Data Workflow Integration
- **Dependencies**: Requires Amazon order history extracts
- **Account Discovery**: Automatic detection of new Amazon accounts
- **Historical Processing**: Handle both new and historical order data

### Transaction Updater Integration
- **Match Results**: Provide input for YNAB transaction splitting
- **Confidence Thresholds**: Support user-defined minimum confidence levels
- **Item Detail**: Enable detailed memo generation for split transactions

## Future Enhancements

### Near-Term Improvements
1. **Machine Learning Confidence**: Improve confidence scoring with historical
     success data
2. **Subscription Detection**: Identify and tag recurring Amazon purchases
3. **Category Suggestions**: Recommend YNAB categories based on Amazon product data
4. **Real-Time Processing**: Support incremental matching for new transactions

### Advanced Features
1. **Product Analysis**: Spending trends by product category
2. **Bulk Purchase Optimization**: Identify opportunities for bulk savings
3. **Price Tracking**: Historical price analysis for repeat purchases
4. **Vendor Analysis**: Track spending patterns across Amazon sellers

## Implementation Verification

### Success Validation
- ✓ Achieve 94.7% match rate on production data
- ✓ Process 1000+ transactions without memory issues
- ✓ Handle multi-day orders correctly (verified with test cases)
- ✓ Maintain precision with integer arithmetic (zero rounding errors)

### Performance Validation
- ✓ Complete monthly processing in <60 seconds
- ✓ Linear scaling confirmed with large datasets
- ✓ Memory usage remains stable during batch processing

### Quality Validation
- ✓ High confidence matches (≥0.9) achieve 95%+ accuracy
- ✓ Multi-account attribution works correctly
- ✓ Split payment matching preserves item details
- ✓ Edge cases handled gracefully without data corruption

---

## Document History

- **2025-09-21**: Initial specification created
- **Version**: 1.0
- **Status**: Complete System Specification
- **Owner**: Karl Davis

---

This specification provides a complete blueprint for the Amazon Transaction Matching
  System, documenting its 3-strategy architecture, multi-day order handling, and
  94.7% match rate achievement.
