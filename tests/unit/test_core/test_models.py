#!/usr/bin/env python3
"""Tests for core data models with Money and FinancialDate integration."""

from datetime import date

from finances.core import FinancialDate, Money, Receipt, Transaction


class TestTransactionWithMoney:
    """Test Transaction integration with Money type."""

    def test_transaction_with_money_object(self):
        """Test Transaction with explicit Money amount."""
        tx = Transaction(
            id="test-1",
            date=date(2024, 1, 15),
            amount=0,  # Will be sync'd from amount_money
            amount_money=Money.from_cents(1234),
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.amount_money.to_cents() == 1234
        assert tx.amount == 12340  # Auto-synced to milliunits

    def test_transaction_auto_creates_money_from_milliunits(self):
        """Test Transaction auto-creates Money from legacy milliunits with sign preservation."""
        tx = Transaction(
            id="test-2",
            date=date(2024, 1, 15),
            amount=-12340,  # Negative milliunits (expense)
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.amount_money is not None
        assert tx.amount_money.to_cents() == -1234  # Sign preserved
        assert tx.amount == -12340  # Legacy field preserved

    def test_transaction_amount_dollars_property(self):
        """Test amount_dollars property uses Money if available."""
        tx = Transaction(
            id="test-3",
            date=date(2024, 1, 15),
            amount=0,
            amount_money=Money.from_cents(1234),
            description="Test",
            account_name="Checking",
        )
        assert tx.amount_dollars == "$12.34"


class TestTransactionWithFinancialDate:
    """Test Transaction integration with FinancialDate type."""

    def test_transaction_with_financial_date_object(self):
        """Test Transaction with explicit FinancialDate."""
        fd = FinancialDate(date=date(2024, 1, 15))
        tx = Transaction(
            id="test-1",
            date_obj=fd,
            date=date(2024, 1, 15),
            amount=12340,
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.date_obj is not None
        assert tx.date_obj.to_iso_string() == "2024-01-15"
        assert tx.date == date(2024, 1, 15)

    def test_transaction_auto_creates_financial_date_from_date(self):
        """Test Transaction auto-creates FinancialDate from legacy date."""
        tx = Transaction(
            id="test-2",
            date=date(2024, 1, 15),
            amount=12340,
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.date_obj is not None
        assert tx.date_obj.date == date(2024, 1, 15)


class TestReceiptWithMoney:
    """Test Receipt integration with Money type."""

    def test_receipt_with_money_objects(self):
        """Test Receipt with explicit Money amounts."""
        receipt = Receipt(
            id="receipt-1",
            date=date(2024, 1, 15),
            vendor="Test Vendor",
            total_amount=0,
            total_money=Money.from_cents(1234),
            subtotal_money=Money.from_cents(1000),
            tax_money=Money.from_cents(234),
        )
        assert receipt.total_money.to_cents() == 1234
        assert receipt.subtotal_money.to_cents() == 1000
        assert receipt.tax_money.to_cents() == 234

    def test_receipt_auto_creates_money_from_cents(self):
        """Test Receipt auto-creates Money from legacy cents."""
        receipt = Receipt(
            id="receipt-2",
            date=date(2024, 1, 15),
            vendor="Test Vendor",
            total_amount=1234,  # Legacy cents
            subtotal=1000,
            tax_amount=234,
        )
        assert receipt.total_money is not None
        assert receipt.total_money.to_cents() == 1234
        assert receipt.subtotal_money.to_cents() == 1000
        assert receipt.tax_money.to_cents() == 234


class TestReceiptWithFinancialDate:
    """Test Receipt integration with FinancialDate type."""

    def test_receipt_auto_creates_financial_date(self):
        """Test Receipt auto-creates FinancialDate from legacy date."""
        receipt = Receipt(
            id="receipt-1",
            date=date(2024, 1, 15),
            vendor="Test Vendor",
            total_amount=1234,
        )
        assert receipt.date_obj is not None
        assert receipt.date_obj.date == date(2024, 1, 15)
