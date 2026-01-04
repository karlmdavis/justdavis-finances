"""Tests for bank account configuration loading and validation."""

import tempfile
from pathlib import Path

import pytest

from finances.bank_accounts.config import (
    ConfigValidationError,
    generate_config_stub,
    load_config,
    validate_config,
)
from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, ImportPattern
from finances.core.json_utils import write_json


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        """Test loading valid config from JSON file."""
        # Create valid config JSON
        config_data = {
            "accounts": [
                {
                    "ynab_account_id": "acc-123",
                    "ynab_account_name": "Chase Checking",
                    "slug": "chase-checking",
                    "bank_name": "Chase",
                    "account_type": "checking",
                    "statement_frequency": "monthly",
                    "source_directory": str(tmp_path),
                    "download_instructions": "Download from Chase website",
                    "import_patterns": [
                        {
                            "pattern": "*_transactions.csv",
                            "format_handler": "chase_checking_csv",
                        }
                    ],
                }
            ]
        }

        config_path = tmp_path / "config.json"
        write_json(config_path, config_data)

        # Load config
        config = load_config(config_path)

        # Verify loaded correctly
        assert isinstance(config, BankAccountsConfig)
        assert len(config.accounts) == 1
        assert config.accounts[0].slug == "chase-checking"
        assert config.accounts[0].ynab_account_id == "acc-123"
        assert config.accounts[0].account_type == "checking"
        assert len(config.accounts[0].import_patterns) == 1

    def test_load_config_missing_file(self, tmp_path: Path) -> None:
        """Test loading config from non-existent file raises FileNotFoundError."""
        config_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_config(config_path)


class TestValidateConfig:
    """Tests for validate_config() function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

        # YNAB accounts for validation
        self.ynab_accounts = {
            "acc-123": {"name": "Chase Checking", "type": "checking"},
            "acc-456": {"name": "Amex Credit", "type": "creditCard"},
        }

        # Available format handlers
        self.available_handlers = ["chase_checking_csv", "amex_credit_csv"]

    def test_validate_config_success(self) -> None:
        """Test validation succeeds for valid config."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        # Should not raise
        validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_todo_slug(self) -> None:
        """Test validation fails if slug is TODO_REQUIRED."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="TODO_REQUIRED",  # Invalid
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(ConfigValidationError, match="slug must not be 'TODO_REQUIRED'"):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_duplicate_slug(self) -> None:
        """Test validation fails for duplicate slugs."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
                AccountConfig(
                    ynab_account_id="acc-456",
                    ynab_account_name="Amex Credit",
                    slug="chase",  # Duplicate
                    bank_name="Amex",
                    account_type="credit",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Amex",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="amex_credit_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(ConfigValidationError, match="Duplicate slug 'chase'"):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_duplicate_ynab_account_id(self) -> None:
        """Test validation fails for duplicate YNAB account IDs."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
                AccountConfig(
                    ynab_account_id="acc-123",  # Duplicate
                    ynab_account_name="Chase Checking Duplicate",
                    slug="chase-checking-2",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(ConfigValidationError, match="Duplicate ynab_account_id 'acc-123'"):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_invalid_ynab_account(self) -> None:
        """Test validation fails if ynab_account_id doesn't exist in YNAB accounts."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-999",  # Not in ynab_accounts
                    ynab_account_name="Unknown Account",
                    slug="unknown",
                    bank_name="Unknown",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(
            ConfigValidationError, match="ynab_account_id 'acc-999' not found in YNAB accounts"
        ):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_invalid_account_type(self) -> None:
        """Test validation fails for invalid account_type."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="invalid_type",  # Invalid
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(
            ConfigValidationError,
            match="account_type must be one of: checking, credit, savings",
        ):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_invalid_statement_frequency(self) -> None:
        """Test validation fails for invalid statement_frequency."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="yearly",  # Invalid
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(
            ConfigValidationError,
            match="statement_frequency must be one of: daily, monthly",
        ):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_source_directory_not_exists(self) -> None:
        """Test validation fails if source_directory doesn't exist."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/nonexistent/path",  # Doesn't exist
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="chase_checking_csv",
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(ConfigValidationError, match="source_directory does not exist"):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_empty_import_patterns(self) -> None:
        """Test validation fails if import_patterns is empty."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(),  # Empty
                ),
            )
        )

        with pytest.raises(ConfigValidationError, match="import_patterns must not be empty"):
            validate_config(config, self.ynab_accounts, self.available_handlers)

    def test_validate_config_invalid_format_handler(self) -> None:
        """Test validation fails if format_handler doesn't exist."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acc-123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory=str(self.tmp_path),
                    download_instructions="Download from Chase",
                    import_patterns=(
                        ImportPattern(
                            pattern="*_transactions.csv",
                            format_handler="nonexistent_handler",  # Invalid
                        ),
                    ),
                ),
            )
        )

        with pytest.raises(
            ConfigValidationError,
            match="format_handler 'nonexistent_handler' not found in available handlers",
        ):
            validate_config(config, self.ynab_accounts, self.available_handlers)


class TestGenerateConfigStub:
    """Tests for generate_config_stub() function."""

    def test_generate_config_stub(self) -> None:
        """Test generating stub config from YNAB accounts."""
        ynab_accounts = {
            "acc-123": {"name": "Chase Checking", "type": "checking"},
            "acc-456": {"name": "Amex Credit", "type": "creditCard"},
            "acc-789": {"name": "Ally Savings", "type": "savings"},
            "acc-000": {"name": "Investment Account", "type": "investmentAccount"},
        }

        config = generate_config_stub(ynab_accounts)

        # Verify structure
        assert isinstance(config, BankAccountsConfig)
        assert len(config.accounts) == 4

        # Verify checking account
        checking = config.accounts[0]
        assert checking.ynab_account_id == "acc-123"
        assert checking.ynab_account_name == "Chase Checking"
        assert checking.account_type == "checking"
        assert checking.slug == "TODO_REQUIRED"
        assert checking.bank_name == "TODO_REQUIRED"
        assert checking.source_directory == "TODO_REQUIRED"
        assert checking.download_instructions == "TODO_REQUIRED"
        assert checking.import_patterns == ()

        # Verify credit account
        credit = config.accounts[1]
        assert credit.ynab_account_id == "acc-456"
        assert credit.ynab_account_name == "Amex Credit"
        assert credit.account_type == "credit"

        # Verify savings account
        savings = config.accounts[2]
        assert savings.ynab_account_id == "acc-789"
        assert savings.ynab_account_name == "Ally Savings"
        assert savings.account_type == "savings"

        # Verify unknown type
        unknown = config.accounts[3]
        assert unknown.ynab_account_id == "acc-000"
        assert unknown.ynab_account_name == "Investment Account"
        assert unknown.account_type == "TODO_REQUIRED"

    def test_generate_config_stub_empty_ynab_accounts(self) -> None:
        """Test generating stub config with no YNAB accounts."""
        config = generate_config_stub({})

        assert isinstance(config, BankAccountsConfig)
        assert len(config.accounts) == 0
