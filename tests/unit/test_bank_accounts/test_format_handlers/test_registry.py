"""Tests for format handler registry."""

from pathlib import Path

import pytest

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry


class MockHandler(BankExportFormatHandler):
    """Mock handler for testing."""

    @property
    def format_name(self) -> str:
        return "mock_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path) -> ParseResult:
        return ParseResult.create(transactions=[], balance_points=[])


def test_register_handler():
    """Test registering a format handler."""
    registry = FormatHandlerRegistry()
    registry.register(MockHandler)

    assert "mock_csv" in registry.list_formats()


def test_get_handler():
    """Test retrieving a registered handler."""
    registry = FormatHandlerRegistry()
    registry.register(MockHandler)

    handler = registry.get("mock_csv")
    assert isinstance(handler, MockHandler)


def test_get_unknown_handler_raises():
    """Test that getting unknown handler raises KeyError."""
    registry = FormatHandlerRegistry()

    with pytest.raises(KeyError, match="Unknown format handler: unknown"):
        registry.get("unknown")


def test_list_formats_empty():
    """Test listing formats when registry is empty."""
    registry = FormatHandlerRegistry()
    assert registry.list_formats() == []


def test_list_formats_multiple():
    """Test listing multiple registered formats."""

    class AnotherMockHandler(BankExportFormatHandler):
        @property
        def format_name(self) -> str:
            return "another_csv"

        @property
        def supported_extensions(self) -> tuple[str, ...]:
            return (".csv",)

        def validate_file(self, file_path: Path) -> bool:
            return True

        def parse(self, file_path: Path) -> ParseResult:
            return ParseResult.create(transactions=[], balance_points=[])

    registry = FormatHandlerRegistry()
    registry.register(MockHandler)
    registry.register(AnotherMockHandler)

    formats = registry.list_formats()
    assert "mock_csv" in formats
    assert "another_csv" in formats
    assert len(formats) == 2
