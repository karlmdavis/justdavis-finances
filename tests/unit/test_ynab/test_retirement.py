#!/usr/bin/env python3
"""
Unit tests for YNAB-based retirement account management.
"""

from datetime import date
from pathlib import Path

import pytest

from finances.ynab.retirement import (
    RetirementAccount,
    YnabRetirementService,
    discover_retirement_accounts,
    generate_retirement_edits,
)


class TestRetirementAccount:
    """Test RetirementAccount dataclass."""

    def test_balance_conversion(self):
        """Test milliunits to cents conversion."""
        account = RetirementAccount(
            id="test-id",
            name="Test Account",
            balance_milliunits=1234560,  # milliunits
            cleared_balance_milliunits=1234560,
            last_reconciled_at=None,
        )

        # milliunits / 10 = cents
        assert account.balance_cents == 123456
        assert account.cleared_balance_cents == 123456

    def test_provider_extraction(self):
        """Test provider extraction from account names."""
        test_cases = [
            ("Karl's Fidelity: 401k Plan", "Fidelity"),
            ("Erica's Vanguard: IRA", "Vanguard"),
            ("Simple Account Name", "Unknown"),
            ("Chase: Retirement Account", "Chase"),
        ]

        for name, expected_provider in test_cases:
            account = RetirementAccount(
                id="test",
                name=name,
                balance_milliunits=0,
                cleared_balance_milliunits=0,
                last_reconciled_at=None,
            )
            assert account.provider == expected_provider

    def test_account_type_detection(self):
        """Test account type detection from names."""
        test_cases = [
            ("Karl's 401(k) Plan", "401(k)"),
            ("My 401K Account", "401(k)"),
            ("Erica's Roth IRA", "Roth IRA"),
            ("Traditional IRA", "IRA"),
            ("Thrift Savings Plan", "TSP"),
            ("Generic Investment", "Investment"),
        ]

        for name, expected_type in test_cases:
            account = RetirementAccount(
                id="test",
                name=name,
                balance_milliunits=0,
                cleared_balance_milliunits=0,
                last_reconciled_at=None,
            )
            assert account.account_type == expected_type


class TestYnabRetirementService:
    """Test YnabRetirementService functionality."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create temporary data directory structure."""
        data_dir = tmp_path / "data"
        (data_dir / "ynab" / "cache").mkdir(parents=True)
        (data_dir / "ynab" / "edits").mkdir(parents=True)
        return data_dir

    @pytest.fixture
    def sample_accounts_data(self):
        """Sample YNAB accounts data."""
        return {
            "accounts": [
                {
                    "id": "retirement-1",
                    "name": "Karl's 401(k)",
                    "type": "otherAsset",
                    "on_budget": False,
                    "closed": False,
                    "balance": 1000000,  # $100 in milliunits
                    "cleared_balance": 1000000,
                    "last_reconciled_at": "2024-01-01T00:00:00Z",
                },
                {
                    "id": "retirement-2",
                    "name": "Erica's IRA",
                    "type": "otherAsset",
                    "on_budget": False,
                    "closed": False,
                    "balance": 2000000,  # $200 in milliunits
                    "cleared_balance": 2000000,
                    "last_reconciled_at": None,
                },
                {
                    "id": "checking-1",
                    "name": "Checking Account",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 500000,
                    "cleared_balance": 500000,
                    "last_reconciled_at": None,
                },
            ]
        }

    def test_discover_retirement_accounts(self, temp_data_dir, sample_accounts_data):
        """Test discovering retirement accounts from YNAB cache."""
        import json

        # Write sample data
        accounts_file = temp_data_dir / "ynab" / "cache" / "accounts.json"
        with open(accounts_file, "w") as f:
            json.dump(sample_accounts_data, f)

        service = YnabRetirementService(temp_data_dir)
        accounts = service.discover_retirement_accounts()

        # Should find 2 retirement accounts (otherAsset + off-budget)
        assert len(accounts) == 2
        assert accounts[0].name == "Erica's IRA"  # Sorted by name
        assert accounts[1].name == "Karl's 401(k)"
        assert accounts[0].balance_cents == 200000  # 2000000 milliunits / 10 = 200000 cents
        assert accounts[1].balance_cents == 100000  # 1000000 milliunits / 10 = 100000 cents

    def test_generate_balance_adjustment_increase(self, temp_data_dir):
        """Test generating adjustment for balance increase."""
        service = YnabRetirementService(temp_data_dir)

        account = RetirementAccount(
            id="test-id",
            name="Test Account",
            balance_milliunits=1000000,  # Current: 100000 cents = $1000
            cleared_balance_milliunits=1000000,
            last_reconciled_at=None,
        )

        # Increase balance to $1500
        mutation = service.generate_balance_adjustment(account, 150000, date(2024, 1, 1))  # $1500 in cents

        assert mutation is not None
        assert mutation["account_id"] == "test-id"
        assert mutation["amount_milliunits"] == 500000  # $500 increase in milliunits
        assert mutation["action"] == "create_reconciliation"
        assert "$1,000.00 → $1,500.00" in mutation["memo"]

    def test_generate_balance_adjustment_decrease(self, temp_data_dir):
        """Test generating adjustment for balance decrease."""
        service = YnabRetirementService(temp_data_dir)

        account = RetirementAccount(
            id="test-id",
            name="Test Account",
            balance_milliunits=2000000,  # Current: 200000 cents = $2000
            cleared_balance_milliunits=2000000,
            last_reconciled_at=None,
        )

        # Decrease balance to $1500
        mutation = service.generate_balance_adjustment(account, 150000, date(2024, 1, 1))  # $1500 in cents

        assert mutation is not None
        assert mutation["amount_milliunits"] == -500000  # $500 decrease in milliunits
        assert "$2,000.00 → $1,500.00" in mutation["memo"]

    def test_generate_balance_adjustment_no_change(self, temp_data_dir):
        """Test no adjustment when balance unchanged."""
        service = YnabRetirementService(temp_data_dir)

        account = RetirementAccount(
            id="test-id",
            name="Test Account",
            balance_milliunits=1000000,  # Current: 100000 cents = $1000
            cleared_balance_milliunits=1000000,
            last_reconciled_at=None,
        )

        # Same balance
        mutation = service.generate_balance_adjustment(
            account, 100000, date(2024, 1, 1)  # $1000 in cents (same as current)
        )

        assert mutation == {}

    def test_create_retirement_edits(self, temp_data_dir):
        """Test creating YNAB edits file."""
        service = YnabRetirementService(temp_data_dir)

        adjustments = [
            {
                "account_id": "acc1",
                "account_name": "Account 1",
                "action": "create_reconciliation",
                "amount_milliunits": 100000,
                "metadata": {"adjustment_cents": 10000},
            },
            {
                "account_id": "acc2",
                "account_name": "Account 2",
                "action": "create_reconciliation",
                "amount_milliunits": -50000,
                "metadata": {"adjustment_cents": -5000},
            },
        ]

        output_file = service.create_retirement_edits(adjustments)

        assert output_file is not None
        assert output_file.exists()
        assert "retirement_edits.yaml" in str(output_file)

        # Verify file contents
        import json

        with open(output_file) as f:
            data = json.load(f)

        assert data["metadata"]["total_mutations"] == 2
        assert data["metadata"]["total_adjustment"] == 5000  # 10000 - 5000
        assert data["metadata"]["auto_approved"] == 2
        assert len(data["mutations"]) == 2


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_discover_retirement_accounts_function(self, tmp_path):
        """Test discover_retirement_accounts convenience function."""
        data_dir = tmp_path / "data"
        (data_dir / "ynab" / "cache").mkdir(parents=True)

        # Write empty accounts file
        import json

        accounts_file = data_dir / "ynab" / "cache" / "accounts.json"
        with open(accounts_file, "w") as f:
            json.dump({"accounts": []}, f)

        accounts = discover_retirement_accounts(data_dir)
        assert accounts == []

    def test_generate_retirement_edits_function(self, tmp_path):
        """Test generate_retirement_edits convenience function."""
        data_dir = tmp_path / "data"
        (data_dir / "ynab" / "cache").mkdir(parents=True)
        (data_dir / "ynab" / "edits").mkdir(parents=True)

        # Write accounts file with one retirement account
        import json

        accounts_file = data_dir / "ynab" / "cache" / "accounts.json"
        accounts_data = {
            "accounts": [
                {
                    "id": "ret1",
                    "name": "Test Retirement",
                    "type": "otherAsset",
                    "on_budget": False,
                    "closed": False,
                    "balance": 1000000,
                    "cleared_balance": 1000000,
                    "last_reconciled_at": None,
                }
            ]
        }
        with open(accounts_file, "w") as f:
            json.dump(accounts_data, f)

        # Generate edits with balance update
        result = generate_retirement_edits(data_dir, {"ret1": 15000})  # Update to $150

        assert result is not None
        assert result.exists()
        assert "retirement_edits" in str(result)
