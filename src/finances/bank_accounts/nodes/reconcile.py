"""Reconcile bank data with YNAB transactions."""

from datetime import datetime
from pathlib import Path
from typing import Any

from finances.bank_accounts.balance_reconciliation import build_balance_reconciliation
from finances.bank_accounts.matching import MatchResult, YnabTransaction, find_matches
from finances.bank_accounts.models import (
    BalancePoint,
    BankAccountsConfig,
    BankTransaction,
)
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json, write_json


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
) -> Path:
    """
    Reconcile bank data with YNAB transactions.

    Orchestrates:
    1. Load normalized bank data (from parse node output)
    2. Match bank transactions with YNAB transactions
    3. Generate operations for unmatched transactions
    4. Build balance reconciliation
    5. Write operations JSON

    Args:
        config: Bank accounts configuration
        base_dir: Base directory for data (contains normalized/, reconciliation/)
        ynab_transactions: List of YNAB transactions to match against

    Returns:
        Path to generated operations JSON file
    """
    # Process each account
    account_results: list[dict[str, Any]] = []

    for account in config.accounts:
        # 1. Load normalized bank data
        normalized_file = base_dir / "normalized" / f"{account.slug}.json"
        normalized_data = read_json(normalized_file)

        bank_txs = [BankTransaction.from_dict(tx) for tx in normalized_data["transactions"]]
        balance_points = [BalancePoint.from_dict(bp) for bp in normalized_data["balances"]]

        # Filter YNAB transactions for this account
        ynab_txs_for_account = [tx for tx in ynab_transactions if tx.account_id == account.ynab_account_id]

        # 2. Match bank transactions with YNAB transactions
        bank_matches: dict[BankTransaction, MatchResult] = {}
        for bank_tx in bank_txs:
            match_result = find_matches(bank_tx, ynab_txs_for_account)
            bank_matches[bank_tx] = match_result

        # Track matched YNAB transaction IDs
        matched_ynab_ids = set()
        for match_result in bank_matches.values():
            if match_result.match_type in ("exact", "fuzzy") and match_result.ynab_transaction:
                # Use object id to track which YNAB transactions were matched
                matched_ynab_ids.add(id(match_result.ynab_transaction))

        # Track unmatched transactions
        unmatched_bank_txs = [tx for tx, result in bank_matches.items() if result.match_type == "none"]
        unmatched_ynab_txs = [tx for tx in ynab_txs_for_account if id(tx) not in matched_ynab_ids]

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

        # Build account result
        account_result = {
            "account_id": account.slug,
            "operations": operations,
            "balance_reconciliation": balance_recon.to_dict(),
        }
        account_results.append(account_result)

    # 5. Write operations JSON
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = base_dir / "reconciliation" / f"{timestamp}_reconciliation.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Calculate summary
    all_operations = [op for account in account_results for op in account["operations"]]
    operations_by_type = {
        "create_transaction": sum(1 for op in all_operations if op["type"] == "create_transaction"),
        "flag_discrepancy": sum(1 for op in all_operations if op["type"] == "flag_discrepancy"),
    }

    output_data = {
        "version": "1.0",
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source_system": "bank_reconciliation",
        },
        "accounts": account_results,
        "summary": {
            "total_operations": len(all_operations),
            "operations_by_type": operations_by_type,
        },
    }

    write_json(output_file, output_data)
    return output_file
