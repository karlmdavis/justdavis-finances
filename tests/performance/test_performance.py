#!/usr/bin/env python3
"""Performance tests with realistic data volumes."""

import json

import pytest

from finances.analysis import CashFlowAnalyzer, CashFlowConfig


@pytest.mark.slow
@pytest.mark.performance
def test_cash_flow_performance_large_dataset(temp_dir):
    """Test cash flow analysis performance with realistic data volumes."""
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
