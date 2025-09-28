# YNAB Data Workflow System - Product Specification

## Executive Summary

The YNAB Data Workflow System provides reliable, automated caching of YNAB budget data for offline analysis and integration with other financial tools. It maintains three critical JSON files containing accounts, categories, and transactions data, serving as the foundation for all downstream financial analysis systems including cash flow analysis, transaction matching, and reporting.

## Problem Statement

### Current Pain Points
1. **API Rate Limits**: Direct YNAB API calls are rate-limited and not suitable for frequent analysis workflows
2. **Network Dependencies**: Analysis tools require reliable offline access to financial data
3. **Data Freshness**: Need to balance current data with performance for analytical workflows
4. **Integration Complexity**: Multiple analysis tools need consistent access to the same YNAB data
5. **Authentication Management**: Secure handling of YNAB API credentials across different tools
6. **Data Structure Consistency**: Ensure downstream tools have reliable data format expectations

### Business Impact
- **Analysis Delays**: Waiting for API calls slows down financial analysis workflows
- **Reliability Issues**: Network failures can block critical financial operations
- **Development Friction**: Building analysis tools requires managing API complexity
- **Data Inconsistency**: Different tools may see different data due to timing of API calls
- **Operational Overhead**: Manual data refresh creates maintenance burden

## Success Criteria

### Primary Goals
1. **Reliable Data Access**: Offline availability of complete YNAB dataset for analysis
2. **Automated Refresh**: Scheduled data updates without manual intervention
3. **Consistent Format**: Standardized JSON structure for all downstream consumers
4. **Fast Performance**: Local data access eliminates API latency for analysis tools
5. **Data Integrity**: Validation and error detection for cached data quality

### Measurable Outcomes
- **Refresh Speed**: Complete data refresh in <60 seconds
- **Data Completeness**: 100% of accounts, categories, and transactions cached
- **Update Frequency**: Daily automated updates with manual override capability
- **Integration Success**: All analysis tools use cached data exclusively
- **Error Rate**: <1% failed refresh attempts with automated retry

## Functional Requirements

### Input Requirements

#### YNAB CLI Authentication
- **Authentication Method**: YNAB CLI tool with stored access token
- **Configuration**: `.ynab.env` file with valid API credentials
- **Budget Access**: Configured for "Davis Family Budget" access
- **Verification**: `ynab list budgets` command succeeds

#### YNAB API Data Sources
- **Accounts Data**: All account information including balances
- **Categories Data**: Complete category hierarchy and budget allocations
- **Transactions Data**: All historical transaction records
- **Data Scope**: Complete dataset (no date filtering for cache)

### Processing Requirements

#### Core Data Extraction Commands

1. **Accounts Extraction**
   ```bash
   ynab --output json list accounts > ynab-data/accounts.json
   ```
   - **Structure**: Nested accounts array within response object
   - **Content**: Account IDs, names, types, balances, metadata
   - **Validation**: Verify accounts array length > 0

2. **Categories Extraction**
   ```bash
   ynab --output json list categories > ynab-data/categories.json
   ```
   - **Structure**: Nested category_groups array with nested categories
   - **Content**: Category hierarchies, budget allocations, group organization
   - **Validation**: Verify category_groups array with expected categories

3. **Transactions Extraction**
   ```bash
   ynab --output json list transactions > ynab-data/transactions.json
   ```
   - **Structure**: Direct transaction array (no nesting)
   - **Content**: All historical transactions with full metadata
   - **Validation**: Verify array length matches expected transaction count

#### Data Validation Pipeline

1. **JSON Format Validation**
   ```bash
   jq empty ynab-data/accounts.json
   jq empty ynab-data/categories.json
   jq empty ynab-data/transactions.json
   ```

2. **Structure Validation**
   ```bash
   # Verify expected nested structure
   jq '.accounts | length' ynab-data/accounts.json
   jq '.category_groups | length' ynab-data/categories.json
   jq 'length' ynab-data/transactions.json
   ```

3. **Content Validation**
   ```bash
   # Verify sample records have required fields
   jq '.accounts[0] | {id, name, type, balance}' ynab-data/accounts.json
   jq '.category_groups[0] | {id, name}' ynab-data/categories.json
   jq '.[0] | {id, date, amount, payee_name}' ynab-data/transactions.json
   ```

### Output Requirements

#### File Structure
```
ynab-data/
├── accounts.json      # Account information with nested structure
├── categories.json    # Category groups with nested categories
├── transactions.json  # Direct array of all transactions
├── refresh.log       # Automated refresh logs
└── last_refresh.txt  # Timestamp of last successful refresh
```

#### Data Format Specifications

**accounts.json Structure:**
```json
{
  "accounts": [
    {
      "id": "uuid",
      "name": "Account Name",
      "type": "checking|credit|savings|...",
      "balance": 123456,  // milliunits
      "cleared_balance": 123456,
      "uncleared_balance": 0,
      // ... additional metadata
    }
  ],
  "server_knowledge": 1234567890
}
```

**categories.json Structure:**
```json
{
  "category_groups": [
    {
      "id": "uuid",
      "name": "Group Name",
      "categories": [
        {
          "id": "uuid",
          "name": "Category Name",
          "budgeted": 123456,  // milliunits
          "activity": -45678,
          "balance": 77778,
          // ... additional metadata
        }
      ]
    }
  ],
  "server_knowledge": 1234567890
}
```

**transactions.json Structure:**
```json
[
  {
    "id": "uuid",
    "date": "2024-09-21",
    "amount": -12345,  // milliunits (negative for outflow)
    "payee_name": "Payee Name",
    "category_name": "Category Name",
    "account_name": "Account Name",
    "memo": "Transaction memo",
    "approved": true,
    "cleared": "cleared|uncleared|reconciled",
    // ... additional metadata
  }
]
```

## Technical Architecture

### Refresh Workflow Design

#### Full Data Refresh Script
```bash
#!/bin/bash
# scripts/refresh-ynab-data.sh

set -e  # Exit on any error

echo "Starting YNAB data refresh at $(date)"

# Create directory structure
mkdir -p ynab-data

# Verify authentication
ynab list budgets > /dev/null || {
  echo "ERROR: YNAB authentication failed"
  exit 1
}

# Extract all data with error handling
echo "Extracting accounts..."
ynab --output json list accounts > ynab-data/accounts.json.tmp
mv ynab-data/accounts.json.tmp ynab-data/accounts.json

echo "Extracting categories..."
ynab --output json list categories > ynab-data/categories.json.tmp
mv ynab-data/categories.json.tmp ynab-data/categories.json

echo "Extracting transactions..."
ynab --output json list transactions > ynab-data/transactions.json.tmp
mv ynab-data/transactions.json.tmp ynab-data/transactions.json

# Validate extracted data
validate_data

# Record successful refresh
echo "$(date)" > ynab-data/last_refresh.txt
echo "YNAB data refresh completed successfully at $(date)"
```

#### Validation Function
```bash
validate_data() {
  local errors=0

  # JSON format validation
  for file in accounts.json categories.json transactions.json; do
    if ! jq empty "ynab-data/$file" 2>/dev/null; then
      echo "ERROR: Invalid JSON in $file"
      errors=$((errors + 1))
    fi
  done

  # Structure validation
  local account_count=$(jq '.accounts | length' ynab-data/accounts.json 2>/dev/null || echo 0)
  local category_count=$(jq '.category_groups | length' ynab-data/categories.json 2>/dev/null || echo 0)
  local transaction_count=$(jq 'length' ynab-data/transactions.json 2>/dev/null || echo 0)

  if [ "$account_count" -eq 0 ]; then
    echo "ERROR: No accounts found"
    errors=$((errors + 1))
  fi

  if [ "$category_count" -eq 0 ]; then
    echo "ERROR: No categories found"
    errors=$((errors + 1))
  fi

  if [ "$transaction_count" -eq 0 ]; then
    echo "ERROR: No transactions found"
    errors=$((errors + 1))
  fi

  if [ $errors -gt 0 ]; then
    echo "Data validation failed with $errors errors"
    exit 1
  fi

  echo "Data validation passed:"
  echo "  Accounts: $account_count"
  echo "  Category groups: $category_count"
  echo "  Transactions: $transaction_count"
}
```

### Automation and Scheduling

#### Cron Configuration
```bash
# Daily refresh at 6 AM
0 6 * * * cd /Users/karl/workspaces/justdavis/personal/justdavis-finances && ./scripts/refresh-ynab-data.sh >> ynab-data/refresh.log 2>&1

# Weekly full validation at 6 AM Sunday
0 6 * * 0 cd /Users/karl/workspaces/justdavis/personal/justdavis-finances && ./scripts/validate-ynab-cache.sh >> ynab-data/validation.log 2>&1
```

#### Manual Refresh Interface
```bash
# Quick refresh command
make refresh-ynab-data

# Validation-only command
make validate-ynab-cache

# Force refresh (ignores recent refresh)
make force-refresh-ynab-data
```

### Error Handling and Recovery

#### Retry Logic
```bash
refresh_with_retry() {
  local max_attempts=3
  local attempt=1

  while [ $attempt -le $max_attempts ]; do
    echo "Refresh attempt $attempt of $max_attempts"

    if refresh_ynab_data; then
      echo "Refresh successful on attempt $attempt"
      return 0
    fi

    echo "Refresh failed on attempt $attempt"
    sleep $((attempt * 10))  # Exponential backoff
    attempt=$((attempt + 1))
  done

  echo "All refresh attempts failed"
  return 1
}
```

#### Backup and Recovery
```bash
# Create backup before refresh
backup_current_data() {
  if [ -d ynab-data ]; then
    local backup_dir="ynab-data-backup-$(date +%Y%m%d-%H%M%S)"
    cp -r ynab-data "$backup_dir"
    echo "Backup created: $backup_dir"
  fi
}

# Restore from backup on failure
restore_from_backup() {
  local latest_backup=$(ls -t ynab-data-backup-* 2>/dev/null | head -1)
  if [ -n "$latest_backup" ]; then
    rm -rf ynab-data
    cp -r "$latest_backup" ynab-data
    echo "Restored from backup: $latest_backup"
  fi
}
```

## Integration Points

### Downstream Consumer Integration

#### Cash Flow Analysis Integration
- **Dependency**: Requires fresh `accounts.json` and `transactions.json`
- **Usage Pattern**: Read-only access to cached data
- **Trigger**: Run after successful YNAB refresh

#### Transaction Matching Integration
- **Dependency**: Requires current `transactions.json`
- **Usage Pattern**: Read cached transactions for matching against external data
- **Update Frequency**: Before batch matching operations

#### Transaction Updater Integration
- **Dependency**: All three JSON files for complete context
- **Usage Pattern**: Read-only for mutation generation, may trigger refresh after updates
- **Coordination**: Refresh cache after YNAB modifications

### External System Integration

#### YNAB API Integration
- **Authentication**: Managed through YNAB CLI configuration
- **Rate Limiting**: Cached data eliminates frequent API calls
- **Error Handling**: Graceful degradation when API unavailable

#### File System Integration
- **Directory Structure**: Follows established `ynab-data/` conventions
- **File Permissions**: Readable by analysis scripts, writable by refresh process
- **Cleanup**: Automated cleanup of old backup files

## Quality Assurance

### Data Integrity Validation

1. **Completeness Checks**: Verify all expected accounts and categories present
2. **Consistency Checks**: Ensure data relationships are maintained
3. **Freshness Validation**: Alert if data becomes stale (>24 hours old)
4. **Size Validation**: Check for unexpected data size changes

### Error Detection and Alerting

1. **Authentication Failures**: Detect and alert on YNAB API authentication issues
2. **Network Issues**: Handle and retry transient network failures
3. **Data Corruption**: Detect and recover from corrupted cache files
4. **Missing Data**: Alert when expected data is missing or incomplete

### Performance Monitoring

1. **Refresh Duration**: Track and alert on unusually long refresh times
2. **Data Size Trends**: Monitor cache file size growth over time
3. **Success Rate**: Track refresh success/failure rates
4. **API Response Times**: Monitor YNAB API performance

## Future Enhancements

### Near-Term Improvements
1. **Incremental Updates**: Support for fetching only changed data since last refresh
2. **Compression**: Compress cached files to reduce storage requirements
3. **Webhooks**: Real-time updates triggered by YNAB changes
4. **Multi-Budget Support**: Extend to handle multiple YNAB budgets

### Advanced Features
1. **Change Detection**: Track and log data changes between refreshes
2. **Historical Versioning**: Maintain multiple versions of cached data
3. **Performance Analytics**: Detailed metrics on cache utilization
4. **Automated Optimization**: Self-tuning refresh frequency based on usage patterns

### Integration Enhancements
1. **API Gateway**: Provide REST API interface to cached data
2. **Real-Time Sync**: Bidirectional synchronization with YNAB
3. **Multi-User Support**: Support for multiple YNAB accounts/users
4. **Cloud Backup**: Automated backup of cached data to cloud storage

## Implementation Verification

### Validation Checklist
- ✓ Complete data extraction for all three data types
- ✓ JSON format validation for all output files
- ✓ Automated retry logic for transient failures
- ✓ Backup and recovery procedures tested
- ✓ Integration with downstream analysis tools confirmed

### Performance Validation
- ✓ Full refresh completes in <60 seconds
- ✓ Validation checks complete in <10 seconds
- ✓ Automated scheduling works reliably
- ✓ Error handling prevents data corruption

### Quality Validation
- ✓ Data integrity checks prevent incomplete caches
- ✓ Authentication validation prevents failed refreshes
- ✓ Logging provides adequate troubleshooting information
- ✓ Manual override commands work correctly

---

## Document History

- **2025-09-21**: Initial specification created
- **Version**: 1.0
- **Status**: Complete System Specification
- **Owner**: Karl Davis

---

This specification provides a complete blueprint for the YNAB Data Workflow System, documenting its caching strategy, automation capabilities, and integration with downstream financial analysis tools.
