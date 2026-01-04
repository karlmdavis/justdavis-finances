"""Tests for bank account configuration models."""

import pytest

from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, ImportPattern


class TestImportPattern:
    """Tests for ImportPattern model."""

    def test_creation(self):
        """Test ImportPattern creation with all fields."""
        pattern = ImportPattern(
            pattern="*_transactions.csv",
            format_handler="chase_checking_csv",
        )

        assert pattern.pattern == "*_transactions.csv"
        assert pattern.format_handler == "chase_checking_csv"

    def test_to_dict(self):
        """Test ImportPattern serialization."""
        pattern = ImportPattern(
            pattern="*_Activity.csv",
            format_handler="chase_credit_csv",
        )

        result = pattern.to_dict()

        assert result == {
            "pattern": "*_Activity.csv",
            "format_handler": "chase_credit_csv",
        }

    def test_from_dict(self):
        """Test ImportPattern deserialization."""
        data = {
            "pattern": "statement_*.csv",
            "format_handler": "usaa_checking_csv",
        }

        pattern = ImportPattern.from_dict(data)

        assert pattern.pattern == "statement_*.csv"
        assert pattern.format_handler == "usaa_checking_csv"

    def test_immutable(self):
        """Test ImportPattern is immutable."""
        pattern = ImportPattern(
            pattern="*.csv",
            format_handler="handler",
        )

        with pytest.raises(AttributeError):
            pattern.pattern = "new_pattern"  # type: ignore[misc]


class TestAccountConfig:
    """Tests for AccountConfig model."""

    def test_creation(self):
        """Test AccountConfig creation with all fields."""
        config = AccountConfig(
            ynab_account_id="acc_123",
            ynab_account_name="Chase Checking",
            slug="chase-checking",
            bank_name="Chase",
            account_type="checking",
            statement_frequency="monthly",
            source_directory="data/bank_statements/chase_checking",
            download_instructions="Download from chase.com > Accounts > Checking > Activity",
            import_patterns=(
                ImportPattern(
                    pattern="*_transactions.csv",
                    format_handler="chase_checking_csv",
                ),
                ImportPattern(
                    pattern="*_activity.csv",
                    format_handler="chase_checking_csv_v2",
                ),
            ),
        )

        assert config.ynab_account_id == "acc_123"
        assert config.ynab_account_name == "Chase Checking"
        assert config.slug == "chase-checking"
        assert config.bank_name == "Chase"
        assert config.account_type == "checking"
        assert config.statement_frequency == "monthly"
        assert config.source_directory == "data/bank_statements/chase_checking"
        assert config.download_instructions == "Download from chase.com > Accounts > Checking > Activity"
        assert len(config.import_patterns) == 2
        assert config.import_patterns[0].pattern == "*_transactions.csv"
        assert config.import_patterns[1].format_handler == "chase_checking_csv_v2"

    def test_to_dict(self):
        """Test AccountConfig serialization with nested ImportPattern."""
        config = AccountConfig(
            ynab_account_id="acc_456",
            ynab_account_name="Chase Freedom",
            slug="chase-freedom",
            bank_name="Chase",
            account_type="credit",
            statement_frequency="monthly",
            source_directory="data/bank_statements/chase_freedom",
            download_instructions="Download from chase.com",
            import_patterns=(
                ImportPattern(
                    pattern="*_Activity.csv",
                    format_handler="chase_credit_csv",
                ),
            ),
        )

        result = config.to_dict()

        assert result == {
            "ynab_account_id": "acc_456",
            "ynab_account_name": "Chase Freedom",
            "slug": "chase-freedom",
            "bank_name": "Chase",
            "account_type": "credit",
            "statement_frequency": "monthly",
            "source_directory": "data/bank_statements/chase_freedom",
            "download_instructions": "Download from chase.com",
            "import_patterns": [
                {
                    "pattern": "*_Activity.csv",
                    "format_handler": "chase_credit_csv",
                }
            ],
        }

    def test_from_dict(self):
        """Test AccountConfig deserialization with nested ImportPattern."""
        data = {
            "ynab_account_id": "acc_789",
            "ynab_account_name": "USAA Checking",
            "slug": "usaa-checking",
            "bank_name": "USAA",
            "account_type": "checking",
            "statement_frequency": "monthly",
            "source_directory": "data/bank_statements/usaa",
            "download_instructions": "Download from usaa.com",
            "import_patterns": [
                {
                    "pattern": "statement_*.csv",
                    "format_handler": "usaa_checking_csv",
                },
                {
                    "pattern": "*_export.csv",
                    "format_handler": "usaa_checking_csv_v2",
                },
            ],
        }

        config = AccountConfig.from_dict(data)

        assert config.ynab_account_id == "acc_789"
        assert config.ynab_account_name == "USAA Checking"
        assert config.slug == "usaa-checking"
        assert config.bank_name == "USAA"
        assert config.account_type == "checking"
        assert config.statement_frequency == "monthly"
        assert config.source_directory == "data/bank_statements/usaa"
        assert config.download_instructions == "Download from usaa.com"
        assert len(config.import_patterns) == 2
        assert isinstance(config.import_patterns, tuple)
        assert config.import_patterns[0].pattern == "statement_*.csv"
        assert config.import_patterns[1].format_handler == "usaa_checking_csv_v2"

    def test_immutable(self):
        """Test AccountConfig is immutable."""
        config = AccountConfig(
            ynab_account_id="acc_123",
            ynab_account_name="Test",
            slug="test",
            bank_name="Test Bank",
            account_type="checking",
            statement_frequency="monthly",
            source_directory="data/test",
            download_instructions="Test instructions",
            import_patterns=(),
        )

        with pytest.raises(AttributeError):
            config.slug = "new-slug"  # type: ignore[misc]


class TestBankAccountsConfig:
    """Tests for BankAccountsConfig model."""

    def test_creation(self):
        """Test BankAccountsConfig creation with multiple accounts."""
        account1 = AccountConfig(
            ynab_account_id="acc_1",
            ynab_account_name="Account 1",
            slug="account-1",
            bank_name="Bank A",
            account_type="checking",
            statement_frequency="monthly",
            source_directory="data/account1",
            download_instructions="Instructions 1",
            import_patterns=(ImportPattern(pattern="*.csv", format_handler="handler1"),),
        )
        account2 = AccountConfig(
            ynab_account_id="acc_2",
            ynab_account_name="Account 2",
            slug="account-2",
            bank_name="Bank B",
            account_type="credit",
            statement_frequency="monthly",
            source_directory="data/account2",
            download_instructions="Instructions 2",
            import_patterns=(ImportPattern(pattern="*.csv", format_handler="handler2"),),
        )

        config = BankAccountsConfig(accounts=(account1, account2))

        assert len(config.accounts) == 2
        assert config.accounts[0].slug == "account-1"
        assert config.accounts[1].slug == "account-2"

    def test_to_dict(self):
        """Test BankAccountsConfig serialization with nested structures."""
        account = AccountConfig(
            ynab_account_id="acc_123",
            ynab_account_name="Test Account",
            slug="test",
            bank_name="Test Bank",
            account_type="checking",
            statement_frequency="monthly",
            source_directory="data/test",
            download_instructions="Test instructions",
            import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_handler"),),
        )
        config = BankAccountsConfig(accounts=(account,))

        result = config.to_dict()

        assert result == {
            "accounts": [
                {
                    "ynab_account_id": "acc_123",
                    "ynab_account_name": "Test Account",
                    "slug": "test",
                    "bank_name": "Test Bank",
                    "account_type": "checking",
                    "statement_frequency": "monthly",
                    "source_directory": "data/test",
                    "download_instructions": "Test instructions",
                    "import_patterns": [
                        {
                            "pattern": "*.csv",
                            "format_handler": "test_handler",
                        }
                    ],
                }
            ]
        }

    def test_from_dict(self):
        """Test BankAccountsConfig deserialization with nested structures."""
        data = {
            "accounts": [
                {
                    "ynab_account_id": "acc_1",
                    "ynab_account_name": "Account 1",
                    "slug": "account-1",
                    "bank_name": "Bank A",
                    "account_type": "checking",
                    "statement_frequency": "monthly",
                    "source_directory": "data/account1",
                    "download_instructions": "Instructions 1",
                    "import_patterns": [{"pattern": "*.csv", "format_handler": "handler1"}],
                },
                {
                    "ynab_account_id": "acc_2",
                    "ynab_account_name": "Account 2",
                    "slug": "account-2",
                    "bank_name": "Bank B",
                    "account_type": "credit",
                    "statement_frequency": "monthly",
                    "source_directory": "data/account2",
                    "download_instructions": "Instructions 2",
                    "import_patterns": [{"pattern": "*.csv", "format_handler": "handler2"}],
                },
            ]
        }

        config = BankAccountsConfig.from_dict(data)

        assert len(config.accounts) == 2
        assert isinstance(config.accounts, tuple)
        assert config.accounts[0].slug == "account-1"
        assert config.accounts[0].bank_name == "Bank A"
        assert config.accounts[1].slug == "account-2"
        assert config.accounts[1].bank_name == "Bank B"

    def test_empty(self):
        """Test BankAccountsConfig.empty() classmethod."""
        config = BankAccountsConfig.empty()

        assert len(config.accounts) == 0
        assert isinstance(config.accounts, tuple)

    def test_immutable(self):
        """Test BankAccountsConfig is immutable."""
        config = BankAccountsConfig(accounts=())

        with pytest.raises(AttributeError):
            config.accounts = ()  # type: ignore[misc]
