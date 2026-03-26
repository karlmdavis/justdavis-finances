#!/usr/bin/env python3
"""One-time diagnostic script for bank reconciliation mismatch analysis.

Reads the latest normalized bank data, reconciliation operations, YNAB transaction cache,
and account config (including manual balance points) to produce a per-account, per-month
markdown report showing balance mismatches and unmatched YNAB transactions.

Usage (from repo root):
    uv run python dev/scripts/bank_reconciliation_diagnostic.py
"""

import calendar
import datetime
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add src to path so finances package is importable without editable install
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, BankTransaction
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_latest_normalized(base_dir: Path) -> dict[str, dict]:
    """Load latest normalized data per account slug."""
    normalized_dir = base_dir / "normalized"
    results: dict[str, dict] = {}
    for slug in ["chase-checking", "chase-credit", "apple-card", "apple-savings"]:
        files = sorted(normalized_dir.glob(f"*_{slug}.json"))
        if files:
            results[slug] = read_json(files[-1])
    return results


def load_latest_operations(base_dir: Path) -> dict:
    """Load the latest reconciliation operations JSON file."""
    recon_dir = base_dir / "reconciliation"
    files = sorted(recon_dir.glob("*_operations.json"))
    if not files:
        return {}
    return read_json(files[-1])


def load_ynab_txs_by_account(data_dir: Path) -> dict[str, list[dict]]:
    """Load YNAB transactions from cache, grouped by account_id."""
    txs_file = data_dir / "ynab" / "cache" / "transactions.json"
    data = read_json(txs_file)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for tx in data:
        acct_id = tx.get("account_id")
        if acct_id:
            grouped[acct_id].append(tx)
    return dict(grouped)


# ---------------------------------------------------------------------------
# Computation helpers
# ---------------------------------------------------------------------------


def classify_reason(
    date: FinancialDate,
    coverage_intervals: list[tuple[FinancialDate, FinancialDate]],
) -> str:
    """Classify why a YNAB transaction has no matching bank transaction."""
    if not coverage_intervals:
        return "pre_coverage"
    sorted_ivs = sorted(coverage_intervals, key=lambda iv: iv[0])
    first_start = sorted_ivs[0][0]
    last_end = sorted_ivs[-1][1]
    if date < first_start:
        return "pre_coverage"
    if date > last_end:
        return "post_coverage"
    for start, end in sorted_ivs:
        if start <= date <= end:
            return "within_coverage"
    return "coverage_gap"


def eom(year: int, month: int) -> FinancialDate:
    """Return the last day of the given month as a FinancialDate."""
    last_day = calendar.monthrange(year, month)[1]
    return FinancialDate(date=datetime.date(year, month, last_day))


def som(year: int, month: int) -> FinancialDate:
    """Return the first day of the given month as a FinancialDate."""
    return FinancialDate(date=datetime.date(year, month, 1))


def fmt(m: Money) -> str:
    """Format Money as a dollar string using integer arithmetic."""
    cents = m.to_cents()
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}${c // 100:,}.{c % 100:02d}"


def ynab_running_balance_at(ynab_txs: list[dict], date: FinancialDate) -> Money:
    """Sum all YNAB transactions up to and including date."""
    return sum(
        (
            Money.from_milliunits(tx["amount"])
            for tx in ynab_txs
            if FinancialDate.from_string(tx["date"]) <= date
        ),
        Money.from_cents(0),
    )


def bank_balance_at_eom(
    account: AccountConfig,
    bank_txs: list[BankTransaction],
    date: FinancialDate,
    manual_bps: list[tuple[FinancialDate, Money]],
) -> Money | None:
    """
    Compute the bank balance at the given date.

    For checking accounts: use the running_balance field of the last TX on/before date.
    For credit/savings: use cumulative sum of bank TXs from zero, anchored by the
    nearest manual balance point at or before the target date.
    """
    if account.account_type == "checking":
        candidates = [
            (tx.posted_date, tx.running_balance)
            for tx in bank_txs
            if tx.posted_date <= date and tx.running_balance is not None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[0])[1]

    # credit / savings: cumulative TX sum from zero (account opens at $0, or known starting amount)
    # The first manual balance point anchors the cumulative sum.
    if not bank_txs:
        return None

    # Find the best anchor: the manual balance point closest to (and on or before) date
    anchor_date: FinancialDate | None = None
    anchor_amount = Money.from_cents(0)
    if manual_bps:
        prior = [(d, a) for d, a in manual_bps if d <= date]
        if prior:
            anchor_date, anchor_amount = max(prior, key=lambda x: x[0])

    if anchor_date is None:
        # Sum all bank TXs from the very start up to date
        return sum(
            (tx.amount for tx in bank_txs if tx.posted_date <= date),
            Money.from_cents(0),
        )

    # Sum bank TXs between anchor_date (exclusive) and target date (inclusive)
    delta = sum(
        (tx.amount for tx in bank_txs if anchor_date < tx.posted_date <= date),
        Money.from_cents(0),
    )
    return anchor_amount + delta


def month_range_from_coverage(
    coverage_intervals: list[tuple[FinancialDate, FinancialDate]],
    bank_txs: list[BankTransaction],
    manual_bps: list[tuple[FinancialDate, Money]],
) -> list[tuple[int, int]]:
    """Return list of (year, month) tuples spanning all covered/known data."""
    dates: list[FinancialDate] = []

    for start, end in coverage_intervals:
        dates += [start, end]
    for d, _ in manual_bps:
        dates.append(d)
    if bank_txs:
        dates.append(min(tx.posted_date for tx in bank_txs))
        dates.append(max(tx.posted_date for tx in bank_txs))

    if not dates:
        return []

    earliest = min(dates)
    latest = max(dates)

    months: list[tuple[int, int]] = []
    cur_y, cur_m = earliest.date.year, earliest.date.month
    end_y, end_m = latest.date.year, latest.date.month
    while (cur_y, cur_m) <= (end_y, end_m):
        months.append((cur_y, cur_m))
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return months


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------


def section_coverage(
    account: AccountConfig,
    coverage_intervals: list[tuple[FinancialDate, FinancialDate]],
    categorized: list[dict],
) -> list[str]:
    lines: list[str] = []
    lines.append("### Coverage Intervals")
    lines.append("")

    if not coverage_intervals:
        lines.append("_No coverage intervals available. Bank data may not have been parsed yet._")
        lines.append("")
        return lines

    sorted_ci = sorted(coverage_intervals, key=lambda x: x[0])

    lines.append("| Period | Status | Unmatched YNAB TXs |")
    lines.append("|---|---|---|")

    # Pre-coverage
    pre = [tx for tx in categorized if tx["mismatch_reason"] == "pre_coverage"]
    if pre:
        pre_start = min(FinancialDate.from_string(tx["date"]) for tx in pre)
        lines.append(
            f"| {pre_start} - {sorted_ci[0][0]} | ⬛ pre-coverage | "
            f"{len(pre)} txs (pre-date bank data - cannot auto-resolve) |"
        )

    for i, (start, end) in enumerate(sorted_ci):
        within = [
            tx
            for tx in categorized
            if tx["mismatch_reason"] == "within_coverage"
            and start <= FinancialDate.from_string(tx["date"]) <= end
        ]
        note = f"{len(within)} true mismatches ⚠" if within else "✓ clean"
        lines.append(f"| {start} - {end} | ✓ covered | {note} |")

        # Gap to next interval
        if i + 1 < len(sorted_ci):
            next_start = sorted_ci[i + 1][0]
            gap_days = (next_start.date - end.date).days - 1
            in_gap = [
                tx
                for tx in categorized
                if tx["mismatch_reason"] == "coverage_gap"
                and end < FinancialDate.from_string(tx["date"]) < next_start
            ]
            note = (
                f"{gap_days} day gap, {len(in_gap)} YNAB txs -> " f"download statements for this period"
                if in_gap
                else f"{gap_days} day gap"
            )
            lines.append(f"| {end} - {next_start} | ⚠ GAP | {note} |")

    # Post-coverage
    post = [tx for tx in categorized if tx["mismatch_reason"] == "post_coverage"]
    if post:
        lines.append(
            f"| after {sorted_ci[-1][1]} | 🔲 post-coverage | "
            f"{len(post)} txs -> download newer statements |"
        )

    lines.append("")
    return lines


def section_monthly_balance(
    account: AccountConfig,
    bank_txs: list[BankTransaction],
    ynab_txs: list[dict],
    coverage_intervals: list[tuple[FinancialDate, FinancialDate]],
    manual_bps: list[tuple[FinancialDate, Money]],
    categorized: list[dict],
) -> list[str]:
    lines: list[str] = []
    lines.append("### Per-Month Balance Comparison")
    lines.append("")

    months = month_range_from_coverage(coverage_intervals, bank_txs, manual_bps)
    if not months:
        lines.append("_No data range available for balance comparison._")
        lines.append("")
        return lines

    has_bank_balance = account.account_type == "checking" or bool(manual_bps) or bool(bank_txs)

    lines.append(
        "| Month | Cvg? | Bank TXs | YNAB TXs | "
        "Unmatched Bank | Unmatched YNAB | "
        "Bank EOM | YNAB EOM | Running Diff |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")

    # Pre-compute sets for fast lookup
    unmatched_ynab_by_month: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for tx in categorized:
        d = FinancialDate.from_string(tx["date"])
        unmatched_ynab_by_month[(d.date.year, d.date.month)].append(tx)

    for year, month in months:
        eom_d = eom(year, month)
        som_d = som(year, month)

        # Coverage status for this month
        in_coverage = any(start <= eom_d and som_d <= end for start, end in coverage_intervals)
        cvg_mark = "✓" if in_coverage else "⚠"

        # Bank TXs this month
        month_bank = [
            tx for tx in bank_txs if tx.posted_date.date.year == year and tx.posted_date.date.month == month
        ]
        # YNAB TXs this month
        month_ynab = [
            tx
            for tx in ynab_txs
            if FinancialDate.from_string(tx["date"]).date.year == year
            and FinancialDate.from_string(tx["date"]).date.month == month
        ]
        # Unmatched YNAB this month
        month_unmatched_ynab = unmatched_ynab_by_month.get((year, month), [])

        # Bank EOM balance
        if has_bank_balance:
            bank_eom = bank_balance_at_eom(account, bank_txs, eom_d, manual_bps)
            bank_eom_str = fmt(bank_eom) if bank_eom is not None else "N/A"
        else:
            bank_eom = None
            bank_eom_str = "N/A"

        # YNAB EOM balance
        ynab_eom = ynab_running_balance_at(ynab_txs, eom_d)
        ynab_eom_str = fmt(ynab_eom)

        # Running diff
        if bank_eom is not None:
            diff = bank_eom - ynab_eom
            diff_str = fmt(diff)
            if diff.to_cents() == 0:
                diff_str = "**$0.00** ✓"
        else:
            diff_str = "N/A"

        lines.append(
            f"| {year}-{month:02d} | {cvg_mark} | {len(month_bank)} | {len(month_ynab)} | "
            f"0 | {len(month_unmatched_ynab)} | "
            f"{bank_eom_str} | {ynab_eom_str} | {diff_str} |"
        )

    lines.append("")

    # Manual balance point spot-checks
    if manual_bps:
        lines.append("**Manual balance point spot-checks:**")
        lines.append("")
        lines.append("| Date | Wallet/Manual Balance | YNAB Balance | Diff |")
        lines.append("|---|---|---|---|")
        for d, bank_amount in sorted(manual_bps, key=lambda x: x[0]):
            ynab_amount = ynab_running_balance_at(ynab_txs, d)
            diff = bank_amount - ynab_amount
            diff_str = fmt(diff)
            if diff.to_cents() == 0:
                diff_str = "**$0.00** ✓"
            lines.append(f"| {d} | {fmt(bank_amount)} | {fmt(ynab_amount)} | {diff_str} |")
        lines.append("")

    return lines


def section_unmatched_ynab(categorized: list[dict]) -> list[str]:
    lines: list[str] = []
    lines.append("### Unmatched YNAB Transactions")
    lines.append("")

    if not categorized:
        lines.append("_No unmatched YNAB transactions._")
        lines.append("")
        return lines

    reason_counts = Counter(tx["mismatch_reason"] for tx in categorized)
    total = sum(reason_counts.values())
    lines.append(f"**Total: {total} unmatched**")
    for reason in ("pre_coverage", "coverage_gap", "post_coverage", "within_coverage"):
        count = reason_counts.get(reason, 0)
        if count > 0:
            lines.append(f"- `{reason}`: {count}")
    lines.append("")

    # Only show within_coverage (true mismatches) in detail - others are expected
    within = [tx for tx in categorized if tx["mismatch_reason"] == "within_coverage"]
    if within:
        lines.append("**Within-coverage mismatches (require investigation):**")
        lines.append("")
        lines.append("| Date | Amount | Payee | Transfer? |")
        lines.append("|---|---|---|---|")
        for tx in sorted(within, key=lambda t: t["date"]):
            date = tx["date"]
            amt = fmt(Money.from_milliunits(tx["amount_milliunits"]))
            payee = (tx.get("payee_name") or "").replace("|", "\\|")
            is_xfer = "yes" if tx.get("is_transfer") else "no"
            lines.append(f"| {date} | {amt} | {payee} | {is_xfer} |")
        lines.append("")

    # For non-within types, show compressed summary
    for reason in ("pre_coverage", "coverage_gap", "post_coverage"):
        group = [tx for tx in categorized if tx["mismatch_reason"] == reason]
        if not group:
            continue
        group_sorted = sorted(group, key=lambda t: t["date"])
        date_range = f"{group_sorted[0]['date']} - {group_sorted[-1]['date']}"
        total_amt = sum((Money.from_milliunits(tx["amount_milliunits"]) for tx in group), Money.from_cents(0))
        lines.append(f"**{reason}** ({len(group)} txs, {date_range}, net {fmt(total_amt)}):")
        lines.append("")
        lines.append("| Date | Amount | Payee | Transfer? |")
        lines.append("|---|---|---|---|")
        for tx in group_sorted:
            date = tx["date"]
            amt = fmt(Money.from_milliunits(tx["amount_milliunits"]))
            payee = (tx.get("payee_name") or "").replace("|", "\\|")
            is_xfer = "yes" if tx.get("is_transfer") else "no"
            lines.append(f"| {date} | {amt} | {payee} | {is_xfer} |")
        lines.append("")

    return lines


def section_actions(
    account: AccountConfig,
    coverage_intervals: list[tuple[FinancialDate, FinancialDate]],
    categorized: list[dict],
) -> list[str]:
    lines: list[str] = []
    lines.append("### Actions Needed")
    lines.append("")

    reason_counts = Counter(tx["mismatch_reason"] for tx in categorized)

    any_action = False

    post = reason_counts.get("post_coverage", 0)
    if post > 0:
        last_end = max(end for _, end in coverage_intervals) if coverage_intervals else "?"
        lines.append(
            f"- **Download newer bank statements** (after {last_end}): "
            f"resolves {post} YNAB txs currently post-coverage"
        )
        any_action = True

    gap = reason_counts.get("coverage_gap", 0)
    if gap > 0:
        lines.append(
            f"- **Download missing bank statements for coverage gaps**: "
            f"resolves {gap} YNAB txs currently in gaps"
        )
        any_action = True

    within = reason_counts.get("within_coverage", 0)
    if within > 0:
        lines.append(
            f"- **⚠ Investigate {within} within-coverage mismatches** - "
            f"these are true discrepancies; see table above"
        )
        any_action = True

    pre = reason_counts.get("pre_coverage", 0)
    if pre > 0:
        lines.append(
            f"- **Pre-coverage txs** ({pre}): pre-date all bank data - "
            f"no bank download will resolve these; manually verify if correct"
        )
        any_action = True

    if not any_action:
        lines.append("_No actions needed._")

    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Main report generator
# ---------------------------------------------------------------------------


def generate_report(
    config: BankAccountsConfig,
    normalized_by_slug: dict[str, dict],
    operations: dict,
    ynab_txs_by_account_id: dict[str, list[dict]],
) -> str:
    today = datetime.date.today().isoformat()
    lines: list[str] = [
        f"# Bank Reconciliation Mismatch Analysis - {today}",
        "",
        "Diagnostic report generated from:",
        "- Latest `data/bank_accounts/normalized/` files",
        "- Latest `data/bank_accounts/reconciliation/*_operations.json`",
        "- `config/bank_accounts_config.json` (manual balance points)",
        "- `data/ynab/cache/transactions.json`",
        "",
        "---",
        "",
    ]

    accounts_ops = operations.get("accounts", {})

    for account in config.accounts:
        slug = account.slug
        norm = normalized_by_slug.get(slug, {})
        acct_ops = accounts_ops.get(slug, {})
        ynab_txs = ynab_txs_by_account_id.get(account.ynab_account_id, [])

        # Parse coverage intervals from normalized data
        raw_ci = norm.get("coverage_intervals", [])
        coverage_intervals = [
            (
                FinancialDate.from_string(ci["start_date"]),
                FinancialDate.from_string(ci["end_date"]),
            )
            for ci in raw_ci
        ]

        # Parse bank transactions
        bank_txs = [BankTransaction.from_dict(tx) for tx in norm.get("transactions", [])]

        # Parse unmatched YNAB txs from operations
        unmatched_raw = acct_ops.get("unmatched_ynab_txs", [])

        # Use pre-computed categorized data (new format) or compute ourselves
        categorized_raw = acct_ops.get("categorized_unmatched_ynab", [])
        if categorized_raw:
            categorized = list(categorized_raw)
        else:
            categorized = []
            for tx in unmatched_raw:
                date = FinancialDate.from_string(tx["date"])
                categorized.append(
                    {
                        "date": tx["date"],
                        "amount_milliunits": tx["amount_milliunits"],
                        "payee_name": tx.get("payee_name"),
                        "memo": tx.get("memo"),
                        "id": tx.get("id"),
                        "is_transfer": tx.get("is_transfer", False),
                        "mismatch_reason": classify_reason(date, coverage_intervals),
                    }
                )

        # Manual balance points from config
        manual_bps = [(mbp.date, mbp.amount) for mbp in account.manual_balance_points]

        unmatched_bank_count = len(acct_ops.get("unmatched_bank_txs", []))
        lines.append(f"## {account.ynab_account_name} (`{slug}`)")
        lines.append("")
        lines.append(f"**Account type:** {account.account_type}")
        lines.append(f"**Unmatched:** {unmatched_bank_count} bank txs, " f"{len(categorized)} YNAB txs")
        if bank_txs:
            first_tx = min(tx.posted_date for tx in bank_txs)
            last_tx = max(tx.posted_date for tx in bank_txs)
            lines.append(f"**Bank TX range:** {first_tx} - {last_tx} ({len(bank_txs)} txs)")
        if coverage_intervals:
            sorted_ci = sorted(coverage_intervals, key=lambda x: x[0])
            lines.append(
                f"**Coverage:** {sorted_ci[0][0]} - {sorted_ci[-1][1]} "
                f"({len(coverage_intervals)} interval(s))"
            )
        if manual_bps:
            lines.append(f"**Manual balance points:** {len(manual_bps)}")
        lines.append("")

        lines += section_coverage(account, coverage_intervals, categorized)
        lines += section_monthly_balance(
            account, bank_txs, ynab_txs, coverage_intervals, manual_bps, categorized
        )
        lines += section_unmatched_ynab(categorized)
        lines += section_actions(account, coverage_intervals, categorized)

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).parent.parent.parent
    bank_dir = repo_root / "data" / "bank_accounts"
    data_dir = repo_root / "data"
    config_path = repo_root / "config" / "bank_accounts_config.json"
    output_path = (
        repo_root
        / "dev"
        / "reports"
        / f"{datetime.date.today().isoformat()}-bank-reconciliation-mismatch-analysis.md"
    )

    print("Loading config...")
    config = BankAccountsConfig.load(str(config_path))

    print("Loading normalized data...")
    normalized_by_slug = load_latest_normalized(bank_dir)
    for slug, norm in normalized_by_slug.items():
        tx_count = len(norm.get("transactions", []))
        ci_count = len(norm.get("coverage_intervals", []))
        print(f"  {slug}: {tx_count} txs, {ci_count} coverage intervals")

    print("Loading operations...")
    operations = load_latest_operations(bank_dir)
    reconciled_at = operations.get("reconciled_at", "unknown")
    print(f"  Reconciled at: {reconciled_at}")

    print("Loading YNAB transactions...")
    ynab_txs_by_account_id = load_ynab_txs_by_account(data_dir)
    total_ynab = sum(len(v) for v in ynab_txs_by_account_id.values())
    print(f"  {total_ynab} YNAB txs across {len(ynab_txs_by_account_id)} accounts")

    print("Generating report...")
    report = generate_report(config, normalized_by_slug, operations, ynab_txs_by_account_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report + "\n")
    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
