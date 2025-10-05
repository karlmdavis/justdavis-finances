# Test Data Directory

This directory contains synthetic test data for end-to-end and integration tests.

## Important: PII Protection

**All test data must be synthetic and anonymized.**
Never commit real:
- Account balances or IDs
- Transaction details with personal information
- Email addresses or phone numbers
- Credit card numbers or financial account numbers

## Directory Structure

- `ynab/` - Synthetic YNAB cache files (accounts, categories, transactions)
- `amazon/` - Anonymized Amazon order history CSVs and ZIP files
- `apple/` - Anonymized Apple receipt HTML files

## Data Generation

Test data is generated using `tests/fixtures/synthetic_data.py`.
See that module for details on how to create new synthetic test data.
