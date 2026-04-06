"""Tests for bank account configuration models."""

from pathlib import Path

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
            "ynab_date_offset_days": 0,
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
                    "ynab_date_offset_days": 0,
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

    def test_load_creates_stub_when_config_missing_and_ynab_cache_exists(
        self, tmp_path: Path, capsys, monkeypatch
    ):
        """Test that load() creates stub config when file doesn't exist and YNAB cache is available."""
        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        ynab_cache_dir = data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Create YNAB accounts cache
        ynab_accounts = {
            "accounts": [
                {
                    "id": "acc-123",
                    "name": "Chase Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 100000,
                    "cleared_balance": 100000,
                    "uncleared_balance": 0,
                },
                {
                    "id": "acc-456",
                    "name": "Apple Card",
                    "type": "creditCard",
                    "on_budget": True,
                    "closed": False,
                    "balance": -50000,
                    "cleared_balance": -50000,
                    "uncleared_balance": 0,
                },
                {
                    "id": "acc-789",
                    "name": "Closed Account",
                    "type": "checking",
                    "on_budget": True,
                    "closed": True,  # Should be excluded
                    "balance": 0,
                    "cleared_balance": 0,
                    "uncleared_balance": 0,
                },
            ]
        }

        from finances.core.json_utils import write_json

        write_json(ynab_cache_dir / "accounts.json", ynab_accounts)

        # Set environment variables
        monkeypatch.setenv("FINANCES_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))

        # Load config (should create stub)
        config = BankAccountsConfig.load()

        # Verify empty config returned (user needs to edit stub first)
        assert len(config.accounts) == 0

        # Verify stub file was created
        stub_file = config_dir / "bank_accounts_config.json"
        assert stub_file.exists()

        # Verify stub contents
        from finances.core.json_utils import read_json

        stub_data = read_json(stub_file)
        assert "accounts" in stub_data
        assert len(stub_data["accounts"]) == 2  # Only non-closed, on-budget accounts

        # Verify first account (checking)
        acct1 = stub_data["accounts"][0]
        assert acct1["ynab_account_id"] == "acc-123"
        assert acct1["ynab_account_name"] == "Chase Checking"
        assert acct1["account_type"] == "checking"
        assert acct1["slug"] == "TODO_REQUIRED"
        assert acct1["bank_name"] == "TODO_REQUIRED"
        assert acct1["source_directory"] == "TODO_REQUIRED"
        assert acct1["import_patterns"] == []

        # Verify second account (credit)
        acct2 = stub_data["accounts"][1]
        assert acct2["ynab_account_id"] == "acc-456"
        assert acct2["ynab_account_name"] == "Apple Card"
        assert acct2["account_type"] == "credit"

        # Verify helpful message was printed
        captured = capsys.readouterr()
        assert "Created stub configuration" in captured.out
        assert str(stub_file) in captured.out
        assert "TODO_REQUIRED" in captured.out

    def test_load_does_not_create_stub_when_config_exists(self, tmp_path: Path, monkeypatch, capsys):
        """Test that load() does NOT create stub when config file already exists."""
        # Setup directories
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        data_dir = tmp_path / "data"
        ynab_cache_dir = data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Create existing config file
        existing_config = {
            "accounts": [
                {
                    "ynab_account_id": "existing-123",
                    "ynab_account_name": "Existing Account",
                    "slug": "existing-account",
                    "bank_name": "Existing Bank",
                    "account_type": "checking",
                    "statement_frequency": "monthly",
                    "source_directory": str(tmp_path / "downloads"),
                    "download_instructions": "Download from bank.com",
                    "import_patterns": [{"pattern": "*.csv", "format_handler": "test_csv"}],
                }
            ]
        }

        from finances.core.json_utils import write_json

        config_file = config_dir / "bank_accounts_config.json"
        write_json(config_file, existing_config)

        # Create YNAB accounts cache (should be ignored since config exists)
        ynab_accounts = {
            "accounts": [
                {
                    "id": "ynab-999",
                    "name": "Different Account",
                    "type": "savings",
                    "on_budget": True,
                    "closed": False,
                    "balance": 200000,
                    "cleared_balance": 200000,
                    "uncleared_balance": 0,
                }
            ]
        }
        write_json(ynab_cache_dir / "accounts.json", ynab_accounts)

        # Set environment variables
        monkeypatch.setenv("FINANCES_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))

        # Load config (should load existing, not create stub)
        config = BankAccountsConfig.load()

        # Verify existing config was loaded
        assert len(config.accounts) == 1
        assert config.accounts[0].ynab_account_id == "existing-123"
        assert config.accounts[0].slug == "existing-account"

        # Verify no stub creation message
        captured = capsys.readouterr()
        assert "Created stub configuration" not in captured.out

    def test_load_graceful_degradation_when_no_ynab_cache(self, tmp_path: Path, monkeypatch, capsys):
        """Test that load() returns empty config gracefully when neither config nor YNAB cache exists."""
        # Setup directories (no YNAB cache)
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"

        # Set environment variables
        monkeypatch.setenv("FINANCES_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))

        # Load config (should return empty gracefully)
        config = BankAccountsConfig.load()

        # Verify empty config returned
        assert len(config.accounts) == 0

        # Verify no stub file was created
        config_file = config_dir / "bank_accounts_config.json"
        assert not config_file.exists()

        # Verify no stub creation message
        captured = capsys.readouterr()
        assert "Created stub configuration" not in captured.out
