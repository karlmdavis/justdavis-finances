"""
Expected values for table_format (2020-era) Apple receipt samples.

These are real production receipts with expected extraction values.
Used for parameterized integration tests.
"""

from finances.core import FinancialDate, Money

# Sample 1: Single app purchase
TABLE_SAMPLE_1 = {
    "html_filename": "20201024_084743_Your_receipt_from_Apple._d6f911bd-formatted-simple.html",
    "expected": {
        "format_detected": "table_format",
        "apple_id": "karl_apple@justdavis.com",
        "receipt_date": FinancialDate.from_string("2020-10-23"),
        "order_id": "MSBQLG265J",
        "document_number": "114382498203",
        "subtotal": None,  # Not shown separately for single-item
        "tax": None,  # Not shown separately
        "total": Money.from_cents(999),  # $9.99
        "items": [
            {
                "title": "Slay the Spire",
                "cost": Money.from_cents(999),
                "quantity": 1,
                "subscription": False,
            }
        ],
    },
}

# TODO: Add 1-2 more samples after first passes
TABLE_SAMPLES = [TABLE_SAMPLE_1]
