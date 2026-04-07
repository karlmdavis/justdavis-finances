"""Reconcile bank data with YNAB transactions."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from finances.bank_accounts.balance_reconciliation import build_balance_reconciliation
from finances.bank_accounts.matching import MatchingYnabTransaction, MatchResult, find_matches, make_import_id
from finances.bank_accounts.models import (
    BalancePoint,
    BalanceReconciliation,
    BankAccountsConfig,
    BankTransaction,
)
from finances.bank_accounts.operations import CandidateMatch, CreateOp, DeleteOp, FlagOp, Op
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json

# YNAB's internal payee name for the initial balance entry on every account.
# Kept as a module-level constant so the delete-op guard is testable without magic strings.
# Source: YNAB API documentation / observed YNAB export behavior.
YNAB_STARTING_BALANCE_PAYEE = "Starting Balance"


def _classify_mismatch_reason(
    ynab_tx_date: FinancialDate,
    coverage_intervals: list[tuple[FinancialDate, FinancialDate]],
) -> str:
    """Classify why a YNAB transaction has no matching bank transaction.

    Returns one of:
        "pre_coverage"       — date is before the first coverage interval
        "coverage_gap"       — date falls between two coverage intervals
        "post_coverage"      — date is after the last coverage interval
        "within_coverage"    — date is inside coverage but no bank tx matched (true mismatch)
    """
    if not coverage_intervals:
        return "pre_coverage"

    sorted_ivs = sorted(coverage_intervals, key=lambda iv: iv[0])
    first_start = sorted_ivs[0][0]
    last_end = sorted_ivs[-1][1]

    if ynab_tx_date < first_start:
        return "pre_coverage"
    if ynab_tx_date > last_end:
        return "post_coverage"
    for start, end in sorted_ivs:
        if start <= ynab_tx_date <= end:
            return "within_coverage"
    return "coverage_gap"


@dataclass(frozen=True)
class ReconciliationResult:
    """Result of reconciling a single account."""

    reconciliation: BalanceReconciliation
    unmatched_bank_txs: tuple[BankTransaction, ...]
    unmatched_ynab_txs: tuple[MatchingYnabTransaction, ...]
    operations: tuple[Op, ...]
    # Each entry: {tx dict, "mismatch_reason": str}
    categorized_unmatched_ynab: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "balance_reconciliation": self.reconciliation.to_dict(),
            "unmatched_bank_txs": [tx.to_dict() for tx in self.unmatched_bank_txs],
            "unmatched_ynab_txs": [tx.to_dict() for tx in self.unmatched_ynab_txs],
            "categorized_unmatched_ynab": list(self.categorized_unmatched_ynab),
            "operations": [op.to_dict() for op in self.operations],
        }


def calculate_ynab_balances(
    ynab_txs: list[MatchingYnabTransaction],
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
    if not balance_points or not ynab_txs:
        return {}

    sorted_ynab_txs = sorted(ynab_txs, key=lambda tx: tx.date)
    sorted_dates = sorted({bp.date for bp in balance_points})

    # Single-pass O(n+m): advance through sorted txs once, recording cumulative
    # balance at each balance point date instead of re-summing from the start.
    running_total = Money.from_cents(0)
    cumulative: dict[FinancialDate, Money] = {}
    tx_idx = 0
    for date in sorted_dates:
        while tx_idx < len(sorted_ynab_txs) and sorted_ynab_txs[tx_idx].date <= date:
            running_total += sorted_ynab_txs[tx_idx].amount
            tx_idx += 1
        cumulative[date] = running_total

    return {bp.date: cumulative[bp.date] for bp in balance_points}


def reconcile_account_data(
    config: BankAccountsConfig,
    base_dir: Path,
    ynab_transactions: list[MatchingYnabTransaction],
    raw_ynab_by_id: dict[str, Any] | None = None,
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
        raw_ynab_by_id: Dict mapping YNAB transaction id → raw YNAB dict.
            Required for constructing delete_ynab_transaction operations.
            Defaults to {} (skips delete ops if not provided).

    Returns:
        Dictionary mapping account slug to ReconciliationResult
    """
    if raw_ynab_by_id is None:
        raw_ynab_by_id = {}

    # Process each account
    results: dict[str, ReconciliationResult] = {}

    for account in config.accounts:
        # 1. Load normalized bank data using timestamped files (Pattern C)
        normalized_dir = base_dir / "normalized"

        account_files = list(normalized_dir.glob(f"*_{account.slug}.json"))

        if not account_files:
            # Skip account if no normalized data exists
            continue

        most_recent_file = max(account_files, key=lambda f: f.name)
        normalized_data = read_json(most_recent_file)

        bank_txs = [BankTransaction.from_dict(tx) for tx in normalized_data["transactions"]]
        balance_points = [BalancePoint.from_dict(bp) for bp in normalized_data["balance_points"]]

        if not bank_txs and not balance_points:
            print(
                f"  WARNING: account '{account.slug}' has no transactions in {most_recent_file} — skipping reconciliation"
            )
            continue

        # Filter YNAB transactions for this account
        ynab_txs_for_account = [tx for tx in ynab_transactions if tx.account_id == account.ynab_account_id]

        # 2. Match bank transactions with YNAB transactions (greedy one-to-one)
        # Each claimed YNAB tx is removed from the pool so two bank txs can't claim the same one.
        # seq tracks how many bank txs share the same (date, amount, description) key so that
        # each gets a distinct import_id (seq=0 → original formula, seq≥1 → ":N" suffix).
        # Use a list of (bank_tx, match_result, seq) tuples — NOT a dict keyed by bank_tx.
        # BankTransaction is a frozen dataclass so duplicate txs (same date/amount/description)
        # share the same hash, causing dict key collisions that silently drop match results.
        bank_match_entries: list[tuple[BankTransaction, MatchResult, int]] = []
        # Key by Python object identity so removal is O(1) rather than O(n) list.remove().
        remaining_ynab: dict[int, MatchingYnabTransaction] = {id(tx): tx for tx in ynab_txs_for_account}
        seen_keys: dict[tuple[str, int, str], int] = {}
        for bank_tx in bank_txs:
            key = (str(bank_tx.posted_date), bank_tx.amount.to_milliunits(), bank_tx.description)
            seq = seen_keys.get(key, 0)
            seen_keys[key] = seq + 1
            expected_id = make_import_id(
                account.slug,
                str(bank_tx.posted_date),
                bank_tx.amount.to_milliunits(),
                bank_tx.description,
                seq,
            )
            match_result = find_matches(
                bank_tx,
                list(remaining_ynab.values()),
                account.ynab_date_offset_days,
                expected_import_id=expected_id,
            )
            bank_match_entries.append((bank_tx, match_result, seq))
            if match_result.match_type in ("exact", "fuzzy") and match_result.ynab_transaction:
                del remaining_ynab[id(match_result.ynab_transaction)]  # O(1)

        # Track unmatched transactions.
        # Ambiguous bank txs are included here: they generate a FlagOp but the bank still
        # recorded these transactions, so they must count toward balance adjustment.
        unmatched_bank_txs = [
            tx for tx, result, _seq in bank_match_entries if result.match_type in ("none", "ambiguous")
        ]
        unmatched_ynab_txs = list(remaining_ynab.values())  # whatever wasn't claimed

        # 3. Generate operations
        operations: list[Op] = []

        for bank_tx, match_result, seq in bank_match_entries:
            if match_result.match_type == "none":
                operations.append(
                    CreateOp(
                        account_id=account.ynab_account_id,
                        transaction=bank_tx,
                        import_id_seq=seq,
                    )
                )
            elif match_result.match_type == "ambiguous":
                candidates_dicts: list[CandidateMatch] = (
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
                    FlagOp(
                        transaction=bank_tx,
                        candidates=tuple(candidates_dicts),
                        message="Multiple possible matches - manual review required",
                    )
                )

        # 3b. Generate delete operations for orphaned YNAB transactions
        raw_intervals = normalized_data.get("coverage_intervals", [])
        coverage_intervals = [
            (
                FinancialDate.from_string(iv["start_date"]),
                FinancialDate.from_string(iv["end_date"]),
            )
            for iv in raw_intervals
        ]

        for ynab_tx in unmatched_ynab_txs:
            if _classify_mismatch_reason(ynab_tx.date, coverage_intervals) != "within_coverage":
                continue
            if ynab_tx.is_transfer:
                continue
            if ynab_tx.payee_name == YNAB_STARTING_BALANCE_PAYEE:
                continue
            if ynab_tx.id is None:
                raise ValueError(
                    f"YNAB transaction with date={ynab_tx.date} amount={ynab_tx.amount} "
                    f"is an orphan within coverage but has no id — "
                    f"this indicates a programming error in the YNAB cache loader"
                )
            raw_tx = raw_ynab_by_id.get(ynab_tx.id)
            if raw_tx is None:
                raise ValueError(
                    f"YNAB transaction id={ynab_tx.id} not found in raw cache — "
                    f"the cache may be incomplete or out of sync"
                )
            operations.append(DeleteOp(transaction=raw_tx))

        # 3c. Categorize each unmatched YNAB tx with a mismatch_reason
        categorized: list[dict[str, Any]] = []
        for ynab_tx in unmatched_ynab_txs:
            reason = _classify_mismatch_reason(ynab_tx.date, list(coverage_intervals))
            entry: dict[str, Any] = {
                "date": str(ynab_tx.date),
                "amount_milliunits": ynab_tx.amount.to_milliunits(),
                "payee_name": ynab_tx.payee_name,
                "memo": ynab_tx.memo,
                "id": ynab_tx.id,
                "is_transfer": ynab_tx.is_transfer,
                "mismatch_reason": reason,
            }
            categorized.append(entry)

        # 4. Build balance reconciliation
        # Calculate YNAB running balances from transactions
        all_balance_points = balance_points + list(account.manual_balance_points)
        ynab_balances = calculate_ynab_balances(ynab_txs_for_account, all_balance_points)

        balance_recon = build_balance_reconciliation(
            account_id=account.slug,
            balance_points=balance_points,
            ynab_balances=ynab_balances,
            unmatched_bank_txs=unmatched_bank_txs,
            unmatched_ynab_txs=unmatched_ynab_txs,
            manual_balance_points=list(account.manual_balance_points),
        )

        # Build reconciliation result for this account
        result = ReconciliationResult(
            reconciliation=balance_recon,
            unmatched_bank_txs=tuple(unmatched_bank_txs),
            unmatched_ynab_txs=tuple(unmatched_ynab_txs),
            operations=tuple(operations),
            categorized_unmatched_ynab=tuple(categorized),
        )
        results[account.slug] = result

    return results


def print_reconciliation_summary(results: dict[str, "ReconciliationResult"]) -> None:
    """Print a human-readable reconciliation summary to stdout."""
    print("\n=== Bank Reconciliation Summary ===\n")
    for slug, result in results.items():
        unmatched_bank = len(result.unmatched_bank_txs)
        unmatched_ynab = len(result.unmatched_ynab_txs)
        print(f"{slug}: {unmatched_bank} unmatched bank txs, {unmatched_ynab} unmatched YNAB txs")

        # Count by mismatch reason
        reason_counts: Counter[str] = Counter(e["mismatch_reason"] for e in result.categorized_unmatched_ynab)
        for reason in ("pre_coverage", "coverage_gap", "post_coverage", "within_coverage"):
            count = reason_counts.get(reason, 0)
            if count == 0 and reason != "within_coverage":
                continue
            suffix = ""
            if reason == "post_coverage" and count > 0:
                suffix = "  → download newer bank statements"
            elif reason == "coverage_gap" and count > 0:
                suffix = "  → download missing bank statements to fill gap"
            elif reason == "pre_coverage" and count > 0:
                suffix = "  → pre-dates bank data coverage (cannot auto-resolve)"
            elif reason == "within_coverage" and count > 0:
                suffix = "  ⚠ true mismatch within coverage — needs investigation"
            print(f"  {reason:<25}: {count:3d} txs{suffix}")

        if result.unmatched_bank_txs:
            print("  unmatched bank txs (→ create operations):")
            for tx in sorted(result.unmatched_bank_txs, key=lambda t: t.posted_date):
                payee = tx.merchant or tx.description
                print(f"    {tx.posted_date}  {tx.amount.format_signed()}  {payee}")

        recon = result.reconciliation
        if recon.last_reconciled_date:
            print(f"  last reconciled: {recon.last_reconciled_date}")
        elif recon.points:
            closest = min(recon.points, key=lambda p: abs(p.difference.to_cents()))
            print(f"  closest to reconciled: {closest.date} (diff {closest.difference})")
        print()
