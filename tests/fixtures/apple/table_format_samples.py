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
        "apple_id": "test_user@example.com",
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

# Sample 2: Single subscription renewal
TABLE_SAMPLE_2 = {
    "html_filename": "20220302_235709_Your_receipt_from_Apple._910bb4e4-formatted-simple.html",
    "expected": {
        "format_detected": "table_format",
        "apple_id": "test_user@example.com",
        "receipt_date": FinancialDate.from_string("2022-03-01"),
        "order_id": "MSBXTTLGFV",
        "document_number": "190522161022",
        "subtotal": Money.from_cents(1499),  # $14.99
        "tax": Money.from_cents(90),  # $0.90
        "total": Money.from_cents(1589),  # $15.89
        "items": [
            {
                "title": "CARROT Weather",
                "cost": Money.from_cents(1499),
                "quantity": 1,
                "subscription": True,
            }
        ],
    },
}

# Sample 3: Multiple in-app purchases
TABLE_SAMPLE_3 = {
    "html_filename": "20250123_071123_Your_receipt_from_Apple._017670ab-formatted-simple.html",
    "expected": {
        "format_detected": "table_format",
        "apple_id": "test_user2@example.com",
        "receipt_date": FinancialDate.from_string("2025-01-22"),
        "order_id": "MT8XNQNZD6",
        "document_number": "146905477009",
        "subtotal": Money.from_cents(2495),  # $24.95
        "tax": Money.from_cents(150),  # $1.50
        "total": Money.from_cents(2645),  # $26.45
        "items": [
            {
                "title": "Match Factory!",
                "cost": Money.from_cents(199),
                "quantity": 1,
                "subscription": False,
            },
            {
                "title": "Match Factory!",
                "cost": Money.from_cents(699),
                "quantity": 1,
                "subscription": False,
            },
            {
                "title": "Match Factory!",
                "cost": Money.from_cents(699),
                "quantity": 1,
                "subscription": False,
            },
            {
                "title": "Match Factory!",
                "cost": Money.from_cents(199),
                "quantity": 1,
                "subscription": False,
            },
            {
                "title": "Match Factory!",
                "cost": Money.from_cents(699),
                "quantity": 1,
                "subscription": False,
            },
        ],
    },
}

TABLE_SAMPLES = [TABLE_SAMPLE_1, TABLE_SAMPLE_2, TABLE_SAMPLE_3]
