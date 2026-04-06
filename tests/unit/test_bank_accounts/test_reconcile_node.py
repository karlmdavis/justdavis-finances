"""Unit tests for greedy one-to-one matching in reconcile_account_data."""

import json
import tempfile
from pathlib import Path

from finances.bank_accounts.matching import MatchingYnabTransaction
from finances.bank_accounts.models import (
    AccountConfig,
    BankAccountsConfig,
    ImportPattern,
)
from finances.bank_accounts.nodes.reconcile import reconcile_account_data
from finances.bank_accounts.operations import CreateOp
from finances.core import FinancialDate, Money


def _make_account(slug: str = "test-account", ynab_account_id: str = "acct-001") -> AccountConfig:
    """Create a minimal AccountConfig for testing."""
    return AccountConfig(
        ynab_account_id=ynab_account_id,
        ynab_account_name="Test Account",
        slug=slug,
        bank_name="Test Bank",
        source_directory="~/Downloads/test",
        download_instructions="N/A",
        import_patterns=(ImportPattern(pattern="*.csv", format_handler="chase_checking_csv"),),
    )


def _write_normalized(
    base_dir: Path, slug: str, transactions: list[dict], balances: list[dict] | None = None
) -> None:
    """Write a normalized JSON file for the given account slug."""
    normalized_dir = base_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "transactions": transactions,
        "balance_points": balances or [],
    }
    (normalized_dir / f"2024-01-01_00-00-00_{slug}.json").write_text(json.dumps(data))


def test_greedy_two_identical_bank_txs_claim_separate_ynab_txs():
    """Two bank txs with same date+amount each claim their own YNAB tx (greedy pool)."""
    account = _make_account()
    config = BankAccountsConfig(accounts=(account,))

    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp)

        # Two identical bank transactions (e.g., two Amazon.com charges same day)
        # Use "Amazon.com" so normalized bank desc == normalized YNAB payee → fuzzy score 1.0
        bank_data = [
            {"posted_date": "2024-12-08", "description": "Amazon.com", "amount_milliunits": -1999000},
            {"posted_date": "2024-12-08", "description": "Amazon.com", "amount_milliunits": -1999000},
        ]
        _write_normalized(base_dir, account.slug, bank_data)

        # Two matching YNAB transactions
        ynab_txs = [
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-12-08"),
                amount=Money.from_milliunits(-1999000),
                payee_name="Amazon.com",
                account_id=account.ynab_account_id,
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-12-08"),
                amount=Money.from_milliunits(-1999000),
                payee_name="Amazon.com",
                account_id=account.ynab_account_id,
            ),
        ]

        results = reconcile_account_data(config, base_dir, ynab_txs)

    result = results[account.slug]
    # Both bank txs matched → no creates
    creates = [op for op in result.operations if isinstance(op, CreateOp)]
    assert len(creates) == 0, f"Expected 0 creates, got {len(creates)}"
    # Both YNAB txs claimed → nothing left unmatched
    assert len(result.unmatched_ynab_txs) == 0


def test_greedy_pool_exhausted_third_bank_tx_becomes_create():
    """Third bank tx with same date+amount gets no match when only 2 YNAB txs exist."""
    account = _make_account()
    config = BankAccountsConfig(accounts=(account,))

    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp)

        # Three identical bank transactions
        # Three identical bank transactions; use "Safeway" so normalized desc == YNAB payee → score 1.0
        bank_data = [
            {"posted_date": "2024-12-08", "description": "Safeway", "amount_milliunits": -500000},
            {"posted_date": "2024-12-08", "description": "Safeway", "amount_milliunits": -500000},
            {"posted_date": "2024-12-08", "description": "Safeway", "amount_milliunits": -500000},
        ]
        _write_normalized(base_dir, account.slug, bank_data)

        # Only two YNAB transactions
        ynab_txs = [
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-12-08"),
                amount=Money.from_milliunits(-500000),
                payee_name="Safeway",
                account_id=account.ynab_account_id,
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-12-08"),
                amount=Money.from_milliunits(-500000),
                payee_name="Safeway",
                account_id=account.ynab_account_id,
            ),
        ]

        results = reconcile_account_data(config, base_dir, ynab_txs)

    result = results[account.slug]
    # First two bank txs matched, third becomes a create
    creates = [op for op in result.operations if isinstance(op, CreateOp)]
    assert len(creates) == 1, f"Expected 1 create, got {len(creates)}"
    # Both YNAB txs were claimed
    assert len(result.unmatched_ynab_txs) == 0
