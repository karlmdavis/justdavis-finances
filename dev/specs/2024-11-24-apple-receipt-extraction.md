# Apple Receipt Email Extraction System - Product Specification

## Executive Summary

The Apple Receipt Email Extraction System addresses the challenge of categorizing Apple App Store,
  iTunes, and other Apple service purchases within YNAB (You Need A Budget).
Apple consolidates multiple purchases into single credit card transactions, making it impossible to
  properly categorize individual items without access to the detailed receipt information sent via
  email.

## Problem Statement

### Current Pain Points
1. **Opaque Transaction Data**: Apple charges appear in YNAB as consolidated amounts (e.g.,
     "$45.67 from APPLE.COM/BILL") without itemization.
2. **Manual Categorization Burden**: Users must manually search email receipts to understand what
     was purchased.
3. **Family Sharing Complexity**: Multiple family members' purchases appear as single charges,
     complicating budget allocation.
4. **Historical Data Loss**: Years of purchase history remains uncategorized in YNAB.
5. **Subscription Tracking**: Recurring subscriptions are difficult to identify and track over
     time.

### User Impact
- **Time Cost**: 5-10 minutes per Apple transaction to manually match and categorize.
- **Accuracy Issues**: Purchases often miscategorized or left in generic "Shopping" categories.
- **Budget Insights**: Unable to analyze spending patterns for apps, media, subscriptions
    separately.
- **Family Budgeting**: Cannot allocate costs to appropriate family members.

## Solution Overview

An automated system that extracts Apple receipt emails, parses purchase details, and structures
  the data for matching with YNAB transactions—similar to the existing Amazon transaction matching
  system but tailored for Apple's unique receipt format and purchase patterns.

## Functional Requirements

### Data Extraction Requirements

#### Email Retrieval
- **Source**: IMAP access to email account (user@example.com).
- **Search Criteria**: Emails with subject "Your receipt from Apple" or similar patterns.
- **Historical Scope**: Extract all available receipts (potentially years of history).
- **Incremental Updates**: Support for fetching only new receipts in future runs.
- **Error Handling**: Graceful handling of connection issues, malformed emails.

#### Receipt Types to Support
- **App Store Purchases**: iOS and macOS applications.
- **In-App Purchases**: Additional content within apps.
- **Subscriptions**: Recurring charges for services.
- **Media Purchases**: Music, movies, TV shows, books (if same format).
- **iCloud Services**: Storage and other Apple services.
- **Hardware Purchases**: Excluded if format differs significantly.

### Data Parsing Requirements

#### Required Fields per Receipt
1. **Receipt Metadata**
   - Apple Account ID (purchaser's email).
   - Receipt date and time.
   - Order ID (unique identifier).
   - Document/Invoice number.

2. **Financial Information**
   - Subtotal amount.
   - Tax amount.
   - Total amount charged.
   - Currency (if international).

3. **Line Item Details**
   - Product name/title.
   - Product description/subtitle.
   - Purchase type (app, subscription, in-app, etc.).
   - Device/platform (iPhone, Mac, etc.).
   - Individual item cost.
   - Quantity (if applicable).

#### Format Handling
- **Version Detection**: Identify and handle different receipt formats over time.
- **Flexible Parsing**: Adapt to HTML structure variations.
- **Encoding Support**: Handle various character encodings properly.
- **Error Recovery**: Skip unparseable receipts without stopping batch processing.

### Data Export Requirements

#### Output Format
- **Structure**: JSON format for consistency with existing tools.
- **Organization**: Chronologically sorted receipts.
- **Metadata**: Include extraction statistics and date ranges.
- **Validation**: Built-in data integrity checks.

#### Storage Convention
- **Directory Structure**: Follow `apple/data/` pattern similar to Amazon.
- **File Naming**: Timestamped exports (YYYY-MM-DD_apple_receipts.json).
- **Intermediate Storage**: Cached .eml files for re-processing.

## Non-Functional Requirements

### Performance
- **Batch Processing**: Handle hundreds of emails efficiently.
- **Resumable**: Support interruption and resume of long extraction runs.
- **Caching**: Store intermediate results to avoid re-processing.

### Reliability
- **Retry Logic**: Automatic retry for transient failures.
- **Logging**: Detailed logs for debugging and audit trail.
- **Validation**: Automated checks for data consistency.

### Maintainability
- **Modular Design**: Separate components for fetch, parse, export.
- **Format Evolution**: Easy to add new receipt format parsers.
- **Documentation**: Clear documentation of receipt formats and parsing logic.

### Security
- **Credential Management**: Environment variables for email credentials.
- **Data Privacy**: No logging of sensitive purchase details.
- **Local Processing**: All data processing happens locally.

## Success Criteria

### Quantitative Metrics
- **Coverage**: Successfully parse >95% of Apple receipt emails.
- **Accuracy**: 100% accuracy in amount extraction for parsed receipts.
- **Performance**: Process 100 receipts in <30 seconds.
- **Historical Reach**: Extract receipts dating back at least 3 years.

### Qualitative Goals
- **User Experience**: Simple command-line interface matching existing tools.
- **Integration Ready**: Output format compatible with future YNAB matching.
- **Debugging Support**: Clear error messages and validation reports.
- **Extensibility**: Architecture supports adding new Apple services.

## Integration Points

### Upstream Dependencies
- **Email Service**: IMAP access to email provider.
- **Apple Receipt Format**: HTML email structure from Apple.

### Downstream Consumers
- **YNAB Transaction Matcher**: Future system to match receipts with transactions.
- **Financial Analysis Tools**: Spending pattern analysis scripts.
- **Budget Reports**: Category allocation and trending.

## Constraints and Assumptions

### Technical Constraints
- **Email Access**: Requires IMAP credentials and server support.
- **Receipt Format**: Assumes Apple maintains parseable HTML structure.
- **Local Storage**: Sufficient disk space for email cache.

### Business Assumptions
- **Receipt Completeness**: All Apple purchases generate email receipts.
- **Single Email Address**: All family receipts arrive at one email account.
- **Format Stability**: Receipt formats change gradually, not drastically.

## Future Enhancements

### Near-term Opportunities
- **Smart Categorization**: Suggest YNAB categories based on purchase type.
- **Subscription Tracking**: Identify and track recurring subscriptions.
- **Family Member Attribution**: Determine which family member made purchase.

### Long-term Vision
- **Real-time Processing**: Process receipts as they arrive.
- **Multi-source Support**: Extend to other digital stores (Google Play, etc.).
- **Automated YNAB Updates**: Direct integration with YNAB API.

## Appendix: Sample Data Structures

### Sample Receipt (Conceptual)
```json
{
  "apple_id": "user@example.com",
  "receipt_date": "2024-11-15T10:23:45Z",
  "order_id": "MLYPH7KXN9",
  "document_number": "723994857234",
  "subtotal": 45.97,
  "tax": 3.78,
  "total": 49.75,
  "currency": "USD",
  "items": [
    {
      "title": "Things 3",
      "subtitle": "Productivity App",
      "type": "app_purchase",
      "platform": "macOS",
      "cost": 35.99,
      "quantity": 1
    },
    {
      "title": "Overcast Premium",
      "subtitle": "Annual Subscription",
      "type": "subscription",
      "platform": "iOS",
      "cost": 9.98,
      "quantity": 1
    }
  ]
}
```

### Sample YNAB Transaction (For Reference)
```json
{
  "id": "transaction-uuid",
  "date": "2024-11-15",
  "amount": -49750,  // milliunits (divide by 1000 for dollars)
  "payee_name": "APPLE.COM/BILL",
  "account_name": "Chase Credit Card",
  "category_name": "Shopping",
  "cleared": "cleared"
}
```

## Document History

- **2024-11-24**: Initial specification created.
- **Version**: 1.0.
- **Status**: Draft.

---

This specification provides the foundation for building a robust Apple receipt extraction system
  that solves the transaction categorization problem while maintaining consistency with existing
  financial automation tools.
