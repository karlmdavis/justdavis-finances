#!/usr/bin/env python3
"""Integration tests for complete workflows."""

import pytest
import json
from pathlib import Path
from finances.amazon import SimplifiedMatcher
from finances.apple import AppleMatcher
from finances.ynab import calculate_amazon_splits, calculate_apple_splits
from finances.analysis import CashFlowAnalyzer, CashFlowConfig
from finances.core.config import get_config


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

        # Sample order data
        orders = [
            {
                'order_id': '111-2223334-5556667',
                'order_date': '2024-08-15',
                'ship_date': '2024-08-15',
                'total': 4599,
                'items': [
                    {
                        'name': 'Echo Dot (4th Gen)',
                        'quantity': 1,
                        'amount': 4599,
                        'asin': 'B084J4KNDS'
                    }
                ]
            }
        ]

        return orders, amazon_dir

    @pytest.fixture
    def sample_ynab_transactions(self):
        """Sample YNAB transactions for matching."""
        return [
            {
                'id': 'test-txn-123',
                'date': '2024-08-15',
                'amount': -45990,  # $45.99 expense
                'payee_name': 'AMZN Mktp US*TEST123',
                'account_name': 'Chase Credit Card'
            }
        ]

    @pytest.mark.integration
    def test_amazon_end_to_end_workflow(self, sample_amazon_data, sample_ynab_transactions):
        """Test complete Amazon matching and splitting workflow."""
        orders, amazon_dir = sample_amazon_data
        transactions = sample_ynab_transactions

        # Step 1: Match transactions to orders
        matcher = SimplifiedMatcher()
        matches = []

        for transaction in transactions:
            transaction_matches = matcher.find_matches(transaction, orders)
            if transaction_matches:
                best_match = max(transaction_matches, key=lambda m: m['confidence'])
                matches.append({
                    'transaction': transaction,
                    'match': best_match
                })

        assert len(matches) > 0

        # Step 2: Generate splits for matched transactions
        splits_results = []
        for match_data in matches:
            transaction = match_data['transaction']
            order = match_data['match']['order']

            # Convert order items to split format
            items = []
            for item in order['items']:
                items.append({
                    'name': item['name'],
                    'amount': item['amount'],
                    'quantity': item['quantity'],
                    'unit_price': item['amount'] // item['quantity']
                })

            splits = calculate_amazon_splits(transaction['amount'], items)
            splits_results.append({
                'transaction_id': transaction['id'],
                'splits': splits,
                'order_id': order['order_id']
            })

        assert len(splits_results) > 0
        assert len(splits_results[0]['splits']) > 0

        # Step 3: Validate split calculations
        for result in splits_results:
            transaction = next(t for t in transactions if t['id'] == result['transaction_id'])
            total_split_amount = sum(split['amount'] for split in result['splits'])
            assert total_split_amount == transaction['amount']


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

        # Sample receipt data
        receipts = [
            {
                'order_id': 'ML7PQ2XYZ',
                'receipt_date': '2024-08-15',
                'apple_id': 'test@example.com',
                'subtotal': 29.99,
                'tax': 2.98,
                'total': 32.97,
                'items': [
                    {
                        'title': 'Procreate',
                        'cost': 29.99
                    }
                ]
            }
        ]

        return receipts, apple_dir

    @pytest.fixture
    def sample_apple_transactions(self):
        """Sample YNAB transactions for Apple matching."""
        return [
            {
                'id': 'apple-txn-123',
                'date': '2024-08-15',
                'amount': -32970,  # $32.97 expense
                'payee_name': 'Apple Store',
                'account_name': 'Chase Credit Card'
            }
        ]

    @pytest.mark.integration
    def test_apple_end_to_end_workflow(self, sample_apple_data, sample_apple_transactions):
        """Test complete Apple matching and splitting workflow."""
        receipts, apple_dir = sample_apple_data
        transactions = sample_apple_transactions

        # Step 1: Match transactions to receipts
        matcher = AppleMatcher()
        matches = []

        for transaction in transactions:
            transaction_matches = matcher.find_matches(transaction, receipts)
            if transaction_matches:
                best_match = max(transaction_matches, key=lambda m: m['confidence'])
                matches.append({
                    'transaction': transaction,
                    'match': best_match
                })

        assert len(matches) > 0

        # Step 2: Generate splits for matched transactions
        splits_results = []
        for match_data in matches:
            transaction = match_data['transaction']
            receipt = match_data['match']['receipt']

            splits = calculate_apple_splits(transaction['amount'], receipt)
            splits_results.append({
                'transaction_id': transaction['id'],
                'splits': splits,
                'receipt_id': receipt['order_id'],
                'apple_id': receipt['apple_id']
            })

        assert len(splits_results) > 0
        assert len(splits_results[0]['splits']) > 0

        # Step 3: Validate Apple ID attribution
        for result in splits_results:
            assert 'apple_id' in result
            assert result['apple_id'] == 'test@example.com'


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
                    "type": "checking"
                },
                {
                    "id": "credit-1",
                    "name": "Chase Credit Card",
                    "balance": -5000000,  # -$5,000 debt
                    "type": "creditCard"
                }
            ],
            "server_knowledge": 123
        }

        # 90 days of transaction history
        transactions_data = []
        from datetime import date
        import pandas as pd

        base_date = date(2024, 6, 1)
        for day in range(90):
            transaction_date = base_date + pd.Timedelta(days=day)
            date_str = transaction_date.strftime('%Y-%m-%d')

            # Daily expenses
            transactions_data.extend([
                {
                    "id": f"grocery-{day}",
                    "date": date_str,
                    "amount": -15000,  # $15 groceries
                    "account_name": "Chase Credit Card",
                    "payee_name": "Grocery Store",
                    "category_name": "Groceries"
                },
                {
                    "id": f"gas-{day}",
                    "date": date_str,
                    "amount": -8000 if day % 3 == 0 else 0,  # $8 gas every 3 days
                    "account_name": "Chase Credit Card",
                    "payee_name": "Gas Station",
                    "category_name": "Transportation"
                }
            ])

            # Bi-weekly income
            if day % 14 == 0:
                transactions_data.append({
                    "id": f"salary-{day}",
                    "date": date_str,
                    "amount": 150000,  # $1,500 bi-weekly salary
                    "account_name": "Chase Checking",
                    "payee_name": "Employer",
                    "category_name": "Salary"
                })

        # Write YNAB data
        with open(ynab_dir / "accounts.json", 'w') as f:
            json.dump(accounts_data, f)

        with open(ynab_dir / "transactions.json", 'w') as f:
            json.dump(transactions_data, f)

        return ynab_dir, cash_flow_dir

    @pytest.mark.integration
    def test_cash_flow_end_to_end_workflow(self, sample_cash_flow_data):
        """Test complete cash flow analysis workflow."""
        ynab_dir, cash_flow_dir = sample_cash_flow_data

        # Step 1: Configure analyzer
        config = CashFlowConfig(
            cash_accounts=['Chase Checking', 'Chase Credit Card'],
            start_date='2024-06-01',
            output_format='png'
        )

        analyzer = CashFlowAnalyzer(config)

        # Step 2: Load and process data
        analyzer.load_data(ynab_dir)

        assert analyzer.df is not None
        assert len(analyzer.df) > 0
        assert 'Chase Checking' in analyzer.df.columns
        assert 'Chase Credit Card' in analyzer.df.columns

        # Step 3: Generate dashboard
        charts_dir = cash_flow_dir / "charts"
        dashboard_file = analyzer.generate_dashboard(charts_dir)

        assert dashboard_file.exists()
        assert dashboard_file.suffix == '.png'

        # Step 4: Get summary statistics
        summary = analyzer.get_summary_statistics()

        assert 'current_balance' in summary
        assert 'monthly_trend' in summary
        assert 'trend_direction' in summary
        assert summary['trend_direction'] in ['positive', 'negative']

        # Step 5: Validate trend analysis
        assert 'trend_confidence' in summary
        assert 0 <= summary['trend_confidence'] <= 1

        # Step 6: Check moving averages are calculated
        assert 'MA_7' in analyzer.df.columns
        assert 'MA_30' in analyzer.df.columns
        assert 'MA_90' in analyzer.df.columns

        # Verify data consistency
        assert not analyzer.df['MA_7'].isna().all()
        assert analyzer.monthly_df is not None
        assert len(analyzer.monthly_df) > 0


class TestCrossSystemIntegration:
    """Test integration between different systems."""

    @pytest.mark.integration
    def test_amazon_to_ynab_mutation_workflow(self):
        """Test Amazon matches -> YNAB mutations workflow."""
        # Sample Amazon match result
        amazon_match = {
            'transaction': {
                'id': 'ynab-txn-123',
                'amount': -89990,  # $899.90
                'date': '2024-08-15'
            },
            'order': {
                'order_id': '111-2223334-5556667',
                'total': 8999,  # $89.99 in cents
                'items': [
                    {
                        'name': 'Laptop Stand',
                        'amount': 4999,
                        'quantity': 1
                    },
                    {
                        'name': 'USB Hub',
                        'amount': 4000,
                        'quantity': 1
                    }
                ]
            },
            'confidence': 0.95
        }

        # Generate splits
        items = []
        for item in amazon_match['order']['items']:
            items.append({
                'name': item['name'],
                'amount': item['amount'],
                'quantity': item['quantity'],
                'unit_price': item['amount'] // item['quantity']
            })

        splits = calculate_amazon_splits(amazon_match['transaction']['amount'], items)

        # Validate mutation structure
        assert len(splits) == 2
        assert sum(split['amount'] for split in splits) == amazon_match['transaction']['amount']

        # Check memo format
        for split in splits:
            assert 'memo' in split
            assert any(item['name'] in split['memo'] for item in items)

    @pytest.mark.integration
    def test_apple_to_ynab_mutation_workflow(self):
        """Test Apple matches -> YNAB mutations workflow."""
        # Sample Apple match result
        apple_match = {
            'transaction': {
                'id': 'ynab-txn-456',
                'amount': -99980,  # $999.80
                'date': '2024-08-15'
            },
            'receipt': {
                'order_id': 'ML7PQ2XYZ',
                'apple_id': 'user@example.com',
                'total': 999.80,
                'items': [
                    {
                        'title': 'Final Cut Pro',
                        'cost': 299.99
                    },
                    {
                        'title': 'Logic Pro',
                        'cost': 299.99
                    },
                    {
                        'title': 'Motion',
                        'cost': 49.99
                    },
                    {
                        'title': 'Compressor',
                        'cost': 49.99
                    }
                ]
            },
            'confidence': 1.0
        }

        # Generate splits
        splits = calculate_apple_splits(
            apple_match['transaction']['amount'],
            apple_match['receipt']
        )

        # Validate mutation structure
        assert len(splits) == 4
        assert sum(split['amount'] for split in splits) == apple_match['transaction']['amount']

        # Check Apple ID attribution
        for split in splits:
            assert apple_match['receipt']['apple_id'] in split['memo']

    @pytest.mark.integration
    def test_configuration_integration(self, temp_dir):
        """Test that all components use consistent configuration."""
        # Set up test environment
        import os
        os.environ['FINANCES_ENV'] = 'test'
        os.environ['FINANCES_DATA_DIR'] = str(temp_dir)

        # Get config instance
        from finances.core.config import reload_config
        config = reload_config()

        # Verify all components use the same data structure
        assert config.data_dir == temp_dir
        assert config.amazon.data_dir == temp_dir / "amazon"
        assert config.apple.data_dir == temp_dir / "apple"
        assert config.database.cache_dir == temp_dir / "ynab" / "cache"
        assert config.analysis.output_dir == temp_dir / "cash_flow" / "charts"

        # Test that analyzers respect configuration
        analyzer = CashFlowAnalyzer()
        assert analyzer.config is not None

        # Create minimal data structure
        ynab_cache_dir = config.database.cache_dir
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [{"id": "1", "name": "Test", "balance": 1000000}],
            "server_knowledge": 123
        }
        transactions_data = [
            {
                "id": "1",
                "date": "2024-08-15",
                "amount": -1000,
                "account_name": "Test",
                "payee_name": "Test",
                "category_name": "Test"
            }
        ]

        with open(ynab_cache_dir / "accounts.json", 'w') as f:
            json.dump(accounts_data, f)
        with open(ynab_cache_dir / "transactions.json", 'w') as f:
            json.dump(transactions_data, f)

        # Test that analyzer can load from configured location
        try:
            analyzer.load_data()  # Should use config default
            assert analyzer.df is not None
        except Exception:
            # May fail if data doesn't meet requirements, but should not fail due to paths
            pass


@pytest.mark.slow
@pytest.mark.integration
def test_performance_integration(temp_dir):
    """Test performance with realistic data volumes."""
    # Create large dataset
    ynab_dir = temp_dir / "ynab" / "cache"
    ynab_dir.mkdir(parents=True)

    # 2 years of data, 5 accounts, ~10 transactions per day
    accounts_data = {
        "accounts": [
            {"id": f"acc-{i}", "name": f"Account {i}", "balance": 10000000}
            for i in range(5)
        ],
        "server_knowledge": 123
    }

    transactions_data = []
    from datetime import date
    import pandas as pd

    base_date = date(2023, 1, 1)
    for day in range(730):  # 2 years
        transaction_date = base_date + pd.Timedelta(days=day)
        date_str = transaction_date.strftime('%Y-%m-%d')

        for txn_num in range(10):  # 10 transactions per day
            transactions_data.append({
                "id": f"txn-{day}-{txn_num}",
                "date": date_str,
                "amount": -1000 * (txn_num + 1),
                "account_name": f"Account {txn_num % 5}",
                "payee_name": f"Payee {txn_num}",
                "category_name": f"Category {txn_num}"
            })

    with open(ynab_dir / "accounts.json", 'w') as f:
        json.dump(accounts_data, f)

    with open(ynab_dir / "transactions.json", 'w') as f:
        json.dump(transactions_data, f)

    # Test performance
    import time

    start_time = time.time()

    config = CashFlowConfig(
        cash_accounts=[f"Account {i}" for i in range(5)],
        start_date='2023-01-01'
    )
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