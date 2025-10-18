# Cash Flow Analysis System - Product Specification

## Executive Summary

The Cash Flow Analysis System provides comprehensive financial dashboard generation
  and trend analysis for the Davis family's cash and liquid accounts.
It transforms raw YNAB transaction data into visual insights including moving
  averages, volatility analysis, trend projections, and financial health metrics to
  support informed budgeting and spending decisions.

## Problem Statement

### Current Pain Points
1. **Limited Financial Visibility**: YNAB provides transaction-level detail but lacks
     comprehensive cash flow trend analysis
2. **Manual Analysis Burden**: Understanding spending patterns, seasonal trends, and
     financial health requires manual spreadsheet work
3. **Missing Context**: Individual transactions don't reveal broader financial
     patterns or trajectory
4. **No Predictive Insights**: Inability to project future cash flow based on
     historical trends
5. **Volatility Blindness**: Difficult to understand balance fluctuation patterns and
     what drives them
6. **Multi-Account Complexity**: Five different accounts need unified analysis to
     understand total financial picture

### Business Impact
- **Decision Making**: Limited visibility into whether spending patterns are
    sustainable
- **Budget Planning**: Cannot identify seasonal patterns or cyclical spending
    behaviors
- **Risk Assessment**: No early warning system for negative cash flow trends
- **Goal Setting**: Difficult to set realistic financial targets without historical
    context
- **Performance Tracking**: No quantitative way to measure financial health
    improvement over time

## Success Criteria

### Primary Goals
1. **Comprehensive Visualization**: Generate multi-faceted dashboard showing all key
     financial metrics
2. **Trend Analysis**: Identify and quantify financial trajectory with statistical
     confidence
3. **Automated Insights**: Extract actionable insights without manual analysis
4. **Historical Context**: Process all available reliable financial data for complete
     picture
5. **Repeatable Analysis**: Enable regular dashboard generation for ongoing
     monitoring

### Measurable Outcomes
- **Dashboard Generation**: Complete analysis in <30 seconds
- **Data Coverage**: Process all transactions since May 2024 (reliable data cutoff)
- **Visual Clarity**: 6-panel dashboard covering all major financial dimensions
- **Statistical Accuracy**: Trend analysis with confidence intervals and validation
    metrics
- **Actionable Insights**: Clear recommendations based on quantitative analysis

## Functional Requirements

### Input Requirements

#### YNAB Transaction Data
- **Source**: YNAB transaction cache in `ynab-data/transactions.json`
- **Account Coverage**: Five cash/liquid accounts (Chase Checking, Chase Credit Card,
    Apple Card, Apple Cash, Apple Savings)
- **Time Range**: All transactions from May 1, 2024 onward (excludes unreliable
    historical data)
- **Required Fields**:
  - Transaction ID, date, amount (in milliunits)
  - Account name, payee name
  - Transaction type and categorization

#### YNAB Account Data
- **Source**: YNAB account cache in `ynab-data/accounts.json`
- **Required Fields**:
  - Account names and current balances (in milliunits)
  - Account types and metadata
- **Purpose**: Establish current balance baseline for historical reconstruction

### Processing Requirements

#### Daily Balance Calculation
1. **Balance Reconstruction**: Work backwards from current balances using transaction
     history
2. **Time Series Completion**: Fill gaps to create complete daily balance series
3. **Account Aggregation**: Calculate total liquid balance across all cash accounts
4. **Data Validation**: Ensure balance calculations align with current account states

#### Statistical Analysis Components

1. **Moving Average Calculations**
   - 7-day moving average (short-term smoothing)
   - 30-day moving average (monthly trend identification)
   - 90-day moving average (quarterly pattern analysis)

2. **Trend Analysis**
   - Linear regression for overall trajectory
   - Statistical confidence calculation (R-squared)
   - Daily, monthly, and yearly trend projections

3. **Volatility Metrics**
   - Standard deviation of balance fluctuations
   - Coefficient of variation for relative volatility
   - Monthly balance range analysis

4. **Cash Flow Patterns**
   - Daily net change calculations
   - Positive vs negative flow day distribution
   - Rolling 30-day velocity analysis

#### Dashboard Generation Components

1. **Main Balance Plot**: Daily balances with multiple moving averages and trend line
2. **Monthly Cash Flow**: Bar chart showing net monthly changes with averages
3. **Volatility Analysis**: Monthly balance ranges showing financial stability
4. **Cash Flow Velocity**: 30-day rolling changes showing flow
     acceleration/deceleration
5. **Account Composition**: Stacked visualization of individual account contributions
6. **Statistical Summary**: Comprehensive metrics box with key insights

### Output Requirements

#### Dashboard Format
- **File Type**: High-resolution PNG (150 DPI)
- **Dimensions**: 16x12 inches for detailed visibility
- **Layout**: 3x2 panel grid with comprehensive title
- **Timestamped Files**: Format `YYYY-MM-DD_HH-MM-SS_cash_flow_analysis.png`

#### Key Metrics Included
```
📊 FINANCIAL HEALTH METRICS
• Current Balance: Real-time total across all accounts
• 30/90-Day Averages: Recent performance context
• Historical Analysis: Average, std dev, min/max with dates
• Cash Flow Patterns: Positive vs negative flow day percentages
• Trend Analysis: Daily/monthly/yearly projections with confidence
• Volatility Metrics: Coefficient of variation, monthly ranges
```

#### Automated Insights
- **Trend Direction**: Growing vs declining with confidence percentage
- **Burn Rate**: Average monthly spending rate
- **Volatility Assessment**: Stability metrics and patterns
- **Performance Benchmarks**: Current status vs historical averages

## Technical Architecture

### Current Implementation (Flow System Integration)

**Modern Implementation:**
The Cash Flow Analysis System is integrated into the Financial Flow System as **CashFlowNode**.

```bash
# Execute cash flow analysis via flow system
finances flow

# The flow system:
# - Prompts for cash flow analysis update
# - Depends on YnabDataNode (requires YNAB data)
# - Uses CashFlowAnalyzer with CashFlowDataStore
# - Generates 6-panel dashboard automatically
# - Outputs to data/cash_flow/charts/
```

**DataStore Pattern:**
- **CashFlowDataStore**: Manages cash flow analysis results and dashboards
- **Location**: `data/cash_flow/` directory
- **Charts**: Timestamped PNG files with 6-panel dashboards
- **Archiving**: Previous dashboards maintained for trend comparison
- **Configuration**: Account selection and date ranges via environment variables

**Code Organization:**
The Python analysis code described below is implemented in `src/finances/analysis/cash_flow.py`
  and integrated into the flow system.
The architectural patterns and statistical methods remain as specified.

### Data Pipeline Design

#### Phase 1: Data Loading and Validation
```python
# Load YNAB data with error handling
accounts_data = load_json('ynab-data/accounts.json')
transactions = load_json('ynab-data/transactions.json')

# Validate required fields and data quality
validate_account_data(accounts_data)
validate_transaction_data(transactions)
```

#### Phase 2: Balance Reconstruction
```python
# Filter to cash accounts and reliable date range
cash_transactions = filter_transactions(
    transactions,
    accounts=CASH_ACCOUNTS,
    start_date='2024-05-01'
)

# Reconstruct daily balances working backwards
daily_balances = reconstruct_balances(
    cash_transactions,
    current_balances
)
```

#### Phase 3: Statistical Analysis
```python
# Convert to pandas DataFrame for analysis
df = create_timeseries_dataframe(daily_balances)

# Calculate all moving averages and metrics
df = add_moving_averages(df, windows=[7, 30, 90])
df = add_trend_analysis(df)
df = add_volatility_metrics(df)
```

#### Phase 4: Visualization Generation
```python
# Create comprehensive 6-panel dashboard
fig = create_dashboard_layout(figsize=(16, 12))
plots = generate_all_panels(df, monthly_stats)
save_timestamped_dashboard(fig, 'results/')
```

### Statistical Methods

#### Trend Analysis
- **Method**: Linear regression using scipy.stats.linregress
- **Confidence**: R-squared correlation coefficient
- **Projections**: Slope-based daily/monthly/yearly extrapolations
- **Validation**: Statistical significance testing

#### Smoothing Techniques
- **Simple Moving Averages**: Unweighted rolling windows (7, 30, 90 days)
- **Purpose**: Noise reduction and pattern identification
- **Implementation**: Pandas rolling() with minimum periods handling

#### Volatility Calculations
- **Standard Deviation**: Population standard deviation of daily balances
- **Coefficient of Variation**: Normalized volatility metric (std/mean)
- **Range Analysis**: Monthly high-low spread for stability assessment

### Performance Characteristics

#### Processing Speed
- **Target**: Complete analysis in <30 seconds
- **Current**: ~5-10 seconds for 150+ days of data
- **Scalability**: Linear with transaction volume

#### Memory Efficiency
- **Data Loading**: Efficient JSON parsing and filtering
- **DataFrame Operations**: Pandas vectorized calculations
- **Visualization**: Matplotlib memory optimization

#### Output Quality
- **Resolution**: 150 DPI for crisp dashboard display
- **Color Scheme**: Consistent, accessible color palette
- **Typography**: Clear fonts with appropriate sizing

## Quality Assurance

### Data Validation

1. **Input Validation**: Check required JSON fields and data types
2. **Date Range Validation**: Ensure transactions fall within expected ranges
3. **Balance Consistency**: Verify reconstructed balances align with current state
4. **Statistical Validation**: Check for outliers and data anomalies

### Edge Case Handling

1. **Missing Data**: Handle gaps in transaction history gracefully
2. **Zero Balances**: Properly display accounts with zero or negative balances
3. **Short History**: Generate meaningful analysis even with limited data
4. **Account Changes**: Handle account additions/closures in time series

### Visual Quality Assurance

1. **Layout Optimization**: Ensure all panels fit properly without overlap
2. **Color Accessibility**: Use colorblind-friendly palettes
3. **Text Readability**: Verify all labels and statistics are clearly visible
4. **Scale Appropriateness**: Choose axis scales that highlight relevant patterns

## Configuration and Customization

### Account Selection
```python
# Define which accounts to include in analysis
CASH_ACCOUNTS = [
    'Chase Checking',
    'Chase Credit Card',
    'Apple Card',
    'Apple Cash',
    'Apple Savings'
]
```

### Date Range Configuration
```python
# Exclude unreliable data before this date
START_DATE = '2024-05-01'
```

### Visualization Customization
- **Color Schemes**: Configurable plot colors and styling
- **Panel Layout**: Adjustable dashboard arrangement
- **Metric Selection**: Customizable statistics display
- **Time Windows**: Configurable moving average periods

## Integration Points

### YNAB Data Workflow Integration
- **Dependencies**: Requires current YNAB data cache
- **Trigger Points**: Run after YNAB data refresh
- **Output Location**: Results saved to `analysis/cash_flow/results/`

### Reporting Integration
- **Dashboard Archives**: Timestamped files for historical comparison
- **Trend Tracking**: Compare current vs previous analysis results
- **Alert System**: Potential for automated alerts on negative trends

## Future Enhancements

### Near-Term Improvements
1. **Budget vs Actual Analysis**: Compare cash flow to YNAB budget targets
2. **Category-Level Insights**: Break down cash flow by spending categories
3. **Seasonal Analysis**: Identify and quantify seasonal spending patterns
4. **Automated Alerts**: Email notifications for significant trend changes

### Advanced Features
1. **Predictive Modeling**: Machine learning for cash flow forecasting
2. **Goal Tracking**: Visual progress toward financial targets
3. **Comparison Analysis**: Multi-period dashboard comparisons
4. **Interactive Dashboards**: Web-based interactive visualizations

### Integration Opportunities
1. **Transaction Matching Integration**: Incorporate Amazon/Apple categorization
     insights
2. **Investment Analysis**: Expand to include investment account performance
3. **External Data Sources**: Bank account direct feeds, investment APIs
4. **Mobile Notifications**: Real-time financial health alerts

## Implementation Verification

### Validation Metrics
- ✓ Process 150+ days of transaction data in <30 seconds
- ✓ Generate statistically valid trend analysis with R-squared confidence
- ✓ Create clear, readable 6-panel dashboard layout
- ✓ Handle multiple account types and negative balances correctly

### Quality Checks
- ✓ Balance reconstruction matches current account states
- ✓ Moving averages properly smooth short-term volatility
- ✓ Statistical metrics provide actionable insights
- ✓ Visual output is professional and information-dense

### User Experience Validation
- ✓ Dashboard provides immediate financial health overview
- ✓ Trend projections help with future planning
- ✓ Volatility analysis identifies stability patterns
- ✓ Automated insights reduce manual analysis time

---

## Document History

- **2025-09-21**: Initial specification created
- **Version**: 1.0
- **Status**: Complete System Specification
- **Owner**: Karl Davis

---

This specification provides a complete blueprint for the Cash Flow Analysis System,
  documenting its statistical methods, 6-panel dashboard design, and comprehensive
  financial health metrics generation.
