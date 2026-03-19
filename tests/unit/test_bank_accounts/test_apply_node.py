"""Unit tests for bank_accounts.nodes.apply."""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from finances.bank_accounts.models import BankAccountsConfig
from finances.bank_accounts.nodes.apply import (
    _format_amount,
    _group_operations,
    _make_import_id,
    apply_reconciliation_operations,
)
from finances.core.json_utils import write_json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(accounts: list[dict] | None = None) -> BankAccountsConfig:
    """Build a minimal BankAccountsConfig for testing."""
    return BankAccountsConfig(accounts=[])


def _make_ops_data(accounts: dict) -> dict:
    """Wrap account operations in top-level reconciliation JSON structure."""
    return {"reconciled_at": "2026-03-08T10:00:00", "accounts": accounts}


def _build_ops_file(tmp_dir: Path, accounts: dict) -> Path:
    ops_file = tmp_dir / "ops.json"
    write_json(ops_file, _make_ops_data(accounts))
    return ops_file


def _make_create_op(
    posted_date: str = "2024-03-15",
    amount_milliunits: int = -12990,
    description: str = "SPOTIFY USA 8888812345 NY USA",
    merchant: str | None = "Spotify",
    account_id: str = "acct-apple",
) -> dict:
    tx: dict = {
        "posted_date": posted_date,
        "amount_milliunits": amount_milliunits,
        "description": description,
    }
    if merchant is not None:
        tx["merchant"] = merchant
    return {
        "type": "create_transaction",
        "account_id": account_id,
        "transaction": tx,
    }


def _make_flag_op(
    posted_date: str = "2024-06-28",
    amount_milliunits: int = -25000,
    description: str = "STARBUCKS 800-782-7282 WA USA",
    merchant: str = "Starbucks",
    candidates: list[dict] | None = None,
    account_id: str = "acct-apple",
) -> dict:
    if candidates is None:
        candidates = [
            {
                "payee_name": "Inst for Jh Nursing",
                "date": posted_date,
                "amount_milliunits": amount_milliunits,
            },
            {"payee_name": "Starbucks", "date": posted_date, "amount_milliunits": amount_milliunits},
        ]
    return {
        "type": "flag_discrepancy",
        "account_id": account_id,
        "transaction": {
            "posted_date": posted_date,
            "amount_milliunits": amount_milliunits,
            "description": description,
            "merchant": merchant,
        },
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# _format_amount tests
# ---------------------------------------------------------------------------


def test_format_amount_expense():
    """Negative milliunits display as -$X.XX."""
    assert _format_amount(-12990) == "-$12.99"


def test_format_amount_income():
    """Positive milliunits display as +$X.XX."""
    assert _format_amount(12990) == "+$12.99"


# ---------------------------------------------------------------------------
# import_id tests
# ---------------------------------------------------------------------------


def test_import_id_stable_for_same_bank_tx():
    """Same inputs always produce the same import_id (idempotent apply)."""
    id1 = _make_import_id("apple-card", "2024-03-15", -12990, "SPOTIFY USA 8888812345 NY USA")
    id2 = _make_import_id("apple-card", "2024-03-15", -12990, "SPOTIFY USA 8888812345 NY USA")
    assert id1 == id2


def test_import_id_unique_for_different_amounts():
    """Different amounts → different import_ids."""
    id1 = _make_import_id("apple-card", "2024-03-15", -12990, "SPOTIFY USA")
    id2 = _make_import_id("apple-card", "2024-03-15", -9990, "SPOTIFY USA")
    assert id1 != id2


def test_import_id_unique_for_different_descriptions():
    """Different descriptions → different import_ids (hash differs)."""
    id1 = _make_import_id("apple-card", "2024-03-15", -12990, "SPOTIFY USA")
    id2 = _make_import_id("apple-card", "2024-03-15", -12990, "NETFLIX USA")
    assert id1 != id2


def test_import_id_format():
    """import_id is a valid UUID (always exactly 36 characters)."""
    import_id = _make_import_id("apple-card", "2024-03-15", -12990, "SPOTIFY USA")
    assert len(import_id) == 36
    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    assert uuid_pattern.match(import_id), f"import_id {import_id!r} is not a valid UUID"


def test_import_id_within_ynab_limit():
    """import_id is always ≤ 36 characters even with very long slug and large amount."""
    long_slug = "this-is-a-very-long-bank-account-slug-that-exceeds-normal-length"
    import_id = _make_import_id(long_slug, "2024-03-15", -999999999999, "A" * 200)
    assert len(import_id) <= 36


# ---------------------------------------------------------------------------
# Grouping tests
# ---------------------------------------------------------------------------


def test_operations_sorted_chronologically():
    """Operations from multiple accounts are grouped by account then date."""
    accounts_data = {
        "chase-checking": {
            "account_id": "acct-1",
            "operations": [
                {
                    "type": "create_transaction",
                    "account_id": "acct-1",
                    "transaction": {
                        "posted_date": "2024-06-10",
                        "amount_milliunits": -1000,
                        "description": "A",
                    },
                },
                {
                    "type": "create_transaction",
                    "account_id": "acct-1",
                    "transaction": {
                        "posted_date": "2024-06-20",
                        "amount_milliunits": -2000,
                        "description": "C",
                    },
                },
            ],
        },
        "apple-card": {
            "account_id": "acct-2",
            "operations": [
                {
                    "type": "create_transaction",
                    "account_id": "acct-2",
                    "transaction": {
                        "posted_date": "2024-06-15",
                        "amount_milliunits": -1500,
                        "description": "B",
                    },
                },
            ],
        },
    }

    grouped = _group_operations(accounts_data)

    # chase-checking has 2 creates
    assert "2024-06-10" in grouped["chase-checking"]["creates"]
    assert "2024-06-20" in grouped["chase-checking"]["creates"]
    # apple-card has 1 create
    assert "2024-06-15" in grouped["apple-card"]["creates"]


# ---------------------------------------------------------------------------
# Account-level UX tests
# ---------------------------------------------------------------------------


def test_account_with_no_pending_ops_skipped_silently():
    """Account with zero operations prints 'Nothing pending.' with no prompt."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(tmp_path, {"apple-card": {"account_id": "acct-a", "operations": []}})
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        with patch("builtins.input") as mock_input:
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        # No prompt should have been issued
        mock_input.assert_not_called()
        assert counts == {"applied": 0, "skipped": 0, "acknowledged": 0, "failed": 0, "deleted": 0}
        # Log should be empty
        assert not log_path.exists() or log_path.read_text().strip() == ""


def test_account_skipped_when_user_says_no():
    """When user presses 'n' at account prompt, all ops logged as skipped, no ynab calls."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_create_op("2024-03-15", -12990, "SPOTIFY USA", "Spotify"),
                        _make_create_op("2024-03-15", -6500, "STARBUCKS WA USA", "Starbucks"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", return_value="n"),
        ):
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        mock_run.assert_not_called()
        assert counts["skipped"] == 2
        assert counts["applied"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert entry["action"] == "skipped"
            assert entry["op_type"] == "create_transaction"


# ---------------------------------------------------------------------------
# CREATE batch tests
# ---------------------------------------------------------------------------


def test_create_batch_applied_via_file():
    """'y' on create batch → subprocess called with --file -, each tx logged with included_in_batch=True."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_create_op("2024-03-15", -12990, "SPOTIFY USA 8888812345 NY USA", "Spotify"),
                        _make_create_op("2024-03-15", -6500, "STARBUCKS UTAH AVE S WA USA", "Starbucks"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # First input() call is for account prompt, second for batch prompt
        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "y"]),
        ):
            mock_run.return_value.returncode = 0
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        # Should call ynab with --file -
        assert mock_run.call_count == 1
        call_args = mock_run.call_args
        assert "--file" in call_args[0][0]
        assert "-" in call_args[0][0]

        # Verify the JSON payload passed to stdin
        passed_input = call_args[1]["input"]
        payload = json.loads(passed_input)
        assert len(payload) == 2
        assert payload[0]["payee_name"] == "Spotify"
        assert "memo" not in payload[0]
        assert payload[1]["payee_name"] == "Starbucks"
        assert "memo" not in payload[1]

        assert counts["applied"] == 2
        assert counts["skipped"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert entry["action"] == "applied"
            assert entry["included_in_batch"] is True
            assert entry["ynab_exit_code"] == 0


def test_memo_absent_regardless_of_merchant():
    """Memo is omitted from payload — matches YNAB's direct bank import behavior."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        # merchant set (Apple Card style)
                        _make_create_op("2024-03-15", -12990, "SPOTIFY USA 8888812345 NY USA", "Spotify"),
                        # no merchant (Chase Checking style)
                        _make_create_op("2024-03-15", -3000, "NON-CHASE ATM FEE-WITH", merchant=None),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "y"]),
        ):
            mock_run.return_value.returncode = 0
            apply_reconciliation_operations(ops_file, log_path, config)

        payload = json.loads(mock_run.call_args[1]["input"])
        assert payload[0]["payee_name"] == "Spotify"
        assert "memo" not in payload[0]
        assert payload[1]["payee_name"] == "NON-CHASE ATM FEE-WITH"
        assert "memo" not in payload[1]


def test_create_batch_skipped():
    """'N' on create batch → all skipped, no ynab call."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "chase-checking": {
                    "account_id": "acct-chase",
                    "operations": [
                        _make_create_op("2023-12-29", -3000, "Non-Chase Atm Fee-With", None, "acct-chase"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "n"]),
        ):
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        mock_run.assert_not_called()
        assert counts["skipped"] == 1
        assert counts["applied"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "skipped"
        assert entry["included_in_batch"] is True
        assert "ynab_exit_code" not in entry


def test_create_batch_split_then_applied():
    """'s' on batch → individual prompts → y/n per item → [Returning to batch view] printed."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_create_op("2024-03-15", -12990, "SPOTIFY USA", "Spotify"),
                        _make_create_op("2024-03-15", -6500, "STARBUCKS WA USA", "Starbucks"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # Account prompt: y; batch prompt: s; item 1: y; item 2: n
        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "s", "y", "n"]),
            patch("builtins.print") as mock_print,
        ):
            mock_run.return_value.returncode = 0
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        # Individual calls (not --file) for each applied item
        assert mock_run.call_count == 1
        call_args = mock_run.call_args[0][0]
        assert "--file" not in call_args
        assert "--account-id" in call_args

        assert counts["applied"] == 1
        assert counts["skipped"] == 1

        # Verify [Returning to batch view] was printed
        printed_args = [str(c) for c in mock_print.call_args_list]
        assert any("[Returning to batch view]" in s for s in printed_args)

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        entries = [json.loads(line) for line in lines]
        applied = [e for e in entries if e["action"] == "applied"]
        skipped = [e for e in entries if e["action"] == "skipped"]
        assert len(applied) == 1
        assert len(skipped) == 1
        assert applied[0]["included_in_batch"] is False
        assert skipped[0]["included_in_batch"] is False


def test_create_batch_failed_logs_failed():
    """--file exits non-zero → all txs logged as action='failed' with ynab_exit_code."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_create_op("2024-03-15", -12990, "SPOTIFY USA", "Spotify"),
                        _make_create_op("2024-03-15", -6500, "STARBUCKS WA USA", "Starbucks"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "y"]),
        ):
            mock_run.return_value.returncode = 1
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        assert counts["failed"] == 2
        assert counts["applied"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert entry["action"] == "failed"
            assert entry["ynab_exit_code"] == 1
            assert entry["included_in_batch"] is True


# ---------------------------------------------------------------------------
# FLAG batch tests
# ---------------------------------------------------------------------------


def test_flag_batch_acknowledged():
    """'A' on flag batch → each logged as acknowledged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [_make_flag_op()],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # Account prompt: y; flag batch prompt: A
        with patch("builtins.input", side_effect=["y", "a"]):
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        assert counts["acknowledged"] == 1
        assert counts["skipped"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["op_type"] == "flag_discrepancy"
        assert entry["action"] == "acknowledged"
        assert entry["candidates"] == ["Inst for Jh Nursing", "Starbucks"]


def test_flag_batch_skipped():
    """'n' on flag batch → each logged as skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [_make_flag_op()],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # Account prompt: y; flag batch prompt: n
        with patch("builtins.input", side_effect=["y", "n"]):
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        assert counts["skipped"] == 1
        assert counts["acknowledged"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "skipped"
        assert entry["op_type"] == "flag_discrepancy"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


def test_single_item_batch_no_split_option():
    """Batch with 1 op → prompt does NOT offer 's' option."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [_make_create_op()],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        captured_prompts: list[str] = []

        def capturing_input(prompt: str = "") -> str:
            captured_prompts.append(prompt)
            # First call: account prompt → y; Second call: batch prompt → n
            return "y" if len(captured_prompts) == 1 else "n"

        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run"),
            patch("builtins.input", side_effect=capturing_input),
        ):
            apply_reconciliation_operations(ops_file, log_path, config)

        # Single-item batch prompt: no 's' option, but 'j' option present
        batch_prompt = captured_prompts[1]
        assert "/s" not in batch_prompt
        assert "[y/N/s/j]" not in batch_prompt
        assert "/j" in batch_prompt


def test_batches_interleaved_by_date():
    """Creates and flags for the same account appear in date order."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_create_op("2024-06-20", -5000, "NETFLIX USA", "Netflix"),
                        _make_flag_op("2024-05-01"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "a", "n"]),
        ):
            mock_run.return_value.returncode = 0
            apply_reconciliation_operations(ops_file, log_path, config)

        lines = log_path.read_text().strip().splitlines()
        entries = [json.loads(line) for line in lines]
        dates = [e["posted_date"] for e in entries]

        # Flag on 2024-05-01 should appear before create on 2024-06-20
        assert dates == ["2024-05-01", "2024-06-20"]


# ---------------------------------------------------------------------------
# DELETE batch tests
# ---------------------------------------------------------------------------


def _make_delete_op(
    ynab_date: str = "2024-03-20",
    amount: int = -12340,
    payee_name: str = "Netflix",
    ynab_id: str = "ynab-abc-123",
) -> dict:
    return {
        "type": "delete_ynab_transaction",
        "transaction": {
            "id": ynab_id,
            "date": ynab_date,
            "amount": amount,
            "payee_name": payee_name,
        },
    }


def test_delete_batch_applied():
    """'y' on delete batch → ynab delete transaction called per op, logged as applied."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_delete_op("2024-03-20", -12340, "Netflix", "ynab-id-1"),
                        _make_delete_op("2024-03-20", -9990, "Spotify", "ynab-id-2"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # Account prompt: y; delete batch prompt: y
        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "y"]),
        ):
            mock_run.return_value.returncode = 0
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        # Should call ynab delete transaction twice (once per op)
        assert mock_run.call_count == 2
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert cmd[:4] == ["ynab", "delete", "transaction", "--id"]

        assert counts["deleted"] == 2
        assert counts["applied"] == 0
        assert counts["skipped"] == 0

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert entry["op_type"] == "delete_ynab_transaction"
            assert entry["action"] == "applied"
            assert entry["ynab_exit_code"] == 0


def test_delete_batch_skipped():
    """'N' on delete batch → all logged as skipped, no ynab call."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_delete_op("2024-03-20", -12340, "Netflix", "ynab-id-1"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # Account prompt: y; delete batch prompt: n
        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "n"]),
        ):
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        mock_run.assert_not_called()
        assert counts["deleted"] == 0
        assert counts["skipped"] == 1

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["op_type"] == "delete_ynab_transaction"
        assert entry["action"] == "skipped"


def test_delete_batch_split():
    """'s' on delete batch → individual review, one applied, one skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ops_file = _build_ops_file(
            tmp_path,
            {
                "apple-card": {
                    "account_id": "acct-apple",
                    "operations": [
                        _make_delete_op("2024-03-20", -12340, "Netflix", "ynab-id-1"),
                        _make_delete_op("2024-03-20", -9990, "Spotify", "ynab-id-2"),
                    ],
                }
            },
        )
        log_path = tmp_path / "log.ndjson"
        config = _make_config()

        # Account prompt: y; batch prompt: s; item 1: y; item 2: n
        with (
            patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
            patch("builtins.input", side_effect=["y", "s", "y", "n"]),
            patch("builtins.print"),
        ):
            mock_run.return_value.returncode = 0
            counts = apply_reconciliation_operations(ops_file, log_path, config)

        assert mock_run.call_count == 1
        assert counts["deleted"] == 1
        assert counts["skipped"] == 1

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        entries = [json.loads(line) for line in lines]
        applied = [e for e in entries if e["action"] == "applied"]
        skipped = [e for e in entries if e["action"] == "skipped"]
        assert len(applied) == 1
        assert len(skipped) == 1
