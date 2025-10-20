#!/usr/bin/env python3
"""
Configuration Management for Davis Family Finances

Handles environment-based configuration with secure defaults and validation.
Supports multiple environments (development, test, production) with appropriate
security measures for each.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Environment(Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    # For local caching of YNAB data
    cache_dir: Path
    backup_enabled: bool = True
    backup_retention_days: int = 30


@dataclass
class YNABConfig:
    """YNAB API configuration."""

    api_token: str | None = None
    base_url: str = "https://api.youneedabudget.com/v1"
    timeout: int = 30
    rate_limit_delay: float = 0.5  # Seconds between API calls


@dataclass
class EmailConfig:
    """Email configuration for receipt fetching."""

    # Apple receipt email settings
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    username: str | None = None
    password: str | None = None
    use_oauth: bool = False


@dataclass
class AmazonConfig:
    """Amazon data processing configuration."""

    data_dir: Path
    account_names: list = field(default_factory=lambda: ["karl", "erica"])
    file_patterns: list = field(default_factory=lambda: ["Retail.OrderHistory.*.csv"])


@dataclass
class AppleConfig:
    """Apple data processing configuration."""

    data_dir: Path
    receipt_cache_days: int = 90


@dataclass
class AnalysisConfig:
    """Analysis and reporting configuration."""

    output_dir: Path
    chart_width: int = 12
    chart_height: int = 8
    date_range_months: int = 12
    smoothing_window_days: int = 30


@dataclass
class Config:
    """
    Main configuration class for the finances application.

    Loads configuration from environment variables with secure defaults
    and validation for each environment type.
    """

    environment: Environment

    # Core directories
    data_dir: Path
    cache_dir: Path
    output_dir: Path

    # Component configurations
    database: DatabaseConfig
    ynab: YNABConfig
    email: EmailConfig
    amazon: AmazonConfig
    apple: AppleConfig
    analysis: AnalysisConfig

    # Application settings
    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> "Config":
        """Create configuration from environment variables."""
        env = Environment(os.getenv("FINANCES_ENV", "development"))

        # Base directories
        if env == Environment.TEST:
            default_test_dir = Path(tempfile.gettempdir()) / "test_finances"
            base_dir = Path(os.getenv("FINANCES_DATA_DIR", str(default_test_dir)))
        else:
            base_dir = Path(os.getenv("FINANCES_DATA_DIR", "./data")).expanduser().resolve()

        data_dir = base_dir
        cache_dir = data_dir / "cache"
        output_dir = data_dir / "analysis"

        # Ensure directories exist
        for directory in [data_dir, cache_dir, output_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Component configurations
        database = DatabaseConfig(
            cache_dir=data_dir / "ynab" / "cache",
            backup_enabled=env != Environment.TEST,
        )

        ynab = YNABConfig(
            api_token=os.getenv("YNAB_API_TOKEN"),
            timeout=int(os.getenv("YNAB_TIMEOUT", "30")),
        )

        email = EmailConfig(
            imap_server=os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com"),
            imap_port=int(os.getenv("EMAIL_IMAP_PORT", "993")),
            username=os.getenv("EMAIL_USERNAME"),
            password=os.getenv("EMAIL_PASSWORD"),
            use_oauth=os.getenv("EMAIL_USE_OAUTH", "false").lower() == "true",
        )

        amazon = AmazonConfig(
            data_dir=data_dir / "amazon",
            account_names=_parse_list(os.getenv("AMAZON_ACCOUNTS", "karl,erica")),
        )

        apple = AppleConfig(
            data_dir=data_dir / "apple",
            receipt_cache_days=int(os.getenv("APPLE_CACHE_DAYS", "90")),
        )

        analysis = AnalysisConfig(
            output_dir=data_dir / "cash_flow" / "charts",
            chart_width=int(os.getenv("CHART_WIDTH", "12")),
            chart_height=int(os.getenv("CHART_HEIGHT", "8")),
            date_range_months=int(os.getenv("ANALYSIS_MONTHS", "12")),
            smoothing_window_days=int(os.getenv("SMOOTHING_DAYS", "30")),
        )

        return cls(
            environment=env,
            data_dir=data_dir,
            cache_dir=cache_dir,
            output_dir=output_dir,
            database=database,
            ynab=ynab,
            email=email,
            amazon=amazon,
            apple=apple,
            analysis=analysis,
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> list:
        """Validate configuration and return list of errors."""
        errors = []

        # Check required directories
        for name, path in [
            ("data_dir", self.data_dir),
            ("cache_dir", self.cache_dir),
            ("output_dir", self.output_dir),
        ]:
            if not path.exists():
                errors.append(f"{name} does not exist: {path}")

        # Check YNAB configuration for production
        if self.environment == Environment.PRODUCTION and not self.ynab.api_token:
            errors.append("YNAB_API_TOKEN is required in production")

        # Check email configuration if needed
        if self.email.username and not self.email.password and not self.email.use_oauth:
            errors.append("EMAIL_PASSWORD is required when EMAIL_USERNAME is provided")

        # Validate numeric values
        try:
            if self.ynab.timeout <= 0:
                errors.append("YNAB timeout must be positive")
            if self.email.imap_port <= 0 or self.email.imap_port > 65535:
                errors.append("Email IMAP port must be 1-65535")
            if self.apple.receipt_cache_days < 0:
                errors.append("Apple receipt cache days must be non-negative")
        except (ValueError, TypeError) as e:
            errors.append(f"Invalid numeric configuration: {e}")

        return errors

    def setup_logging(self) -> None:
        """Configure logging based on configuration."""
        level = getattr(logging, self.log_level, logging.INFO)

        # Configure format based on environment
        if self.environment == Environment.DEVELOPMENT:
            format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        else:
            format_str = "%(asctime)s - %(levelname)s - %(message)s"

        logging.basicConfig(level=level, format=format_str, datefmt="%Y-%m-%d %H:%M:%S")

        # Reduce noise from external libraries in production
        if self.environment == Environment.PRODUCTION:
            logging.getLogger("urllib3").setLevel(logging.WARNING)
            logging.getLogger("requests").setLevel(logging.WARNING)

    def get_sensitive_fields(self) -> list:
        """Get list of field names that contain sensitive data."""
        return [
            "ynab.api_token",
            "email.password",
            "email.username",
        ]

    def to_dict(self, include_sensitive: bool = False) -> dict[str, Any]:
        """Convert configuration to dictionary, optionally excluding sensitive data."""
        result: dict[str, Any] = {}

        # Convert dataclass fields to dict
        for field_name, field_value in self.__dict__.items():
            if hasattr(field_value, "__dict__"):
                # Nested dataclass
                nested_dict: dict[str, Any] = {}
                for nested_name, nested_value in field_value.__dict__.items():
                    full_field_name = f"{field_name}.{nested_name}"

                    if not include_sensitive and full_field_name in self.get_sensitive_fields():
                        nested_dict[nested_name] = "***REDACTED***"
                    elif isinstance(nested_value, Path):
                        nested_dict[nested_name] = str(nested_value)
                    elif isinstance(nested_value, Enum):
                        nested_dict[nested_name] = nested_value.value
                    else:
                        nested_dict[nested_name] = nested_value

                result[field_name] = nested_dict
            elif isinstance(field_value, Path):
                result[field_name] = str(field_value)
            elif isinstance(field_value, Enum):
                result[field_name] = field_value.value
            else:
                result[field_name] = field_value

        return result


def _parse_list(value: str, delimiter: str = ",") -> list:
    """Parse comma-separated string into list, handling empty values."""
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter) if item.strip()]


# Global configuration instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_environment()

        # Validate configuration
        errors = _config.validate()
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        # Setup logging
        _config.setup_logging()

    return _config


def reload_config() -> Config:
    """Reload configuration from environment (useful for testing)."""
    global _config
    _config = None
    return get_config()


# Convenience functions
def get_data_dir() -> Path:
    """Get the data directory path."""
    return get_config().data_dir


def get_cache_dir() -> Path:
    """Get the cache directory path."""
    return get_config().cache_dir


def get_output_dir() -> Path:
    """Get the output directory path."""
    return get_config().output_dir


def is_development() -> bool:
    """Check if running in development environment."""
    return get_config().environment == Environment.DEVELOPMENT


def is_test() -> bool:
    """Check if running in test environment."""
    return get_config().environment == Environment.TEST


def is_production() -> bool:
    """Check if running in production environment."""
    return get_config().environment == Environment.PRODUCTION
