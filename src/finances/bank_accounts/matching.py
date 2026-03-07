"""
Transaction matching algorithm for bank reconciliation.

Architecture:
    Three-tier matching strategy for pairing bank transactions with YNAB:
    1. Exact matching: Date + amount match (highest confidence)
    2. Fuzzy matching: SequenceMatcher on normalized descriptions
    3. Ambiguous: Multiple similar matches (requires manual review)

Configuration:
    FUZZY_MATCH_CONFIDENCE_THRESHOLD: 0.8 (configurable)
        - Scores above threshold → fuzzy match
        - Scores below threshold → ambiguous (manual review)

Normalization:
    - Removes all digits and special characters
    - Converts to lowercase
    - Normalizes whitespace
    - Example: "AMAZON.COM*XX1234" → "amazoncom"

YNAB Payee Expansion:
    YNAB Direct Import sometimes abbreviates payee names relative to the bank's
    description.
    YNAB_PAYEE_EXPANSIONS maps the normalized YNAB abbreviation to the bank's full
    description so fuzzy scoring compares equal strings.
    Example: YNAB "Deposit" → expanded to "daily cash deposit" to match Apple Savings
      bank CSV.

Usage:
    result = find_matches(bank_tx, ynab_txs)
    if result.match_type == "exact":
        # High confidence - single match with date+amount
    elif result.match_type == "fuzzy":
        # Good confidence - description similarity above threshold
    elif result.match_type == "ambiguous":
        # Low confidence - multiple candidates or low scores
    else:  # "none"
        # No YNAB transaction found - create new

Performance:
    - O(n) for exact matching (filter by date+amount)
    - O(n*m) for fuzzy matching (compare descriptions)
    - Optimized for typical case: 1-100 transactions per reconciliation
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money

# Fuzzy matching configuration
FUZZY_MATCH_CONFIDENCE_THRESHOLD = 0.8

# Known cases where YNAB Direct Import uses a shorter payee name than the bank description.
# Expanding the YNAB side preserves the bank's more specific description as the reference.
YNAB_PAYEE_EXPANSIONS: dict[str, str] = {
    "deposit": "daily cash deposit",  # Apple Savings: YNAB strips "Daily Cash" prefix
    "amazon kindle services": "kindle svcs",  # Chase Credit: Kindle subscription
}


@dataclass(frozen=True)
class YnabTransaction:
    """Minimal YNAB transaction model for matching (temporary)."""

    date: FinancialDate
    amount: Money
    payee_name: str | None = None
    memo: str | None = None
    account_id: str | None = None
    is_transfer: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        result = {
            "date": str(self.date),
            "amount_milliunits": self.amount.to_milliunits(),
        }
        if self.payee_name is not None:
            result["payee_name"] = self.payee_name
        if self.memo is not None:
            result["memo"] = self.memo
        if self.account_id is not None:
            result["account_id"] = self.account_id
        return result


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a transaction."""

    match_type: str  # "exact", "fuzzy", "ambiguous", "none"
    ynab_transaction: YnabTransaction | None = None
    confidence: float | None = None  # 0.0-1.0
    candidates: tuple[YnabTransaction, ...] | None = None
    similarity_scores: tuple[float, ...] | None = None


def normalize_description(text: str) -> str:
    """
    Normalize description for fuzzy matching.

    Removes digits, converts to lowercase, and normalizes whitespace.
    """
    # Lowercase
    text = text.lower()
    # Remove all digits
    text = re.sub(r"\d+", "", text)
    # Normalize spaces (multiple spaces to single space)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_matches(
    bank_tx: BankTransaction, ynab_txs: list[YnabTransaction], ynab_date_offset_days: int = 0
) -> MatchResult:
    """
    Find YNAB transaction matching bank transaction.

    Strategy:
    1. Filter YNAB txs by exact date + amount
    2. If unique match → return exact match
    3. If multiple matches → fuzzy match by description similarity
    4. If no matches → return none

    Args:
        bank_tx: Bank transaction to match
        ynab_txs: List of YNAB transactions to search
        ynab_date_offset_days: Days to shift bank posted_date when searching YNAB.
            Used when YNAB uses a different date convention than the bank CSV
            (e.g., Apple Savings: YNAB uses earned date, bank uses deposited date).

    Returns:
        MatchResult with match_type and associated data
    """
    # Filter by posted_date + amount (primary)
    candidates = [tx for tx in ynab_txs if tx.date == bank_tx.posted_date and tx.amount == bank_tx.amount]

    # Fallback: try transaction_date when it differs from posted_date
    if (
        len(candidates) == 0
        and bank_tx.transaction_date is not None
        and bank_tx.transaction_date != bank_tx.posted_date
    ):
        candidates = [
            tx for tx in ynab_txs if tx.date == bank_tx.transaction_date and tx.amount == bank_tx.amount
        ]

    # Fallback: try posted_date adjusted by account-level YNAB date offset
    # Handles cases where YNAB uses a different date convention than the bank CSV
    # (e.g., Apple Savings: YNAB uses earned date, bank uses deposited date, ~1 day offset)
    if len(candidates) == 0 and ynab_date_offset_days != 0:
        from datetime import timedelta

        offset_date = FinancialDate(date=bank_tx.posted_date.date + timedelta(days=ynab_date_offset_days))
        candidates = [tx for tx in ynab_txs if tx.date == offset_date and tx.amount == bank_tx.amount]

    # Transfer fallback: ±5 day window for YNAB transfer entries
    # Handles YNAB initiation date vs bank clearing date offset (observed max: 4 days)
    if len(candidates) == 0:
        for ynab_tx in ynab_txs:
            if ynab_tx.is_transfer and ynab_tx.amount == bank_tx.amount:
                days_diff = abs(bank_tx.posted_date.age_days(ynab_tx.date))
                if days_diff <= 5:
                    candidates.append(ynab_tx)

    if len(candidates) == 0:
        return MatchResult(match_type="none")

    if len(candidates) == 1:
        return MatchResult(match_type="exact", ynab_transaction=candidates[0], confidence=1.0)

    # Multiple candidates - fuzzy match by description
    scores: list[tuple[YnabTransaction, float]] = []
    for ynab_tx in candidates:
        # Normalize descriptions
        bank_desc = normalize_description(bank_tx.description)
        # Combine payee_name and memo for better matching
        ynab_parts = []
        if ynab_tx.payee_name:
            ynab_parts.append(ynab_tx.payee_name)
        if ynab_tx.memo:
            ynab_parts.append(ynab_tx.memo)
        ynab_desc = normalize_description(" ".join(ynab_parts) if ynab_parts else "")
        ynab_desc = YNAB_PAYEE_EXPANSIONS.get(ynab_desc, ynab_desc)  # expand if known abbreviation

        # Calculate similarity using SequenceMatcher
        score = SequenceMatcher(None, bank_desc, ynab_desc).ratio()
        scores.append((ynab_tx, score))

    # Get best match
    best_match, best_score = max(scores, key=lambda x: x[1])

    if best_score > FUZZY_MATCH_CONFIDENCE_THRESHOLD:
        return MatchResult(match_type="fuzzy", ynab_transaction=best_match, confidence=best_score)
    else:
        return MatchResult(
            match_type="ambiguous",
            candidates=tuple(tx for tx, _ in scores),
            similarity_scores=tuple(score for _, score in scores),
        )
