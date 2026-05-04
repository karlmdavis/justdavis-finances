#!/usr/bin/env python3
"""Tests for cash flow analysis module."""

import json
from datetime import date
from unittest.mock import MagicMock

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
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 50000000,  # $50,000 in milliunits
                    "cleared_balance": 50000000,
                    "uncleared_balance": 0,
                },
                {
                    "id": "account-2",
                    "name": "Chase Credit Card",
                    "type": "creditCard",
                    "on_budget": True,
                    "closed": False,
                    "balance": -5000000,  # -$5,000 in milliunits (debt)
                    "cleared_balance": -5000000,
                    "uncleared_balance": 0,
                },
                {
                    "id": "account-3",
                    "name": "Apple Card",
                    "type": "creditCard",
                    "on_budget": True,
                    "closed": False,
                    "balance": -2000000,  # -$2,000 in milliunits (debt)
                    "cleared_balance": -2000000,
                    "uncleared_balance": 0,
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
                        "account_id": "chase-checking",
                        "account_name": "Chase Checking",
                        "payee_name": "Coffee Shop",
                        "category_name": "Dining Out",
                    },
                    {
                        "id": f"txn-{day}-2",
                        "date": date_str,
                        "amount": -10000,  # $10 expense
                        "account_id": "chase-credit-card",
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
                        "account_id": "chase-checking",
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

        with pytest.raises(FileNotFoundError, match="YNAB accounts cache not found"):
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
        """Test trend statistics calculation across three windows."""
        analyzer.load_data(sample_ynab_data)

        assert analyzer.trend_stats is not None
        assert set(analyzer.trend_stats.keys()) == {"overall", "thirteen_months", "six_months"}

        # The overall window always covers the full dataset (>= 2 days)
        overall = analyzer.trend_stats["overall"]
        assert overall is not None
        required_keys = {
            "slope",
            "intercept",
            "r_value",
            "p_value",
            "std_err",
            "monthly_trend",
            "yearly_trend",
            "direction",
            "fit_quality",
            "trend_line",
            "window_index",
            "window_start",
            "window_end",
            "n_days",
        }
        assert required_keys.issubset(overall.keys())
        assert len(overall["trend_line"]) == overall["n_days"]
        assert len(overall["trend_line"]) == len(overall["window_index"])
        assert overall["direction"] in {"positive", "negative", "flat"}
        assert 0 <= overall["fit_quality"] <= 1

        # Shorter windows: either None (insufficient fixture data) or a dict with the same shape
        for key in ("thirteen_months", "six_months"):
            window = analyzer.trend_stats[key]
            if window is None:
                continue
            assert required_keys.issubset(window.keys())
            assert len(window["trend_line"]) == window["n_days"]
            assert window["direction"] in {"positive", "negative", "flat"}
            assert 0 <= window["fit_quality"] <= 1

    def test_short_data_returns_none_for_long_windows(self, analyzer, sample_ynab_data):
        """Windows whose cutoff predates the dataset return None (no duplicate of overall)."""
        # The sample fixture covers only 30 days starting 2024-08-01, so 6mo and 13mo
        # cutoffs both predate the earliest date.
        analyzer.load_data(sample_ynab_data)

        assert analyzer.trend_stats["overall"] is not None
        assert analyzer.trend_stats["thirteen_months"] is None
        assert analyzer.trend_stats["six_months"] is None

    def test_eight_month_data_keeps_six_skips_thirteen(self, analyzer):
        """When data spans ~8 months, 6mo is a real window and 13mo is dedup-skipped."""
        # 240 days ≈ 8 months — between the 6mo and 13mo cutoffs.
        df = pd.DataFrame(
            {"Total": [100.0 * i for i in range(240)]},
            index=pd.date_range("2024-08-01", periods=240, freq="D"),
        )
        df["MA_7"] = df["Total"].rolling(window=7, min_periods=1).mean()
        df["MA_30"] = df["Total"].rolling(window=30, min_periods=1).mean()
        df["MA_90"] = df["Total"].rolling(window=90, min_periods=1).mean()
        df["Daily_Change"] = df["Total"].diff()

        analyzer.df = df
        analyzer._calculate_trend_statistics()

        assert analyzer.trend_stats["overall"] is not None
        assert analyzer.trend_stats["thirteen_months"] is None
        assert analyzer.trend_stats["six_months"] is not None
        assert analyzer.trend_stats["six_months"]["n_days"] < 240

    def test_trend_for_flat_window(self, analyzer):
        """A constant-balance window reports direction='flat' and 0 fit_quality (no NaN, no warning)."""
        flat_df = pd.DataFrame(
            {"Total": [50000.0] * 10},
            index=pd.date_range("2024-08-01", periods=10, freq="D"),
        )
        result = analyzer._calculate_trend_for_window(flat_df)

        assert result is not None
        assert result["slope"] == 0.0
        assert result["direction"] == "flat"
        assert result["fit_quality"] == 0.0
        assert result["monthly_trend"] == 0.0
        assert result["yearly_trend"] == 0.0
        # trend_line should be horizontal at the constant value
        assert all(result["trend_line"] == 50000.0)

    def test_windowed_trends_distinguish_inflection(self, analyzer):
        """Three windows reveal different slopes when the data has a regime change.

        Verifies the feature's core promise: a long-run flat trend that masks a
        recent steep upturn shows up clearly in the shorter windows.
        """
        # 720 days: 360 flat at 0, then 360 days rising linearly by 1/day.
        flat = [0.0] * 360
        rising = [float(i) for i in range(1, 361)]
        df = pd.DataFrame(
            {"Total": flat + rising},
            index=pd.date_range("2024-01-01", periods=720, freq="D"),
        )
        df["MA_7"] = df["Total"].rolling(window=7, min_periods=1).mean()
        df["MA_30"] = df["Total"].rolling(window=30, min_periods=1).mean()
        df["MA_90"] = df["Total"].rolling(window=90, min_periods=1).mean()
        df["Daily_Change"] = df["Total"].diff()

        analyzer.df = df
        analyzer._calculate_trend_statistics()

        overall = analyzer.trend_stats["overall"]
        thirteen = analyzer.trend_stats["thirteen_months"]
        six = analyzer.trend_stats["six_months"]

        assert overall is not None and thirteen is not None and six is not None
        assert overall["direction"] == "positive"
        assert thirteen["direction"] == "positive"
        assert six["direction"] == "positive"

        # Recent windows show steeper slopes than the long-run average.
        assert six["monthly_trend"] > thirteen["monthly_trend"] > overall["monthly_trend"]

        # The 6-month window sits entirely inside the linear-rising segment, so its
        # R² should be near 1.
        assert six["fit_quality"] > 0.99

    def test_statistics_panel_text_renders_without_leaked_python(self, analyzer, sample_ynab_data):
        """Rendered statistics panel text must not leak Python source artifacts.

        Regression test for the bug where '# type: ignore[union-attr]' embedded
        inside a multi-line f-string rendered as visible text in the dashboard.
        """
        analyzer.load_data(sample_ynab_data)

        mock_ax = MagicMock()
        analyzer._create_statistics_panel(mock_ax)

        mock_ax.text.assert_called_once()
        stats_text = mock_ax.text.call_args.args[2]

        assert "# type:" not in stats_text
        assert "FINANCIAL HEALTH METRICS" in stats_text
        assert "TREND ANALYSIS:" in stats_text

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

        required_keys = [
            "current_balance",
            "monthly_burn_rate",
            "trends",
            "volatility",
            "data_start_date",
            "analysis_date",
        ]
        for key in required_keys:
            assert key in stats

        assert isinstance(stats["current_balance"], int | float)
        assert stats["data_start_date"] == analyzer.config.start_date

        # Trends is a dict of three windows, each either None or a per-window summary dict
        assert isinstance(stats["trends"], dict)
        assert set(stats["trends"].keys()) == {"overall", "thirteen_months", "six_months"}

        overall = stats["trends"]["overall"]
        assert overall is not None
        assert isinstance(overall["monthly_trend"], int | float)
        assert isinstance(overall["yearly_trend"], int | float)
        assert overall["direction"] in ["positive", "negative", "flat"]
        assert 0 <= overall["fit_quality"] <= 1
        assert overall["n_days"] >= 2

        for key in ("thirteen_months", "six_months"):
            window = stats["trends"][key]
            if window is None:
                continue
            assert isinstance(window["monthly_trend"], int | float)
            assert isinstance(window["yearly_trend"], int | float)
            assert window["direction"] in ["positive", "negative", "flat"]
            assert 0 <= window["fit_quality"] <= 1

    def test_empty_transactions_error(self, analyzer, temp_dir):
        """Test error handling with empty transactions."""
        # Create YNAB data with no transactions in date range
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [
                {
                    "id": "1",
                    "name": "Chase Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 50000000,
                    "cleared_balance": 50000000,
                    "uncleared_balance": 0,
                }
            ],
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

    def test_deleted_transactions_excluded(self, temp_dir):
        """Deleted transactions must not affect the backwards balance reconstruction.

        Regression test: YNAB soft-deletes transactions (deleted: true) but keeps
        them in the API response. Including them in the backwards reconstruction
        inflates historical balances — a deleted expense of -$500 would add $500
        to every prior date's total.
        """
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [
                {
                    "id": "1",
                    "name": "Chase Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 10000000,  # $10,000 current balance
                    "cleared_balance": 10000000,
                    "uncleared_balance": 0,
                }
            ],
            "server_knowledge": 123,
        }

        transactions_data = [
            {
                "id": "normal-expense",
                "date": "2024-08-15",
                "amount": -5000,  # -$5 normal expense
                "account_id": "chase-checking",
                "account_name": "Chase Checking",
                "payee_name": "Coffee Shop",
                "deleted": False,
            },
            {
                "id": "deleted-expense",
                "date": "2024-08-15",
                "amount": -500000,  # -$500 deleted expense (duplicate import, etc.)
                "account_id": "chase-checking",
                "account_name": "Chase Checking",
                "payee_name": "Phantom Charge",
                "deleted": True,
            },
        ]

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        config = CashFlowConfig(cash_accounts=["Chase Checking"], start_date="2024-08-01")
        analyzer = CashFlowAnalyzer(config)
        analyzer.load_data(ynab_cache_dir)

        # Working backwards from $10,000 (current), undoing the -$5 normal expense:
        # balance at start of Aug 15 = $10,000 + $5 = $10,005.
        # If deleted transaction were included, it would be $10,000 + $5 + $500 = $10,505.
        assert analyzer.df is not None
        start_balance = float(analyzer.df["Total"].iloc[0])
        assert (
            abs(start_balance - 10005.0) < 0.01
        ), f"Expected ~$10,005 (deleted transaction excluded), got ${start_balance:.2f}"

    def test_closed_accounts_excluded(self, temp_dir):
        """Closed accounts must not appear in cash flow calculations.

        Regression test: accounts.json includes all accounts including closed ones.
        A closed account in the cash_accounts config list should be silently excluded
        so its stale balance doesn't distort the total.
        """
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [
                {
                    "id": "1",
                    "name": "Active Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 10000000,  # $10,000
                    "cleared_balance": 10000000,
                    "uncleared_balance": 0,
                },
                {
                    "id": "2",
                    "name": "Closed Old Account",
                    "type": "checking",
                    "on_budget": True,
                    "closed": True,  # Closed account
                    "balance": 5000000,  # $5,000 residual balance (should be ignored)
                    "cleared_balance": 5000000,
                    "uncleared_balance": 0,
                },
            ],
            "server_knowledge": 123,
        }

        transactions_data = [
            {
                "id": "txn-1",
                "date": "2024-08-15",
                "amount": -10000,  # -$10 expense on active account
                "account_id": "active-checking",
                "account_name": "Active Checking",
                "payee_name": "Store",
                "deleted": False,
            },
            {
                "id": "txn-closed",
                "date": "2024-08-10",
                "amount": -3000000,  # -$3,000 final transfer on closed account
                "account_id": "closed-old-account",
                "account_name": "Closed Old Account",
                "payee_name": "Transfer",
                "deleted": False,
            },
        ]

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        config = CashFlowConfig(
            cash_accounts=["Active Checking", "Closed Old Account"], start_date="2024-08-01"
        )
        analyzer = CashFlowAnalyzer(config)
        analyzer.load_data(ynab_cache_dir)

        assert analyzer.df is not None
        # Total should only reflect Active Checking ($10,000 + $10 = $10,010 at start of Aug 15).
        # If Closed Old Account's balance or transactions were included, start balance would
        # be ~$18,010 (stale $5,000 balance + $3,000 reversed transfer + $10,010).
        start_balance = float(analyzer.df["Total"].iloc[0])
        assert (
            abs(start_balance - 10010.0) < 0.01
        ), f"Expected ~$10,010 (closed account excluded), got ${start_balance:.2f}"

    def test_off_budget_credit_cards_included(self, temp_dir):
        """Off-budget accounts must be included in the net balance calculation.

        Regression test: the on_budget filter was incorrectly excluding credit cards
        that are tracked as off-budget in YNAB (e.g. Apple Card).
        A credit card with on_budget=False still carries real debt and must reduce
        the reported total — excluding it inflates the balance by the full debt amount.
        """
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [
                {
                    "id": "1",
                    "name": "Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 10000000,  # $10,000
                    "cleared_balance": 10000000,
                    "uncleared_balance": 0,
                },
                {
                    "id": "2",
                    "name": "Off Budget Card",
                    "type": "creditCard",
                    "on_budget": False,  # Tracked as off-budget in YNAB
                    "closed": False,
                    "balance": -5000000,  # -$5,000 debt
                    "cleared_balance": -5000000,
                    "uncleared_balance": 0,
                },
            ],
            "server_knowledge": 123,
        }

        transactions_data = [
            {
                "id": "txn-1",
                "date": "2024-08-15",
                "amount": -10000,  # -$10 expense on checking
                "account_id": "checking",
                "account_name": "Checking",
                "payee_name": "Store",
                "deleted": False,
            },
        ]

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(transactions_data, f, indent=2)

        config = CashFlowConfig(cash_accounts=["Checking", "Off Budget Card"], start_date="2024-08-01")
        analyzer = CashFlowAnalyzer(config)
        analyzer.load_data(ynab_cache_dir)

        assert analyzer.df is not None
        # Net should be $10,000 - $5,000 = $5,000 (plus $10 from backward reconstruction).
        # If Off Budget Card were excluded, start balance would be ~$10,010.
        start_balance = float(analyzer.df["Total"].iloc[0])
        assert (
            abs(start_balance - 5010.0) < 0.01
        ), f"Expected ~$5,010 (off-budget card included), got ${start_balance:.2f}"


class TestCashFlowEdgeCases:
    """Test edge cases and error conditions."""

    def test_missing_account_data(self, temp_dir):
        """Test handling of missing account data."""
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Accounts data missing target accounts
        accounts_data = {
            "accounts": [
                {
                    "id": "1",
                    "name": "Other Account",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 1000000,
                    "cleared_balance": 1000000,
                    "uncleared_balance": 0,
                }
            ],
            "server_knowledge": 123,
        }

        transactions_data = [
            {
                "id": "txn-1",
                "date": "2024-08-15",
                "amount": -5000,
                "account_id": "missing-account",
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
            "accounts": [
                {
                    "id": "1",
                    "name": "Test Account",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 50000000,
                    "cleared_balance": 50000000,
                    "uncleared_balance": 0,
                }
            ],
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
                    "account_id": "test-account",
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
            {
                "id": "1",
                "name": "Checking",
                "type": "checking",
                "on_budget": True,
                "closed": False,
                "balance": 10000000,
                "cleared_balance": 10000000,
                "uncleared_balance": 0,
            },
            {
                "id": "2",
                "name": "Credit Card",
                "type": "creditCard",
                "on_budget": True,
                "closed": False,
                "balance": -3000000,
                "cleared_balance": -3000000,
                "uncleared_balance": 0,
            },
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
                    "account_id": "credit-card",
                    "account_name": "Credit Card",
                    "payee_name": "Daily Expense",
                    "category_name": "Shopping",
                },
                {
                    "id": f"income-{day}",
                    "date": date_str,
                    "amount": 5000 if day % 7 == 0 else 0,  # $5 weekly income
                    "account_id": "checking",
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
    assert isinstance(summary["current_balance"], int | float)
    assert summary["trends"]["overall"]["direction"] in ["positive", "negative", "flat"]
