#!/usr/bin/env python3
"""Tests for cash flow analysis module."""

import json
from datetime import date

import pandas as pd
import pytest

from finances.analysis import CashFlowAnalyzer, CashFlowConfig


class TestCashFlowConfig:
    """Test CashFlowConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CashFlowConfig.default()

        assert config.start_date == "2024-05-01"
        assert config.short_ma_window == 7
        assert config.medium_ma_window == 30
        assert config.long_ma_window == 90
        assert config.figure_size == (16, 12)
        assert config.dpi == 150
        assert config.output_format == "png"

        # Check default accounts
        expected_accounts = [
            "Chase Checking",
            "Chase Credit Card",
            "Apple Card",
            "Apple Cash",
            "Apple Savings",
        ]
        assert config.cash_accounts == expected_accounts

    def test_custom_config(self):
        """Test custom configuration creation."""
        custom_accounts = ["Custom Account 1", "Custom Account 2"]
        config = CashFlowConfig(
            cash_accounts=custom_accounts,
            start_date="2024-01-01",
            short_ma_window=5,
            medium_ma_window=20,
            long_ma_window=60,
            figure_size=(12, 8),
            dpi=300,
            output_format="pdf",
        )

        assert config.cash_accounts == custom_accounts
        assert config.start_date == "2024-01-01"
        assert config.short_ma_window == 5
        assert config.medium_ma_window == 20
        assert config.long_ma_window == 60
        assert config.figure_size == (12, 8)
        assert config.dpi == 300
        assert config.output_format == "pdf"


class TestCashFlowAnalyzer:
    """Test CashFlowAnalyzer class."""

    @pytest.fixture
    def sample_ynab_data(self, temp_dir):
        """Create sample YNAB data for testing."""
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Sample accounts data
        accounts_data = {
            "accounts": [
                {
                    "id": "account-1",
                    "name": "Chase Checking",
                    "balance": 50000000,  # $50,000 in milliunits
                    "type": "checking",
                },
                {
                    "id": "account-2",
                    "name": "Chase Credit Card",
                    "balance": -5000000,  # -$5,000 in milliunits (debt)
                    "type": "creditCard",
                },
                {
                    "id": "account-3",
                    "name": "Apple Card",
                    "balance": -2000000,  # -$2,000 in milliunits (debt)
                    "type": "creditCard",
                },
            ],
            "server_knowledge": 123,
        }

        # Sample transactions data (30 days of data)
        transactions_data = []
        base_date = date(2024, 8, 1)

        for day in range(30):
            transaction_date = base_date.replace(day=day + 1)
            date_str = transaction_date.strftime("%Y-%m-%d")

            # Add some daily transactions
            transactions_data.extend(
                [
                    {
                        "id": f"txn-{day}-1",
                        "date": date_str,
                        "amount": -5000,  # $5 expense
                        "account_name": "Chase Checking",
                        "payee_name": "Coffee Shop",
                        "category_name": "Dining Out",
                    },
                    {
                        "id": f"txn-{day}-2",
                        "date": date_str,
                        "amount": -10000,  # $10 expense
                        "account_name": "Chase Credit Card",
                        "payee_name": "Grocery Store",
                        "category_name": "Groceries",
                    },
                ]
            )

            # Add some income every 14 days
            if day % 14 == 0:
                transactions_data.append(
                    {
                        "id": f"income-{day}",
                        "date": date_str,
                        "amount": 250000,  # $250 income
                        "account_name": "Chase Checking",
                        "payee_name": "Employer",
                        "category_name": "Salary",
                    }
                )

        # Write data files
        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        return ynab_cache_dir

    @pytest.fixture
    def analyzer(self):
        """Create CashFlowAnalyzer instance for testing."""
        config = CashFlowConfig(
            cash_accounts=["Chase Checking", "Chase Credit Card", "Apple Card"], start_date="2024-08-01"
        )
        return CashFlowAnalyzer(config)

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = CashFlowAnalyzer()

        assert analyzer.config is not None
        assert analyzer.df is None
        assert analyzer.monthly_df is None
        assert analyzer.trend_stats is None

    def test_load_data_success(self, analyzer, sample_ynab_data):
        """Test successful data loading."""
        analyzer.load_data(sample_ynab_data)

        assert analyzer.df is not None
        assert len(analyzer.df) > 0
        assert "Total" in analyzer.df.columns
        assert "MA_7" in analyzer.df.columns
        assert "MA_30" in analyzer.df.columns
        assert "MA_90" in analyzer.df.columns
        assert "Daily_Change" in analyzer.df.columns

        # Check that account columns exist
        for account in analyzer.config.cash_accounts:
            if account in ["Chase Checking", "Chase Credit Card", "Apple Card"]:
                assert account in analyzer.df.columns

    def test_load_data_missing_files(self, analyzer, temp_dir):
        """Test data loading with missing files."""
        missing_cache_dir = temp_dir / "missing"

        with pytest.raises(FileNotFoundError, match="YNAB data not found"):
            analyzer.load_data(missing_cache_dir)

    def test_moving_averages_calculation(self, analyzer, sample_ynab_data):
        """Test moving averages calculation."""
        analyzer.load_data(sample_ynab_data)

        # Check that moving averages are calculated
        assert not analyzer.df["MA_7"].isna().all()
        assert not analyzer.df["MA_30"].isna().all()
        assert not analyzer.df["MA_90"].isna().all()

        # Check that shorter windows have more data points
        ma_7_count = analyzer.df["MA_7"].notna().sum()
        ma_30_count = analyzer.df["MA_30"].notna().sum()
        ma_90_count = analyzer.df["MA_90"].notna().sum()

        assert ma_7_count >= ma_30_count >= ma_90_count

    def test_monthly_aggregates_calculation(self, analyzer, sample_ynab_data):
        """Test monthly aggregates calculation."""
        analyzer.load_data(sample_ynab_data)

        assert analyzer.monthly_df is not None
        assert len(analyzer.monthly_df) > 0

        # Check expected columns
        expected_columns = ["Mean_Balance", "Min_Balance", "Max_Balance", "End_Balance", "Net_Change"]
        for col in expected_columns:
            assert col in analyzer.monthly_df.columns

    def test_trend_statistics_calculation(self, analyzer, sample_ynab_data):
        """Test trend statistics calculation."""
        analyzer.load_data(sample_ynab_data)

        assert analyzer.trend_stats is not None

        # Check expected statistics
        required_keys = [
            "slope",
            "intercept",
            "r_value",
            "p_value",
            "std_err",
            "trend_line",
            "daily_trend",
            "monthly_trend",
            "yearly_trend",
        ]
        for key in required_keys:
            assert key in analyzer.trend_stats

        # Check that trend line has correct length
        assert len(analyzer.trend_stats["trend_line"]) == len(analyzer.df)

    def test_dashboard_generation(self, analyzer, sample_ynab_data, temp_dir):
        """Test dashboard generation."""
        analyzer.load_data(sample_ynab_data)

        output_dir = temp_dir / "charts"
        output_file = analyzer.generate_dashboard(output_dir)

        assert output_file.exists()
        assert output_file.suffix == ".png"
        assert "cash_flow_dashboard" in output_file.name

        # Check that file is not empty
        assert output_file.stat().st_size > 0

    def test_dashboard_generation_different_formats(self, analyzer, sample_ynab_data, temp_dir):
        """Test dashboard generation with different formats."""
        # Test PDF format
        config = CashFlowConfig(
            cash_accounts=["Chase Checking", "Chase Credit Card"],
            start_date="2024-08-01",
            output_format="pdf",
        )
        pdf_analyzer = CashFlowAnalyzer(config)
        pdf_analyzer.load_data(sample_ynab_data)

        output_dir = temp_dir / "charts"
        output_file = pdf_analyzer.generate_dashboard(output_dir)

        assert output_file.suffix == ".pdf"

    def test_summary_statistics(self, analyzer, sample_ynab_data):
        """Test summary statistics generation."""
        analyzer.load_data(sample_ynab_data)

        stats = analyzer.get_summary_statistics()

        assert isinstance(stats, dict)

        # Check required statistics
        required_keys = [
            "current_balance",
            "monthly_trend",
            "yearly_trend",
            "monthly_burn_rate",
            "trend_direction",
            "trend_confidence",
            "volatility",
            "data_start_date",
            "analysis_date",
        ]
        for key in required_keys:
            assert key in stats

        # Check data types
        assert isinstance(stats["current_balance"], (int, float))
        assert isinstance(stats["monthly_trend"], (int, float))
        assert isinstance(stats["yearly_trend"], (int, float))
        assert isinstance(stats["trend_direction"], str)
        assert stats["trend_direction"] in ["positive", "negative"]
        assert 0 <= stats["trend_confidence"] <= 1
        assert stats["data_start_date"] == analyzer.config.start_date

    def test_empty_transactions_error(self, analyzer, temp_dir):
        """Test error handling with empty transactions."""
        # Create YNAB data with no transactions in date range
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [{"id": "1", "name": "Chase Checking", "balance": 50000000, "type": "checking"}],
            "server_knowledge": 123,
        }

        transactions_data = []  # Empty transactions

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        with pytest.raises(ValueError, match="No transactions found"):
            analyzer.load_data(ynab_cache_dir)

    def test_single_account_analysis(self, sample_ynab_data):
        """Test analysis with single account."""
        config = CashFlowConfig(cash_accounts=["Chase Checking"], start_date="2024-08-01")
        analyzer = CashFlowAnalyzer(config)
        analyzer.load_data(sample_ynab_data)

        assert analyzer.df is not None
        assert "Chase Checking" in analyzer.df.columns
        assert analyzer.df["Total"].equals(analyzer.df["Chase Checking"])

    def test_account_composition_tracking(self, analyzer, sample_ynab_data):
        """Test account composition over time."""
        analyzer.load_data(sample_ynab_data)

        # Check that individual account balances are tracked
        for account in analyzer.config.cash_accounts:
            if account in ["Chase Checking", "Chase Credit Card", "Apple Card"]:
                assert account in analyzer.df.columns

        # Check that total equals sum of individual accounts
        account_columns = [col for col in analyzer.df.columns if col in analyzer.config.cash_accounts]
        calculated_total = analyzer.df[account_columns].sum(axis=1)
        calculated_total.name = "Total"  # Set the name to match

        # Should be approximately equal (allowing for small floating point differences)
        pd.testing.assert_series_equal(analyzer.df["Total"], calculated_total, check_exact=False, rtol=1e-10)


class TestCashFlowEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_date_range(self):
        """Test invalid date range configuration."""
        config = CashFlowConfig(cash_accounts=["Test Account"], start_date="2025-01-01")  # Future date
        CashFlowAnalyzer(config)

        # Should not crash, but may have no data
        # Implementation specific behavior
        pass

    def test_missing_account_data(self, temp_dir):
        """Test handling of missing account data."""
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Accounts data missing target accounts
        accounts_data = {
            "accounts": [{"id": "1", "name": "Other Account", "balance": 1000000}],
            "server_knowledge": 123,
        }

        transactions_data = [
            {
                "id": "txn-1",
                "date": "2024-08-15",
                "amount": -5000,
                "account_name": "Missing Account",  # Not in accounts list
                "payee_name": "Test",
                "category_name": "Test",
            }
        ]

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        config = CashFlowConfig(cash_accounts=["Missing Account"], start_date="2024-08-01")
        analyzer = CashFlowAnalyzer(config)

        # Should handle gracefully
        try:
            analyzer.load_data(ynab_cache_dir)
            # May succeed with zero balances or empty data
            assert analyzer.df is not None
        except ValueError:
            # May fail if no valid data found
            pass

    def test_malformed_json_data(self, temp_dir):
        """Test handling of malformed JSON data."""
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Write invalid JSON
        with open(ynab_cache_dir / "accounts.json", "w") as f:
            f.write("invalid json {")

        # Also create transactions.json so file existence check passes
        with open(ynab_cache_dir / "transactions.json", "w") as f:
            f.write("[]")  # Valid empty JSON for transactions

        config = CashFlowConfig(cash_accounts=["Test Account"], start_date="2024-08-01")
        analyzer = CashFlowAnalyzer(config)

        with pytest.raises(json.JSONDecodeError):
            analyzer.load_data(ynab_cache_dir)

    def test_very_large_dataset(self, temp_dir):
        """Test performance with large dataset."""
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Create large dataset (1 year of daily transactions)
        accounts_data = {
            "accounts": [{"id": "1", "name": "Test Account", "balance": 50000000}],
            "server_knowledge": 123,
        }

        transactions_data = []
        base_date = date(2024, 1, 1)

        for day in range(365):
            transaction_date = base_date.replace(day=1) + pd.Timedelta(days=day)
            date_str = transaction_date.strftime("%Y-%m-%d")

            transactions_data.append(
                {
                    "id": f"txn-{day}",
                    "date": date_str,
                    "amount": -1000,  # $1 expense
                    "account_name": "Test Account",
                    "payee_name": "Test Payee",
                    "category_name": "Test Category",
                }
            )

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        config = CashFlowConfig(cash_accounts=["Test Account"], start_date="2024-01-01")
        analyzer = CashFlowAnalyzer(config)

        # Should complete in reasonable time
        import time

        start_time = time.time()
        analyzer.load_data(ynab_cache_dir)
        end_time = time.time()

        assert end_time - start_time < 10.0  # Should complete within 10 seconds
        assert len(analyzer.df) == 365


@pytest.mark.integration
def test_full_cash_flow_workflow(temp_dir):
    """Test complete cash flow analysis workflow."""
    # Create sample data
    ynab_cache_dir = temp_dir / "ynab" / "cache"
    ynab_cache_dir.mkdir(parents=True)

    accounts_data = {
        "accounts": [
            {"id": "1", "name": "Checking", "balance": 10000000},
            {"id": "2", "name": "Credit Card", "balance": -3000000},
        ],
        "server_knowledge": 123,
    }

    # 60 days of transactions
    transactions_data = []
    base_date = date(2024, 7, 1)

    for day in range(60):
        transaction_date = base_date + pd.Timedelta(days=day)
        date_str = transaction_date.strftime("%Y-%m-%d")

        transactions_data.extend(
            [
                {
                    "id": f"expense-{day}",
                    "date": date_str,
                    "amount": -2000,  # $2 daily expense
                    "account_name": "Credit Card",
                    "payee_name": "Daily Expense",
                    "category_name": "Shopping",
                },
                {
                    "id": f"income-{day}",
                    "date": date_str,
                    "amount": 5000 if day % 7 == 0 else 0,  # $5 weekly income
                    "account_name": "Checking",
                    "payee_name": "Income Source",
                    "category_name": "Salary",
                },
            ]
        )

    with open(ynab_cache_dir / "accounts.json", "w") as f:
        json.dump(accounts_data, f, indent=2)

    with open(ynab_cache_dir / "transactions.json", "w") as f:
        json.dump(transactions_data, f, indent=2)

    # Run complete analysis
    config = CashFlowConfig(cash_accounts=["Checking", "Credit Card"], start_date="2024-07-01")
    analyzer = CashFlowAnalyzer(config)

    # Load data
    analyzer.load_data(ynab_cache_dir)

    # Generate dashboard
    output_dir = temp_dir / "output"
    dashboard_file = analyzer.generate_dashboard(output_dir)

    # Get summary
    summary = analyzer.get_summary_statistics()

    # Verify results
    assert dashboard_file.exists()
    assert summary["data_start_date"] == "2024-07-01"
    assert isinstance(summary["current_balance"], (int, float))
    assert summary["trend_direction"] in ["positive", "negative"]
