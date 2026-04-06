"""
Transaction matching algorithm for bank reconciliation.

Architecture:
    Six-strategy waterfall for candidate selection, then a resolution tier:

    Candidate selection (find_matches runs these in order; first non-empty result wins):
        0. _by_import_id         — UUID5 import_id exact match (immune to date offsets)
        1. _by_ynab_date_offset  — posted_date + account-level day offset + amount
        2. _by_posted_date       — posted_date + amount (primary for most accounts)
        3. _by_transaction_date  — transaction_date + amount (when it differs from posted)
        4. _by_import_posted_date — YNAB import_id clearing date + amount (re-match)
        5. _by_transfer_window   — ±5 day window for YNAB transfer entries

    Resolution tier (_pick_best applied to candidate set):
        Exact:     exactly one candidate
        Fuzzy:     highest SequenceMatcher score above FUZZY_MATCH_CONFIDENCE_THRESHOLD
        Ambiguous: multiple candidates with similar scores (requires manual review)

Configuration:
    FUZZY_MATCH_CONFIDENCE_THRESHOLD: 0.75 (configurable)
        - Scores above threshold → fuzzy match
        - Scores below threshold → ambiguous (manual review)

Normalization:
    - Converts to lowercase
    - Removes digits
    - Normalizes whitespace
    - Example: "AMAZON.COM*XX1234" → "amazon.com*xx"

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
import uuid
from dataclasses import dataclass
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Any, Literal

from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money

# Namespace UUID for deterministic import ID generation (bank reconciliation)
_IMPORT_ID_NS = uuid.UUID("86ac2fc2-b0ad-4834-9241-63c577a477b3")


def _is_uuid_format(s: str) -> bool:
    """Return True if s looks like a UUID (36 chars, dashes at positions 8/13/18/23)."""
    return len(s) == 36 and s[8] == "-" and s[13] == "-" and s[18] == "-" and s[23] == "-"


def make_import_id(
    slug: str, posted_date: str, amount_milliunits: int, description: str, seq: int = 0
) -> str:
    """
    Generate stable import ID for a bank transaction.

    Format: UUID v5 derived from bank:{slug}:{posted_date}:{amount_milliunits}:{description}
    For seq=0 the formula is identical to the historical _make_import_id in apply.py.
    For seq>=1 a ":{seq}" suffix is appended, producing a distinct UUID for the Nth
    occurrence of an otherwise-identical (date, amount, description) tuple — needed when
    the same payee charges the same amount twice on the same day.

    Always exactly 36 characters (YNAB API limit).
    Stable per bank transaction → applying is fully idempotent.
    The YNAB API rejects duplicate import-id values, preventing duplicate transactions.
    """
    if seq == 0:
        name = f"bank:{slug}:{posted_date}:{amount_milliunits}:{description}"
    else:
        name = f"bank:{slug}:{posted_date}:{amount_milliunits}:{description}:{seq}"
    return str(uuid.uuid5(_IMPORT_ID_NS, name))


# Fuzzy matching configuration
FUZZY_MATCH_CONFIDENCE_THRESHOLD = 0.75

# Maximum days between bank clearing date and YNAB initiation date for transfer matching
_TRANSFER_DATE_WINDOW_DAYS = 5

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
class MatchingYnabTransaction:
    """Minimal YNAB transaction model for matching."""

    date: FinancialDate
    amount: Money
    payee_name: str | None = None
    memo: str | None = None
    account_id: str | None = None
    is_transfer: bool = False
    id: str | None = None
    import_posted_date: FinancialDate | None = None
    import_id: str | None = None

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


MatchType = Literal["exact", "fuzzy", "ambiguous", "none"]


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a transaction."""

    match_type: MatchType
    ynab_transaction: MatchingYnabTransaction | None = None
    confidence: float | None = None  # 0.0-1.0
    candidates: tuple[MatchingYnabTransaction, ...] | None = None
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


def _by_import_id(ynab_txs: list[MatchingYnabTransaction], expected_id: str) -> list[MatchingYnabTransaction]:
    """Exact match by previously assigned import_id.

    Handles transactions created by bank_data_reconcile_apply: they have a deterministic
    UUID5 import_id stored in YNAB.  Matching by that ID is immune to date-offset
    mismatches (e.g. apply.py writes date=posted_date while YNAB Direct Import uses
    date=posted_date-1 for Apple Card/Savings).  Must run before any date-based strategy
    so it cannot be pre-empted by an adjacent bank tx stealing the pool entry.
    """
    return [tx for tx in ynab_txs if tx.import_id == expected_id]


def _by_posted_date(
    bank_tx: BankTransaction, ynab_txs: list[MatchingYnabTransaction]
) -> list[MatchingYnabTransaction]:
    """Filter YNAB txs matching bank posted_date + amount (primary strategy)."""
    return [tx for tx in ynab_txs if tx.date == bank_tx.posted_date and tx.amount == bank_tx.amount]


def _by_transaction_date(
    bank_tx: BankTransaction, ynab_txs: list[MatchingYnabTransaction]
) -> list[MatchingYnabTransaction]:
    """Fallback: try transaction_date when it differs from posted_date.

    Handles Apple Card 1-day offset where YNAB stores purchase date but bank CSV
    uses posted (clearing) date.
    """
    if bank_tx.transaction_date is None or bank_tx.transaction_date == bank_tx.posted_date:
        return []
    return [tx for tx in ynab_txs if tx.date == bank_tx.transaction_date and tx.amount == bank_tx.amount]


def _by_import_posted_date(
    bank_tx: BankTransaction, ynab_txs: list[MatchingYnabTransaction]
) -> list[MatchingYnabTransaction]:
    """Fallback: match via YNAB import_id's encoded clearing date.

    Handles manually-entered YNAB transactions later matched by Direct Import:
    the transaction's date field retains the manual entry date but import_id
    encodes the actual bank clearing date (format: YNAB:<amount>:<date>:<seq>).
    """
    return [
        tx for tx in ynab_txs if tx.import_posted_date == bank_tx.posted_date and tx.amount == bank_tx.amount
    ]


def _by_ynab_date_offset(
    bank_tx: BankTransaction, ynab_txs: list[MatchingYnabTransaction], ynab_date_offset_days: int
) -> list[MatchingYnabTransaction]:
    """Fallback: try posted_date adjusted by account-level YNAB date offset.

    Handles cases where YNAB uses a different date convention than the bank CSV
    (e.g., Apple Savings: YNAB uses earned date, bank uses deposited date, ~1 day offset).
    """
    if ynab_date_offset_days == 0:
        return []
    offset_date = FinancialDate(date=bank_tx.posted_date.date + timedelta(days=ynab_date_offset_days))
    return [tx for tx in ynab_txs if tx.date == offset_date and tx.amount == bank_tx.amount]


def _by_transfer_window(
    bank_tx: BankTransaction, ynab_txs: list[MatchingYnabTransaction]
) -> list[MatchingYnabTransaction]:
    """Fallback: ±5 day window for YNAB transfer entries.

    Handles YNAB initiation date vs bank clearing date offset (observed max: 4 days).
    Only applies to transactions marked as transfers in YNAB.
    """
    return [
        tx
        for tx in ynab_txs
        if tx.is_transfer
        and tx.amount == bank_tx.amount
        and abs(bank_tx.posted_date.age_days(tx.date)) <= _TRANSFER_DATE_WINDOW_DAYS
    ]


def _pick_best(bank_tx: BankTransaction, candidates: list[MatchingYnabTransaction]) -> MatchResult:
    """Resolve multiple candidates via fuzzy description matching."""
    scores: list[tuple[MatchingYnabTransaction, float]] = []
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
    # Note: confidence may be below FUZZY_MATCH_CONFIDENCE_THRESHOLD in this path.
    unique_payees = {
        YNAB_PAYEE_EXPANSIONS.get(
            normalize_description(tx.payee_name or ""), normalize_description(tx.payee_name or "")
        )
        for tx, _ in scores
    }
    if len(unique_payees) == 1:
        return MatchResult(match_type="fuzzy", ynab_transaction=best_match, confidence=best_score)

    return MatchResult(
        match_type="ambiguous",
        candidates=tuple(tx for tx, _ in scores),
        similarity_scores=tuple(score for _, score in scores),
    )


def find_matches(
    bank_tx: BankTransaction,
    ynab_txs: list[MatchingYnabTransaction],
    ynab_date_offset_days: int = 0,
    expected_import_id: str | None = None,
) -> MatchResult:
    """
    Find YNAB transaction matching bank transaction.

    Waterfall of strategies (first non-empty result wins):
    0. import_id exact match (transactions previously created by bank_data_reconcile_apply)
    1. posted_date + offset + amount (account-configured date shift; e.g., Apple Card/Savings
       use purchase date = posted_date - 1; no-op when offset=0 so Chase is unaffected)
    2. posted_date + amount (bank clearing date; primary for Chase where YNAB uses posted_date)
    3. transaction_date + amount (purchase date fallback for Apple Card without offset)
    4. import_posted_date + amount (YNAB Direct Import re-match of manual entries)
    5. transfer ±5 day window (YNAB initiation vs bank clearing date)

    Args:
        bank_tx: Bank transaction to match
        ynab_txs: List of YNAB transactions to search
        ynab_date_offset_days: Days to shift bank posted_date when searching YNAB.
            Used when YNAB uses a different date convention than the bank CSV
            (e.g., Apple Savings: YNAB uses earned date, bank uses deposited date).
        expected_import_id: UUID5 import_id previously written by bank_data_reconcile_apply.
            When provided, checked first so apply-created transactions are always found
            regardless of which date they landed on in YNAB.

    Returns:
        MatchResult with match_type and associated data
    """
    # Step 0: import_id exact match (uses full pool — the entry we want is ours)
    candidates = _by_import_id(ynab_txs, expected_import_id) if expected_import_id else []

    if not candidates:
        # For date-based fallback, exclude YNAB txs that belong to a different bank
        # transaction.  A YNAB tx with a UUID-format import_id (our format: 36 chars in
        # standard 8-4-4-4-12 layout, not "YNAB:" prefix) that doesn't match
        # expected_import_id was created for a different seq of the same (date, amount,
        # description) key.  Allowing it to be claimed here would steal the entry from
        # the bank tx it actually belongs to, causing a duplicate-import-id rejection on
        # the next apply.  Non-UUID import_ids (YNAB Direct Import "YNAB:…", None, or
        # any other format) are always eligible for date+amount fallback.
        date_eligible = [
            tx
            for tx in ynab_txs
            if tx.import_id is None or not _is_uuid_format(tx.import_id) or tx.import_id == expected_import_id
        ]
        candidates = (
            _by_ynab_date_offset(bank_tx, date_eligible, ynab_date_offset_days)
            or _by_posted_date(bank_tx, date_eligible)
            or _by_transaction_date(bank_tx, date_eligible)
            or _by_import_posted_date(bank_tx, date_eligible)
            or _by_transfer_window(bank_tx, date_eligible)
        )

    if not candidates:
        return MatchResult(match_type="none")
    if len(candidates) == 1:
        return MatchResult(match_type="exact", ynab_transaction=candidates[0], confidence=1.0)
    return _pick_best(bank_tx, candidates)
