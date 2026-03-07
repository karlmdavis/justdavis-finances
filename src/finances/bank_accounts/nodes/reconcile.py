"""Reconcile bank data with YNAB transactions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from finances.bank_accounts.balance_reconciliation import build_balance_reconciliation
from finances.bank_accounts.matching import MatchResult, YnabTransaction, find_matches
from finances.bank_accounts.models import (
    BalancePoint,
    BalanceReconciliation,
    BankAccountsConfig,
    BankTransaction,
)
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json


@dataclass(frozen=True)
class ReconciliationResult:
    """Result of reconciling a single account."""

    reconciliation: BalanceReconciliation
    unmatched_bank_txs: tuple[BankTransaction, ...]
    unmatched_ynab_txs: tuple[YnabTransaction, ...]
    operations: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "balance_reconciliation": self.reconciliation.to_dict(),
            "unmatched_bank_txs": [tx.to_dict() for tx in self.unmatched_bank_txs],
            "unmatched_ynab_txs": [tx.to_dict() for tx in self.unmatched_ynab_txs],
            "operations": list(self.operations),
        }


def calculate_ynab_balances(
    ynab_txs: list[YnabTransaction],
    balance_points: list[BalancePoint],
) -> dict[FinancialDate, Money]:
    """
    Calculate YNAB running balances for each balance point date.

    Sums all YNAB transactions up to and including each balance point date.

    Args:
        ynab_txs: List of YNAB transactions for the account
        balance_points: List of bank balance points with dates

    Returns:
        Dictionary mapping balance point dates to calculated YNAB balances
    """
    ynab_balances: dict[FinancialDate, Money] = {}

    if not balance_points or not ynab_txs:
        return ynab_balances

    # Sort YNAB transactions by date for efficient calculation
    sorted_ynab_txs = sorted(ynab_txs, key=lambda tx: tx.date)

    # Calculate running balance for each balance point date
    for balance_point in balance_points:
        balance_date = balance_point.date
        # Sum all YNAB transactions up to and including this date
        running_balance = sum(
            (tx.amount for tx in sorted_ynab_txs if tx.date <= balance_date),
            Money.from_cents(0),
        )
        ynab_balances[balance_date] = running_balance

    return ynab_balances


def reconcile_account_data(
    config: BankAccountsConfig,
    base_dir: Path,
    ynab_transactions: list[YnabTransaction],
) -> dict[str, ReconciliationResult]:
    """
    Reconcile bank data with YNAB transactions.

    Orchestrates:
    1. Load normalized bank data (from parse node output)
    2. Match bank transactions with YNAB transactions
    3. Generate operations for unmatched transactions
    4. Build balance reconciliation
    5. Return reconciliation results per account

    Args:
        config: Bank accounts configuration
        base_dir: Base directory for data (contains normalized/)
        ynab_transactions: List of YNAB transactions to match against

    Returns:
        Dictionary mapping account slug to ReconciliationResult
    """
    # Process each account
    results: dict[str, ReconciliationResult] = {}

    for account in config.accounts:
        # 1. Load normalized bank data using timestamped files (Pattern C)
        normalized_dir = base_dir / "normalized"

        # Find all files for this account (timestamped or non-timestamped)
        timestamped_files = list(normalized_dir.glob(f"*_{account.slug}.json"))
        non_timestamped_file = normalized_dir / f"{account.slug}.json"

        account_files = timestamped_files
        if non_timestamped_file.exists():
            account_files.append(non_timestamped_file)

        if not account_files:
            # Skip account if no normalized data exists
            continue

        # Load most recent file for this account (by mtime)
        most_recent_file = max(account_files, key=lambda f: f.stat().st_mtime)
        normalized_data = read_json(most_recent_file)

        bank_txs = [BankTransaction.from_dict(tx) for tx in normalized_data["transactions"]]
        # Handle both "balance_points" (flow node format) and "balances" (legacy test format)
        balance_data = normalized_data.get("balance_points", normalized_data.get("balances", []))
        balance_points = [BalancePoint.from_dict(bp) for bp in balance_data]

        # Filter YNAB transactions for this account
        ynab_txs_for_account = [tx for tx in ynab_transactions if tx.account_id == account.ynab_account_id]

        # 2. Match bank transactions with YNAB transactions (greedy one-to-one)
        # Each claimed YNAB tx is removed from the pool so two bank txs can't claim the same one.
        bank_matches: dict[BankTransaction, MatchResult] = {}
        remaining_ynab = list(ynab_txs_for_account)
        for bank_tx in bank_txs:
            match_result = find_matches(bank_tx, remaining_ynab, account.ynab_date_offset_days)
            bank_matches[bank_tx] = match_result
            if match_result.match_type in ("exact", "fuzzy") and match_result.ynab_transaction:
                remaining_ynab.remove(match_result.ynab_transaction)

        # Track unmatched transactions
        unmatched_bank_txs = [tx for tx, result in bank_matches.items() if result.match_type == "none"]
        unmatched_ynab_txs = remaining_ynab  # whatever wasn't claimed

        # 3. Generate operations
        operations: list[dict[str, Any]] = []

        for bank_tx, match_result in bank_matches.items():
            if match_result.match_type == "none":
                operations.append(
                    {
                        "type": "create_transaction",
                        "source": "bank",
                        "transaction": bank_tx.to_dict(),
                        "account_id": account.ynab_account_id,
                    }
                )
            elif match_result.match_type == "ambiguous":
                # Serialize candidates to dicts
                candidates_dicts: list[dict[str, Any]] = (
                    [
                        {
                            "date": str(candidate.date),
                            "amount_milliunits": candidate.amount.to_milliunits(),
                            "payee_name": candidate.payee_name,
                            "memo": candidate.memo,
                            "account_id": candidate.account_id,
                        }
                        for candidate in match_result.candidates
                    ]
                    if match_result.candidates
                    else []
                )

                operations.append(
                    {
                        "type": "flag_discrepancy",
                        "source": "bank",
                        "transaction": bank_tx.to_dict(),
                        "candidates": candidates_dicts,
                        "message": "Multiple possible matches - manual review required",
                    }
                )

        # 4. Build balance reconciliation
        # Calculate YNAB running balances from transactions
        ynab_balances = calculate_ynab_balances(ynab_txs_for_account, balance_points)

        balance_recon = build_balance_reconciliation(
            account_id=account.slug,
            balance_points=balance_points,
            ynab_balances=ynab_balances,
            unmatched_bank_txs=unmatched_bank_txs,
            unmatched_ynab_txs=unmatched_ynab_txs,
        )

        # Build reconciliation result for this account
        result = ReconciliationResult(
            reconciliation=balance_recon,
            unmatched_bank_txs=tuple(unmatched_bank_txs),
            unmatched_ynab_txs=tuple(unmatched_ynab_txs),
            operations=tuple(operations),
        )
        results[account.slug] = result

    return results
