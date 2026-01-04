"""Unit tests for bank_accounts.matching."""

import pytest

from finances.bank_accounts.matching import MatchResult, YnabTransaction, find_matches, normalize_description
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
