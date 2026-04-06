"""Interactive apply node for bank reconciliation operations."""

import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from finances.bank_accounts.matching import make_import_id
from finances.bank_accounts.models import BankAccountsConfig
from finances.bank_accounts.operations import CreateOp, DeleteOp, FlagOp, op_from_dict
from finances.core import Money
from finances.core.json_utils import format_json, read_json


def _parse_duplicate_ids(stdout: str) -> set[str]:
    """Parse duplicate import IDs from ynab create transaction stdout.

    YNAB prints a line like:
        Warning: 2 duplicate import ID(s) skipped: ["id1", "id2"]
    when it rejects transactions whose import_id already exists in the budget.
    Returns the set of rejected IDs so callers can log them separately.
    """
    match = re.search(r"Warning: \d+ duplicate import ID\(s\) skipped: \[([^\]]*)\]", stdout)
    if not match:
        return set()
    try:
        ids: list[str] = json.loads(f"[{match.group(1)}]")
        return set(ids)
    except (json.JSONDecodeError, ValueError):
        return set()


def _group_operations(accounts_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Group operations by account slug, then by type and date.

    Returns:
        {slug: {
            "creates": {date: [CreateOp, ...]},
            "flags": {date: [FlagOp, ...]},
            "deletes": {date: [DeleteOp, ...]},
        }}
    """
    result: dict[str, dict[str, Any]] = {}
    for slug, account_data in accounts_data.items():
        creates: dict[str, list[CreateOp]] = {}
        flags: dict[str, list[FlagOp]] = {}
        deletes: dict[str, list[DeleteOp]] = {}
        for raw_op in account_data.get("operations", []):
            op = op_from_dict(raw_op)
            if isinstance(op, CreateOp):
                date = str(op.transaction.posted_date)
                creates.setdefault(date, []).append(op)
            elif isinstance(op, FlagOp):
                date = str(op.transaction.posted_date)
                flags.setdefault(date, []).append(op)
            elif isinstance(op, DeleteOp):
                date = op.transaction.get("date", "")
                deletes.setdefault(date, []).append(op)
        result[slug] = {
            "creates": creates,
            "flags": flags,
            "deletes": deletes,
        }
    return result


def _build_file_payload(ops: list[CreateOp], account_id: str, slug: str) -> list[dict[str, Any]]:
    """Build list of transaction dicts for ynab create transaction --file -."""
    payload = []
    for op in ops:
        posted_date = str(op.transaction.posted_date)
        amount_milliunits = op.transaction.amount.to_milliunits()
        payee_name = op.transaction.merchant or op.transaction.description
        import_id = _get_import_id(op, slug)
        payload.append(
            {
                "account_id": account_id,
                "date": posted_date,
                "amount": amount_milliunits,
                "payee_name": payee_name,
                "cleared": "reconciled",
                "import_id": import_id,
            }
        )
    return payload


def _get_import_id(op: CreateOp, slug: str) -> str:
    """Compute the stable import ID for a create_transaction operation."""
    return make_import_id(
        slug,
        str(op.transaction.posted_date),
        op.transaction.amount.to_milliunits(),
        op.transaction.description,
        op.import_id_seq,
    )


def _display_create_batch(date: str, ops: list[CreateOp], slug: str) -> None:
    """Display a CREATE batch header with line items."""
    total = sum(op.transaction.amount.to_milliunits() for op in ops)
    total_display = Money.from_milliunits(total).format_signed()
    n = len(ops)
    noun = f"{n} Transaction{'s' if n != 1 else ''}"
    print(f"\n  Create {noun} in Batch Operation?")
    print(f"    Date:  {date}")
    print(f"    Total: {total_display}")
    print()
    for i, op in enumerate(ops, 1):
        amount_display = op.transaction.amount.format_signed()
        payee_name = op.transaction.merchant or op.transaction.description
        print(f"    {i}. Amount: {amount_display}")
        print(f"       Payee:  {payee_name}")
    print()
    print("    Command To Be Run: ynab create transaction --file -")
    print(f"                       ({n} transaction{'s' if n != 1 else ''} specified as JSON via STDIN)")


def _display_individual_create(date: str, op: CreateOp, account_id: str, slug: str) -> None:
    """Display a single CREATE item for individual review."""
    amount_milliunits = op.transaction.amount.to_milliunits()
    payee_name = op.transaction.merchant or op.transaction.description
    import_id = _get_import_id(op, slug)
    amount_display = op.transaction.amount.format_signed()
    print()
    print("  Create Transaction Individually?")
    print(f"    Date:   {date}")
    print(f"    Amount: {amount_display}")
    print(f"    Payee:  {payee_name}")
    print()
    print("    Command To Be Run: ynab create transaction")
    print(f"                       --account-id {account_id}")
    print(f"                       --amount {amount_milliunits}")
    print(f"                       --date {date}")
    print(f'                       --payee-name "{payee_name}"')
    print("                       --cleared reconciled")
    print(f'                       --import-id "{import_id}"')


def _display_flag_batch(date: str, ops: list[FlagOp]) -> None:
    """Display a FLAG batch header with candidate listings."""
    n = len(ops)
    noun = f"{n} Transaction{'s' if n != 1 else ''}"
    print()
    print(f"  Manual Fix Required: {noun} on {date}")
    print("    These bank transactions matched multiple YNAB entries — resolve manually in YNAB.")
    print()
    for i, op in enumerate(ops, 1):
        amount_display = op.transaction.amount.format_signed()
        merchant = op.transaction.merchant or op.transaction.description
        candidates = list(op.candidates)
        print(f"    {i}. Amount: {amount_display}")
        print(f"       Payee:  {merchant}")
        print("       Candidate Matching Transactions in YNAB:")
        for j, candidate in enumerate(candidates):
            label = chr(ord("a") + j)
            payee = candidate.get("payee_name", "(unknown)")
            cdate = candidate.get("date", "")
            camt = candidate.get("amount_milliunits", 0)
            camt_display = Money.from_milliunits(camt).format_signed()
            print(f"         {label}. Payee:  {payee}")
            print(f"            Date:   {cdate}")
            print(f"            Amount: {camt_display}")


def _read_input(prompt: str, default: str) -> str:
    """Read one line of user input; return default on EOF."""
    try:
        return input(prompt).strip().lower()
    except EOFError:
        print()
        return default


def _prompt_account(slug: str) -> str:
    """Prompt 'Process this account? [Y/n]'. Returns 'y' or 'n'."""
    response = _read_input("Process this account? [Y/n] ", default="n")
    return "n" if response == "n" else "y"


def _prompt_create_batch(has_multiple: bool, payload: list[dict[str, Any]]) -> str:
    """Prompt for batch action. Returns 'y', 'n', or 's' (if multiple items).

    When 'j' is entered, pretty-prints the JSON payload and re-prompts.
    """
    prompt = (
        "  Apply batch, Split batch, see Json? [y/N/s/j] "
        if has_multiple
        else "  Apply batch, see Json? [y/N/j] "
    )
    while True:
        response = _read_input(prompt, default="n")
        if response == "j":
            print(format_json(payload))
            continue
        if response == "y":
            return "y"
        if response == "s" and has_multiple:
            return "s"
        return "n"


def _prompt_apply_individual() -> bool:
    """Prompt for individual apply. Returns True for 'y'."""
    return _read_input("    Apply transaction? [y/N] ", default="n") == "y"


def _prompt_acknowledge_batch() -> str:
    """Prompt 'Acknowledge all, Skip all? [A/n]'. Returns 'a' or 'n'."""
    response = _read_input("  Acknowledge all, Skip all? [A/n] ", default="n")
    return "n" if response == "n" else "a"


def _display_delete_batch(date: str, ops: list[DeleteOp], ynab_delete_log_path: Path) -> None:
    """Display a DELETE batch header with line items."""
    n = len(ops)
    noun = f"{n} Transaction{'s' if n != 1 else ''}"
    print()
    print(f"  Delete Unmatched YNAB {noun} on {date}?")
    print("    These YNAB entries have no corresponding bank transaction.")
    print()
    for i, op in enumerate(ops, 1):
        ynab_tx = op.transaction
        amount_display = Money.from_milliunits(ynab_tx["amount"]).format_signed()
        payee = ynab_tx.get("payee_name", "(unknown)")
        ynab_id = ynab_tx.get("id", "")
        memo = ynab_tx.get("memo")
        print(f"    {i}. Amount: {amount_display}")
        print(f"       Payee:  {payee}")
        if memo:
            print(f"       Memo:   {memo}")
        print(f"       YNAB ID: {ynab_id}")
    print()
    times = f"({n} time{'s' if n != 1 else ''})"
    print(f"    Command To Be Run: ynab delete transaction --id {{id}}  {times}")
    print(f"                       --delete-log {ynab_delete_log_path}")


def _display_individual_delete(date: str, op: DeleteOp, ynab_delete_log_path: Path) -> None:
    """Display a single DELETE item for individual review."""
    ynab_tx = op.transaction
    amount_display = Money.from_milliunits(ynab_tx["amount"]).format_signed()
    payee = ynab_tx.get("payee_name", "(unknown)")
    ynab_id = ynab_tx.get("id", "")
    print()
    print("  Delete YNAB Transaction Individually?")
    memo = ynab_tx.get("memo")
    print(f"    Date:    {date}")
    print(f"    Amount:  {amount_display}")
    print(f"    Payee:   {payee}")
    if memo:
        print(f"    Memo:    {memo}")
    print(f"    YNAB ID: {ynab_id}")
    print()
    print(f"    Command To Be Run: ynab delete transaction --id {ynab_id}")
    print(f"                       --delete-log {ynab_delete_log_path}")


def _prompt_delete_batch(has_multiple: bool) -> str:
    """Prompt for delete batch action. Returns 'y', 'n', or 's' (if multiple items)."""
    prompt = "  Delete all, Split batch, Skip all? [y/N/s] " if has_multiple else "  Delete, Skip? [y/N] "
    response = _read_input(prompt, default="n")
    if response == "y":
        return "y"
    if response == "s" and has_multiple:
        return "s"
    return "n"


_OpT = TypeVar("_OpT", CreateOp, FlagOp, DeleteOp)


def _process_operations_by_date(
    ops_by_date: dict[str, list[_OpT]],
    handle_batch: Callable[[str, list[_OpT]], None],
) -> None:
    """Iterate date-sorted operation batches, calling handle_batch for each."""
    for date in sorted(ops_by_date.keys()):
        handle_batch(date, ops_by_date[date])


def apply_reconciliation_operations(
    ops_file: Path,
    apply_log_path: Path,
    ynab_delete_log_path: Path,
    config: BankAccountsConfig,
) -> dict[str, int]:
    """
    Interactively walk through reconciliation operations and apply them.

    Groups operations account-by-account, then batches by (type, date).
    For create_transaction batches: prompts to apply all, skip all, or split for
    individual review.
    For flag_discrepancy batches: displays candidates and prompts acknowledgement.
    Writes one NDJSON log line per transaction after each API call completes.

    Args:
        ops_file: Path to reconciliation operations JSON file
        apply_log_path: Path for NDJSON apply log output
        ynab_delete_log_path: Path for NDJSON delete log output (sibling of apply_log_path)
        config: Bank accounts configuration (for account ordering and slug lookups)

    Returns:
        Summary counts dict with keys: "applied", "skipped", "acknowledged",
        "deleted", "duplicate_skipped", "failed"
    """
    data = read_json(ops_file)
    accounts_data = data.get("accounts", {})

    # Build slug → account_id mapping from config
    slug_to_account_id: dict[str, str] = {
        account.slug: account.ynab_account_id for account in config.accounts
    }

    grouped = _group_operations(accounts_data)

    counts: dict[str, int] = {
        "applied": 0,
        "skipped": 0,
        "acknowledged": 0,
        "failed": 0,
        "deleted": 0,
        "duplicate_skipped": 0,
    }

    apply_log_path.parent.mkdir(parents=True, exist_ok=True)

    print()
    print("  This node reconciles (i.e. corrects) the transaction data in YNAB,")
    print("  using data from your banks as the source of truth.")
    print()
    print("  CAUTION: If an account has YNAB Direct Import (live bank connection) enabled,")
    print("  creating transactions that predate its Starting Balance may cause YNAB's")
    print("  backend to re-sync historical data from the bank on your behalf. If that")
    print("  happens, watch for new YNAB-imported transactions appearing in the next")
    print("  ynab_sync — treat them as already-reconciled rather than missing, to avoid")
    print("  creating duplicates. You will also need to adjust the Starting Balance entry's")
    print("  date and amount to remain accurate after adding pre-Starting-Balance data.")

    with open(apply_log_path, "a") as log_file:

        def write_log(entry: dict[str, Any]) -> None:
            entry["timestamp"] = datetime.now().isoformat()
            # NDJSON format: one compact JSON object per line — intentionally bypasses
            # format_json (which adds indent=2) to keep each log entry on a single line.
            log_file.write(json.dumps(entry) + "\n")
            log_file.flush()

        # Walk accounts in config order, falling back to dict order for any not in config
        config_slugs = [account.slug for account in config.accounts]
        all_slugs = config_slugs + [s for s in grouped if s not in config_slugs]

        for slug in all_slugs:
            if slug not in grouped:
                continue
            group = grouped[slug]
            account_id = slug_to_account_id.get(slug, "")
            creates = group["creates"]  # {date: [op, ...]}
            flags = group["flags"]  # {date: [op, ...]}
            deletes = group["deletes"]  # {date: [op, ...]}

            total_creates = sum(len(ops) for ops in creates.values())
            total_flags = sum(len(ops) for ops in flags.values())
            total_deletes = sum(len(ops) for ops in deletes.values())
            total_pending = total_creates + total_flags + total_deletes

            print(f"\n  Account Reconciliation Overview: {slug}")

            if total_pending == 0:
                print("    Nothing pending.")
                continue

            # Display account summary
            if total_flags > 0:
                flag_dates = sorted(flags.keys())
                date_range = f"{flag_dates[0]} \u2013 {flag_dates[-1]}"
                noun = f"transaction{'s' if total_flags != 1 else ''}"
                print(f"    Needing Manual Fixes: {total_flags} {noun}")
                print(f"                          ({date_range})")
            if total_deletes > 0:
                delete_dates = sorted(deletes.keys())
                date_range = f"{delete_dates[0]} \u2013 {delete_dates[-1]}"
                days = len(delete_dates)
                noun = f"transaction{'s' if total_deletes != 1 else ''}"
                print(f"    To Be Deleted:        {total_deletes} {noun}")
                print(
                    f"                          (across {days} day{'s' if days != 1 else ''}, {date_range})"
                )
            if total_creates > 0:
                create_dates = sorted(creates.keys())
                date_range = f"{create_dates[0]} \u2013 {create_dates[-1]}"
                days = len(create_dates)
                noun = f"transaction{'s' if total_creates != 1 else ''}"
                print(f"    To Be Created:        {total_creates} {noun}")
                print(
                    f"                          (across {days} day{'s' if days != 1 else ''}, {date_range})"
                )

            print()
            choice = _prompt_account(slug)
            if choice == "n":
                # Log all ops as skipped
                for _date, ops in sorted(flags.items()):
                    for op in ops:
                        candidate_names = [c.get("payee_name", "(unknown)") for c in op.candidates]
                        write_log(
                            {
                                "op_type": "flag_discrepancy",
                                "action": "skipped",
                                "account_slug": slug,
                                "posted_date": str(op.transaction.posted_date),
                                "amount_milliunits": op.transaction.amount.to_milliunits(),
                                "candidates": candidate_names,
                            }
                        )
                        counts["skipped"] += 1
                for _date, ops in sorted(deletes.items()):
                    for op in ops:
                        write_log(
                            {
                                "op_type": "delete_ynab_transaction",
                                "action": "skipped",
                                "account_slug": slug,
                                "transaction": op.transaction,
                            }
                        )
                        counts["skipped"] += 1
                for _date, ops in sorted(creates.items()):
                    for op in ops:
                        import_id = _get_import_id(op, slug)
                        payee_name = op.transaction.merchant or op.transaction.description
                        write_log(
                            {
                                "op_type": "create_transaction",
                                "action": "skipped",
                                "account_slug": slug,
                                "posted_date": str(op.transaction.posted_date),
                                "amount_milliunits": op.transaction.amount.to_milliunits(),
                                "payee_name": payee_name,
                                "import_id": import_id,
                                "included_in_batch": True,
                            }
                        )
                        counts["skipped"] += 1
                continue

            # Process in order: flags, deletes, creates
            def _handle_flag_batch(date: str, batch_ops: list[Any], *, slug: str = slug) -> None:
                _display_flag_batch(date, batch_ops)
                action = _prompt_acknowledge_batch()
                log_action = "acknowledged" if action == "a" else "skipped"
                for op in batch_ops:
                    candidate_names = [c.get("payee_name", "(unknown)") for c in op.candidates]
                    write_log(
                        {
                            "op_type": "flag_discrepancy",
                            "action": log_action,
                            "account_slug": slug,
                            "posted_date": str(op.transaction.posted_date),
                            "amount_milliunits": op.transaction.amount.to_milliunits(),
                            "candidates": candidate_names,
                        }
                    )
                    if log_action == "acknowledged":
                        counts["acknowledged"] += 1
                    else:
                        counts["skipped"] += 1

            def _handle_delete_batch(date: str, batch_ops: list[Any], *, slug: str = slug) -> None:
                _display_delete_batch(date, batch_ops, ynab_delete_log_path)
                has_multiple = len(batch_ops) > 1
                action = _prompt_delete_batch(has_multiple)

                if action == "y":
                    for op in batch_ops:
                        ynab_tx = op.transaction
                        ynab_id = ynab_tx.get("id")
                        if not ynab_id:
                            raise ValueError(
                                f"Delete operation is missing 'id' field — "
                                f"this indicates a programming error in the reconcile node: {ynab_tx}"
                            )
                        del_proc = subprocess.run(
                            [
                                "ynab",
                                "delete",
                                "transaction",
                                "--id",
                                ynab_id,
                                "--delete-log",
                                str(ynab_delete_log_path),
                            ],
                        )
                        exit_code = del_proc.returncode
                        if exit_code != 0:
                            print(f"  ERROR: ynab exited with code {exit_code}")
                            write_log(
                                {
                                    "op_type": "delete_ynab_transaction",
                                    "action": "failed",
                                    "account_slug": slug,
                                    "transaction": ynab_tx,
                                    "ynab_exit_code": exit_code,
                                }
                            )
                            counts["failed"] += 1
                        else:
                            write_log(
                                {
                                    "op_type": "delete_ynab_transaction",
                                    "action": "applied",
                                    "account_slug": slug,
                                    "transaction": ynab_tx,
                                    "ynab_exit_code": exit_code,
                                }
                            )
                            counts["deleted"] += 1

                elif action == "s":
                    # Individual review
                    for op in batch_ops:
                        ynab_tx = op.transaction
                        ynab_id = ynab_tx.get("id")
                        if not ynab_id:
                            raise ValueError(
                                f"Delete operation is missing 'id' field — "
                                f"this indicates a programming error in the reconcile node: {ynab_tx}"
                            )
                        _display_individual_delete(date, op, ynab_delete_log_path)
                        if _prompt_apply_individual():
                            result = subprocess.run(
                                [
                                    "ynab",
                                    "delete",
                                    "transaction",
                                    "--id",
                                    ynab_id,
                                    "--delete-log",
                                    str(ynab_delete_log_path),
                                ],
                            )
                            exit_code = result.returncode
                            if exit_code != 0:
                                print(f"  ERROR: ynab exited with code {exit_code}")
                                write_log(
                                    {
                                        "op_type": "delete_ynab_transaction",
                                        "action": "failed",
                                        "account_slug": slug,
                                        "transaction": ynab_tx,
                                        "ynab_exit_code": exit_code,
                                    }
                                )
                                counts["failed"] += 1
                            else:
                                write_log(
                                    {
                                        "op_type": "delete_ynab_transaction",
                                        "action": "applied",
                                        "account_slug": slug,
                                        "transaction": ynab_tx,
                                        "ynab_exit_code": exit_code,
                                    }
                                )
                                counts["deleted"] += 1
                        else:
                            write_log(
                                {
                                    "op_type": "delete_ynab_transaction",
                                    "action": "skipped",
                                    "account_slug": slug,
                                    "transaction": ynab_tx,
                                }
                            )
                            counts["skipped"] += 1
                    print("  [Returning to batch view]")

                else:  # n
                    for op in batch_ops:
                        write_log(
                            {
                                "op_type": "delete_ynab_transaction",
                                "action": "skipped",
                                "account_slug": slug,
                                "transaction": op.transaction,
                            }
                        )
                        counts["skipped"] += 1

            def _handle_create_batch(
                date: str, batch_ops: list[Any], *, slug: str = slug, account_id: str = account_id
            ) -> None:
                _display_create_batch(date, batch_ops, slug)
                has_multiple = len(batch_ops) > 1
                payload = _build_file_payload(batch_ops, account_id, slug)
                action = _prompt_create_batch(has_multiple, payload)

                if action == "y":
                    proc = subprocess.run(
                        ["ynab", "create", "transaction", "--file", "-"],
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                    )
                    # Print captured output so user sees creation confirmations and warnings
                    if proc.stdout:
                        print(proc.stdout, end="")
                    if proc.stderr:
                        print(proc.stderr, end="")
                    exit_code = proc.returncode
                    duplicate_ids = _parse_duplicate_ids(proc.stdout or "")
                    if exit_code != 0:
                        print(f"  ERROR: ynab exited with code {exit_code}")
                        for op in batch_ops:
                            import_id = _get_import_id(op, slug)
                            payee_name = op.transaction.merchant or op.transaction.description
                            write_log(
                                {
                                    "op_type": "create_transaction",
                                    "action": "failed",
                                    "account_slug": slug,
                                    "posted_date": str(op.transaction.posted_date),
                                    "amount_milliunits": op.transaction.amount.to_milliunits(),
                                    "payee_name": payee_name,
                                    "import_id": import_id,
                                    "ynab_exit_code": exit_code,
                                    "included_in_batch": True,
                                }
                            )
                            counts["failed"] += 1
                    else:
                        for op in batch_ops:
                            import_id = _get_import_id(op, slug)
                            payee_name = op.transaction.merchant or op.transaction.description
                            if import_id in duplicate_ids:
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "duplicate_skipped",
                                        "account_slug": slug,
                                        "posted_date": str(op.transaction.posted_date),
                                        "amount_milliunits": op.transaction.amount.to_milliunits(),
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": 0,
                                        "included_in_batch": True,
                                    }
                                )
                                counts["duplicate_skipped"] += 1
                            else:
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "applied",
                                        "account_slug": slug,
                                        "posted_date": str(op.transaction.posted_date),
                                        "amount_milliunits": op.transaction.amount.to_milliunits(),
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": 0,
                                        "included_in_batch": True,
                                    }
                                )
                                counts["applied"] += 1

                elif action == "s":
                    # Individual review
                    for op in batch_ops:
                        posted_date = str(op.transaction.posted_date)
                        amount_milliunits = op.transaction.amount.to_milliunits()
                        payee_name = op.transaction.merchant or op.transaction.description
                        import_id = _get_import_id(op, slug)

                        _display_individual_create(posted_date, op, account_id, slug)
                        if _prompt_apply_individual():
                            individual_cmd = [
                                "ynab",
                                "create",
                                "transaction",
                                "--account-id",
                                account_id,
                                "--amount",
                                str(amount_milliunits),
                                "--date",
                                posted_date,
                                "--payee-name",
                                payee_name,
                                "--cleared",
                                "reconciled",
                                "--import-id",
                                import_id,
                            ]
                            create_result = subprocess.run(
                                individual_cmd,
                                capture_output=True,
                                text=True,
                            )
                            if create_result.stdout:
                                print(create_result.stdout, end="")
                            if create_result.stderr:
                                print(create_result.stderr, end="")
                            exit_code = create_result.returncode
                            duplicate_ids = _parse_duplicate_ids(create_result.stdout or "")
                            if exit_code != 0:
                                print(f"  ERROR: ynab exited with code {exit_code}")
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "failed",
                                        "account_slug": slug,
                                        "posted_date": posted_date,
                                        "amount_milliunits": amount_milliunits,
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": exit_code,
                                        "included_in_batch": False,
                                    }
                                )
                                counts["failed"] += 1
                            elif import_id in duplicate_ids:
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "duplicate_skipped",
                                        "account_slug": slug,
                                        "posted_date": posted_date,
                                        "amount_milliunits": amount_milliunits,
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": 0,
                                        "included_in_batch": False,
                                    }
                                )
                                counts["duplicate_skipped"] += 1
                            else:
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "applied",
                                        "account_slug": slug,
                                        "posted_date": posted_date,
                                        "amount_milliunits": amount_milliunits,
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": 0,
                                        "included_in_batch": False,
                                    }
                                )
                                counts["applied"] += 1
                        else:
                            write_log(
                                {
                                    "op_type": "create_transaction",
                                    "action": "skipped",
                                    "account_slug": slug,
                                    "posted_date": posted_date,
                                    "amount_milliunits": amount_milliunits,
                                    "payee_name": payee_name,
                                    "import_id": import_id,
                                    "included_in_batch": False,
                                }
                            )
                            counts["skipped"] += 1
                    print("  [Returning to batch view]")

                else:  # n
                    for op in batch_ops:
                        import_id = _get_import_id(op, slug)
                        payee_name = op.transaction.merchant or op.transaction.description
                        write_log(
                            {
                                "op_type": "create_transaction",
                                "action": "skipped",
                                "account_slug": slug,
                                "posted_date": str(op.transaction.posted_date),
                                "amount_milliunits": op.transaction.amount.to_milliunits(),
                                "payee_name": payee_name,
                                "import_id": import_id,
                                "included_in_batch": False,
                            }
                        )
                        counts["skipped"] += 1

            _process_operations_by_date(flags, _handle_flag_batch)
            _process_operations_by_date(deletes, _handle_delete_batch)
            _process_operations_by_date(creates, _handle_create_batch)

    return counts
