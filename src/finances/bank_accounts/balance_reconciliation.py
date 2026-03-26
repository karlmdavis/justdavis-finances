"""Balance reconciliation logic for bank accounts."""

from finances.bank_accounts.matching import YnabTransaction
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
    adjusted_ynab = ynab_balance + ynab_txs_not_in_bank
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
    unmatched_ynab_txs: list[YnabTransaction],
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

    points = []

    for balance_point in merged:
        date = balance_point.date
        ynab_balance = ynab_balances.get(date, Money.from_cents(0))

        # Sum unmatched transactions up to this date
        bank_sum = sum(
            (tx.amount for tx in unmatched_bank_txs if tx.posted_date <= date),
            Money.from_cents(0),
        )
        ynab_sum = sum(
            (tx.amount for tx in unmatched_ynab_txs if tx.date <= date),
            Money.from_cents(0),
        )

        point = reconcile_balance_point(date, balance_point.amount, ynab_balance, bank_sum, ynab_sum)
        points.append(point)

    # Find last reconciled and first diverged
    last_reconciled = None
    first_diverged = None

    for point in points:
        if point.is_reconciled:
            last_reconciled = point.date
        elif first_diverged is None:
            first_diverged = point.date

    return BalanceReconciliation(
        account_id=account_id,
        points=tuple(points),
        last_reconciled_date=last_reconciled,
        first_diverged_date=first_diverged,
    )
