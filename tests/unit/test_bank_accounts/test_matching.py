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
    # Bank transaction
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="AMAZON.COM*XX1234 ORDER #123-456789",
        amount=Money.from_cents(-4567),
    )

    # YNAB transactions - multiple with same date+amount
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

    # Should be fuzzy match (best score > 0.8)
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


def test_fuzzy_match_uses_memo_when_no_payee():
    """Test fuzzy matching uses memo when payee_name is None."""
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

    assert result.match_type == "fuzzy"
    assert result.ynab_transaction == ynab_txs[0]
    assert result.confidence is not None
    assert result.confidence > 0.8


def test_fuzzy_match_combines_payee_and_memo():
    """Test fuzzy matching combines payee_name and memo for better matching."""
    bank_tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="AMAZON.COM ORDER 123-456789",
        amount=Money.from_cents(-4567),
    )

    ynab_txs = [
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Amazon.com",
            memo="Order 123-456789",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-12-15"),
            amount=Money.from_cents(-4567),
            payee_name="Target",
            memo="Gift card",
        ),
    ]

    result = find_matches(bank_tx, ynab_txs)

    # Should match first transaction using combined payee+memo
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
