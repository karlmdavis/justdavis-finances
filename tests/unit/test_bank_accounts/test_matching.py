"""Unit tests for bank_accounts.matching."""

import pytest

from finances.bank_accounts.matching import (
    FUZZY_MATCH_CONFIDENCE_THRESHOLD,
    MatchingYnabTransaction,
    find_matches,
    make_import_id,
    normalize_description,
)
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


def test_exact_match_single():
    """Test matching with unique date+amount match."""
    # Bank transaction
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616 GROCERY STORE",
        amount=Money.from_cents(-1363),
    )

    # YNAB transactions - only one matches date+amount
    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-1363),
            payee_name="Safeway",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-2500),
            payee_name="Target",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-16"),
            amount=Money.from_cents(-1363),
            payee_name="Safeway",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence == 1.0
    assert result.candidates is None
    assert result.similarity_scores is None


def test_fuzzy_match_multiple():
    """Test fuzzy matching when multiple YNAB txs have same date+amount."""
    # Bank transaction — description closely matches one YNAB payee name
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="AMAZON.COM",
        amount=Money.from_cents(-4567),
    )

    # YNAB transactions - multiple with same date+amount, different payees
    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon.com",
            memo="Order #123-456789",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon Prime",
            memo="Monthly subscription",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Target",
            memo="Groceries",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # payee-only: "amazon.com" vs "amazon.com" = 1.0 → fuzzy match (score > threshold)
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]  # Best match by description similarity
    assert result.confidence is not None
    assert result.confidence > FUZZY_MATCH_CONFIDENCE_THRESHOLD
    assert result.candidates is None


def test_fuzzy_match_ambiguous():
    """Test ambiguous match when no candidate scores above threshold."""
    # Bank transaction
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="DEBIT CARD PURCHASE #1234",
        amount=Money.from_cents(-5000),
    )

    # YNAB transactions - multiple with same date+amount but poor description matches
    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-5000),
            payee_name="Safeway",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-5000),
            payee_name="Target",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-5000),
            payee_name="Costco",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Should be ambiguous (no score > threshold)
    assert result.match_type == "ambiguous"
    assert result.ynab_transaction is None
    assert result.confidence is None
    assert result.candidates is not None
    assert len(result.candidates) == 3
    assert result.similarity_scores is not None
    assert len(result.similarity_scores) == 3
    # All scores should be below threshold
    assert all(score <= FUZZY_MATCH_CONFIDENCE_THRESHOLD for score in result.similarity_scores)


def test_no_match():
    """Test when no YNAB transaction matches."""
    # Bank transaction
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363),
    )

    # YNAB transactions - none match date+amount
    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-16"),
            amount=Money.from_cents(-1363),
            payee_name="Safeway",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-2500),
            payee_name="Target",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "none"
    assert result.ynab_transaction is None
    assert result.confidence is None
    assert result.candidates is None
    assert result.similarity_scores is None


def test_normalize_description():
    """Test description normalization."""
    # Test lowercase
    assert normalize_description("SAFEWAY 1616") == "safeway"

    # Test digit removal
    assert normalize_description("AMAZON.COM*XX1234") == "amazon.com*xx"

    # Test space normalization
    assert normalize_description("MULTIPLE   SPACES") == "multiple spaces"

    # Test combined
    assert normalize_description("TARGET #1234  STORE  5678") == "target # store"

    # Test empty string
    assert normalize_description("") == ""

    # Test only digits
    assert normalize_description("1234567890") == ""


def test_fuzzy_match_no_payee_single_payee_fallback():
    """When all candidates have no payee_name, single-payee fallback claims the first.

    Memo is NOT used for matching (user-annotated context, not bank-sourced).  With
    payee_name=None for every candidate the normalized desc is "" for all, so
    unique_payees has length 1 and the single-payee fallback fires.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="AMAZON ORDER 123-456789",
        amount=Money.from_cents(-4567),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name=None,
            memo="Amazon order 123-456789",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name=None,
            memo="Target groceries",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Single-payee fallback fires (both normalize to ""); first candidate is claimed.
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]


def test_fuzzy_match_excludes_memo_from_score():
    """Memo is NOT included when computing fuzzy similarity — payee_name only.

    A long user-entered memo must not inflate the YNAB string length and drag the
    SequenceMatcher score below the threshold when the payee names match exactly.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="AMAZON.COM",
        amount=Money.from_cents(-4567),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon.com",
            memo="This is a very long user-entered memo that would dilute the score if included",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Target",
            memo="Gift card",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # payee-only: "amazon.com" vs "amazon.com" = 1.0 → fuzzy match despite long memo
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence is not None
    assert result.confidence > FUZZY_MATCH_CONFIDENCE_THRESHOLD


def test_transaction_date_fallback_when_posted_date_misses():
    """Test fallback to transaction_date when posted_date finds no match (Apple Card 1-day offset)."""
    # Apple Card: transaction_date is purchase date (what YNAB stores), posted_date is next day
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2023-04-29"),
        transaction_date=FinancialDate.from_string("2023-04-28"),
        description="BLAZE PIZZA",
        amount=Money.from_cents(-3849),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2023-04-28"),
            amount=Money.from_cents(-3849),
            payee_name="Blaze Pizza",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence == 1.0


def test_posted_date_preferred_over_transaction_date():
    """Test that posted_date match is used when found, not transaction_date."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2023-04-29"),
        transaction_date=FinancialDate.from_string("2023-04-28"),
        description="SAFEWAY",
        amount=Money.from_cents(-2500),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2023-04-29"),
            amount=Money.from_cents(-2500),
            payee_name="Safeway",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2023-04-28"),
            amount=Money.from_cents(-2500),
            payee_name="Safeway",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Should use the posted_date match (first one), not the transaction_date match
    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]


@pytest.mark.parametrize(
    "transaction_date",
    [
        None,  # no fallback when transaction_date is absent
        FinancialDate.from_string("2023-04-29"),  # no fallback when equal to posted_date
    ],
    ids=["none", "equal_to_posted_date"],
)
def test_transaction_date_fallback_not_used(transaction_date):
    """Fallback is skipped when transaction_date is None or equals posted_date."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2023-04-29"),
        transaction_date=transaction_date,
        description="SOME STORE",
        amount=Money.from_cents(-1500),
    )
    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2023-04-28"),
            amount=Money.from_cents(-1500),
            payee_name="Some Store",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "none"


def test_transfer_date_window_matches_payment():
    """Test transfer date-window fallback matches payment 2 days after YNAB transfer entry."""
    # Bank: payment posted 2 days after YNAB recorded the transfer initiation
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-06-17"),
        transaction_date=None,
        description="APPLECARD GSBANK PAYMENT",
        amount=Money.from_cents(-1462637),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-1462637),
            payee_name="Transfer to Apple Card",
            is_transfer=True,
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence == 1.0


def test_transfer_date_window_not_used_for_non_transfers():
    """Test transfer date-window fallback is not used for non-transfer YNAB entries."""
    # Regular YNAB entry (is_transfer=False) with matching amount but 2 days off
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-17"),
        transaction_date=None,
        description="KINDLE 529",
        amount=Money.from_cents(-529),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-529),
            payee_name="Amazon Kindle",
            is_transfer=False,
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "none"


def test_transfer_date_window_too_far_apart():
    """Test transfer date-window fallback does not match when offset exceeds 5 days."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-11-20"),
        transaction_date=None,
        description="CHASE CREDIT PAYMENT",
        amount=Money.from_cents(-354009),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-11-14"),  # 6 days before posted_date
            amount=Money.from_cents(-354009),
            payee_name="Transfer to Chase Credit",
            is_transfer=True,
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "none"


def test_single_payee_ambiguous_claims_first():
    """When all YNAB candidates share the same payee, claim the first one as fuzzy.

    Covers Kindle/Venmo/Apple scenarios where N identical YNAB entries exist for N
    identical bank txs and description similarity can't distinguish between them.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-11-01"),
        description="Kindle Svcs*WH9KF0GQ3",
        amount=Money.from_cents(-529),
    )

    # Two YNAB entries with same payee — scores are equal and below threshold
    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-11-01"),
            amount=Money.from_cents(-529),
            payee_name="Amazon Kindle Services",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-11-01"),
            amount=Money.from_cents(-529),
            payee_name="Amazon Kindle Services",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Single-payee fallback: claims first candidate rather than flagging ambiguous
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence is not None


def test_multi_payee_ambiguous_still_ambiguous():
    """When candidates have different payee names, ambiguous is preserved (genuine ambiguity)."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="PURCHASE",
        amount=Money.from_cents(-500),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-500),
            payee_name="CVS Pharmacy",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-500),
            payee_name="Canteen Vending",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "ambiguous"
    assert result.candidates is not None
    assert len(result.candidates) == 2


def test_ynab_payee_expansion_daily_cash_deposit():
    """Test that YNAB 'Deposit' expands to match bank 'Daily Cash Deposit' when ambiguous."""
    # Apple Savings: bank has "Daily Cash Deposit", YNAB Direct Import abbreviates to "Deposit".
    # With two candidates on the same date+amount, the expansion makes both score 1.0 so
    # the first candidate wins as a fuzzy match instead of falling to ambiguous.
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-02-02"),
        description="Daily Cash Deposit",
        amount=Money.from_cents(6),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-02-02"),
            amount=Money.from_cents(6),
            payee_name="Deposit",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-02-02"),
            amount=Money.from_cents(6),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Expansion makes ynab_desc "daily cash deposit" == bank_desc → score 1.0 → fuzzy match
    assert result.match_type == "fuzzy"
    assert result.confidence is not None
    assert result.confidence > FUZZY_MATCH_CONFIDENCE_THRESHOLD


def test_ynab_date_offset_matches_when_posted_date_misses():
    """Test ynab_date_offset_days=-1 fallback finds match when YNAB uses day-before date."""
    # Apple Savings: bank posted Jan 2, YNAB earned/recorded Jan 1 (offset -1)
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-02"),
        description="Daily Cash Deposit",
        amount=Money.from_cents(15),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-01"),  # one day before posted_date
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs, ynab_date_offset_days=-1)

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence == 1.0


def test_ynab_date_offset_zero_not_triggered():
    """Test that offset=0 (default) skips the offset fallback entirely."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-02"),
        description="Daily Cash Deposit",
        amount=Money.from_cents(15),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-01"),  # offset would find this, but offset=0
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs, ynab_date_offset_days=0)

    assert result.match_type == "none"


def test_ynab_date_offset_takes_priority_over_posted_date_when_both_present():
    """Test that offset strategy fires before posted_date when both have candidates.

    For Apple Card/Savings (offset=-1), YNAB uses purchase date (posted_date - 1).
    When YNAB has txs on both posted_date AND posted_date-1, the offset tx is
    the correct match and should be claimed first.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-02"),
        description="Daily Cash Deposit",
        amount=Money.from_cents(15),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-02"),  # posted_date match
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-01"),  # offset match (posted_date - 1)
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs, ynab_date_offset_days=-1)

    # Offset strategy fires first → claims the Jan 1 tx (correct YNAB purchase date)
    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[1]


def test_ynab_payee_expansion_unknown_payee_unchanged():
    """Test that an unknown YNAB payee is not expanded and behavior is unchanged.

    "Safeway" is not in YNAB_PAYEE_EXPANSIONS so it stays as "safeway" after
    normalization.  "safeway grocery" vs "safeway" scores ~0.64 (below threshold)
    so the result is ambiguous — confirming no spurious expansion boosted the score.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-03-01"),
        description="SAFEWAY GROCERY",
        amount=Money.from_cents(-2500),
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-03-01"),
            amount=Money.from_cents(-2500),
            payee_name="Safeway",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-03-01"),
            amount=Money.from_cents(-2500),
            payee_name="Target",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # No expansion → raw similarity below threshold → ambiguous (not artificially boosted)
    assert result.match_type == "ambiguous"
    assert result.candidates is not None
    assert len(result.candidates) == 2
    # All scores below threshold proves no expansion occurred
    assert result.similarity_scores is not None
    assert all(score < FUZZY_MATCH_CONFIDENCE_THRESHOLD for score in result.similarity_scores)


def test_merchant_field_preferred_over_description_for_fuzzy_matching():
    """Merchant field (clean) used instead of verbose description for fuzzy scoring.

    Apple Card OFX: description is verbose ('STARBUCKS 800-782-7282 WA USA'),
    merchant is clean ('Starbucks'). With two candidates on same date+amount,
    merchant should score high against the YNAB payee name, resolving to fuzzy match.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-06-15"),
        description="STARBUCKS 800-782-7282 UTAH AVE S 98134 WA USA",
        amount=Money.from_cents(-650),
        merchant="Starbucks",
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-650),
            payee_name="Starbucks",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-650),
            payee_name="Spotify",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # merchant "Starbucks" matches YNAB payee "Starbucks" closely → fuzzy (not ambiguous)
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence is not None
    assert result.confidence > FUZZY_MATCH_CONFIDENCE_THRESHOLD


def test_description_used_when_merchant_absent():
    """When merchant is None, description is used as before (no regression).

    Uses Chase-style description 'SAFEWAY' which closely matches YNAB 'Safeway'
    to verify description-based fuzzy matching still works when merchant is absent.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-06-15"),
        description="SAFEWAY",
        amount=Money.from_cents(-1999),
        merchant=None,
    )

    ynab_txs = [
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-1999),
            payee_name="Safeway",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-1999),
            payee_name="Target",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # description "safeway" vs "safeway" = 1.0 → fuzzy match to Safeway (not ambiguous)
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]


def test_same_date_same_amount_different_payee_with_user_memos():
    """Regression: two bank txs / two YNAB txs, same date+amount, distinct payees.

    Before the fix, including the user-entered YNAB memo in the description string
    inflated the denominator of SequenceMatcher.ratio(), driving all four scores below
    FUZZY_MATCH_CONFIDENCE_THRESHOLD even when payee names were identical.  Both bank
    transactions ended up flagged as ambiguous and both YNAB transactions remained unmatched.

    After the fix (payee_name only), each bank transaction fuzzy-matches its correct
    YNAB counterpart and no transactions are left unmatched.

    This test calls find_matches() twice (once per bank tx) against the shrinking pool,
    mirroring the greedy-pool logic used in the reconciliation pipeline.
    """
    date = FinancialDate.from_string("2024-09-26")
    amount = Money.from_cents(-50000)  # $500.00

    bank1 = BankTransaction(
        posted_date=date,
        description="VANGUARD BUY INVESTMENT PURCHASE",
        amount=amount,
    )
    bank2 = BankTransaction(
        posted_date=date,
        description="Manual DB-Bkrg 09/26",
        amount=amount,
    )

    ynab1 = MatchingYnabTransaction(
        date=date,
        amount=amount,
        payee_name="VANGUARD BUY INVESTMENT PURCHASE",
        memo="Moved to brokerage per monthly plan",
    )
    ynab2 = MatchingYnabTransaction(
        date=date,
        amount=amount,
        payee_name="Manual DB-Bkrg 09/26",
        memo="Transfer to cover brokerage debit",
    )

    remaining = [ynab1, ynab2]

    # First bank tx should fuzzy-match ynab1
    result1 = find_matches(bank1, remaining)
    assert result1.match_type == "fuzzy", f"Expected fuzzy, got {result1.match_type}"
    assert result1.ynab_transaction == ynab1
    assert result1.confidence is not None
    assert result1.confidence > FUZZY_MATCH_CONFIDENCE_THRESHOLD

    # Simulate greedy pool: remove claimed YNAB tx
    remaining = [tx for tx in remaining if tx is not result1.ynab_transaction]

    # Second bank tx now has only one candidate → exact match
    result2 = find_matches(bank2, remaining)
    assert result2.match_type == "exact", f"Expected exact, got {result2.match_type}"
    assert result2.ynab_transaction == ynab2
    assert result2.confidence == 1.0

    # Both YNAB transactions are claimed — nothing left unmatched
    remaining = [tx for tx in remaining if tx is not result2.ynab_transaction]
    assert remaining == []


def test_import_posted_date_fallback_matches_manually_entered_ynab_tx():
    """Regression: manually-entered YNAB tx with order date resolves via import_posted_date.

    Scenario: User manually enters an Amazon charge in YNAB at the order date (2024-11-29).
    YNAB Direct Import later matches it when the charge clears (2024-12-02), storing
    the clearing date in import_id but leaving the transaction date unchanged.
    The bank CSV uses the clearing date (2024-12-02) as posted_date.

    _by_posted_date should find nothing (date mismatch).
    _by_import_posted_date should find the match via import_id's clearing date.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-02"),
        description="AMAZON.COM",
        amount=Money.from_cents(-1125),  # -$11.25 = -112490 milliunits... but cents here
    )

    # YNAB transaction manually entered at order date, Direct Import set import_id
    ynab_tx = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-11-29"),  # manual entry date (order date)
        amount=Money.from_cents(-1125),
        payee_name="Amazon",
        import_posted_date=FinancialDate.from_string("2024-12-02"),  # bank clearing date
    )
    # Unrelated YNAB transaction on the actual posted date but wrong amount
    ynab_other = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-12-02"),
        amount=Money.from_cents(-999),
        payee_name="Target",
    )

    result = find_matches(bank_tx, [ynab_tx, ynab_other])

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_tx
    assert result.confidence == 1.0


def test_expresscare_brand_name_expansion():
    """Regression: Apple Card merchant "Express Care Of Westmi" should fuzzy-match
    "ExpressCare Urgent Care Centers" rather than "Children's Urgent Care of Westminster".

    Without a YNAB_PAYEE_EXPANSIONS entry, SequenceMatcher gives "Children's Urgent Care
    of Westminster" a higher score (~0.48) than "ExpressCare Urgent Care Centers" (~0.42)
    because the location suffix "care of westm..." creates a long common substring with the
    wrong candidate. The expansion normalizes the YNAB payee to the bank's format so the
    correct candidate scores well above the threshold.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2025-03-26"),
        description="EXPRESS CARE OF WESTMI1011 BALTIMORE BLVD WESTMINSTER 21157 MD USA",
        merchant="Express Care Of Westmi",
        amount=Money.from_milliunits(-30000),
    )

    ynab_expresscare = MatchingYnabTransaction(
        date=FinancialDate.from_string("2025-03-26"),
        amount=Money.from_milliunits(-30000),
        payee_name="ExpressCare Urgent Care Centers",
    )
    ynab_childrens_1 = MatchingYnabTransaction(
        date=FinancialDate.from_string("2025-03-26"),
        amount=Money.from_milliunits(-30000),
        payee_name="Children's Urgent Care of Westminster",
    )
    ynab_childrens_2 = MatchingYnabTransaction(
        date=FinancialDate.from_string("2025-03-26"),
        amount=Money.from_milliunits(-30000),
        payee_name="Children's Urgent Care of Westminster",
    )

    result = find_matches(bank_tx, [ynab_childrens_1, ynab_expresscare, ynab_childrens_2])

    assert result.match_type == "fuzzy", f"Expected fuzzy, got {result.match_type}"
    assert result.ynab_transaction == ynab_expresscare


def test_childrens_urgent_care_threshold():
    """Regression: Apple Card merchant "Children's Urgent Care" should fuzzy-match
    "Children's Urgent Care of Westminster" even when "ExpressCare Urgent Care Centers"
    is also a candidate.

    The bank truncates the merchant name, dropping "of Westminster". The score of the
    correct match is ~0.759 — clearly the right answer but just below the old 0.8 threshold.
    """
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2025-03-26"),
        description="CHILDREN'S URGENT CARE265 BALTIMORE BOULEVARD WESTMINSTER 21157 MD USA",
        merchant="Children's Urgent Care",
        amount=Money.from_milliunits(-30000),
    )

    ynab_childrens_1 = MatchingYnabTransaction(
        date=FinancialDate.from_string("2025-03-26"),
        amount=Money.from_milliunits(-30000),
        payee_name="Children's Urgent Care of Westminster",
    )
    ynab_expresscare = MatchingYnabTransaction(
        date=FinancialDate.from_string("2025-03-26"),
        amount=Money.from_milliunits(-30000),
        payee_name="ExpressCare Urgent Care Centers",
    )
    ynab_childrens_2 = MatchingYnabTransaction(
        date=FinancialDate.from_string("2025-03-26"),
        amount=Money.from_milliunits(-30000),
        payee_name="Children's Urgent Care of Westminster",
    )

    result = find_matches(bank_tx, [ynab_childrens_1, ynab_expresscare, ynab_childrens_2])

    assert result.match_type == "fuzzy", f"Expected fuzzy, got {result.match_type}"
    assert result.ynab_transaction == ynab_childrens_1


def test_ynab_date_offset_takes_priority_over_posted_date():
    """Test that offset strategy fires before posted_date, preventing greedy mis-match.

    Apple Card scenario: two same-amount purchases on consecutive days.
    YNAB Direct Import assigns purchase date (= bank posted_date - 1).

    Without offset-first ordering, Bank-C's posted_date (Jul 10) would steal YNAB-D
    (date=Jul 10), leaving YNAB-C (date=Jul 9) orphaned and Bank-D unmatched.
    With offset-first, Bank-C correctly matches YNAB-C and Bank-D matches YNAB-D.
    """
    # Two bank txs: purchased Jul 9 (posted Jul 10) and Jul 10 (posted Jul 11)
    bank_c = BankTransaction(
        posted_date=FinancialDate.from_string("2024-07-10"),
        transaction_date=FinancialDate.from_string("2024-07-09"),
        description="TST* JEANNIEBIRD BAKIN",
        amount=Money.from_milliunits(-12600),
        merchant="Jeanniebird Bakin",
    )
    bank_d = BankTransaction(
        posted_date=FinancialDate.from_string("2024-07-11"),
        transaction_date=FinancialDate.from_string("2024-07-10"),
        description="TST* JEANNIEBIRD BAKIN",
        amount=Money.from_milliunits(-12600),
        merchant="Jeanniebird Bakin",
    )

    # Two YNAB txs: YNAB Direct Import assigned the purchase dates (Jul 9 and Jul 10)
    ynab_c = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-07-09"),
        amount=Money.from_milliunits(-12600),
        payee_name="JeannieBird Baking Company",
    )
    ynab_d = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-07-10"),
        amount=Money.from_milliunits(-12600),
        payee_name="JeannieBird Baking Company",
    )

    # Simulate greedy pool: Bank-C matches first, removing its YNAB tx from the pool
    pool = [ynab_c, ynab_d]
    result_c = find_matches(bank_c, pool, ynab_date_offset_days=-1)

    assert result_c.match_type in ("exact", "fuzzy"), f"Bank-C should match, got {result_c.match_type}"
    assert result_c.ynab_transaction == ynab_c, (
        f"Bank-C (posted Jul 10) should match YNAB-C (Jul 9), " f"got {result_c.ynab_transaction}"
    )

    # Remove matched tx from pool, then match Bank-D
    pool.remove(result_c.ynab_transaction)
    result_d = find_matches(bank_d, pool, ynab_date_offset_days=-1)

    assert result_d.match_type in ("exact", "fuzzy"), f"Bank-D should match, got {result_d.match_type}"
    assert result_d.ynab_transaction == ynab_d, (
        f"Bank-D (posted Jul 11) should match YNAB-D (Jul 10), " f"got {result_d.ynab_transaction}"
    )


# ---------------------------------------------------------------------------
# make_import_id tests
# ---------------------------------------------------------------------------


def test_make_import_id_seq0_stable():
    """seq=0 produces the same UUID as the historical _make_import_id formula."""
    slug = "apple-card"
    posted_date = "2023-05-06"
    amount = -2100
    description = "Vending Machine"
    # Manually compute expected UUID5 using the original formula
    import uuid as _uuid

    ns = _uuid.UUID("86ac2fc2-b0ad-4834-9241-63c577a477b3")
    expected = str(_uuid.uuid5(ns, f"bank:{slug}:{posted_date}:{amount}:{description}"))
    assert make_import_id(slug, posted_date, amount, description, seq=0) == expected


def test_make_import_id_seq1_differs_from_seq0():
    """seq=1 produces a different UUID than seq=0 for the same inputs."""
    slug = "apple-card"
    posted_date = "2024-01-22"
    amount = -7410
    description = "Apple Services"
    id0 = make_import_id(slug, posted_date, amount, description, seq=0)
    id1 = make_import_id(slug, posted_date, amount, description, seq=1)
    assert id0 != id1


def test_make_import_id_default_seq_is_zero():
    """Calling without seq kwarg gives the same result as seq=0."""
    slug = "chase-checking"
    id_no_seq = make_import_id(slug, "2024-06-01", -5000, "TARGET")
    id_seq0 = make_import_id(slug, "2024-06-01", -5000, "TARGET", seq=0)
    assert id_no_seq == id_seq0


# ---------------------------------------------------------------------------
# _by_import_id / find_matches with expected_import_id tests
# ---------------------------------------------------------------------------


def test_import_id_match_found_before_date_strategies():
    """_by_import_id fires first: apply-created tx found even when at posted_date,
    not the offset date.

    Apple Card scenario (offset=-1): apply.py created a YNAB tx at posted_date.
    Without _by_import_id, _by_ynab_date_offset looks at posted_date-1 and finds
    nothing, then _by_posted_date finds it — but only if no other bank tx has
    already stolen it.  With _by_import_id running first, the tx is always claimed
    by the right bank tx regardless of adjacent-date collisions.
    """
    slug = "apple-card"
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2023-05-06"),
        description="Vending Machine",
        amount=Money.from_milliunits(-2100),
    )
    expected_id = make_import_id(slug, "2023-05-06", -2100, "Vending Machine", seq=0)

    # YNAB tx was stored at posted_date (not posted_date-1) by apply.py
    ynab_tx = MatchingYnabTransaction(
        date=FinancialDate.from_string("2023-05-06"),
        amount=Money.from_milliunits(-2100),
        payee_name="Vending Machine",
        import_id=expected_id,
    )
    # Add a decoy at offset date with same amount — should NOT be picked
    decoy = MatchingYnabTransaction(
        date=FinancialDate.from_string("2023-05-05"),
        amount=Money.from_milliunits(-2100),
        payee_name="Decoy",
        import_id="decoy-id",
    )

    result = find_matches(bank_tx, [decoy, ynab_tx], ynab_date_offset_days=-1, expected_import_id=expected_id)

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_tx


def test_import_id_no_match_falls_through_to_date_strategies():
    """When _by_import_id finds nothing, date-based strategies still work."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-03-15"),
        description="Safeway",
        amount=Money.from_milliunits(-4500),
    )
    ynab_tx = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-03-15"),
        amount=Money.from_milliunits(-4500),
        payee_name="Safeway",
        import_id="some-other-id",
    )

    # Pass a non-matching expected_import_id — should fall through to _by_posted_date
    result = find_matches(bank_tx, [ynab_tx], ynab_date_offset_days=0, expected_import_id="non-matching-id")

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_tx


def test_two_identical_bank_txs_get_different_import_ids_via_seq():
    """Two identical bank transactions (same date/amount/description) can be distinguished
    by assigning seq=0 to the first and seq=1 to the second.

    This models the Apple Services x2 case: two $7.41 charges on 2024-01-22.
    """
    slug = "apple-card"
    posted_date = "2024-01-22"
    amount = -7410
    description = "Apple Services"

    id0 = make_import_id(slug, posted_date, amount, description, seq=0)
    id1 = make_import_id(slug, posted_date, amount, description, seq=1)

    # Two YNAB txs, one per charge, each with its own import_id
    ynab_0 = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-01-22"),
        amount=Money.from_milliunits(-7410),
        payee_name="Apple Services",
        import_id=id0,
    )
    ynab_1 = MatchingYnabTransaction(
        date=FinancialDate.from_string("2024-01-22"),
        amount=Money.from_milliunits(-7410),
        payee_name="Apple Services",
        import_id=id1,
    )

    bank_0 = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-22"),
        description="Apple Services",
        amount=Money.from_milliunits(-7410),
    )
    bank_1 = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-22"),
        description="Apple Services",
        amount=Money.from_milliunits(-7410),
    )

    pool = [ynab_0, ynab_1]

    # First bank tx (seq=0) should claim ynab_0
    result_0 = find_matches(bank_0, pool, expected_import_id=id0)
    assert result_0.match_type == "exact"
    assert result_0.ynab_transaction == ynab_0

    pool.remove(result_0.ynab_transaction)

    # Second bank tx (seq=1) should claim ynab_1
    result_1 = find_matches(bank_1, pool, expected_import_id=id1)
    assert result_1.match_type == "exact"
    assert result_1.ynab_transaction == ynab_1


def test_seq_gap_does_not_steal_higher_seq_ynab_tx():
    """Regression: missing seq=1 YNAB tx must not steal seq=2's YNAB tx.

    When N bank txs share the same (date, amount, description) they get seqs 0,1,2,…
    If YNAB has the entry for seq=0 and seq=2 but NOT seq=1, the seq=1 bank tx used
    to fall through to date+amount matching and claim seq=2's YNAB entry.  seq=2 would
    then generate a "create" op that YNAB rejected as duplicate import ID.

    With the fix, date+amount fallback excludes YNAB txs with a UUID5 import_id that
    doesn't match the current expected_import_id, so seq=1 correctly returns "none" and
    seq=2 correctly matches its own YNAB entry.
    """
    slug = "apple-savings"
    posted_date = "2023-06-15"
    amount = 300
    description = "Daily Cash Deposit"

    id0 = make_import_id(slug, posted_date, amount, description, seq=0)
    id1 = make_import_id(slug, posted_date, amount, description, seq=1)
    id2 = make_import_id(slug, posted_date, amount, description, seq=2)

    # YNAB has seq=0 and seq=2 but NOT seq=1
    ynab_0 = MatchingYnabTransaction(
        date=FinancialDate.from_string(posted_date),
        amount=Money.from_milliunits(amount),
        payee_name="Daily Cash Deposit",
        import_id=id0,
    )
    ynab_2 = MatchingYnabTransaction(
        date=FinancialDate.from_string(posted_date),
        amount=Money.from_milliunits(amount),
        payee_name="Daily Cash Deposit",
        import_id=id2,
    )

    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string(posted_date),
        description=description,
        amount=Money.from_milliunits(amount),
    )

    pool = [ynab_0, ynab_2]

    # seq=0: claims ynab_0 via import_id match
    result_0 = find_matches(bank_tx, pool, expected_import_id=id0)
    assert result_0.match_type == "exact"
    assert result_0.ynab_transaction == ynab_0
    pool.remove(result_0.ynab_transaction)

    # seq=1: import_id not in YNAB; must NOT steal ynab_2 via date+amount fallback
    result_1 = find_matches(bank_tx, pool, expected_import_id=id1)
    assert result_1.match_type == "none"

    # seq=2: claims ynab_2 via import_id match (ynab_2 was NOT stolen by seq=1)
    result_2 = find_matches(bank_tx, pool, expected_import_id=id2)
    assert result_2.match_type == "exact"
    assert result_2.ynab_transaction == ynab_2
