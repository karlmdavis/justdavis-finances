#!/usr/bin/env python3
"""Tests for FinancialDate primitive type."""

from datetime import date, datetime

import pytest

from finances.core.dates import FinancialDate


class TestFinancialDateConstruction:
    """Test FinancialDate construction."""

    @pytest.mark.parametrize(
        "constructor,expected_date",
        [
            (lambda: FinancialDate(date=date(2024, 1, 15)), date(2024, 1, 15)),
            (lambda: FinancialDate.from_string("2024-01-15"), date(2024, 1, 15)),
            (lambda: FinancialDate.from_string("01/15/2024", date_format="%m/%d/%Y"), date(2024, 1, 15)),
            (
                lambda: FinancialDate.from_timestamp(datetime(2024, 1, 15, 12, 0, 0).timestamp()),
                date(2024, 1, 15),
            ),
        ],
        ids=["from_date", "from_string", "from_string_custom_format", "from_timestamp"],
    )
    def test_financial_date_construction(self, constructor, expected_date):
        """Test FinancialDate construction from various sources."""
        fd = constructor()
        assert fd.date == expected_date

    def test_today(self):
        """Test creating today's date."""
        fd = FinancialDate.today()
        assert fd.date == date.today()


class TestFinancialDateFormatting:
    """Test FinancialDate formatting."""

    def test_to_iso_string(self):
        """Test ISO format output."""
        fd = FinancialDate(date=date(2024, 1, 15))
        assert fd.to_iso_string() == "2024-01-15"

    def test_to_ynab_format(self):
        """Test YNAB format (same as ISO)."""
        fd = FinancialDate(date=date(2024, 1, 15))
        assert fd.to_ynab_format() == "2024-01-15"


class TestFinancialDateCalculations:
    """Test FinancialDate calculations."""

    def test_age_days_with_another_date(self):
        """Test calculating days between two dates."""
        old = FinancialDate(date=date(2024, 1, 1))
        new = FinancialDate(date=date(2024, 1, 11))
        assert old.age_days(new) == 10

    def test_age_days_to_today(self):
        """Test calculating age from date to today."""
        fd = FinancialDate(date=date.today())
        assert fd.age_days() == 0


class TestFinancialDateComparison:
    """Test FinancialDate comparison."""

    def test_equality(self):
        """Test date equality."""
        d1 = FinancialDate(date=date(2024, 1, 15))
        d2 = FinancialDate(date=date(2024, 1, 15))
        d3 = FinancialDate(date=date(2024, 1, 16))

        assert d1 == d2
        assert d1 != d3

    def test_ordering(self):
        """Test date ordering."""
        early = FinancialDate(date=date(2024, 1, 1))
        late = FinancialDate(date=date(2024, 1, 15))

        assert early < late
        assert late > early


class TestFinancialDateImmutability:
    """Test FinancialDate immutability."""

    def test_frozen_dataclass(self):
        """Test FinancialDate is immutable."""
        fd = FinancialDate(date=date(2024, 1, 15))
        with pytest.raises(AttributeError):
            fd.date = date(2024, 1, 16)  # type: ignore
