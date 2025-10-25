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

# Sample 2: Single subscription renewal
MODERN_SAMPLE_2 = {
    "html_filename": "20250220_222048_Your_receipt_from_Apple._c89212a9-formatted-simple.html",
    "expected": {
        "format_detected": "modern_format",
        "apple_id": "karl_apple@justdavis.com",
        "receipt_date": FinancialDate.from_string("2025-02-20"),
        "order_id": "MSD2L93271",
        "document_number": "209917685917",
        "subtotal": Money.from_cents(3795),  # $37.95
        "tax": Money.from_cents(194),  # $1.94
        "total": Money.from_cents(3989),  # $39.89
        "items": [
            {
                "title": "Premier",
                "cost": Money.from_cents(3795),
                "quantity": 1,
                "subscription": True,
            }
        ],
    },
}

# Sample 3: Multiple subscription renewals
MODERN_SAMPLE_3 = {
    "html_filename": "20250420_203744_Your_receipt_from_Apple._7a465fa0-formatted-simple.html",
    "expected": {
        "format_detected": "modern_format",
        "apple_id": "karl_apple@justdavis.com",
        "receipt_date": FinancialDate.from_string("2025-04-20"),
        "order_id": "MSD2SYNQT0",
        "document_number": "183943648935",
        "subtotal": Money.from_cents(2198),  # $21.98
        "tax": Money.from_cents(132),  # $1.32
        "total": Money.from_cents(2330),  # $23.30
        "items": [
            {
                "title": "YNAB",
                "cost": Money.from_cents(1499),
                "quantity": 1,
                "subscription": True,
            },
            {
                "title": "Geocaching",
                "cost": Money.from_cents(699),
                "quantity": 1,
                "subscription": True,
            },
        ],
    },
}

MODERN_SAMPLES = [MODERN_SAMPLE_1, MODERN_SAMPLE_2, MODERN_SAMPLE_3]
