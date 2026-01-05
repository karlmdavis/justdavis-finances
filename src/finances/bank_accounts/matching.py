"""Transaction matching algorithm for bank reconciliation."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money

# Fuzzy matching configuration
FUZZY_MATCH_CONFIDENCE_THRESHOLD = 0.8


@dataclass(frozen=True)
class YnabTransaction:
    """Minimal YNAB transaction model for matching (temporary)."""

    date: FinancialDate
    amount: Money
    payee_name: str | None = None
    memo: str | None = None
    account_id: str | None = None


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


def find_matches(bank_tx: BankTransaction, ynab_txs: list[YnabTransaction]) -> MatchResult:
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

    Returns:
        MatchResult with match_type and associated data
    """
    # Filter by date + amount
    candidates = [tx for tx in ynab_txs if tx.date == bank_tx.posted_date and tx.amount == bank_tx.amount]

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
