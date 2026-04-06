"""Configuration loading and validation for bank accounts."""

from pathlib import Path
from typing import Any

from finances.bank_accounts.models import AccountConfig, BankAccountsConfig
from finances.core.json_utils import read_json


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""

    pass


def load_config(config_path: Path) -> BankAccountsConfig:
    """Load BankAccountsConfig from JSON file.

    Args:
        config_path: Path to configuration JSON file

    Returns:
        Loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    try:
        data = read_json(config_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}") from None
    return BankAccountsConfig.from_dict(data)


def validate_config(
    config: BankAccountsConfig,
    ynab_accounts: dict[str, dict[str, Any]],
    available_handlers: list[str],
) -> None:
    """Validate bank accounts configuration.

    Args:
        config: Configuration to validate
        ynab_accounts: Dict mapping YNAB account IDs to account info
        available_handlers: List of available format handler names

    Raises:
        ConfigValidationError: If validation fails with specific error message
    """
    # Track unique values
    slugs_seen: set[str] = set()
    ynab_ids_seen: set[str] = set()

    for account in config.accounts:
        # Validate slug
        if account.slug == "TODO_REQUIRED":
            raise ConfigValidationError(
                f"Account '{account.ynab_account_name}': slug must not be 'TODO_REQUIRED'"
            )

        if account.slug in slugs_seen:
            raise ConfigValidationError(f"Duplicate slug '{account.slug}' found")

        slugs_seen.add(account.slug)

        # Validate YNAB account ID
        if account.ynab_account_id in ynab_ids_seen:
            raise ConfigValidationError(f"Duplicate ynab_account_id '{account.ynab_account_id}' found")

        ynab_ids_seen.add(account.ynab_account_id)

        if account.ynab_account_id not in ynab_accounts:
            raise ConfigValidationError(
                f"Account '{account.slug}': ynab_account_id '{account.ynab_account_id}' "
                f"not found in YNAB accounts"
            )

        # Validate source_directory exists
        source_path = Path(account.source_directory).expanduser()
        if not source_path.exists():
            raise ConfigValidationError(
                f"Account '{account.slug}': source_directory does not exist: " f"{account.source_directory}"
            )

        # Validate import_patterns not empty
        if len(account.import_patterns) == 0:
            raise ConfigValidationError(f"Account '{account.slug}': import_patterns must not be empty")

        # Validate format handlers exist
        for pattern in account.import_patterns:
            if pattern.format_handler not in available_handlers:
                raise ConfigValidationError(
                    f"Account '{account.slug}': format_handler '{pattern.format_handler}' "
                    f"not found in available handlers"
                )


def generate_config_stub(ynab_accounts: dict[str, dict[str, Any]]) -> BankAccountsConfig:
    """Generate stub configuration from YNAB accounts.

    Creates a configuration with TODO_REQUIRED placeholders for user to fill in.
    Infers account_type from YNAB account type where possible.

    Args:
        ynab_accounts: Dict mapping YNAB account IDs to account info
                      Expected format: {account_id: {"name": ..., "type": ...}}

    Returns:
        Stub configuration with TODO_REQUIRED placeholders
    """
    # Map YNAB types to our account types
    type_mapping = {
        "creditCard": "credit",
        "checking": "checking",
        "savings": "savings",
    }

    accounts: list[AccountConfig] = []

    for account_id, account_info in ynab_accounts.items():
        # Infer account_type from YNAB type
        ynab_type = account_info.get("type", "")
        account_type = type_mapping.get(ynab_type, "TODO_REQUIRED")

        account = AccountConfig(
            ynab_account_id=account_id,
            ynab_account_name=account_info["name"],
            slug="TODO_REQUIRED",
            bank_name="TODO_REQUIRED",
            account_type=account_type,
            statement_frequency="monthly",  # Default to monthly
            source_directory="TODO_REQUIRED",
            download_instructions="TODO_REQUIRED",
            import_patterns=(),  # Empty tuple - user must add patterns
        )

        accounts.append(account)

    return BankAccountsConfig(accounts=tuple(accounts))
