"""
YNAB Transaction Updater

Automates the application of Amazon and Apple transaction matching results to YNAB transactions.
Splits consolidated transactions into detailed subtransactions with item-level memos.

Key Features:
- Three-phase safety approach (generate → review → apply)
- Integer arithmetic to avoid floating-point errors
- Complete audit trail for reversibility
- Works with cached YNAB data only
"""