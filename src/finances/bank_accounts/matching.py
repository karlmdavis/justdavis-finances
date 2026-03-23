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
FUZZY_MATCH_CONFIDENCE_THRESHOLD = 0.75

# Known mismatches between YNAB payee names and bank merchant names.
# Maps normalized YNAB payee → string that scores well against the bank's merchant field.
# Covers two directions: YNAB shorter than bank (Direct Import abbreviates), and
# YNAB longer than bank (Apple Card truncates merchant names).
YNAB_PAYEE_EXPANSIONS: dict[str, str] = {
    "deposit": "daily cash deposit",  # Apple Savings: YNAB strips "Daily Cash" prefix
    "amazon kindle services": "kindle svcs",  # Chase Credit: Kindle subscription
    "expresscare urgent care centers": "express care of westminster",  # Apple Card truncates brand+location
    "children's urgent care of westminster": "children's urgent care",  # Apple Card truncates location suffix
    "canteen vending": "vending machine",  # Apple Card: bank reports hardware brand "Vending Machine", YNAB resolves to vendor "Canteen Vending"
    "canteen": "vending machine",  # Apple Card: some YNAB entries use abbreviated "Canteen" payee
    "uplift": "joinuplift.co",  # Apple Card: bank uses domain "joinuplift.co", YNAB resolves to short brand name "Uplift"
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
    id: str | None = None
    import_posted_date: FinancialDate | None = None

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
        if self.id is not None:
            result["id"] = self.id
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


def _by_posted_date(bank_tx: BankTransaction, ynab_txs: list[YnabTransaction]) -> list[YnabTransaction]:
    """Filter YNAB txs matching bank posted_date + amount (primary strategy)."""
    return [tx for tx in ynab_txs if tx.date == bank_tx.posted_date and tx.amount == bank_tx.amount]


def _by_transaction_date(bank_tx: BankTransaction, ynab_txs: list[YnabTransaction]) -> list[YnabTransaction]:
    """Fallback: try transaction_date when it differs from posted_date.

    Handles Apple Card 1-day offset where YNAB stores purchase date but bank CSV
    uses posted (clearing) date.
    """
    if bank_tx.transaction_date is None or bank_tx.transaction_date == bank_tx.posted_date:
        return []
    return [tx for tx in ynab_txs if tx.date == bank_tx.transaction_date and tx.amount == bank_tx.amount]


def _by_import_posted_date(
    bank_tx: BankTransaction, ynab_txs: list[YnabTransaction]
) -> list[YnabTransaction]:
    """Fallback: match via YNAB import_id's encoded clearing date.

    Handles manually-entered YNAB transactions later matched by Direct Import:
    the transaction's date field retains the manual entry date but import_id
    encodes the actual bank clearing date (format: YNAB:<amount>:<date>:<seq>).
    """
    return [
        tx for tx in ynab_txs if tx.import_posted_date == bank_tx.posted_date and tx.amount == bank_tx.amount
    ]


def _by_ynab_date_offset(
    bank_tx: BankTransaction, ynab_txs: list[YnabTransaction], ynab_date_offset_days: int
) -> list[YnabTransaction]:
    """Fallback: try posted_date adjusted by account-level YNAB date offset.

    Handles cases where YNAB uses a different date convention than the bank CSV
    (e.g., Apple Savings: YNAB uses earned date, bank uses deposited date, ~1 day offset).
    """
    if ynab_date_offset_days == 0:
        return []
    from datetime import timedelta

    offset_date = FinancialDate(date=bank_tx.posted_date.date + timedelta(days=ynab_date_offset_days))
    return [tx for tx in ynab_txs if tx.date == offset_date and tx.amount == bank_tx.amount]


def _by_transfer_window(bank_tx: BankTransaction, ynab_txs: list[YnabTransaction]) -> list[YnabTransaction]:
    """Fallback: ±5 day window for YNAB transfer entries.

    Handles YNAB initiation date vs bank clearing date offset (observed max: 4 days).
    Only applies to transactions marked as transfers in YNAB.
    """
    return [
        tx
        for tx in ynab_txs
        if tx.is_transfer and tx.amount == bank_tx.amount and abs(bank_tx.posted_date.age_days(tx.date)) <= 5
    ]


def _pick_best(bank_tx: BankTransaction, candidates: list[YnabTransaction]) -> MatchResult:
    """Resolve multiple candidates via fuzzy description matching."""
    scores: list[tuple[YnabTransaction, float]] = []
    for ynab_tx in candidates:
        # Prefer merchant field (clean, matches YNAB payee names) over verbose description
        bank_desc = normalize_description(bank_tx.merchant if bank_tx.merchant else bank_tx.description)
        # Use payee_name only — memo is user-annotated context and inflates the string
        # length, which drives SequenceMatcher scores below the threshold even when the
        # payee names are identical.
        ynab_desc = normalize_description(ynab_tx.payee_name or "")
        ynab_desc = YNAB_PAYEE_EXPANSIONS.get(ynab_desc, ynab_desc)  # expand if known abbreviation

        score = SequenceMatcher(None, bank_desc, ynab_desc).ratio()
        scores.append((ynab_tx, score))

    best_match, best_score = max(scores, key=lambda x: x[1])

    if best_score > FUZZY_MATCH_CONFIDENCE_THRESHOLD:
        return MatchResult(match_type="fuzzy", ynab_transaction=best_match, confidence=best_score)

    # Single-payee fallback: when all candidates share the same normalized payee name,
    # description similarity can't distinguish between them — claim the first one.
    # The greedy pool in the caller ensures each YNAB tx is claimed by at most one bank tx,
    # so this is safe even when there are N identical YNAB entries for N identical bank txs.
    unique_payees = {normalize_description(tx.payee_name or "") for tx, _ in scores}
    if len(unique_payees) == 1:
        return MatchResult(match_type="fuzzy", ynab_transaction=best_match, confidence=best_score)

    return MatchResult(
        match_type="ambiguous",
        candidates=tuple(tx for tx, _ in scores),
        similarity_scores=tuple(score for _, score in scores),
    )


def find_matches(
    bank_tx: BankTransaction, ynab_txs: list[YnabTransaction], ynab_date_offset_days: int = 0
) -> MatchResult:
    """
    Find YNAB transaction matching bank transaction.

    Waterfall of strategies (first non-empty result wins):
    1. posted_date + amount (primary)
    2. transaction_date + amount (Apple Card 1-day offset)
    3. import_posted_date + amount (YNAB Direct Import re-match of manual entries)
    4. posted_date + offset + amount (account-level date convention difference)
    5. transfer ±5 day window (YNAB initiation vs bank clearing date)

    Args:
        bank_tx: Bank transaction to match
        ynab_txs: List of YNAB transactions to search
        ynab_date_offset_days: Days to shift bank posted_date when searching YNAB.
            Used when YNAB uses a different date convention than the bank CSV
            (e.g., Apple Savings: YNAB uses earned date, bank uses deposited date).

    Returns:
        MatchResult with match_type and associated data
    """
    candidates = (
        _by_posted_date(bank_tx, ynab_txs)
        or _by_transaction_date(bank_tx, ynab_txs)
        or _by_import_posted_date(bank_tx, ynab_txs)
        or _by_ynab_date_offset(bank_tx, ynab_txs, ynab_date_offset_days)
        or _by_transfer_window(bank_tx, ynab_txs)
    )
    if not candidates:
        return MatchResult(match_type="none")
    if len(candidates) == 1:
        return MatchResult(match_type="exact", ynab_transaction=candidates[0], confidence=1.0)
    return _pick_best(bank_tx, candidates)
