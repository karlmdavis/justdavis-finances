#!/usr/bin/env python3
"""
Synthetic Test Data Generators

Generates completely synthetic, anonymized test data for E2E and integration tests.
Ensures no PII (Personally Identifiable Information) is included in test data.

All amounts, dates, IDs, names, and other identifiers are synthetic.

Note: Uses standard random module for test data generation (not cryptographic use).
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from finances.core.currency import cents_to_dollars_str

# Synthetic names and categories
SYNTHETIC_PAYEES = [
    "Generic Grocery Store",
    "Test Gas Station",
    "Sample Coffee Shop",
    "Mock Restaurant",
    "Example Pharmacy",
    "Demo Hardware Store",
    "Test Online Retailer",
]

SYNTHETIC_CATEGORIES = [
    "Groceries",
    "Transportation",
    "Dining Out",
    "Healthcare",
    "Home Improvement",
    "Shopping",
    "Entertainment",
]

SYNTHETIC_AMAZON_ITEMS = [
    "Wireless Mouse",
    "USB Cable",
    "Phone Case",
    "Book: Example Title",
    "Kitchen Gadget",
    "Office Supplies",
    "Electronics Accessory",
]

SYNTHETIC_APPLE_ITEMS = [
    "Test App Pro",
    "Example Game",
    "Sample Subscription",
    "Demo Music Album",
    "Mock Photo Editor",
]


def generate_synthetic_ynab_cache(
    num_accounts: int = 3,
    num_transactions: int = 100,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Generate synthetic YNAB cache data.

    Args:
        num_accounts: Number of accounts to generate
        num_transactions: Number of transactions to generate
        start_date: Start date for transactions (default: 90 days ago)
        end_date: End date for transactions (default: today)

    Returns:
        Dictionary with 'accounts', 'categories', and 'transactions'
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=90)
    if end_date is None:
        end_date = date.today()

    # Generate accounts
    accounts = [
        {
            "id": f"account-{i:03d}",
            "name": f"Test Account {i}",
            "type": random.choice(["checking", "savings", "creditCard"]),
            "balance": random.randint(100000, 5000000),  # $1,000 - $50,000 in milliunits
            "cleared_balance": random.randint(100000, 5000000),
            "uncleared_balance": 0,
            "closed": False,
            "on_budget": True,
        }
        for i in range(1, num_accounts + 1)
    ]

    # Generate categories
    category_groups = [
        {
            "id": f"group-{i:03d}",
            "name": f"Test Group {i}",
            "hidden": False,
            "categories": [
                {
                    "id": f"category-{i:03d}-{j:02d}",
                    "name": category,
                    "hidden": False,
                    "budgeted": random.randint(50000, 500000),
                    "activity": random.randint(-500000, -50000),
                    "balance": random.randint(0, 100000),
                }
                for j, category in enumerate(SYNTHETIC_CATEGORIES, 1)
            ],
        }
        for i in range(1, 3)
    ]

    # Generate transactions
    transactions = []
    days_range = (end_date - start_date).days

    for i in range(num_transactions):
        # Random date within range
        random_days = random.randint(0, days_range)
        transaction_date = start_date + timedelta(days=random_days)

        account = random.choice(accounts)
        category = random.choice(category_groups[0]["categories"])
        payee = random.choice(SYNTHETIC_PAYEES)

        # Random transaction amount (negative for expenses)
        amount = random.randint(-50000, -1000)  # -$500 to -$10 in milliunits

        transactions.append(
            {
                "id": f"transaction-{i:05d}",
                "date": transaction_date.strftime("%Y-%m-%d"),
                "amount": amount,
                "account_id": account["id"],
                "account_name": account["name"],
                "payee_name": payee,
                "category_id": category["id"],
                "category_name": category["name"],
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            }
        )

    return {
        "accounts": {"accounts": accounts, "server_knowledge": 12345},
        "categories": {"category_groups": category_groups, "server_knowledge": 67890},
        "transactions": transactions,
    }


def generate_synthetic_amazon_orders(num_orders: int = 10) -> list[dict[str, Any]]:
    """
    Generate synthetic Amazon order data in CSV format.

    Args:
        num_orders: Number of orders to generate

    Returns:
        List of order dictionaries (one per item)
    """
    orders = []
    base_date = date.today() - timedelta(days=30)

    for _ in range(num_orders):
        order_date = base_date + timedelta(days=random.randint(0, 30))
        ship_date = order_date + timedelta(days=random.randint(1, 3))
        order_id = f"{random.randint(100, 999)}-{random.randint(1000000, 9999999)}-{random.randint(1000000, 9999999)}"

        # Generate 1-3 items per order (prices in cents for integer arithmetic)
        num_items = random.randint(1, 3)
        item_prices_cents = [random.randint(500, 10000) for _ in range(num_items)]
        total_cents = sum(item_prices_cents)

        for j, (item, price_cents) in enumerate(
            zip(random.sample(SYNTHETIC_AMAZON_ITEMS, num_items), item_prices_cents, strict=False)
        ):
            tax_cents = price_cents * 8 // 100  # 8% tax using integer arithmetic
            orders.append(
                {
                    "Order ID": order_id,
                    "Order Date": order_date.strftime("%m/%d/%Y"),
                    "Ship Date": ship_date.strftime("%m/%d/%Y"),
                    "Total Owed": f"${cents_to_dollars_str(total_cents)}" if j == 0 else "",
                    "Title": item,
                    "Quantity": 1,
                    "ASIN/ISBN": f"B0{random.randint(10000000, 99999999)}",
                    "Item Subtotal": f"${cents_to_dollars_str(price_cents)}",
                    "Item Tax": f"${cents_to_dollars_str(tax_cents)}",
                }
            )

    return orders


def generate_synthetic_apple_receipt_html(
    receipt_id: str = "ML7PQ2XYZ",
    customer_id: str = "test@example.com",
    items: list[dict[str, Any]] | None = None,
) -> str:
    """
    Generate synthetic Apple receipt HTML.

    Args:
        receipt_id: Receipt order ID
        customer_id: Apple ID (email)
        items: List of items with 'title' and 'price' (in cents)

    Returns:
        HTML string of synthetic Apple receipt
    """
    if items is None:
        items = [
            {"title": random.choice(SYNTHETIC_APPLE_ITEMS), "price": random.randint(99, 9999)}
            for _ in range(2)
        ]

    subtotal = sum(item["price"] for item in items)
    tax = int(subtotal * 0.08)
    total = subtotal + tax

    receipt_date = (date.today() - timedelta(days=random.randint(1, 30))).strftime("%b %d, %Y")

    items_html = "\n".join(
        [
            f"""
        <tr>
            <td class="item-title">{item['title']}</td>
            <td class="item-price">${cents_to_dollars_str(item['price'])}</td>
        </tr>
        """
            for item in items
        ]
    )

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Apple Receipt - Order {receipt_id}</title>
</head>
<body>
    <div class="receipt">
        <h1>Receipt from Apple</h1>
        <p class="order-id">Order ID: {receipt_id}</p>
        <p class="date">Date: {receipt_date}</p>
        <p class="customer">Bill To: {customer_id}</p>

        <table class="items">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Price</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>

        <table class="totals">
            <tr>
                <td>Subtotal:</td>
                <td>${cents_to_dollars_str(subtotal)}</td>
            </tr>
            <tr>
                <td>Tax:</td>
                <td>${cents_to_dollars_str(tax)}</td>
            </tr>
            <tr class="total">
                <td>Total:</td>
                <td>${cents_to_dollars_str(total)}</td>
            </tr>
        </table>
    </div>
</body>
</html>
"""
    return html.strip()


def save_synthetic_ynab_data(output_dir: Path) -> None:
    """
    Generate and save synthetic YNAB cache files.

    Args:
        output_dir: Directory to save files (typically tests/test_data/ynab)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    data = generate_synthetic_ynab_cache()

    with open(output_dir / "accounts.json", "w") as f:
        json.dump(data["accounts"], f, indent=2)

    with open(output_dir / "categories.json", "w") as f:
        json.dump(data["categories"], f, indent=2)

    with open(output_dir / "transactions.json", "w") as f:
        json.dump(data["transactions"], f, indent=2)


def save_synthetic_amazon_data(output_dir: Path) -> None:
    """
    Generate and save synthetic Amazon order CSV.

    Args:
        output_dir: Directory to save files (typically tests/test_data/amazon)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    orders = generate_synthetic_amazon_orders()

    # Write CSV
    import csv

    csv_file = output_dir / "sample_orders.csv"
    if orders:
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=orders[0].keys())
            writer.writeheader()
            writer.writerows(orders)


def save_synthetic_apple_receipt(output_dir: Path) -> None:
    """
    Generate and save synthetic Apple receipt HTML.

    Args:
        output_dir: Directory to save files (typically tests/test_data/apple)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    html = generate_synthetic_apple_receipt_html()

    with open(output_dir / "sample_receipt.html", "w") as f:
        f.write(html)


if __name__ == "__main__":
    # Generate all synthetic test data
    base_dir = Path(__file__).parent.parent / "test_data"

    save_synthetic_ynab_data(base_dir / "ynab")
    save_synthetic_amazon_data(base_dir / "amazon")
    save_synthetic_apple_receipt(base_dir / "apple")

    print(f"✅ Synthetic test data generated in {base_dir}")
