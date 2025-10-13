#!/usr/bin/env python3
"""Integration tests for complete workflows."""

import json

import pandas as pd
import pytest

from finances.amazon import SimplifiedMatcher
from finances.analysis import CashFlowAnalyzer, CashFlowConfig
from finances.apple import AppleMatcher, normalize_apple_receipt_data
from finances.ynab import calculate_amazon_splits, calculate_apple_splits


class TestAmazonWorkflow:
    """Test complete Amazon transaction matching workflow."""

    @pytest.fixture
    def sample_amazon_data(self, temp_dir):
        """Create sample Amazon data structure."""
        amazon_dir = temp_dir / "amazon"
        raw_dir = amazon_dir / "raw"
        matches_dir = amazon_dir / "transaction_matches"

        raw_dir.mkdir(parents=True)
        matches_dir.mkdir(parents=True)

        # Sample order data - using actual Amazon CSV column names
        orders = [
            {
                "Order ID": "111-2223334-5556667",
                "Order Date": "2024-08-15",
                "Ship Date": "2024-08-15",
                "Total Owed": "$45.99",
                "Title": "Echo Dot (4th Gen)",
                "Quantity": 1,
                "ASIN/ISBN": "B084J4KNDS",
                "Item Subtotal": "$45.99",
                "Item Tax": "$0.00",
            }
        ]

        return orders, amazon_dir

    @pytest.fixture
    def sample_ynab_transactions(self):
        """Sample YNAB transactions for matching."""
        return [
            {
                "id": "test-txn-123",
                "date": "2024-08-15",
                "amount": -45990,  # $45.99 expense
                "payee_name": "AMZN Mktp US*TEST123",
                "account_name": "Chase Credit Card",
            }
        ]

    @pytest.mark.integration
    def test_amazon_end_to_end_workflow(self, sample_amazon_data, sample_ynab_transactions):
        """Test complete Amazon matching and splitting workflow."""
        orders, _amazon_dir = sample_amazon_data
        transactions = sample_ynab_transactions

        # Step 1: Match transactions to orders
        matcher = SimplifiedMatcher()
        matches = []

        # Convert orders to account_data format with proper date handling
        orders_df = pd.DataFrame(orders)
        orders_df["Order Date"] = pd.to_datetime(orders_df["Order Date"])
        orders_df["Ship Date"] = pd.to_datetime(orders_df["Ship Date"])
        account_data = {"test_account": (orders_df, pd.DataFrame())}

        for transaction in transactions:
            result = matcher.match_transaction(transaction, account_data)
            if result["matches"]:
                best_match = result["best_match"]
                matches.append({"transaction": transaction, "match": best_match})

        assert len(matches) > 0

        # Step 2: Generate splits for matched transactions
        splits_results = []
        for match_data in matches:
            transaction = match_data["transaction"]
            amazon_orders = match_data["match"]["amazon_orders"]

            # Convert order items to split format
            items = [
                {
                    "name": item["name"],
                    "amount": item["amount"],
                    "quantity": item["quantity"],
                    "unit_price": item["amount"] // item["quantity"],
                }
                for order in amazon_orders
                for item in order["items"]
            ]

            splits = calculate_amazon_splits(transaction["amount"], items)
            splits_results.append(
                {
                    "transaction_id": transaction["id"],
                    "splits": splits,
                    "order_id": amazon_orders[0]["order_id"] if amazon_orders else None,
                }
            )

        assert len(splits_results) > 0
        assert len(splits_results[0]["splits"]) > 0

        # Step 3: Validate split calculations
        for result in splits_results:
            transaction = next(t for t in transactions if t["id"] == result["transaction_id"])
            total_split_amount = sum(split["amount"] for split in result["splits"])
            assert total_split_amount == transaction["amount"]


class TestAppleWorkflow:
    """Test complete Apple transaction matching workflow."""

    @pytest.fixture
    def sample_apple_data(self, temp_dir):
        """Create sample Apple receipt data."""
        apple_dir = temp_dir / "apple"
        exports_dir = apple_dir / "exports"
        matches_dir = apple_dir / "transaction_matches"

        exports_dir.mkdir(parents=True)
        matches_dir.mkdir(parents=True)

        # Sample receipt data (amounts in cents - parser output format)
        receipts = [
            {
                "order_id": "ML7PQ2XYZ",
                "receipt_date": "Aug 15, 2024",  # Proper Apple date format
                "apple_id": "test@example.com",
                "subtotal": 2999,  # $29.99 → 2999 cents (parser returns int cents)
                "tax": 298,  # $2.98 → 298 cents
                "total": 3297,  # $32.97 → 3297 cents
                "items": [{"title": "Procreate", "cost": 2999}],  # $29.99 → 2999 cents
            }
        ]

        return receipts, apple_dir

    @pytest.fixture
    def sample_apple_transactions(self):
        """Sample YNAB transactions for Apple matching."""
        return [
            {
                "id": "apple-txn-123",
                "date": "2024-08-15",
                "amount": -32970,  # $32.97 expense
                "payee_name": "Apple Store",
                "account_name": "Chase Credit Card",
            }
        ]

    @pytest.mark.integration
    def test_apple_end_to_end_workflow(self, sample_apple_data, sample_apple_transactions):
        """Test complete Apple matching and splitting workflow."""
        receipts, _apple_dir = sample_apple_data
        transactions = sample_apple_transactions

        # Step 1: Match transactions to receipts
        matcher = AppleMatcher()
        matches = []

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(receipts)

        for transaction in transactions:
            result = matcher.match_single_transaction(transaction, receipts_df)
            if result.receipts:  # If match found
                matches.append({"transaction": transaction, "match": result})

        assert len(matches) > 0

        # Step 2: Generate splits for matched transactions
        splits_results = []
        for match_data in matches:
            transaction = match_data["transaction"]
            match_result = match_data["match"]
            # Get the first matched receipt from the MatchResult object
            receipt = match_result.receipts[0] if match_result.receipts else None

            # Convert Receipt object to the format expected by calculate_apple_splits
            if receipt:
                # Transform Apple item format to expected format
                # Note: receipt.items contains raw parser data with float costs in dollars
                # Split calculator expects int prices in cents
                transformed_items = [
                    {
                        "name": item["title"],  # Apple uses 'title'
                        "price": int(item["cost"] * 100),  # Convert dollars to cents
                    }
                    for item in receipt.items
                ]

                splits = calculate_apple_splits(
                    transaction_amount=transaction["amount"],
                    apple_items=transformed_items,
                    receipt_subtotal=receipt.subtotal,
                    receipt_tax=receipt.tax_amount,
                )
                receipt_id = receipt.id
            else:
                splits = []
                receipt_id = None

            splits_results.append(
                {
                    "transaction_id": transaction["id"],
                    "splits": splits,
                    "receipt_id": receipt_id,
                    "apple_id": receipt.customer_id if receipt else None,
                }
            )

        assert len(splits_results) > 0
        assert len(splits_results[0]["splits"]) > 0

        # Step 3: Validate Apple ID attribution
        for result in splits_results:
            assert "apple_id" in result
            assert result["apple_id"] == "test@example.com"


class TestCashFlowWorkflow:
    """Test complete cash flow analysis workflow."""

    @pytest.fixture
    def sample_cash_flow_data(self, temp_dir):
        """Create sample cash flow data."""
        ynab_dir = temp_dir / "ynab" / "cache"
        cash_flow_dir = temp_dir / "cash_flow"

        ynab_dir.mkdir(parents=True)
        cash_flow_dir.mkdir(parents=True)

        # Sample YNAB data for cash flow analysis
        accounts_data = {
            "accounts": [
                {
                    "id": "checking-1",
                    "name": "Chase Checking",
                    "balance": 25000000,  # $25,000
                    "type": "checking",
                },
                {
                    "id": "credit-1",
                    "name": "Chase Credit Card",
                    "balance": -5000000,  # -$5,000 debt
                    "type": "creditCard",
                },
            ],
            "server_knowledge": 123,
        }

        # 90 days of transaction history
        transactions_data = []
        from datetime import date

        import pandas as pd

        base_date = date(2024, 6, 1)
        for day in range(90):
            transaction_date = base_date + pd.Timedelta(days=day)
            date_str = transaction_date.strftime("%Y-%m-%d")

            # Daily expenses
            transactions_data.extend(
                [
                    {
                        "id": f"grocery-{day}",
                        "date": date_str,
                        "amount": -15000,  # $15 groceries
                        "account_name": "Chase Credit Card",
                        "payee_name": "Grocery Store",
                        "category_name": "Groceries",
                    },
                    {
                        "id": f"gas-{day}",
                        "date": date_str,
                        "amount": -8000 if day % 3 == 0 else 0,  # $8 gas every 3 days
                        "account_name": "Chase Credit Card",
                        "payee_name": "Gas Station",
                        "category_name": "Transportation",
                    },
                ]
            )

            # Bi-weekly income
            if day % 14 == 0:
                transactions_data.append(
                    {
                        "id": f"salary-{day}",
                        "date": date_str,
                        "amount": 150000,  # $1,500 bi-weekly salary
                        "account_name": "Chase Checking",
                        "payee_name": "Employer",
                        "category_name": "Salary",
                    }
                )

        # Write YNAB data
        with open(ynab_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        return ynab_dir, cash_flow_dir

    @pytest.mark.integration
    def test_cash_flow_end_to_end_workflow(self, sample_cash_flow_data):
        """Test complete cash flow analysis workflow."""
        ynab_dir, cash_flow_dir = sample_cash_flow_data

        # Step 1: Configure analyzer
        config = CashFlowConfig(
            cash_accounts=["Chase Checking", "Chase Credit Card"],
            start_date="2024-06-01",
            output_format="png",
        )

        analyzer = CashFlowAnalyzer(config)

        # Step 2: Load and process data
        analyzer.load_data(ynab_dir)

        assert analyzer.df is not None
        assert len(analyzer.df) > 0
        assert "Chase Checking" in analyzer.df.columns
        assert "Chase Credit Card" in analyzer.df.columns

        # Step 3: Generate dashboard
        charts_dir = cash_flow_dir / "charts"
        dashboard_file = analyzer.generate_dashboard(charts_dir)

        assert dashboard_file.exists()
        assert dashboard_file.suffix == ".png"

        # Step 4: Get summary statistics
        summary = analyzer.get_summary_statistics()

        assert "current_balance" in summary
        assert "monthly_trend" in summary
        assert "trend_direction" in summary
        assert summary["trend_direction"] in ["positive", "negative"]

        # Step 5: Validate trend analysis
        assert "trend_confidence" in summary
        assert 0 <= summary["trend_confidence"] <= 1

        # Step 6: Check moving averages are calculated
        assert "MA_7" in analyzer.df.columns
        assert "MA_30" in analyzer.df.columns
        assert "MA_90" in analyzer.df.columns

        # Verify data consistency
        assert not analyzer.df["MA_7"].isna().all()
        assert analyzer.monthly_df is not None
        assert len(analyzer.monthly_df) > 0


class TestCrossSystemIntegration:
    """Test integration between different systems."""

    @pytest.mark.integration
    def test_amazon_to_ynab_edit_workflow(self):
        """Test Amazon matches -> YNAB edits workflow."""
        # Sample Amazon match result
        amazon_match = {
            "transaction": {"id": "ynab-txn-123", "amount": -89990, "date": "2024-08-15"},  # $899.90
            "order": {
                "order_id": "111-2223334-5556667",
                "total": 8999,  # $89.99 in cents
                "items": [
                    {"name": "Laptop Stand", "amount": 4999, "quantity": 1},
                    {"name": "USB Hub", "amount": 4000, "quantity": 1},
                ],
            },
            "confidence": 0.95,
        }

        # Generate splits
        items = [
            {
                "name": item["name"],
                "amount": item["amount"],
                "quantity": item["quantity"],
                "unit_price": item["amount"] // item["quantity"],
            }
            for item in amazon_match["order"]["items"]
        ]

        splits = calculate_amazon_splits(amazon_match["transaction"]["amount"], items)

        # Validate edit structure
        assert len(splits) == 2
        assert sum(split["amount"] for split in splits) == amazon_match["transaction"]["amount"]

        # Check memo format
        for split in splits:
            assert "memo" in split
            assert any(item["name"] in split["memo"] for item in items)

    @pytest.mark.integration
    def test_apple_to_ynab_edit_workflow(self):
        """Test Apple matches -> YNAB edits workflow."""
        # Sample Apple match result
        apple_match = {
            "transaction": {
                "id": "ynab-txn-456",
                "amount": -699960,  # $699.96 (299.99+299.99+49.99+49.99)
                "date": "2024-08-15",
            },
            "receipt": {
                "order_id": "ML7PQ2XYZ",
                "apple_id": "user@example.com",
                "total": 69996,  # $699.96 in cents
                "items": [
                    {"title": "Final Cut Pro", "cost": 29999},  # $299.99 in cents
                    {"title": "Logic Pro", "cost": 29999},  # $299.99 in cents
                    {"title": "Motion", "cost": 4999},  # $49.99 in cents
                    {"title": "Compressor", "cost": 4999},  # $49.99 in cents
                ],
            },
            "confidence": 1.0,
        }

        # Generate splits
        # Transform Apple item format to expected format
        transformed_items = [
            {"name": item["title"], "price": item["cost"]}  # Apple uses 'title' and 'cost'
            for item in apple_match["receipt"]["items"]
        ]

        splits = calculate_apple_splits(
            apple_match["transaction"]["amount"],
            transformed_items,
            receipt_subtotal=apple_match["receipt"]["total"],
        )

        # Validate edit structure
        assert len(splits) == 4
        assert sum(split["amount"] for split in splits) == apple_match["transaction"]["amount"]

        # Check that splits have the expected item names as memos
        expected_titles = ["Final Cut Pro", "Logic Pro", "Motion", "Compressor"]
        actual_memos = [split["memo"] for split in splits]
        for title in expected_titles:
            assert title in actual_memos

    @pytest.mark.integration
    def test_configuration_integration(self, temp_dir):
        """Test that all components use consistent configuration."""
        # Set up test environment
        import os

        os.environ["FINANCES_ENV"] = "test"
        os.environ["FINANCES_DATA_DIR"] = str(temp_dir)

        # Get config instance
        from finances.core.config import reload_config

        config = reload_config()

        # Verify all components use the same data structure
        assert config.data_dir == temp_dir
        assert config.amazon.data_dir == temp_dir / "amazon"
        assert config.apple.data_dir == temp_dir / "apple"
        assert config.database.cache_dir == temp_dir / "ynab" / "cache"
        assert config.analysis.output_dir == temp_dir / "cash_flow" / "charts"

        # Create minimal data structure
        ynab_cache_dir = config.database.cache_dir
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [{"id": "1", "name": "Test", "balance": 1000000}],
            "server_knowledge": 123,
        }
        transactions_data = [
            {
                "id": "1",
                "date": "2024-08-15",
                "amount": -1000,
                "account_name": "Test",
                "payee_name": "Test",
                "category_name": "Test",
            }
        ]

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)
        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        # Test that analyzers respect configuration
        # Create analyzer with custom config that includes test account
        from finances.analysis.cash_flow import CashFlowConfig

        test_config = CashFlowConfig(cash_accounts=["Test"], start_date="2024-05-01")
        analyzer = CashFlowAnalyzer(config=test_config)
        assert analyzer.config is not None

        # Test that analyzer can load from configured location
        # Note: This may fail if data doesn't meet minimum requirements, which is acceptable
        # The test verifies configuration paths are correct
        analyzer.load_data()  # Should use config default
        assert analyzer.df is not None


@pytest.mark.slow
@pytest.mark.integration
def test_performance_integration(temp_dir):
    """Test performance with realistic data volumes."""
    # Create large dataset
    ynab_dir = temp_dir / "ynab" / "cache"
    ynab_dir.mkdir(parents=True)

    # 2 years of data, 5 accounts, ~10 transactions per day
    accounts_data = {
        "accounts": [{"id": f"acc-{i}", "name": f"Account {i}", "balance": 10000000} for i in range(5)],
        "server_knowledge": 123,
    }

    from datetime import date

    import pandas as pd

    base_date = date(2023, 1, 1)
    transactions_data = [
        {
            "id": f"txn-{day}-{txn_num}",
            "date": (base_date + pd.Timedelta(days=day)).strftime("%Y-%m-%d"),
            "amount": -1000 * (txn_num + 1),
            "account_name": f"Account {txn_num % 5}",
            "payee_name": f"Payee {txn_num}",
            "category_name": f"Category {txn_num}",
        }
        for day in range(730)  # 2 years
        for txn_num in range(10)  # 10 transactions per day
    ]

    with open(ynab_dir / "accounts.json", "w") as f:
        json.dump(accounts_data, f, indent=2)

    with open(ynab_dir / "transactions.json", "w") as f:
        json.dump(transactions_data, f, indent=2)

    # Test performance
    import time

    start_time = time.time()

    config = CashFlowConfig(cash_accounts=[f"Account {i}" for i in range(5)], start_date="2023-01-01")
    analyzer = CashFlowAnalyzer(config)
    analyzer.load_data(ynab_dir)

    load_time = time.time() - start_time

    # Generate dashboard
    dashboard_start = time.time()
    dashboard_file = analyzer.generate_dashboard(temp_dir / "charts")
    dashboard_time = time.time() - dashboard_start

    total_time = time.time() - start_time

    # Performance assertions
    assert load_time < 30.0  # Should load 7,300 transactions in under 30 seconds
    assert dashboard_time < 15.0  # Should generate dashboard in under 15 seconds
    assert total_time < 45.0  # Total workflow under 45 seconds

    # Verify results
    assert dashboard_file.exists()
    assert len(analyzer.df) == 730  # One row per day
    assert len(transactions_data) == 7300  # Verify test data size
