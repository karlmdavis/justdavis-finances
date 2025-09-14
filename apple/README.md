# Apple Receipt Email Extraction System

## Overview

This system extracts and parses Apple receipt emails to enable proper categorization of App Store, iTunes, and other Apple service purchases in YNAB. It solves the problem of Apple consolidating multiple purchases into single credit card transactions.

## Quick Start

```bash
# 1. Set up email credentials (if fetching new emails)
cp .env.template .env
# Edit .env with your IMAP credentials

# 2. Fetch receipt emails (optional - only if getting new data)
uv run python apple/scripts/fetch_receipt_emails.py

# 3. Extract email content 
uv run python apple/scripts/extract_email_content.py

# 4. Parse and export receipts to JSON
uv run python apple/scripts/export_receipts_to_json.py

# 5. Validate results
uv run python apple/scripts/validate_receipts.py
```

## Directory Structure

```
apple/
├── README.md              # This file
├── scripts/              # Core production scripts
│   ├── receipt_parser.py            # Main parsing engine (3 parsers)
│   ├── export_receipts_to_json.py   # JSON export with validation
│   ├── validate_receipts.py         # Enhanced validation system
│   ├── extract_email_content.py     # MIME content extraction
│   ├── extract_receipt_metadata.py  # Receipt metadata analysis
│   ├── fetch_receipt_emails.py      # Email fetching from IMAP
│   └── archive/                     # Development scripts (archived)
├── data/                 # Email data (gitignored)
│   └── YYYY-MM-DD_HH-MM-SS_apple_emails/  # Timestamped email cache
├── exports/              # Generated exports (gitignored)
│   └── YYYY-MM-DD_HH-MM-SS_apple_receipts_export/  # Timestamped exports
└── docs/                 # Documentation
    ├── email_analysis.md             # Email pattern findings
    ├── receipt_formats.md            # Receipt format documentation
    └── format_examples/              # Sample receipts for each format
```

## Scripts

### Core Production Scripts

### receipt_parser.py
Main parsing engine with 3-parser architecture.
- **PlainTextParser**: Handles 2020-2023 plain text receipts (67.9%)
- **LegacyHTMLParser**: Handles 2024+ HTML receipts with aapl-* classes (26.3%)
- **ModernHTMLParser**: Handles 2025+ HTML receipts with custom-* classes (5.8%)
- Achieves 100% parsing success and 100% financial integrity
- Supports desktop-only selection to avoid mobile duplication

### export_receipts_to_json.py
Exports parsed receipts to structured JSON.
- Processes all 327+ purchase receipts
- Generates timestamped exports with metadata
- Creates both individual and combined JSON files
- Includes comprehensive statistics and format breakdown

### validate_receipts.py
Enhanced validation system with smart categorization.
- **Format-aware validation**: Different expectations per receipt format
- **Warning categorization**: Financial discrepancies, data quality, format limitations
- **100% validation success rate** with detailed reporting
- Maintains strict financial integrity (no tolerance for math errors)

### extract_email_content.py
MIME email content extraction.
- Extracts both text/plain and text/html parts from .eml files
- Creates multiple output formats (formatted, simplified HTML)
- Handles complex MIME structures and encoding
- Essential preprocessing step for parsing

### extract_receipt_metadata.py
Receipt metadata analysis and filtering.
- Distinguishes purchase receipts from other Apple emails
- Extracts purchase types, financial structure, format indicators
- Identifies 327 actual receipts out of 388 total emails
- Provides format classification for parser selection

### fetch_receipt_emails.py
Email fetching from IMAP servers.
- Downloads Apple receipt emails with flexible search patterns
- Supports resume on interruption
- Handles multiple Apple ID accounts
- Saves emails as .eml files for offline processing

### Development Scripts (Archived)

The `scripts/archive/` directory contains development and analysis scripts used during system creation:
- Format analysis tools (`analyze_*.py`)
- Testing and debugging scripts (`test_*.py`, `debug_*.py`)  
- Email categorization tools (`categorize_emails.py`)

These are preserved for reference but not needed for regular operations.

## Data Format

### Output JSON Structure
```json
{
  "metadata": {
    "extraction_date": "2024-11-24",
    "email_count": 250,
    "parsed_count": 248,
    "failed_count": 2,
    "date_range": {
      "earliest": "2018-01-15",
      "latest": "2024-11-20"
    }
  },
  "receipts": [
    {
      "apple_id": "***REMOVED***",
      "receipt_date": "2024-11-15T10:23:45Z",
      "order_id": "MLYPH7KXN9",
      "document_number": "723994857234",
      "subtotal": 45.97,
      "tax": 3.78,
      "total": 49.75,
      "currency": "USD",
      "items": [...]
    }
  ]
}
```

## Configuration

### Setting up Credentials
1. Copy `.env.template` to `.env`
2. Edit `.env` with your IMAP credentials:
   - `IMAP_SERVER`: Email server hostname
   - `IMAP_USERNAME`: Email account username  
   - `IMAP_PASSWORD`: Email account password

### Common IMAP Servers
- Gmail: `imap.gmail.com`
- Outlook: `outlook.office365.com`
- iCloud: `imap.mail.me.com`
- Yahoo: `imap.mail.yahoo.com`

### Optional Configuration
Set these in your `.env` file:
- `APPLE_DATA_PATH`: Override default data directory (default: `apple/data`)
- `APPLE_EMAIL_LIMIT`: Limit number of emails to fetch (default: unlimited)

## Troubleshooting

### Common Issues

1. **IMAP Connection Failed**
   - Verify server hostname and port
   - Check username/password
   - Ensure IMAP is enabled in email account

2. **No Emails Found**
   - Check email search patterns in `docs/email_analysis.md`
   - Verify emails exist in the account
   - Try broader date range

3. **Parse Errors**
   - Check `docs/receipt_formats.md` for known formats
   - Review failed receipts in validation report
   - May need to add new format parser

## See Also

- [Product Specification](../dev/specs/2024-11-24-apple-receipt-extraction.md)
- [Email Analysis Results](docs/email_analysis.md)
- [Receipt Format Documentation](docs/receipt_formats.md)