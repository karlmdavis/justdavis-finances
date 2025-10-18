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
    @pytest.mark.parametrize(
        "constructor,input_value,expected_cents,expected_str",
        [
            (Money.from_cents, -1234, -1234, "-$12.34"),
            (Money.from_milliunits, -12340, -1234, "-$12.34"),
            (Money.from_dollars, "-$12.34", -1234, "-$12.34"),
        ],
        ids=["from_cents", "from_milliunits", "from_dollars"],
    )
    def test_negative_amount_construction(self, constructor, input_value, expected_cents, expected_str):
        """Test creating negative Money from various constructors."""
        m = constructor(input_value)
        assert m.to_cents() == expected_cents
        assert str(m) == expected_str

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
    @pytest.mark.parametrize(
        "cents,milliunits,display_str",
        [
            (0, 0, "$0.00"),
            (100_000_000, 1_000_000_000, "$1,000,000.00"),
            (1_000_000_000, 10_000_000_000, "$10,000,000.00"),
        ],
        ids=["zero", "one_million", "ten_million"],
    )
    def test_money_edge_case_amounts(self, cents, milliunits, display_str):
        """Test Money handling of edge case amounts."""
        m_from_cents = Money.from_cents(cents)
        m_from_milliunits = Money.from_milliunits(milliunits)

        assert m_from_cents.to_cents() == cents
        assert m_from_milliunits.to_cents() == cents
        assert str(m_from_cents) == display_str

    @pytest.mark.currency
    def test_small_fractional_amounts(self):
        """Test very small fractional amounts."""
        # 1 milliunit = $0.001, rounds down to 0 cents
        tiny = Money.from_milliunits(9)
        assert tiny.to_cents() == 0

        # 10 milliunits = $0.01 (1 cent)
        penny = Money.from_milliunits(10)
        assert penny.to_cents() == 1
