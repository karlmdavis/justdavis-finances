#!/usr/bin/env python3
"""Tests for core data models with Money and FinancialDate."""

from datetime import date

from finances.core import FinancialDate, Money, Receipt, Transaction


class TestTransaction:
    """Test Transaction model."""

    def test_transaction_construction(self):
        """Test Transaction with Money and FinancialDate."""
        tx = Transaction(
            id="test-1",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            amount_money=Money.from_cents(1234),
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.amount_money.to_cents() == 1234
        assert tx.date_obj.date == date(2024, 1, 15)

    def test_transaction_from_dict_with_new_fields(self):
        """Test Transaction.from_dict with new field names."""
        tx = Transaction.from_dict({
            "id": "test-2",
            "date_obj": FinancialDate(date=date(2024, 1, 15)),
            "amount_money": Money.from_cents(-1234),
            "description": "Test transaction",
            "account_name": "Checking",
        })
        assert tx.amount_money.to_cents() == -1234
        assert tx.date_obj.date == date(2024, 1, 15)

    def test_transaction_from_dict_with_legacy_fields(self):
        """Test Transaction.from_dict with legacy field names (backward compat)."""
        tx = Transaction.from_dict({
            "id": "test-3",
            "date": date(2024, 1, 15),
            "amount": -12340,  # milliunits
            "description": "Test transaction",
            "account_name": "Checking",
        })
        assert tx.amount_money.to_cents() == -1234
        assert tx.date_obj.date == date(2024, 1, 15)

    def test_transaction_backward_compat_properties(self):
        """Test backward compatibility properties (date, amount)."""
        tx = Transaction(
            id="test-4",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            amount_money=Money.from_cents(1234),
            description="Test transaction",
            account_name="Checking",
        )
        # Properties should work for backward compatibility
        assert tx.date == date(2024, 1, 15)
        assert tx.amount == 12340  # milliunits
        assert tx.amount_dollars == "$12.34"


class TestReceipt:
    """Test Receipt model."""

    def test_receipt_construction(self):
        """Test Receipt with Money and FinancialDate."""
        receipt = Receipt(
            id="receipt-1",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            vendor="Test Vendor",
            total_money=Money.from_cents(1234),
            subtotal_money=Money.from_cents(1000),
            tax_money=Money.from_cents(234),
        )
        assert receipt.total_money.to_cents() == 1234
        assert receipt.subtotal_money.to_cents() == 1000
        assert receipt.tax_money.to_cents() == 234
        assert receipt.date_obj.date == date(2024, 1, 15)

    def test_receipt_from_dict_with_new_fields(self):
        """Test Receipt.from_dict with new field names."""
        receipt = Receipt.from_dict({
            "id": "receipt-2",
            "date_obj": FinancialDate(date=date(2024, 1, 15)),
            "vendor": "Test Vendor",
            "total_money": Money.from_cents(1234),
        })
        assert receipt.total_money.to_cents() == 1234
        assert receipt.date_obj.date == date(2024, 1, 15)

    def test_receipt_from_dict_with_legacy_fields(self):
        """Test Receipt.from_dict with legacy field names (backward compat)."""
        receipt = Receipt.from_dict({
            "id": "receipt-3",
            "date": date(2024, 1, 15),
            "vendor": "Test Vendor",
            "total_amount": 1234,  # cents
            "subtotal": 1000,
            "tax_amount": 234,
        })
        assert receipt.total_money.to_cents() == 1234
        assert receipt.subtotal_money.to_cents() == 1000
        assert receipt.tax_money.to_cents() == 234
        assert receipt.date_obj.date == date(2024, 1, 15)

    def test_receipt_backward_compat_properties(self):
        """Test backward compatibility properties."""
        receipt = Receipt(
            id="receipt-4",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            vendor="Test Vendor",
            total_money=Money.from_cents(1234),
            subtotal_money=Money.from_cents(1000),
            tax_money=Money.from_cents(234),
        )
        # Properties should work for backward compatibility
        assert receipt.date == date(2024, 1, 15)
        assert receipt.total_amount == 1234  # cents
        assert receipt.subtotal == 1000
        assert receipt.tax_amount == 234
        assert receipt.total_dollars == "$12.34"
