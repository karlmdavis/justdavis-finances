#!/usr/bin/env python3
"""Integration tests for complete workflows."""

import json

import pandas as pd
import pytest

from finances.analysis import CashFlowAnalyzer, CashFlowConfig

# TestAmazonWorkflow and TestAppleWorkflow removed - redundant with E2E tests
# E2E test (test_flow_system.py::test_flow_interactive_execution_with_matching)
# already validates these complete workflows via CLI with coordinated test data


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


# TestCrossSystemIntegration class removed entirely
# - test_amazon_to_ynab_edit_workflow: Already tested by split_calculator unit tests and E2E tests
# - test_apple_to_ynab_edit_workflow: Already tested by split_calculator unit tests and E2E tests
# - test_configuration_integration: Config testing doesn't belong in workflow tests

# Performance test moved to tests/performance/test_performance.py
# Performance tests should be isolated and run separately from integration tests
