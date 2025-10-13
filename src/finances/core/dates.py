#!/usr/bin/env python3
"""
FinancialDate Primitive Type

Immutable date wrapper with consistent formatting for financial operations.
Provides standardized date handling across YNAB, Amazon, and Apple data sources.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class FinancialDate:
    """Immutable financial date wrapper with consistent formatting."""

    date: date

    @classmethod
    def from_string(cls, date_str: str, format: str = "%Y-%m-%d") -> "FinancialDate":
        """
        Parse from string in specified format.

        Args:
            date_str: Date string to parse
            format: Date format (default: ISO format "%Y-%m-%d")

        Returns:
            FinancialDate object
        """
        return cls(date=datetime.strptime(date_str, format).date())

    @classmethod
    def from_timestamp(cls, timestamp: float) -> "FinancialDate":
        """
        Create from Unix timestamp.

        Args:
            timestamp: Unix timestamp (seconds since epoch)

        Returns:
            FinancialDate object
        """
        return cls(date=datetime.fromtimestamp(timestamp).date())

    @classmethod
    def today(cls) -> "FinancialDate":
        """Get today's date."""
        return cls(date=date.today())

    def to_iso_string(self) -> str:
        """Format as YYYY-MM-DD."""
        return self.date.isoformat()

    def to_ynab_format(self) -> str:
        """Format as YNAB expects (ISO format)."""
        return self.date.isoformat()

    def age_days(self, other: "FinancialDate | None" = None) -> int:
        """
        Calculate days between this date and another (or today).

        Args:
            other: Other date to compare to (default: today)

        Returns:
            Number of days difference
        """
        if other is None:
            other = FinancialDate.today()
        return (other.date - self.date).days

    def __str__(self) -> str:
        """String representation."""
        return self.to_iso_string()

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, FinancialDate):
            return NotImplemented
        return self.date == other.date

    def __lt__(self, other: "FinancialDate") -> bool:
        """Less than comparison."""
        return self.date < other.date

    def __le__(self, other: "FinancialDate") -> bool:
        """Less than or equal comparison."""
        return self.date <= other.date

    def __gt__(self, other: "FinancialDate") -> bool:
        """Greater than comparison."""
        return self.date > other.date

    def __ge__(self, other: "FinancialDate") -> bool:
        """Greater than or equal comparison."""
        return self.date >= other.date

    def __repr__(self) -> str:
        """Repr format."""
        return f"FinancialDate(date={self.date!r})"
