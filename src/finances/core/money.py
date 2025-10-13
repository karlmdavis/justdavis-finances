#!/usr/bin/env python3
"""
Money Primitive Type

Immutable currency value wrapper that uses integer cents internally.
Prevents floating-point errors and provides type-safe currency operations.
"""

from dataclasses import dataclass

from .currency import (
    cents_to_dollars_str,
    cents_to_milliunits,
    parse_dollars_to_cents,
)


@dataclass(frozen=True)
class Money:
    """
    Immutable money value in cents (USD).

    Supports both positive (income/inflows) and negative (expense/outflows) amounts.
    Uses integer arithmetic throughout to prevent floating-point errors.

    Examples:
        >>> # Positive amounts (income/inflows)
        >>> income = Money.from_cents(1234)
        >>> str(income)
        '$12.34'

        >>> # Negative amounts (expenses/outflows)
        >>> expense = Money.from_milliunits(-45990)  # YNAB expense
        >>> str(expense)
        '$-45.99'
        >>> expense.to_cents()
        -4599

        >>> # Arithmetic with mixed signs
        >>> net = income + expense  # $12.34 + (-$45.99)
        >>> str(net)
        '$-33.65'

        >>> # Absolute value for display
        >>> expense.abs()
        Money(cents=4599)
    """

    cents: int

    @classmethod
    def from_cents(cls, cents: int) -> "Money":
        """Create Money from cents."""
        return cls(cents=cents)

    @classmethod
    def from_milliunits(cls, milliunits: int) -> "Money":
        """
        Create Money from YNAB milliunits.

        Preserves sign: negative milliunits (expenses) become negative cents.

        Args:
            milliunits: YNAB amount (1000 = $1.00, -1000 = -$1.00)

        Returns:
            Money object with sign preserved
        """
        return cls(cents=milliunits // 10)

    @classmethod
    def from_dollars(cls, dollars: str | int) -> "Money":
        """
        Parse from dollar string like '$123.45' or integer dollars.

        Args:
            dollars: String like "$12.34" or integer like 12

        Returns:
            Money object
        """
        if isinstance(dollars, int):
            return cls(cents=dollars * 100)
        return cls(cents=parse_dollars_to_cents(dollars))

    def to_cents(self) -> int:
        """Get value in cents."""
        return self.cents

    def to_milliunits(self) -> int:
        """Get value in YNAB milliunits."""
        return cents_to_milliunits(self.cents)

    def to_dollars(self) -> str:
        """Get formatted dollar string."""
        return str(self)

    def abs(self) -> "Money":
        """
        Return absolute value of Money.

        Useful for display purposes when sign doesn't matter.

        Returns:
            New Money object with absolute value
        """
        return Money(cents=abs(self.cents))

    def __add__(self, other: "Money") -> "Money":
        """Add two Money objects."""
        return Money(cents=self.cents + other.cents)

    def __sub__(self, other: "Money") -> "Money":
        """Subtract two Money objects."""
        return Money(cents=self.cents - other.cents)

    def __mul__(self, scalar: int) -> "Money":
        """Multiply Money by integer scalar."""
        return Money(cents=self.cents * scalar)

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents == other.cents

    def __lt__(self, other: "Money") -> bool:
        """Less than comparison."""
        return self.cents < other.cents

    def __le__(self, other: "Money") -> bool:
        """Less than or equal comparison."""
        return self.cents <= other.cents

    def __gt__(self, other: "Money") -> bool:
        """Greater than comparison."""
        return self.cents > other.cents

    def __ge__(self, other: "Money") -> bool:
        """Greater than or equal comparison."""
        return self.cents >= other.cents

    def __str__(self) -> str:
        """Format as dollar string."""
        return f"${cents_to_dollars_str(self.cents)}"

    def __repr__(self) -> str:
        """Repr format."""
        return f"Money(cents={self.cents})"
