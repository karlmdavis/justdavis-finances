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

        # Track unmatched transactions
        unmatched_bank_txs = [tx for tx, result in bank_matches.items() if result.match_type == "none"]

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
        # Create simplified YNAB balances dict (for now, use empty dict - will be populated in future)
        ynab_balances: dict[FinancialDate, Money] = {}

        balance_recon = build_balance_reconciliation(
            account_id=account.slug,
            balance_points=balance_points,
            ynab_balances=ynab_balances,
            unmatched_bank_txs=unmatched_bank_txs,
            unmatched_ynab_txs=[],  # Simplified for now
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
