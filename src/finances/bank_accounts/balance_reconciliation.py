"""Balance reconciliation logic for bank accounts."""

from finances.bank_accounts.matching import MatchingYnabTransaction
from finances.bank_accounts.models import (
    BalancePoint,
    BalanceReconciliation,
    BalanceReconciliationPoint,
    BankTransaction,
)
from finances.core import FinancialDate, Money


def reconcile_balance_point(
    date: FinancialDate,
    bank_balance: Money,
    ynab_balance: Money,
    bank_txs_not_in_ynab: Money,  # Sum of unmatched bank txs
    ynab_txs_not_in_bank: Money,  # Sum of unmatched YNAB txs
) -> BalanceReconciliationPoint:
    """
    Reconcile balances at a single date.

    Formula:
        Adjusted Bank = Bank + sum(bank_txs_not_in_ynab)
        Adjusted YNAB = YNAB + sum(ynab_txs_not_in_bank)
        Difference = Adjusted Bank - Adjusted YNAB
        Reconciled = (Difference == 0)

    Args:
        date: Date of balance point
        bank_balance: Raw bank balance
        ynab_balance: Raw YNAB balance
        bank_txs_not_in_ynab: Sum of unmatched bank transactions
        ynab_txs_not_in_bank: Sum of unmatched YNAB transactions

    Returns:
        BalanceReconciliationPoint with adjusted balances and reconciliation status
    """
    adjusted_bank = bank_balance + bank_txs_not_in_ynab
    # bank_txs_not_in_ynab is negative for expenses → effectively removes those
    # txs from the bank balance so both sides represent the same agreed-upon set
    adjusted_ynab = ynab_balance + ynab_txs_not_in_bank
    # ynab_txs_not_in_bank is negative for expenses → same reasoning as above
    difference = adjusted_bank - adjusted_ynab

    return BalanceReconciliationPoint(
        date=date,
        bank_balance=bank_balance,
        ynab_balance=ynab_balance,
        bank_txs_not_in_ynab=bank_txs_not_in_ynab,
        ynab_txs_not_in_bank=ynab_txs_not_in_bank,
        adjusted_bank_balance=adjusted_bank,
        adjusted_ynab_balance=adjusted_ynab,
        is_reconciled=(difference == Money.from_cents(0)),
        difference=difference,
    )


def build_balance_reconciliation(
    account_id: str,
    balance_points: list[BalancePoint],
    ynab_balances: dict[FinancialDate, Money],
    unmatched_bank_txs: list[BankTransaction],
    unmatched_ynab_txs: list[MatchingYnabTransaction],
    manual_balance_points: list[BalancePoint] | None = None,
) -> BalanceReconciliation:
    """
    Build complete balance reconciliation history.

    Args:
        account_id: Account identifier (slug)
        balance_points: List of bank balance points from statement files
        ynab_balances: Dict mapping dates to YNAB balances
        unmatched_bank_txs: List of bank transactions not in YNAB
        unmatched_ynab_txs: List of YNAB transactions not in bank
        manual_balance_points: Optional list of manually-verified balance checkpoints
            (e.g. from iPhone Wallet). Merged with balance_points; manual points are
            used when no file-derived point exists for the same date.

    Returns:
        BalanceReconciliation with full reconciliation history
    """
    # Merge file-derived and manual balance points.
    # File-derived points take precedence when both exist on the same date.
    if manual_balance_points:
        file_dates = {bp.date for bp in balance_points}
        extra = [bp for bp in manual_balance_points if bp.date not in file_dates]
        merged = sorted(list(balance_points) + extra, key=lambda bp: bp.date)
    else:
        merged = sorted(balance_points, key=lambda bp: bp.date)

    # Pre-sort unmatched transactions for single-pass O(n+m) cumulative summing.
    sorted_bank = sorted(unmatched_bank_txs, key=lambda tx: tx.posted_date)
    sorted_ynab = sorted(unmatched_ynab_txs, key=lambda tx: tx.date)

    bank_ptr = 0
    ynab_ptr = 0
    bank_running = Money.from_cents(0)
    ynab_running = Money.from_cents(0)
    points = []

    for balance_point in merged:
        date = balance_point.date
        ynab_balance = ynab_balances.get(date, Money.from_cents(0))

        while bank_ptr < len(sorted_bank) and sorted_bank[bank_ptr].posted_date <= date:
            bank_running = bank_running + sorted_bank[bank_ptr].amount
            bank_ptr += 1

        while ynab_ptr < len(sorted_ynab) and sorted_ynab[ynab_ptr].date <= date:
            ynab_running = ynab_running + sorted_ynab[ynab_ptr].amount
            ynab_ptr += 1

        point = reconcile_balance_point(date, balance_point.amount, ynab_balance, bank_running, ynab_running)
        points.append(point)

    # Find last reconciled and first diverged
    last_reconciled = None
    first_diverged = None

    for point in points:
        if point.is_reconciled:
            last_reconciled = point.date
            first_diverged = None  # reset: this reconciliation supersedes any prior divergence
        elif first_diverged is None:
            first_diverged = point.date

    return BalanceReconciliation(
        account_id=account_id,
        points=tuple(points),
        last_reconciled_date=last_reconciled,
        first_diverged_date=first_diverged,
    )
