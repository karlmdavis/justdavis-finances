"""Interactive apply node for bank reconciliation operations."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from finances.bank_accounts.models import BankAccountsConfig
from finances.core.json_utils import read_json


def _make_import_id(slug: str, posted_date: str, amount_milliunits: int, description: str) -> str:
    """
    Generate stable import ID for a bank transaction.

    Format: bank:{slug}:{posted_date}:{amount_milliunits}:{sha256(description)[:8]}

    Stable per bank transaction → applying is fully idempotent.
    The YNAB API rejects duplicate import-id values, preventing duplicate transactions.
    """
    desc_hash = hashlib.sha256(description.encode()).hexdigest()[:8]
    return f"bank:{slug}:{posted_date}:{amount_milliunits}:{desc_hash}"


def _format_amount(amount_milliunits: int) -> str:
    """Format milliunits as display string e.g. -$12.99."""
    abs_amount = abs(amount_milliunits)
    dollars = abs_amount // 100000
    cents = (abs_amount % 100000) // 1000
    sign = "-" if amount_milliunits < 0 else "+"
    return f"{sign}${dollars}.{cents:02d}"


def _group_operations(accounts_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Group operations by account slug, then by type and date.

    Returns:
        {slug: {
            "account_id": str,
            "creates": {date: [op, ...]},
            "flags": {date: [op, ...]},
        }}
    """
    result: dict[str, dict[str, Any]] = {}
    for slug, account_data in accounts_data.items():
        account_id = account_data.get("account_id", "")
        creates: dict[str, list[dict[str, Any]]] = {}
        flags: dict[str, list[dict[str, Any]]] = {}
        for op in account_data.get("operations", []):
            date = op["transaction"].get("posted_date", "")
            if op.get("type") == "create_transaction":
                creates.setdefault(date, []).append(op)
            elif op.get("type") == "flag_discrepancy":
                flags.setdefault(date, []).append(op)
        result[slug] = {
            "account_id": account_id,
            "creates": creates,
            "flags": flags,
        }
    return result


def _build_file_payload(ops: list[dict[str, Any]], account_id: str, slug: str) -> list[dict[str, Any]]:
    """Build list of transaction dicts for ynab create transaction --file -."""
    payload = []
    for op in ops:
        bank_tx = op["transaction"]
        posted_date = bank_tx["posted_date"]
        amount_milliunits = bank_tx["amount_milliunits"]
        description = bank_tx["description"]
        payee_name = bank_tx.get("merchant") or description
        import_id = _make_import_id(slug, posted_date, amount_milliunits, description)
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


def _display_create_batch(date: str, ops: list[dict[str, Any]], slug: str) -> None:
    """Display a CREATE batch header with line items."""
    total = sum(op["transaction"]["amount_milliunits"] for op in ops)
    total_display = _format_amount(total)
    n = len(ops)
    noun = f"{n} Transaction{'s' if n != 1 else ''}"
    print(f"\n  Create {noun} in Batch Operation?")
    print(f"    Date:  {date}")
    print(f"    Total: {total_display}")
    print()
    for i, op in enumerate(ops, 1):
        bank_tx = op["transaction"]
        amount_display = _format_amount(bank_tx["amount_milliunits"])
        payee_name = bank_tx.get("merchant") or bank_tx["description"]
        print(f"    {i}. Amount: {amount_display}")
        print(f"       Payee:  {payee_name}")
    print()
    print("    Command To Be Run: ynab create transaction --file -")
    print(f"                       ({n} transaction{'s' if n != 1 else ''} specified as JSON via STDIN)")


def _display_individual_create(date: str, op: dict[str, Any], account_id: str, slug: str) -> None:
    """Display a single CREATE item for individual review."""
    bank_tx = op["transaction"]
    amount_milliunits = bank_tx["amount_milliunits"]
    description = bank_tx["description"]
    payee_name = bank_tx.get("merchant") or description
    import_id = _make_import_id(slug, date, amount_milliunits, description)
    amount_display = _format_amount(amount_milliunits)
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


def _display_flag_batch(date: str, ops: list[dict[str, Any]]) -> None:
    """Display a FLAG batch header with candidate listings."""
    n = len(ops)
    noun = f"{n} Transaction{'s' if n != 1 else ''}"
    print()
    print(f"  Manual Fix Required: {noun} on {date}")
    print("    These bank transactions matched multiple YNAB entries — resolve manually in YNAB.")
    print()
    for i, op in enumerate(ops, 1):
        bank_tx = op["transaction"]
        amount_display = _format_amount(bank_tx["amount_milliunits"])
        merchant = bank_tx.get("merchant") or bank_tx["description"]
        candidates = op.get("candidates", [])
        print(f"    {i}. Amount: {amount_display}")
        print(f"       Payee:  {merchant}")
        print("       Candidate Matching Transactions in YNAB:")
        for j, candidate in enumerate(candidates):
            label = chr(ord("a") + j)
            payee = candidate.get("payee_name", "(unknown)")
            cdate = candidate.get("date", "")
            camt = candidate.get("amount_milliunits", 0)
            camt_display = _format_amount(camt)
            print(f"         {label}. Payee:  {payee}")
            print(f"            Date:   {cdate}")
            print(f"            Amount: {camt_display}")


def _prompt_account(slug: str) -> str:
    """Prompt 'Process this account? [Y/n]'. Returns 'y' or 'n'."""
    try:
        response = input("Process this account? [Y/n] ").strip().lower()
        return "n" if response == "n" else "y"
    except EOFError:
        print()
        return "n"


def _prompt_create_batch(has_multiple: bool, payload: list[dict[str, Any]]) -> str:
    """Prompt for batch action. Returns 'y', 'n', or 's' (if multiple items).

    When 'j' is entered, pretty-prints the JSON payload and re-prompts.
    """
    if has_multiple:
        prompt = "  Apply batch, Split batch, see Json? [y/N/s/j] "
    else:
        prompt = "  Apply batch, see Json? [y/N/j] "
    while True:
        try:
            response = input(prompt).strip().lower()
            if response == "j":
                print(json.dumps(payload, indent=2))
                continue
            if response == "y":
                return "y"
            if response == "s" and has_multiple:
                return "s"
            return "n"
        except EOFError:
            print()
            return "n"


def _prompt_apply_individual() -> bool:
    """Prompt for individual apply. Returns True for 'y'."""
    try:
        response = input("    Apply transaction? [y/N] ").strip().lower()
        return response == "y"
    except EOFError:
        print()
        return False


def _prompt_acknowledge_batch() -> str:
    """Prompt 'Acknowledge all, Skip all? [A/n]'. Returns 'a' or 'n'."""
    try:
        response = input("  Acknowledge all, Skip all? [A/n] ").strip().lower()
        return "n" if response == "n" else "a"
    except EOFError:
        print()
        return "n"


def apply_reconciliation_operations(
    ops_file: Path,
    apply_log_path: Path,
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
        apply_log_path: Path for NDJSON log output
        config: Bank accounts configuration (for account ordering and slug lookups)

    Returns:
        Summary counts dict with "applied", "skipped", "acknowledged", "failed" keys
    """
    data = read_json(ops_file)
    accounts_data = data.get("accounts", {})

    # Build slug → account_id mapping from config
    slug_to_account_id: dict[str, str] = {
        account.slug: account.ynab_account_id for account in config.accounts
    }

    grouped = _group_operations(accounts_data)

    counts: dict[str, int] = {"applied": 0, "skipped": 0, "acknowledged": 0, "failed": 0}

    apply_log_path.parent.mkdir(parents=True, exist_ok=True)

    print()
    print("  This node reconciles (i.e. corrects) the transaction data in YNAB,")
    print("  using data from your banks as the source of truth.")

    with open(apply_log_path, "a") as log_file:

        def write_log(entry: dict[str, Any]) -> None:
            entry["timestamp"] = datetime.now().isoformat()
            log_file.write(json.dumps(entry) + "\n")
            log_file.flush()

        # Walk accounts in config order, falling back to dict order for any not in config
        config_slugs = [account.slug for account in config.accounts]
        all_slugs = config_slugs + [s for s in grouped if s not in config_slugs]

        for slug in all_slugs:
            if slug not in grouped:
                continue
            group = grouped[slug]
            account_id = group["account_id"] or slug_to_account_id.get(slug, "")
            creates = group["creates"]  # {date: [op, ...]}
            flags = group["flags"]  # {date: [op, ...]}

            total_creates = sum(len(ops) for ops in creates.values())
            total_flags = sum(len(ops) for ops in flags.values())
            total_pending = total_creates + total_flags

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
                for _date, ops in sorted(creates.items()):
                    for op in ops:
                        bank_tx = op["transaction"]
                        import_id = _make_import_id(
                            slug,
                            bank_tx["posted_date"],
                            bank_tx["amount_milliunits"],
                            bank_tx["description"],
                        )
                        payee_name = bank_tx.get("merchant") or bank_tx["description"]
                        write_log(
                            {
                                "op_type": "create_transaction",
                                "action": "skipped",
                                "account_slug": slug,
                                "posted_date": bank_tx["posted_date"],
                                "amount_milliunits": bank_tx["amount_milliunits"],
                                "payee_name": payee_name,
                                "import_id": import_id,
                                "included_in_batch": True,
                            }
                        )
                        counts["skipped"] += 1
                for _date, ops in sorted(flags.items()):
                    for op in ops:
                        bank_tx = op["transaction"]
                        candidates = op.get("candidates", [])
                        candidate_names = [c.get("payee_name", "(unknown)") for c in candidates]
                        write_log(
                            {
                                "op_type": "flag_discrepancy",
                                "action": "skipped",
                                "account_slug": slug,
                                "posted_date": bank_tx["posted_date"],
                                "amount_milliunits": bank_tx["amount_milliunits"],
                                "candidates": candidate_names,
                            }
                        )
                        counts["skipped"] += 1
                continue

            # Build combined date-ordered batches: (date, type, ops)
            all_dates: set[str] = set(creates.keys()) | set(flags.keys())
            batches: list[tuple[str, str, list[dict[str, Any]]]] = []
            for date in sorted(all_dates):
                if date in flags:
                    batches.append((date, "flag", flags[date]))
                if date in creates:
                    batches.append((date, "create", creates[date]))

            for date, batch_type, batch_ops in batches:
                if batch_type == "create":
                    _display_create_batch(date, batch_ops, slug)
                    has_multiple = len(batch_ops) > 1
                    payload = _build_file_payload(batch_ops, account_id, slug)
                    action = _prompt_create_batch(has_multiple, payload)

                    if action == "y":
                        proc = subprocess.run(
                            ["ynab", "create", "transaction", "--file", "-"],
                            input=json.dumps(payload),
                            text=True,
                        )
                        exit_code = proc.returncode
                        if exit_code != 0:
                            print(f"  ERROR: ynab exited with code {exit_code}")
                            for op in batch_ops:
                                bank_tx = op["transaction"]
                                import_id = _make_import_id(
                                    slug,
                                    bank_tx["posted_date"],
                                    bank_tx["amount_milliunits"],
                                    bank_tx["description"],
                                )
                                payee_name = bank_tx.get("merchant") or bank_tx["description"]
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "failed",
                                        "account_slug": slug,
                                        "posted_date": bank_tx["posted_date"],
                                        "amount_milliunits": bank_tx["amount_milliunits"],
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": exit_code,
                                        "included_in_batch": True,
                                    }
                                )
                                counts["failed"] += 1
                        else:
                            for op in batch_ops:
                                bank_tx = op["transaction"]
                                import_id = _make_import_id(
                                    slug,
                                    bank_tx["posted_date"],
                                    bank_tx["amount_milliunits"],
                                    bank_tx["description"],
                                )
                                payee_name = bank_tx.get("merchant") or bank_tx["description"]
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "applied",
                                        "account_slug": slug,
                                        "posted_date": bank_tx["posted_date"],
                                        "amount_milliunits": bank_tx["amount_milliunits"],
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
                            bank_tx = op["transaction"]
                            posted_date = bank_tx["posted_date"]
                            amount_milliunits = bank_tx["amount_milliunits"]
                            description = bank_tx["description"]
                            payee_name = bank_tx.get("merchant") or description
                            import_id = _make_import_id(slug, posted_date, amount_milliunits, description)

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
                                result = subprocess.run(individual_cmd)
                                exit_code = result.returncode
                                write_log(
                                    {
                                        "op_type": "create_transaction",
                                        "action": "applied",
                                        "account_slug": slug,
                                        "posted_date": posted_date,
                                        "amount_milliunits": amount_milliunits,
                                        "payee_name": payee_name,
                                        "import_id": import_id,
                                        "ynab_exit_code": exit_code,
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
                            bank_tx = op["transaction"]
                            import_id = _make_import_id(
                                slug,
                                bank_tx["posted_date"],
                                bank_tx["amount_milliunits"],
                                bank_tx["description"],
                            )
                            payee_name = bank_tx.get("merchant") or bank_tx["description"]
                            write_log(
                                {
                                    "op_type": "create_transaction",
                                    "action": "skipped",
                                    "account_slug": slug,
                                    "posted_date": bank_tx["posted_date"],
                                    "amount_milliunits": bank_tx["amount_milliunits"],
                                    "payee_name": payee_name,
                                    "import_id": import_id,
                                    "included_in_batch": True,
                                }
                            )
                            counts["skipped"] += 1

                else:  # flag
                    _display_flag_batch(date, batch_ops)
                    action = _prompt_acknowledge_batch()
                    log_action = "acknowledged" if action == "a" else "skipped"
                    for op in batch_ops:
                        bank_tx = op["transaction"]
                        candidates = op.get("candidates", [])
                        candidate_names = [c.get("payee_name", "(unknown)") for c in candidates]
                        write_log(
                            {
                                "op_type": "flag_discrepancy",
                                "action": log_action,
                                "account_slug": slug,
                                "posted_date": bank_tx["posted_date"],
                                "amount_milliunits": bank_tx["amount_milliunits"],
                                "candidates": candidate_names,
                            }
                        )
                        if log_action == "acknowledged":
                            counts["acknowledged"] += 1
                        else:
                            counts["skipped"] += 1

    return counts
