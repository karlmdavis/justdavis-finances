"""
Expected values for modern_format (2025+) Apple receipt samples.

These are real production receipts with expected extraction values.
Used for parameterized integration tests.
"""

from finances.core import FinancialDate, Money

# Sample 1: Subscription renewals
MODERN_SAMPLE_1 = {
    "html_filename": "20251014_130109_Your_receipt_from_Apple._42f10feb-formatted-simple.html",
    "expected": {
        "format_detected": "modern_format",
        "apple_id": "karl_apple@justdavis.com",
        "receipt_date": FinancialDate.from_string("2025-10-11"),
        "order_id": "MSD3B7XL1D",
        "document_number": "776034761448",
        "subtotal": Money.from_cents(2498),  # $24.98
        "tax": Money.from_cents(150),  # $1.50
        "total": Money.from_cents(2648),  # $26.48
        "items": [
            {
                "title": "RISE: Sleep Tracker",
                "cost": Money.from_cents(999),
                "quantity": 1,
                "subscription": True,
            },
            {
                "title": "YNAB",
                "cost": Money.from_cents(1499),
                "quantity": 1,
                "subscription": True,
            },
        ],
    },
}

# TODO: Add 1-2 more samples after first passes
MODERN_SAMPLES = [MODERN_SAMPLE_1]
