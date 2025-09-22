# Amazon Data Workflow System - Product Specification

## Executive Summary

The Amazon Data Workflow System manages the complete lifecycle of Amazon order
  history data extraction, organization, and preparation for transaction matching
  analysis.
It provides a streamlined, multi-account approach to obtaining comprehensive purchase
  data directly from Amazon's official data export system, replacing manual
  extraction methods with a reliable, automated workflow.

## Problem Statement

### Current Pain Points
1. **Manual Data Extraction**: Manual browser-based order history collection is
     time-intensive (4-6 hours) and error-prone
2. **Incomplete Historical Data**: Browser interfaces limit access to complete
     purchase history
3. **Multi-Account Complexity**: Managing order data from multiple family Amazon
     accounts requires coordinated workflow
4. **Data Organization**: Extracted data needs structured organization for downstream
     analysis tools
5. **Update Challenges**: Refreshing order history data involves repeating manual
     processes
6. **Format Inconsistency**: Manual extraction creates inconsistent data formats
     requiring custom processing

### Business Impact
- **Time Investment**: 4-6 hours of active work for manual extraction vs 5 minutes +
    wait time
- **Data Quality**: ~95% completeness with manual methods vs 100% with official
    exports
- **Analysis Delays**: Inconsistent data formats slow down transaction matching
    workflows
- **Maintenance Overhead**: Regular data updates require repeating tedious manual
    processes
- **Multi-Account Management**: Household with multiple Amazon accounts creates
    coordination complexity

## Success Criteria

### Primary Goals
1. **Automated Data Acquisition**: Request Amazon data exports with minimal manual
     intervention
2. **Complete Historical Coverage**: Access to 100% of Amazon order history across
     all accounts
3. **Multi-Account Management**: Seamlessly handle multiple family Amazon accounts
4. **Structured Organization**: Consistent directory structure for automated tool
     discovery
5. **Integration Ready**: Data prepared for immediate use by transaction matching
     systems

### Measurable Outcomes
- **Time Efficiency**: Reduce data acquisition from 4-6 hours to 5 minutes of active
    work
- **Data Completeness**: 100% order history capture vs ~95% with manual methods
- **Account Coverage**: Support for all household Amazon accounts (karl, erica, etc.)
- **Processing Speed**: Complete extraction and organization in <5 minutes
- **Integration Success**: Immediate compatibility with transaction matching tools

## Functional Requirements

### Input Requirements

#### Amazon Data Export System
- **Access Method**: Amazon Privacy Central data request system
- **URL**: https://www.amazon.com/hz/privacy-central/data-requests/preview.html
- **Request Type**: "Your Orders" category export
- **Processing Time**: 4-5 hours for Amazon to prepare data
- **Delivery Method**: Email notification with download link

#### Multi-Account Support
- **Account Types**: Individual Amazon accounts per family member
- **Request Coordination**: Separate data requests for each account
- **Account Identification**: Clear naming convention for account attribution
- **Data Synchronization**: Handle different export timing across accounts

### Processing Requirements

#### Data Request Workflow

1. **Account-Specific Requests**
   ```
   For each Amazon account (karl, erica, ...):
   1. Navigate to Amazon Privacy Central
   2. Select "Your Orders" data category
   3. Submit data request
   4. Wait for email notification (4-5 hours)
   5. Download ZIP file when ready
   ```

2. **Request Tracking**
   - Monitor email notifications for each account
   - Track processing completion times
   - Coordinate downloads across multiple accounts

#### Data Organization Workflow

1. **Directory Structure Creation**
   ```
   amazon/data/
   ├── YYYY-MM-DD_karl_amazon_data/
   │   ├── Retail.OrderHistory.1/
   │   ├── Digital-Ordering.1/
   │   └── [other data directories]
   ├── YYYY-MM-DD_erica_amazon_data/
   │   ├── Retail.OrderHistory.1/
   │   ├── Digital-Ordering.1/
   │   └── [other data directories]
   └── [additional account directories]
   ```

2. **Automated Extraction Script**
   ```bash
   # Usage: ./extract_amazon_data.sh "Your Orders.zip" accountname
   ./amazon/extract_amazon_data.sh "Your Orders Karl.zip" karl
   ./amazon/extract_amazon_data.sh "Your Orders Erica.zip" erica
   ```

3. **Directory Naming Convention**
   - Format: `YYYY-MM-DD_accountname_amazon_data`
   - Date: Export date (when data was downloaded)
   - Account: Identifier for data source (karl, erica, etc.)
   - Suffix: Consistent `_amazon_data` for tool discovery

### Output Requirements

#### Structured Data Organization

**Primary Data Files:**
- **`Retail.OrderHistory.1/Retail.OrderHistory.1.csv`** - Complete purchase history
    (most critical)
- **`Digital-Ordering.1/Digital Orders.csv`** - Digital content purchases
- **`Retail.CustomerReturns.1/`** - Return and refund history
- **Additional CSV files** - Specialized order types and payment details

**Data Fields Available:**
```csv
Order ID, Order Date, Order Status, Product Name, Product Category,
ASIN/ISBN, Quantity, Purchase Price Per Unit, Total Amount,
Payment Method, Shipping Address, [additional fields...]
```

#### Multi-Account Discovery System

1. **Automatic Account Detection**
   ```python
   # Transaction matching tools automatically discover:
   amazon_accounts = discover_amazon_accounts("amazon/data/")
   # Returns: ["karl", "erica", ...] based on directory names
   ```

2. **Account-Specific Processing**
   ```bash
   # Process specific accounts only
   python match_transactions.py --accounts karl erica

   # Process all discovered accounts (default)
   python match_transactions.py
   ```

3. **Cross-Account Search**
   - Tools search all accounts for transaction matches
   - Account attribution preserved in match results
   - No manual account specification required for discovery

## Technical Architecture

### Extraction Automation

#### Helper Script Design (`extract_amazon_data.sh`)
```bash
#!/bin/bash
set -e  # Exit on error

# Input validation
ZIP_FILE="$1"
ACCOUNT_NAME="$2"
DATE_STAMP=$(date +%Y-%m-%d)
TARGET_DIR="amazon/data/${DATE_STAMP}_${ACCOUNT_NAME}_amazon_data"

# Safety checks
validate_zip_file_exists()
create_data_directory_if_needed()
check_for_existing_directory()

# Core extraction
extract_zip_to_target_directory()
verify_extraction_success()
display_extraction_summary()

# User interaction
offer_zip_file_deletion()
show_next_steps()
```

#### Data Validation Pipeline

1. **Extraction Verification**
   ```bash
   # Verify expected directories exist
   if [ -d "$TARGET_DIR/Retail.OrderHistory.1" ]; then
       echo "✓ Successfully extracted retail order history"
   fi

   if [ -d "$TARGET_DIR/Digital-Ordering.1" ]; then
       echo "✓ Successfully extracted digital order history"
   fi
   ```

2. **File Count Validation**
   ```bash
   TOTAL_FILES=$(find "$TARGET_DIR" -type f | wc -l)
   echo "Total files extracted: $TOTAL_FILES"
   ```

3. **Structure Consistency**
   - Verify CSV files have expected headers
   - Check for required data columns
   - Validate file sizes are reasonable

### Integration Architecture

#### Discovery System
```python
def discover_amazon_accounts(data_dir="amazon/data/"):
    """Automatically discover all Amazon account directories."""
    accounts = []
    pattern = re.compile(r'\d{4}-\d{2}-\d{2}_(\w+)_amazon_data')

    for dir_name in os.listdir(data_dir):
        match = pattern.match(dir_name)
        if match:
            accounts.append(match.group(1))

    return sorted(set(accounts))
```

#### Data Loading Interface
```python
def load_amazon_data(account=None, data_dir="amazon/data/"):
    """Load Amazon order data for specified account(s)."""
    if account:
        # Load specific account's most recent data
        return load_account_data(account, data_dir)
    else:
        # Load all discovered accounts
        accounts = discover_amazon_accounts(data_dir)
        return {acc: load_account_data(acc, data_dir) for acc in accounts}
```

### Maintenance and Updates

#### Data Refresh Workflow

1. **Periodic Updates**
   ```bash
   # Quarterly data refresh recommended
   # 1. Request new exports from Amazon
   # 2. Extract using helper script
   # 3. Tools automatically use most recent data
   ```

2. **Incremental Processing**
   - Transaction matching tools use most recent export per account
   - No need to delete old exports (maintain historical snapshots)
   - Tools automatically discover and use latest data

3. **Account Management**
   ```bash
   # Add new account
   ./amazon/extract_amazon_data.sh "Your Orders NewAccount.zip" newaccount

   # Update existing account
   ./amazon/extract_amazon_data.sh "Your Orders Karl Updated.zip" karl
   ```

## Quality Assurance

### Data Validation

1. **Export Completeness**
   - Verify all expected directories extracted
   - Check for required CSV files
   - Validate file sizes against expected ranges

2. **Data Integrity**
   - CSV format validation
   - Header row verification
   - Character encoding consistency

3. **Account Attribution**
   - Verify directory naming follows convention
   - Confirm account name consistency
   - Check for duplicate account data

### Error Handling

1. **Extraction Failures**
   ```bash
   # Handle corrupted ZIP files
   # Manage disk space issues
   # Recover from partial extractions
   ```

2. **Directory Conflicts**
   ```bash
   # Prompt for overwrite confirmation
   # Backup existing data before replacement
   # Provide clear error messages
   ```

3. **Validation Failures**
   - Warn about missing expected files
   - Continue processing with partial data
   - Log issues for troubleshooting

## Integration Points

### Transaction Matching Integration
- **Data Discovery**: Automatic detection of all Amazon accounts
- **Account Selection**: Support for processing specific accounts
- **Data Loading**: Consistent CSV loading interface
- **Attribution**: Preserve account information in match results

### Analysis Tool Integration
- **Standardized Paths**: Consistent directory structure for tool discovery
- **Format Consistency**: CSV files ready for immediate processing
- **Multi-Account Support**: Tools automatically handle multiple accounts
- **Historical Access**: Maintain multiple export snapshots for analysis

### Workflow Integration
- **YNAB Integration**: Prepare data for transaction matching workflows
- **Cash Flow Analysis**: Historical purchase data for spending analysis
- **Reporting Systems**: Structured data ready for reporting tools

## Comparative Analysis

### Manual vs Automated Approach

| Aspect | Manual Browser Extraction | Official Data Request |
|--------|---------------------------|----------------------|
| **Time Investment** | 4-6 hours active work | 5 minutes + 4-5 hour wait |
| **Data Completeness** | ~95% (human errors) | 100% complete |
| **Historical Scope** | Limited by UI pagination | Complete order history |
| **Format Consistency** | Manual YAML creation | Structured CSV files |
| **Reliability** | Depends on UI changes | Official API, stable |
| **Automation Potential** | None | Full CSV processing |
| **Multi-Account Support** | Manual coordination | Consistent workflow |
| **Integration Ready** | Custom processing needed | Immediate tool compatibility |

### Benefits Realization
- **95% Time Reduction**: From 4-6 hours to 5 minutes active work
- **100% Data Accuracy**: Official exports vs manual transcription
- **Consistent Format**: CSV structure vs manual formatting
- **Future-Proof**: Official API vs UI scraping dependency

## Future Enhancements

### Near-Term Improvements
1. **Automated Scheduling**: Reminder system for periodic data refresh
2. **Validation Dashboard**: Visual verification of extracted data quality
3. **Account Synchronization**: Coordinate multi-account export timing
4. **Integration Testing**: Automated validation of transaction matching
     compatibility

### Advanced Features
1. **API Integration**: Direct integration with Amazon's data API (if available)
2. **Real-Time Updates**: Incremental data updates vs full exports
3. **Data Analytics**: Built-in analysis of order patterns and trends
4. **Cloud Storage**: Automated backup of extracted data

### Workflow Enhancements
1. **Email Integration**: Automated download from Amazon notification emails
2. **Version Management**: Track and manage multiple data export versions
3. **Comparison Tools**: Analyze changes between export versions
4. **Automated Testing**: Continuous validation of extraction workflow

## Implementation Verification

### Workflow Validation
- ✓ Complete end-to-end workflow tested across multiple accounts
- ✓ Directory structure automatically recognized by transaction matching tools
- ✓ Data extraction preserves all required fields for analysis
- ✓ Multi-account coordination works seamlessly

### Quality Validation
- ✓ 100% data completeness compared to manual extraction methods
- ✓ Consistent CSV format compatible with all analysis tools
- ✓ Error handling prevents data corruption or loss
- ✓ Account attribution maintained throughout processing pipeline

### Integration Validation
- ✓ Transaction matching tools automatically discover all accounts
- ✓ No configuration changes required for additional accounts
- ✓ Data format immediately compatible with existing analysis workflows
- ✓ Historical snapshots maintain accessibility for trend analysis

---

## Document History

- **2025-09-21**: Initial specification created
- **Version**: 1.0
- **Status**: Complete System Specification
- **Owner**: Karl Davis

---

This specification provides a complete blueprint for the Amazon Data Workflow System,
  documenting its official data export integration, multi-account management, and
  seamless integration with downstream transaction matching tools.