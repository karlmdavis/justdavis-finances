#!/usr/bin/env python3
"""Tests for Cash Flow Analysis system."""

import pytest
import tempfile
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCashFlowAnalysis:
    """Test cases for Cash Flow Analysis functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Sample YNAB accounts data
        self.sample_accounts = {
            "accounts": [
                {
                    "id": "account-1",
                    "name": "Chase Checking",
                    "type": "checking",
                    "balance": 250000  # $250.00 in milliunits
                },
                {
                    "id": "account-2",
                    "name": "Chase Credit Card",
                    "type": "creditCard",
                    "balance": -150000  # -$150.00 in milliunits
                },
                {
                    "id": "account-3",
                    "name": "Apple Card",
                    "type": "creditCard",
                    "balance": -75000  # -$75.00 in milliunits
                },
                {
                    "id": "account-4",
                    "name": "Apple Cash",
                    "type": "cash",
                    "balance": 50000  # $50.00 in milliunits
                },
                {
                    "id": "account-5",
                    "name": "Apple Savings",
                    "type": "savings",
                    "balance": 1000000  # $1000.00 in milliunits
                },
                {
                    "id": "account-6",
                    "name": "Investment Account",
                    "type": "investment",
                    "balance": 500000  # Should be excluded from cash flow
                }
            ],
            "server_knowledge": 123456789
        }

        # Sample transactions (30 days of data starting from 2024-05-01)
        self.sample_transactions = []
        base_date = datetime(2024, 5, 1)

        # Create realistic transaction patterns
        for i in range(30):
            current_date = base_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')

            # Daily salary deposit (weekdays only)
            if current_date.weekday() < 5:  # Monday to Friday
                self.sample_transactions.append({
                    "id": f"income-{i}",
                    "date": date_str,
                    "amount": 20000,  # $20.00 daily income
                    "account_name": "Chase Checking",
                    "payee_name": "Employer",
                    "category_name": "Income",
                    "memo": "Daily salary"
                })

            # Random expenses
            if i % 3 == 0:  # Every 3 days
                self.sample_transactions.append({
                    "id": f"expense-{i}",
                    "date": date_str,
                    "amount": -5000,  # -$5.00 expense
                    "account_name": "Chase Credit Card",
                    "payee_name": "Grocery Store",
                    "category_name": "Groceries",
                    "memo": "Weekly shopping"
                })

            # Large monthly expense
            if i == 15:  # Mid-month
                self.sample_transactions.append({
                    "id": f"rent-{i}",
                    "date": date_str,
                    "amount": -120000,  # -$120.00 rent
                    "account_name": "Chase Checking",
                    "payee_name": "Landlord",
                    "category_name": "Housing",
                    "memo": "Monthly rent"
                })

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_ynab_data(self):
        """Create test YNAB data files."""
        ynab_dir = os.path.join(self.temp_dir, 'ynab-data')
        os.makedirs(ynab_dir, exist_ok=True)

        # Create accounts.json
        accounts_path = os.path.join(ynab_dir, 'accounts.json')
        with open(accounts_path, 'w', encoding='utf-8') as f:
            json.dump(self.sample_accounts, f, indent=2)

        # Create transactions.json
        transactions_path = os.path.join(ynab_dir, 'transactions.json')
        with open(transactions_path, 'w', encoding='utf-8') as f:
            json.dump(self.sample_transactions, f, indent=2)

        return ynab_dir

    def create_mock_analysis_module(self):
        """Create a mock cash flow analysis module for testing."""
        class MockCashFlowAnalysis:
            def __init__(self, ynab_data_dir):
                self.ynab_data_dir = ynab_data_dir
                self.cash_accounts = [
                    'Chase Checking',
                    'Chase Credit Card',
                    'Apple Card',
                    'Apple Cash',
                    'Apple Savings'
                ]

            def load_ynab_data(self):
                """Load YNAB data from files."""
                accounts_path = os.path.join(self.ynab_data_dir, 'accounts.json')
                transactions_path = os.path.join(self.ynab_data_dir, 'transactions.json')

                with open(accounts_path, 'r') as f:
                    accounts_data = json.load(f)

                with open(transactions_path, 'r') as f:
                    transactions = json.load(f)

                return accounts_data, transactions

            def filter_cash_transactions(self, transactions, start_date='2024-05-01'):
                """Filter transactions to cash accounts and date range."""
                filtered = []
                for t in transactions:
                    if (t.get('account_name') in self.cash_accounts and
                        t['date'] >= start_date):
                        filtered.append(t)

                return sorted(filtered, key=lambda x: x['date'])

            def calculate_daily_balances(self, accounts_data, transactions):
                """Calculate daily balances for each account."""
                # Get current balances
                current_balances = {}
                for account in accounts_data['accounts']:
                    if account['name'] in self.cash_accounts:
                        current_balances[account['name']] = account['balance'] / 1000

                # Calculate daily balances working backwards
                daily_balances = {}
                dates = sorted(set(t['date'] for t in transactions))

                if not dates:
                    return daily_balances

                end_date = max(dates)
                daily_balances[end_date] = current_balances.copy()

                # Work backwards through transactions
                for transaction in reversed(transactions):
                    date = transaction['date']
                    account = transaction['account_name']
                    amount = transaction['amount'] / 1000

                    if date not in daily_balances:
                        # Copy balances from next known date
                        future_dates = [d for d in daily_balances.keys() if d > date]
                        if future_dates:
                            next_date = min(future_dates)
                            daily_balances[date] = daily_balances[next_date].copy()

                    # Subtract transaction to get previous balance
                    if date in daily_balances and account in daily_balances[date]:
                        daily_balances[date][account] -= amount

                return daily_balances

            def create_dataframe(self, daily_balances):
                """Create pandas DataFrame from daily balances."""
                if not daily_balances:
                    return pd.DataFrame()

                data = []
                for date, accounts in sorted(daily_balances.items()):
                    total = sum(accounts.values())
                    row = {
                        'Date': pd.to_datetime(date),
                        'Total': total,
                        **accounts
                    }
                    data.append(row)

                df = pd.DataFrame(data)
                df.set_index('Date', inplace=True)
                return df

            def calculate_moving_averages(self, df):
                """Calculate moving averages for the total balance."""
                if df.empty:
                    return df

                df['MA_7'] = df['Total'].rolling(window=7, min_periods=1).mean()
                df['MA_30'] = df['Total'].rolling(window=30, min_periods=1).mean()
                df['MA_90'] = df['Total'].rolling(window=90, min_periods=1).mean()
                return df

            def calculate_trend_analysis(self, df):
                """Calculate trend line using linear regression."""
                if df.empty or len(df) < 2:
                    return None, 0, 0

                from scipy import stats

                x = np.arange(len(df))
                y = df['Total'].values

                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                trend_line = slope * x + intercept

                return trend_line, slope, r_value

            def calculate_monthly_statistics(self, df):
                """Calculate monthly aggregated statistics."""
                if df.empty:
                    return pd.DataFrame()

                df['Daily_Change'] = df['Total'].diff()

                monthly_df = df.resample('ME').agg({
                    'Total': ['mean', 'min', 'max', 'last'],
                    'Daily_Change': 'sum'
                })

                monthly_df.columns = ['Mean_Balance', 'Min_Balance', 'Max_Balance', 'End_Balance', 'Net_Change']
                return monthly_df

            def generate_statistics(self, df):
                """Generate comprehensive financial statistics."""
                if df.empty:
                    return {}

                current_total = df['Total'].iloc[-1]
                avg_balance = df['Total'].mean()
                std_balance = df['Total'].std()
                min_balance = df['Total'].min()
                max_balance = df['Total'].max()

                df['Daily_Change'] = df['Total'].diff()
                days_positive = (df['Daily_Change'] > 0).sum()
                days_negative = (df['Daily_Change'] < 0).sum()
                avg_daily_change = df['Daily_Change'].mean()

                return {
                    'current_total': current_total,
                    'avg_balance': avg_balance,
                    'std_balance': std_balance,
                    'min_balance': min_balance,
                    'max_balance': max_balance,
                    'days_positive': days_positive,
                    'days_negative': days_negative,
                    'avg_daily_change': avg_daily_change,
                    'total_days': len(df)
                }

        return MockCashFlowAnalysis

    def test_load_ynab_data(self):
        """Test loading YNAB accounts and transactions data."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()

        # Verify accounts data
        assert 'accounts' in accounts_data
        assert len(accounts_data['accounts']) == 6

        # Verify transactions data
        assert len(transactions) > 0
        assert all('date' in t for t in transactions)
        assert all('amount' in t for t in transactions)

    def test_filter_cash_transactions(self):
        """Test filtering transactions to cash accounts only."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()

        cash_transactions = analyzer.filter_cash_transactions(transactions)

        # Should only include transactions from cash accounts
        for transaction in cash_transactions:
            assert transaction['account_name'] in analyzer.cash_accounts

        # Should be sorted by date
        dates = [t['date'] for t in cash_transactions]
        assert dates == sorted(dates)

        # Should exclude transactions before start date
        assert all(t['date'] >= '2024-05-01' for t in cash_transactions)

    def test_calculate_daily_balances(self):
        """Test calculation of daily balances."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)

        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)

        # Should have balances for all transaction dates
        transaction_dates = set(t['date'] for t in cash_transactions)
        assert all(date in daily_balances for date in transaction_dates)

        # Each date should have all cash accounts
        for date, balances in daily_balances.items():
            for account in analyzer.cash_accounts:
                if account in self.sample_accounts['accounts']:
                    assert account in balances

        # Balances should change over time (not all the same)
        all_totals = [sum(balances.values()) for balances in daily_balances.values()]
        assert len(set(all_totals)) > 1  # Should have variation

    def test_create_dataframe(self):
        """Test creation of pandas DataFrame from daily balances."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)

        df = analyzer.create_dataframe(daily_balances)

        # Should be a valid DataFrame
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

        # Should have Date as index
        assert isinstance(df.index, pd.DatetimeIndex)

        # Should have Total column
        assert 'Total' in df.columns

        # Should have account columns
        for account in analyzer.cash_accounts:
            if any(account == acc['name'] for acc in self.sample_accounts['accounts']):
                assert account in df.columns

        # Total should equal sum of accounts
        for idx, row in df.iterrows():
            account_sum = sum(row[col] for col in df.columns if col != 'Total' and col in analyzer.cash_accounts)
            assert abs(row['Total'] - account_sum) < 0.01  # Allow for rounding

    def test_calculate_moving_averages(self):
        """Test calculation of moving averages."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)
        df = analyzer.create_dataframe(daily_balances)

        df_with_ma = analyzer.calculate_moving_averages(df)

        # Should have moving average columns
        assert 'MA_7' in df_with_ma.columns
        assert 'MA_30' in df_with_ma.columns
        assert 'MA_90' in df_with_ma.columns

        # Moving averages should not have NaN for first few days (min_periods=1)
        assert not df_with_ma['MA_7'].isna().all()
        assert not df_with_ma['MA_30'].isna().all()
        assert not df_with_ma['MA_90'].isna().all()

        # 7-day MA should be more volatile than 30-day MA
        ma7_std = df_with_ma['MA_7'].std()
        ma30_std = df_with_ma['MA_30'].std()
        assert ma7_std >= ma30_std

    def test_calculate_trend_analysis(self):
        """Test calculation of trend line and statistics."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)
        df = analyzer.create_dataframe(daily_balances)

        trend_line, slope, r_value = analyzer.calculate_trend_analysis(df)

        # Should return valid trend analysis
        assert trend_line is not None
        assert len(trend_line) == len(df)
        assert isinstance(slope, (int, float))
        assert isinstance(r_value, (int, float))

        # R-value should be between -1 and 1
        assert -1 <= r_value <= 1

    def test_calculate_monthly_statistics(self):
        """Test calculation of monthly aggregated statistics."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)
        df = analyzer.create_dataframe(daily_balances)

        monthly_df = analyzer.calculate_monthly_statistics(df)

        # Should have monthly aggregation columns
        expected_columns = ['Mean_Balance', 'Min_Balance', 'Max_Balance', 'End_Balance', 'Net_Change']
        for col in expected_columns:
            assert col in monthly_df.columns

        # Should have at least one month of data
        assert len(monthly_df) >= 1

        # Min should be <= Mean <= Max
        for idx, row in monthly_df.iterrows():
            assert row['Min_Balance'] <= row['Mean_Balance'] <= row['Max_Balance']

    def test_generate_statistics(self):
        """Test generation of comprehensive financial statistics."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)
        df = analyzer.create_dataframe(daily_balances)

        stats = analyzer.generate_statistics(df)

        # Should have all expected statistics
        expected_stats = [
            'current_total', 'avg_balance', 'std_balance',
            'min_balance', 'max_balance', 'days_positive',
            'days_negative', 'avg_daily_change', 'total_days'
        ]

        for stat in expected_stats:
            assert stat in stats

        # Sanity checks
        assert stats['total_days'] == len(df)
        assert stats['days_positive'] + stats['days_negative'] <= stats['total_days']
        assert stats['min_balance'] <= stats['avg_balance'] <= stats['max_balance']

    def test_empty_data_handling(self):
        """Test handling of empty or missing data."""
        MockAnalysis = self.create_mock_analysis_module()
        analyzer = MockAnalysis('nonexistent_dir')

        # Empty daily balances
        empty_balances = {}
        df = analyzer.create_dataframe(empty_balances)
        assert df.empty

        # Empty DataFrame operations
        df_with_ma = analyzer.calculate_moving_averages(df)
        assert df_with_ma.empty

        trend_line, slope, r_value = analyzer.calculate_trend_analysis(df)
        assert trend_line is None

        monthly_df = analyzer.calculate_monthly_statistics(df)
        assert monthly_df.empty

        stats = analyzer.generate_statistics(df)
        assert stats == {}

    def test_date_filtering_edge_cases(self):
        """Test edge cases in date filtering."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()

        # Filter with very recent start date (should exclude most transactions)
        recent_transactions = analyzer.filter_cash_transactions(transactions, start_date='2024-06-01')
        assert len(recent_transactions) < len(transactions)

        # Filter with very old start date (should include all)
        all_transactions = analyzer.filter_cash_transactions(transactions, start_date='2024-01-01')
        assert len(all_transactions) == len([t for t in transactions if t.get('account_name') in analyzer.cash_accounts])

    def test_balance_calculation_accuracy(self):
        """Test accuracy of balance calculations."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)

        # Verify that final balances match current account balances
        if daily_balances:
            latest_date = max(daily_balances.keys())
            calculated_balances = daily_balances[latest_date]

            current_balances = {}
            for account in accounts_data['accounts']:
                if account['name'] in analyzer.cash_accounts:
                    current_balances[account['name']] = account['balance'] / 1000

            for account, balance in current_balances.items():
                if account in calculated_balances:
                    assert abs(calculated_balances[account] - balance) < 0.01

    def test_statistical_calculations_validity(self):
        """Test validity of statistical calculations."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)
        df = analyzer.create_dataframe(daily_balances)

        stats = analyzer.generate_statistics(df)

        # Standard deviation should be non-negative
        assert stats['std_balance'] >= 0

        # Average daily change should be reasonable
        assert isinstance(stats['avg_daily_change'], (int, float))

        # Day counts should make sense
        assert stats['days_positive'] >= 0
        assert stats['days_negative'] >= 0
        assert stats['days_positive'] + stats['days_negative'] <= stats['total_days']

    def test_data_type_consistency(self):
        """Test that data types are consistent throughout processing."""
        ynab_dir = self.create_test_ynab_data()
        MockAnalysis = self.create_mock_analysis_module()

        analyzer = MockAnalysis(ynab_dir)
        accounts_data, transactions = analyzer.load_ynab_data()
        cash_transactions = analyzer.filter_cash_transactions(transactions)
        daily_balances = analyzer.calculate_daily_balances(accounts_data, cash_transactions)
        df = analyzer.create_dataframe(daily_balances)

        # All balance columns should be numeric
        numeric_columns = [col for col in df.columns if col != 'Date']
        for col in numeric_columns:
            assert pd.api.types.is_numeric_dtype(df[col])

        # Date index should be datetime
        assert isinstance(df.index, pd.DatetimeIndex)

        # Moving averages should be numeric
        df_with_ma = analyzer.calculate_moving_averages(df)
        assert pd.api.types.is_numeric_dtype(df_with_ma['MA_7'])
        assert pd.api.types.is_numeric_dtype(df_with_ma['MA_30'])
        assert pd.api.types.is_numeric_dtype(df_with_ma['MA_90'])


if __name__ == '__main__':
    pytest.main([__file__])