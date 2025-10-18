#!/usr/bin/env python3
"""Tests for Money primitive type."""

import pytest

from finances.core.money import Money


class TestMoneyConstruction:
    """Test Money class construction."""

    @pytest.mark.currency
    def test_from_cents(self):
        """Test creating Money from cents."""
        m = Money.from_cents(1234)
        assert m.to_cents() == 1234

    @pytest.mark.currency
    def test_from_milliunits(self):
        """Test creating Money from YNAB milliunits."""
        m = Money.from_milliunits(12340)  # $12.34
        assert m.to_cents() == 1234

    @pytest.mark.currency
    def test_from_dollars_string(self):
        """Test parsing from dollar strings."""
        m = Money.from_dollars("$12.34")
        assert m.to_cents() == 1234

        m2 = Money.from_dollars("12.34")
        assert m2.to_cents() == 1234

    @pytest.mark.currency
    def test_from_dollars_int(self):
        """Test creating from integer dollars."""
        m = Money.from_dollars(12)
        assert m.to_cents() == 1200


class TestMoneyArithmetic:
    """Test Money arithmetic operations."""

    @pytest.mark.currency
    def test_addition(self):
        """Test adding Money objects."""
        a = Money.from_cents(100)
        b = Money.from_cents(50)
        result = a + b
        assert result.to_cents() == 150

    @pytest.mark.currency
    def test_subtraction(self):
        """Test subtracting Money objects."""
        a = Money.from_cents(100)
        b = Money.from_cents(30)
        result = a - b
        assert result.to_cents() == 70

    @pytest.mark.currency
    def test_multiplication(self):
        """Test multiplying Money by scalar."""
        m = Money.from_cents(50)
        result = m * 3
        assert result.to_cents() == 150


class TestMoneyComparison:
    """Test Money comparison operations."""

    @pytest.mark.currency
    def test_equality(self):
        """Test Money equality."""
        a = Money.from_cents(100)
        b = Money.from_cents(100)
        c = Money.from_cents(50)

        assert a == b
        assert a != c

    @pytest.mark.currency
    def test_comparison(self):
        """Test Money ordering."""
        small = Money.from_cents(50)
        large = Money.from_cents(100)

        assert small < large
        assert large > small
        assert small <= Money.from_cents(50)
        assert large >= Money.from_cents(100)


class TestMoneyImmutability:
    """Test Money immutability."""

    @pytest.mark.currency
    def test_frozen_dataclass(self):
        """Test Money is immutable."""
        m = Money.from_cents(100)
        with pytest.raises(AttributeError):
            m.cents = 200  # type: ignore


class TestMoneyNegativeAmounts:
    """Test Money handling of negative amounts (expenses)."""

    @pytest.mark.currency
    def test_negative_from_cents(self):
        """Test creating negative Money from cents."""
        m = Money.from_cents(-1234)
        assert m.to_cents() == -1234
        assert str(m) == "-$12.34"

    @pytest.mark.currency
    def test_negative_from_milliunits(self):
        """Test negative milliunits (YNAB expenses) preserve sign."""
        # YNAB uses negative amounts for expenses/outflows
        expense = Money.from_milliunits(-45990)  # -$45.99 expense
        assert expense.to_cents() == -4599
        assert str(expense) == "-$45.99"

    @pytest.mark.currency
    def test_negative_from_dollars_string(self):
        """Test parsing negative dollar strings."""
        m = Money.from_dollars("-$12.34")
        assert m.to_cents() == -1234
        assert str(m) == "-$12.34"

    @pytest.mark.currency
    def test_negative_arithmetic(self):
        """Test arithmetic with negative amounts."""
        expense = Money.from_cents(-1000)  # -$10.00
        income = Money.from_cents(1500)  # +$15.00

        # Adding expense to income
        net = income + expense
        assert net.to_cents() == 500  # $5.00 net

        # Subtracting expense from income (double negative)
        result = income - expense
        assert result.to_cents() == 2500  # $25.00

    @pytest.mark.currency
    def test_negative_comparison(self):
        """Test comparisons with negative amounts."""
        expense = Money.from_cents(-1000)
        zero = Money.from_cents(0)
        income = Money.from_cents(1000)

        assert expense < zero < income
        assert expense < income
        assert income > expense

    @pytest.mark.currency
    def test_abs_method(self):
        """Test absolute value method."""
        expense = Money.from_cents(-1234)
        abs_expense = expense.abs()

        assert abs_expense.to_cents() == 1234
        assert str(abs_expense) == "$12.34"

        # abs() on positive amounts
        income = Money.from_cents(5678)
        abs_income = income.abs()
        assert abs_income.to_cents() == 5678

        # Zero abs
        zero = Money.from_cents(0)
        assert zero.abs().to_cents() == 0


class TestMoneyEdgeCases:
    """Test Money edge cases and boundary conditions."""

    @pytest.mark.currency
    def test_zero_amount(self):
        """Test zero amount handling."""
        zero = Money.from_cents(0)
        assert zero.to_cents() == 0
        assert zero.to_milliunits() == 0
        assert str(zero) == "$0.00"

        # Zero from milliunits
        zero_mu = Money.from_milliunits(0)
        assert zero_mu.to_cents() == 0

    @pytest.mark.currency
    def test_large_amounts(self):
        """Test handling of large financial amounts."""
        # $1 million
        million = Money.from_cents(100_000_000)
        assert million.to_cents() == 100_000_000
        assert str(million) == "$1,000,000.00"

        # $10 million
        ten_million = Money.from_milliunits(10_000_000_000)
        assert ten_million.to_cents() == 1_000_000_000
        assert str(ten_million) == "$10,000,000.00"

    @pytest.mark.currency
    def test_small_fractional_amounts(self):
        """Test very small fractional amounts."""
        # 1 milliunit = $0.001, rounds down to 0 cents
        tiny = Money.from_milliunits(9)
        assert tiny.to_cents() == 0

        # 10 milliunits = $0.01 (1 cent)
        penny = Money.from_milliunits(10)
        assert penny.to_cents() == 1
