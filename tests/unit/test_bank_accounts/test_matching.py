"""Unit tests for bank_accounts.matching."""

import pytest

from finances.bank_accounts.matching import (
    FUZZY_MATCH_CONFIDENCE_THRESHOLD,
    MatchResult,
    YnabTransaction,
    find_matches,
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-1363),
            payee_name="Safeway",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-2500),
            payee_name="Target",
        ),
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon.com",
            memo="Order #123-456789",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon Prime",
            memo="Monthly subscription",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Target",
            memo="Groceries",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # payee-only: "amazon.com" vs "amazon.com" = 1.0 → fuzzy match (best score > 0.8)
    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]  # Best match by description similarity
    assert result.confidence is not None
    assert result.confidence > 0.8
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-5000),
            payee_name="Safeway",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-5000),
            payee_name="Target",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-5000),
            payee_name="Costco",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Should be ambiguous (no score > 0.8)
    assert result.match_type == "ambiguous"
    assert result.ynab_transaction is None
    assert result.confidence is None
    assert result.candidates is not None
    assert len(result.candidates) == 3
    assert result.similarity_scores is not None
    assert len(result.similarity_scores) == 3
    # All scores should be below threshold
    assert all(score <= 0.8 for score in result.similarity_scores)


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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-16"),
            amount=Money.from_cents(-1363),
            payee_name="Safeway",
        ),
        YnabTransaction(
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


def test_no_match_empty_ynab_list():
    """Test when YNAB transaction list is empty."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363),
    )

    result = find_matches(bank_tx, [])

    assert result.match_type == "none"


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


def test_ynab_transaction_immutability():
    """Test that YnabTransaction is immutable."""
    tx = YnabTransaction(
        date=FinancialDate.from_string("2024-12-15"),
        amount=Money.from_cents(-1363),
        payee_name="Safeway",
    )

    with pytest.raises(AttributeError):
        tx.amount = Money.from_cents(-5000)  # type: ignore[misc,unused-ignore]


def test_match_result_immutability():
    """Test that MatchResult is immutable."""
    result = MatchResult(
        match_type="exact",
        ynab_transaction=YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-1363),
            payee_name="Safeway",
        ),
        confidence=1.0,
    )

    with pytest.raises(AttributeError):
        result.match_type = "fuzzy"  # type: ignore[misc,unused-ignore]


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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name=None,
            memo="Amazon order 123-456789",
        ),
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon.com",
            memo="This is a very long user-entered memo that would dilute the score if included",
        ),
        YnabTransaction(
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
    assert result.confidence > 0.8


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
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2023-04-29"),
            amount=Money.from_cents(-2500),
            payee_name="Safeway",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2023-04-28"),
            amount=Money.from_cents(-2500),
            payee_name="Safeway",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Should use the posted_date match (first one), not the transaction_date match
    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]


def test_transaction_date_fallback_not_used_when_none():
    """Test that fallback is not attempted when transaction_date is None."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2023-04-29"),
        transaction_date=None,
        description="SOME STORE",
        amount=Money.from_cents(-1500),
    )

    # YNAB tx on a different date - should not be matched
    ynab_txs = [
        YnabTransaction(
            date=FinancialDate.from_string("2023-04-28"),
            amount=Money.from_cents(-1500),
            payee_name="Some Store",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    assert result.match_type == "none"


def test_transaction_date_fallback_not_used_when_equal_to_posted_date():
    """Test that fallback is skipped when transaction_date equals posted_date."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2023-04-29"),
        transaction_date=FinancialDate.from_string("2023-04-29"),  # Same as posted_date
        description="SOME STORE",
        amount=Money.from_cents(-1500),
    )

    # No YNAB tx on that date - fallback would be a no-op anyway
    ynab_txs = [
        YnabTransaction(
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
        YnabTransaction(
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
        YnabTransaction(
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
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-11-01"),
            amount=Money.from_cents(-529),
            payee_name="Amazon Kindle Services",
        ),
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-500),
            payee_name="CVS Pharmacy",
        ),
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-02-02"),
            amount=Money.from_cents(6),
            payee_name="Deposit",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-02-02"),
            amount=Money.from_cents(6),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Expansion makes ynab_desc "daily cash deposit" == bank_desc → score 1.0 → fuzzy match
    assert result.match_type == "fuzzy"
    assert result.confidence is not None
    assert result.confidence >= 0.8


def test_ynab_date_offset_matches_when_posted_date_misses():
    """Test ynab_date_offset_days=-1 fallback finds match when YNAB uses day-before date."""
    # Apple Savings: bank posted Jan 2, YNAB earned/recorded Jan 1 (offset -1)
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-02"),
        description="Daily Cash Deposit",
        amount=Money.from_cents(15),
    )

    ynab_txs = [
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-01"),  # offset would find this, but offset=0
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs, ynab_date_offset_days=0)

    assert result.match_type == "none"


def test_ynab_date_offset_not_triggered_when_step1_succeeds():
    """Test that offset fallback is not triggered when posted_date already found candidates."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-01-02"),
        description="Daily Cash Deposit",
        amount=Money.from_cents(15),
    )

    ynab_txs = [
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-02"),  # exact posted_date match
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-01"),  # offset match — should NOT be used
            amount=Money.from_cents(15),
            payee_name="Deposit",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs, ynab_date_offset_days=-1)

    # Step 1 found one candidate → exact match; offset step is never reached
    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_txs[0]


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
        YnabTransaction(
            date=FinancialDate.from_string("2024-03-01"),
            amount=Money.from_cents(-2500),
            payee_name="Safeway",
        ),
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-650),
            payee_name="Starbucks",
        ),
        YnabTransaction(
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
        YnabTransaction(
            date=FinancialDate.from_string("2024-06-15"),
            amount=Money.from_cents(-1999),
            payee_name="Safeway",
        ),
        YnabTransaction(
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
    the 0.8 threshold even when payee names were identical.  Both bank transactions
    ended up flagged as ambiguous and both YNAB transactions remained unmatched.

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

    ynab1 = YnabTransaction(
        date=date,
        amount=amount,
        payee_name="VANGUARD BUY INVESTMENT PURCHASE",
        memo="Moved to brokerage per monthly plan",
    )
    ynab2 = YnabTransaction(
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
    ynab_tx = YnabTransaction(
        date=FinancialDate.from_string("2024-11-29"),  # manual entry date (order date)
        amount=Money.from_cents(-1125),
        payee_name="Amazon",
        import_posted_date=FinancialDate.from_string("2024-12-02"),  # bank clearing date
    )
    # Unrelated YNAB transaction on the actual posted date but wrong amount
    ynab_other = YnabTransaction(
        date=FinancialDate.from_string("2024-12-02"),
        amount=Money.from_cents(-999),
        payee_name="Target",
    )

    result = find_matches(bank_tx, [ynab_tx, ynab_other])

    assert result.match_type == "exact"
    assert result.ynab_transaction == ynab_tx
    assert result.confidence == 1.0
