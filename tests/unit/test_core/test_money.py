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


class TestMoneyFormatting:
    """Test Money string formatting."""

    @pytest.mark.currency
    def test_str_format(self):
        """Test Money string representation."""
        m = Money.from_cents(1234)
        assert str(m) == "$12.34"

    @pytest.mark.currency
    def test_repr_format(self):
        """Test Money repr."""
        m = Money.from_cents(1234)
        assert repr(m) == "Money(cents=1234)"


class TestMoneyImmutability:
    """Test Money immutability."""

    @pytest.mark.currency
    def test_frozen_dataclass(self):
        """Test Money is immutable."""
        m = Money.from_cents(100)
        with pytest.raises(AttributeError):
            m.cents = 200  # type: ignore
