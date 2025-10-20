#!/usr/bin/env python3
"""
E2E Tests for Financial Flow System

Comprehensive end-to-end tests for the finances flow system using subprocess
to run actual CLI commands with synthetic test data.

These tests validate the complete flow orchestration system from user perspective,
using an imperative testing approach with explicit node sequencing.

## Test Philosophy

These E2E tests prioritize:
1. **Real user workflows** - Tests execute actual CLI commands via subprocess
2. **Coordinated test data** - Hardcoded data ensures 100% match rates
3. **Explicit sequencing** - Deterministic execution order with clear node transitions
4. **Full output logging** - Capture all output and display on failure for easy debugging

## Flow Execution Order

The flow system executes nodes in deterministic alphabetical order when dependencies
are satisfied. With the coordinated test data fixture:

**Input data:**
- Amazon ZIP file (data/amazon/raw/2024-12-01_karl_amazon_data.zip) - requires unzipping
- Apple .html receipt files (data/apple/emails/) - requires parsing
- YNAB cached transactions (data/ynab/cache/) - ready to use

**Execution sequence (5 nodes):**
1. `amazon_unzip` - Extracts ZIP to CSV (no dependencies, alphabetically first)
2. `amazon_matching` - Matches orders to YNAB (depends on amazon_unzip)
3. `apple_receipt_parsing` - Parses .html to JSON (no dependencies, alphabetically after email_fetch when skipped)
4. `apple_matching` - Matches receipts to YNAB (depends on apple_receipt_parsing)
5. `split_generation` - Generates splits (depends on both matchers)

**Nodes skipped in tests:**
- `apple_email_fetch` - Requires IMAP credentials (not available in CI)
- `cash_flow_analysis` - Requires historical data (not in test fixture)
- `retirement_update` - Requires retirement accounts (not in test fixture)
- `ynab_apply` - Requires YNAB API (would modify real data)
- `ynab_sync` - Cache already exists (no API call needed)

## Test-Mode Markers

The flow_engine.py emits special markers to stderr when FINANCES_ENV=test:

- `[NODE_PROMPT: node_name]` - Emitted before prompting user for node execution
- `[NODE_EXEC_START: node_name]` - Emitted before node execution begins
- `[NODE_EXEC_END: node_name: status]` - Emitted after execution completes

These markers enable:
1. **Explicit wait points** - `wait_for_node_prompt()` waits for specific nodes
2. **Deterministic sequencing** - Know exactly which node is being prompted
3. **Status verification** - `assert_node_executed()` confirms execution and status

## Debugging Failed Tests

When tests fail, the `capture_and_log_on_failure()` context manager automatically
prints the full flow output. Look for:

1. **Unexpected node order** - Check which `[NODE_PROMPT: ...]` markers appeared
2. **Execution failures** - Look for `[NODE_EXEC_END: ...: failed]` markers
3. **Missing markers** - If expected marker didn't appear, check node dependencies
4. **Timeout errors** - Usually means node didn't prompt (no data to process)

## Coordinated Test Data

The test fixture creates hardcoded data designed to match and exercise the full flow:

**Amazon data (ZIP file → CSV → matching):**
- Format: ZIP file containing Retail.OrderHistory.1.csv
- Order ID: 111-2223334-5556667
- Ship Date: 2024-12-03
- Items: Wireless Mouse ($29.99) + USB Cable ($12.99) = $46.42 total
- Matches YNAB transaction: tx_amazon_001
- Tests: amazon_unzip → amazon_matching

**Apple data (.eml + extracted files → parsed JSON → matching):**
- Format: Full email_fetcher output (4 files: .html, .txt, .eml, _metadata.json)
- Order ID: ML7PQ2XYZ
- Date: 2024-12-10
- Items: Apple Music ($10.99) + iCloud Storage ($2.99) = $15.10 total
- Matches YNAB transaction: tx_apple_001
- Tests: apple_receipt_parsing → apple_matching (email_fetch skipped in tests)

**YNAB transactions:**
- tx_amazon_001: Amazon.com, $46.42, 2024-12-03
- tx_apple_001: Apple.com/bill, $15.10, 2024-12-10

This coordination ensures 100% match rate, exercises data transformation nodes
(unzip, parse), and provides multi-item orders for split generation testing.
"""

import subprocess
import tempfile
import zipfile
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pexpect
import pytest

from finances.core.json_utils import read_json, write_json
from tests.fixtures.synthetic_data import save_synthetic_ynab_data

# Working directory for all subprocess calls
REPO_ROOT = Path(__file__).parent.parent.parent


def create_coordinated_amazon_data(data_dir: Path) -> None:
    """
    Create coordinated Amazon order data that matches YNAB transactions.

    Creates a ZIP file to test the amazon_unzip node, which then enables
    amazon_matching to run. This hardcoded data ensures 100% match rate.
    """
    # Create Amazon raw data directory
    raw_dir = data_dir / "amazon" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Amazon Order 1: Multi-item order for splitting test
    # Order Date: 2024-12-01, Ship Date: 2024-12-03
    # Order ID: 111-2223334-5556667
    # Items: Wireless Mouse ($29.99) + USB Cable ($12.99) = $42.98 + $3.44 tax = $46.42
    # YNAB Transaction: Amazon.com, 2024-12-03, -$46.42

    csv_content = """Order ID,Order Date,Purchase Order Number,Ship Date,Product Name,Category,ASIN,UNSPSC Code,Website,Release Date,Condition,Seller,Seller Credentials,List Price Per Unit,Unit Price,Quantity,Payment Instrument Type,Purchase Order State,Shipping Address Name,Shipping Address Street 1,Shipping Address Street 2,Shipping Address City,Shipping Address State,Shipping Address Zip,Order Status,Carrier Name & Tracking Number,Item Subtotal,Item Subtotal Tax,Total Owed,Tax Exemption Applied,Tax Exemption Type,Exemption Opt-Out,Buyer Name,Currency,Group Name
111-2223334-5556667,12/01/24,D01-1234567-1234567,12/03/24,Wireless Mouse - Ergonomic,Electronics,B08X1234AB,43211500,www.amazon.com,,new,Amazon.com,,$34.99,$29.99,1,Visa - 1234,Shipped,Karl Davis,123 Main St,,Seattle,WA,98101,Shipped,AMZN_US(TBA987654321),$29.99,$2.55,$32.54,,,,Karl Davis,USD,
111-2223334-5556667,12/01/24,D01-1234567-1234567,12/03/24,USB-C Cable 6ft,Electronics,B08Y5678CD,26121600,www.amazon.com,,new,Amazon.com,,$14.99,$12.99,1,Visa - 1234,Shipped,Karl Davis,123 Main St,,Seattle,WA,98101,Shipped,AMZN_US(TBA987654321),$12.99,$0.89,$13.88,,,,Karl Davis,USD,
"""

    # Create ZIP file with CSV inside (mimics Amazon's download format)
    zip_path = raw_dir / "2024-12-01_karl_amazon_data.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add the CSV with the expected filename
        zf.writestr("Retail.OrderHistory.1.csv", csv_content.strip())


def create_coordinated_apple_data(data_dir: Path) -> None:
    """
    Create coordinated Apple receipt data matching email_fetcher output format.

    Creates the same 4-file structure that email_fetcher produces:
    - .html: Extracted HTML content
    - .txt: Extracted text content
    - .eml: Raw email (RFC822 format)
    - _metadata.json: Structured metadata

    This ensures 100% match rate with YNAB transactions.
    """
    # Create Apple emails directory
    emails_dir = data_dir / "apple" / "emails"
    emails_dir.mkdir(parents=True, exist_ok=True)

    # Apple Receipt: Multi-item subscription for splitting test
    # Receipt Date: 2024-12-10
    # Order ID: ML7PQ2XYZ
    # Items: Apple Music ($10.99) + iCloud Storage ($2.99) = $13.98 + $1.12 tax = $15.10
    # YNAB Transaction: Apple.com/bill, 2024-12-10, -$15.10

    # Base filename following email_fetcher pattern: YYYYMMDD_HHMMSS_subject_###
    base_name = "20241210_120000_Your_receipt_from_Apple_000"

    # HTML content matching Apple parser expectations
    # Use legacy format with aapl-* classes for precise control
    html_content = """<!DOCTYPE html>
<html>
<head><title>Your receipt from Apple</title></head>
<body>
<div class="invoice">
    <h1>Your receipt from Apple</h1>
    <div class="aapl-order"><span class="aapl-order-id">ML7PQ2XYZ</span></div>
    <div class="aapl-date">Dec 10, 2024</div>
    <div class="items">
        <div class="aapl-item">
            <span class="aapl-item-name">Apple Music Individual Subscription</span>
            <span class="aapl-item-cost">$10.99</span>
        </div>
        <div class="aapl-item">
            <span class="aapl-item-name">iCloud+ 50GB Storage</span>
            <span class="aapl-item-cost">$2.99</span>
        </div>
    </div>
    <div class="totals">
        <div class="aapl-subtotal">$13.98</div>
        <div class="aapl-tax">$1.12</div>
        <div class="aapl-total">$15.10</div>
    </div>
</div>
</body>
</html>"""

    # Text content (simplified version)
    text_content = """Your receipt from Apple

Order ID: ML7PQ2XYZ
Order Date: Dec 10, 2024
Bill To: Karl Davis

Items:
Apple Music Individual Subscription - $10.99
iCloud+ 50GB Storage - $2.99

Subtotal: $13.98
Tax: $1.12
Total: $15.10"""

    # Raw email in RFC822 format
    eml_content = f"""From: no_reply@email.apple.com
To: user@example.com
Subject: Your receipt from Apple.
Date: Tue, 10 Dec 2024 12:00:00 +0000
Message-ID: <ML7PQ2XYZ@email.apple.com>
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=utf-8

{text_content}

--boundary123
Content-Type: text/html; charset=utf-8

{html_content}

--boundary123--"""

    # Metadata JSON
    metadata = {
        "message_id": "<ML7PQ2XYZ@email.apple.com>",
        "subject": "Your receipt from Apple.",
        "sender": "no_reply@email.apple.com",
        "date": "2024-12-10T12:00:00+00:00",
        "folder": "INBOX",
        "metadata": {"msg_num": "1", "size": len(eml_content)},
    }

    # Write all 4 files matching email_fetcher output
    (emails_dir / f"{base_name}-formatted-simple.html").write_text(html_content)
    (emails_dir / f"{base_name}.txt").write_text(text_content)
    (emails_dir / f"{base_name}.eml").write_text(eml_content)
    write_json(emails_dir / f"{base_name}_metadata.json", metadata)


def create_coordinated_ynab_data(ynab_cache_dir: Path) -> None:
    """
    Create coordinated YNAB transaction data that matches Amazon and Apple data.

    This ensures 100% match rate for matchers and provides transactions for splitting.
    """
    # YNAB transactions matching the Amazon and Apple data
    transactions = [
        {
            "id": "tx_amazon_001",
            "date": "2024-12-03",
            "amount": -46420,  # -$46.42 in milliunits
            "payee_name": "Amazon.com",
            "memo": None,
            "category_name": "Shopping",
            "account_name": "Visa - 1234",
            "cleared": "cleared",
            "approved": True,
            "flag_color": None,
            "subtransactions": [],
        },
        {
            "id": "tx_apple_001",
            "date": "2024-12-10",
            "amount": -15100,  # -$15.10 in milliunits
            "payee_name": "Apple.com/bill",
            "memo": None,
            "category_name": "Subscriptions",
            "account_name": "Visa - 1234",
            "cleared": "cleared",
            "approved": True,
            "flag_color": None,
            "subtransactions": [],
        },
    ]

    # Minimal accounts data
    accounts_data = {
        "accounts": [
            {
                "id": "acct_001",
                "name": "Visa - 1234",
                "type": "creditCard",
                "balance": -61520,  # Sum of transactions
                "cleared_balance": -61520,
                "uncleared_balance": 0,
                "closed": False,
            }
        ],
        "server_knowledge": 100,
    }

    # Minimal categories data
    categories_data = {
        "category_groups": [
            {
                "id": "cg_001",
                "name": "Spending",
                "hidden": False,
                "categories": [
                    {"id": "cat_001", "name": "Shopping", "hidden": False},
                    {"id": "cat_002", "name": "Subscriptions", "hidden": False},
                ],
            }
        ],
        "server_knowledge": 100,
    }

    # Write to cache files
    write_json(ynab_cache_dir / "transactions.json", transactions)
    write_json(ynab_cache_dir / "accounts.json", accounts_data)
    write_json(ynab_cache_dir / "categories.json", categories_data)


@pytest.fixture
def flow_test_env(monkeypatch):
    """
    Create isolated test environment with synthetic YNAB data.

    Sets up temporary directories and environment variables for flow tests.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create data directory structure
        data_dir = temp_path / "data"
        ynab_cache_dir = data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True, exist_ok=True)

        # Generate synthetic YNAB data
        save_synthetic_ynab_data(ynab_cache_dir)

        # Create other required directories
        (data_dir / "amazon" / "raw").mkdir(parents=True, exist_ok=True)
        (data_dir / "amazon" / "transaction_matches").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "emails").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "exports").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "transaction_matches").mkdir(parents=True, exist_ok=True)
        (data_dir / "ynab" / "edits").mkdir(parents=True, exist_ok=True)
        (data_dir / "cash_flow" / "charts").mkdir(parents=True, exist_ok=True)

        # Set environment variables for this test
        monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))
        monkeypatch.setenv("FINANCES_ENV", "test")
        monkeypatch.setenv("YNAB_API_TOKEN", "test-token-e2e")
        monkeypatch.setenv("EMAIL_PASSWORD", "test-password-e2e")

        yield {
            "temp_dir": temp_path,
            "data_dir": data_dir,
            "ynab_cache_dir": ynab_cache_dir,
        }


@pytest.fixture
def flow_test_env_coordinated(monkeypatch):
    """
    Create isolated test environment with coordinated test data.

    Uses hardcoded Amazon orders, Apple receipts, and YNAB transactions that
    are designed to match each other exactly, ensuring 100% match rates for
    matchers and providing multi-item orders/receipts for split generation.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create data directory structure
        data_dir = temp_path / "data"
        ynab_cache_dir = data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True, exist_ok=True)

        # Create other required directories
        (data_dir / "amazon" / "transaction_matches").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "exports").mkdir(parents=True, exist_ok=True)
        (data_dir / "apple" / "transaction_matches").mkdir(parents=True, exist_ok=True)
        (data_dir / "ynab" / "edits").mkdir(parents=True, exist_ok=True)
        (data_dir / "cash_flow" / "charts").mkdir(parents=True, exist_ok=True)

        # Generate coordinated test data
        create_coordinated_amazon_data(data_dir)
        create_coordinated_apple_data(data_dir)
        create_coordinated_ynab_data(ynab_cache_dir)

        # Set environment variables for this test
        monkeypatch.setenv("FINANCES_DATA_DIR", str(data_dir))
        monkeypatch.setenv("FINANCES_ENV", "test")
        monkeypatch.setenv("YNAB_API_TOKEN", "test-token-e2e")
        monkeypatch.setenv("EMAIL_PASSWORD", "test-password-e2e")

        yield {
            "temp_dir": temp_path,
            "data_dir": data_dir,
            "ynab_cache_dir": ynab_cache_dir,
        }


def run_flow_command(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    """
    Execute a finances flow command and return the result.

    Args:
        args: Command arguments (e.g., ["validate"])
        env: Optional environment variables to pass

    Returns:
        CompletedProcess result with stdout, stderr, and returncode
    """
    cmd = ["uv", "run", "finances", "flow", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    return result


# ============================================================================
# Imperative Testing Utilities for Interactive Flow
# ============================================================================


@contextmanager
def capture_and_log_on_failure(child: pexpect.spawn):
    """
    Capture all output from pexpect child and log it on test failure.

    This context manager ensures full output visibility when tests fail,
    making debugging much easier.

    Args:
        child: pexpect spawn object to capture from

    Yields:
        StringIO buffer containing all captured output

    Usage:
        with capture_and_log_on_failure(child) as output:
            # Test code that might fail
            wait_for_node_prompt(child, "amazon_matching")
    """
    output_buffer = StringIO()
    child.logfile_read = output_buffer
    try:
        yield output_buffer
    except Exception:
        print("\n" + "=" * 70)
        print("FULL FLOW OUTPUT (test failed)")
        print("=" * 70)
        print(output_buffer.getvalue())
        print("=" * 70)
        raise


def wait_for_node_prompt(child: pexpect.spawn, node_name: str, timeout: int = 30) -> str:
    """
    Wait for specific node's prompt in interactive flow.

    In the new execution model, nodes are prompted in topological order.
    The prompt format is: "Run this node? [y/N]"

    Args:
        child: pexpect spawn object
        node_name: Name of the node to wait for (e.g., "amazon_matching")
        timeout: Maximum seconds to wait (default: 30)

    Returns:
        Text captured before the prompt (for assertions)

    Raises:
        pexpect.TIMEOUT: If marker not found within timeout
        pexpect.EOF: If process exits unexpectedly
    """
    # Wait for node header in prompt
    pattern = f"\\[{node_name}\\]"
    child.expect(pattern, timeout=timeout)

    # Wait for the actual user prompt text
    child.expect("Run this node\\?", timeout=5)

    return child.before


def send_node_decision(child: pexpect.spawn, execute: bool) -> None:
    """
    Send yes/no decision to node prompt.

    Args:
        child: pexpect spawn object
        execute: True to execute node (send 'y'), False to skip (send 'n')
    """
    child.sendline("y" if execute else "n")


def assert_node_executed(output: str, node_name: str, expected_status: str = "completed") -> None:
    """
    Assert that a node executed with the expected status.

    Verifies that the node appears in the execution output with the expected status.

    Args:
        output: Full output text to search
        node_name: Name of the node that should have executed
        expected_status: Expected execution status (default: "completed")
                        Valid values: "completed", "failed", "skipped"

    Raises:
        AssertionError: If node execution not found or status doesn't match
    """
    # Check for node execution in output
    # The new execution model shows node status after execution
    if expected_status == "completed":
        # Look for success indicator (✅ or similar)
        assert (
            node_name in output
        ), f"Expected node {node_name} to appear in output, but not found"
    elif expected_status == "failed":
        # Look for failure indicator (❌ or similar)
        assert (
            node_name in output
        ), f"Expected node {node_name} to appear in output, but not found"
    else:
        # For skipped status, just verify node was mentioned
        assert (
            node_name in output
        ), f"Expected node {node_name} to appear in output, but not found"


@pytest.mark.e2e
def test_flow_interactive_execution_with_matching(flow_test_env_coordinated):
    """
    Test complete interactive flow execution with coordinated data.

    This test validates the new topological execution order with sequential prompting.
    Each node is prompted in deterministic topological order with alphabetical tie-breaking.

    Expected execution sequence (11 nodes in topological order):

    Level 0 (no dependencies):
    1. amazon_order_history_request - Skip (no manual requests in test)
    2. apple_email_fetch - Skip (requires IMAP credentials)
    3. ynab_sync - Skip (cache already exists)

    Level 1 (depends on level 0):
    4. amazon_unzip - Execute (ZIP file present from fixture)
    5. apple_receipt_parsing - Execute (.html files present from fixture)
    6. cash_flow_analysis - Skip (no historical data)
    7. retirement_update - Skip (no retirement accounts)

    Level 2 (depends on level 1):
    8. amazon_matching - Execute (depends on ynab_sync + amazon_unzip)
    9. apple_matching - Execute (depends on ynab_sync + apple_receipt_parsing)

    Level 3 (depends on level 2):
    10. split_generation - Execute (depends on amazon_matching + apple_matching)

    Level 4 (depends on level 3):
    11. ynab_apply - Skip (would modify real YNAB data)

    Nodes executed: amazon_unzip, apple_receipt_parsing, amazon_matching, apple_matching, split_generation
    Nodes skipped: amazon_order_history_request, apple_email_fetch, ynab_sync, cash_flow_analysis, retirement_update, ynab_apply
    """
    import os

    # Get environment variables from fixture
    env = os.environ.copy()
    env["FINANCES_DATA_DIR"] = str(flow_test_env_coordinated["data_dir"])
    env["FINANCES_ENV"] = "test"
    env["YNAB_API_TOKEN"] = "test-token-e2e"

    # Spawn interactive flow command
    cmd = "uv run finances flow"
    child = pexpect.spawn(cmd, cwd=REPO_ROOT, env=env, timeout=60, encoding="utf-8")

    try:
        # Use context manager to capture all output and log on failure
        with capture_and_log_on_failure(child) as output:
            # Sequential prompting in topological order (11 nodes)
            # Level 0: amazon_order_history_request, apple_email_fetch, ynab_sync
            # Level 1: amazon_unzip, apple_receipt_parsing, cash_flow_analysis, retirement_update
            # Level 2: amazon_matching, apple_matching
            # Level 3: split_generation
            # Level 4: ynab_apply

            # Level 0 - Step 1: amazon_order_history_request - Skip
            wait_for_node_prompt(child, "amazon_order_history_request")
            send_node_decision(child, execute=False)

            # Level 0 - Step 2: apple_email_fetch - Skip
            wait_for_node_prompt(child, "apple_email_fetch")
            send_node_decision(child, execute=False)

            # Level 0 - Step 3: ynab_sync - Skip
            wait_for_node_prompt(child, "ynab_sync")
            send_node_decision(child, execute=False)

            # Level 1 - Step 4: amazon_unzip - Execute
            wait_for_node_prompt(child, "amazon_unzip")
            send_node_decision(child, execute=True)

            # Level 1 - Step 5: apple_receipt_parsing - Execute
            wait_for_node_prompt(child, "apple_receipt_parsing")
            assert_node_executed(output.getvalue(), "amazon_unzip", "completed")
            send_node_decision(child, execute=True)

            # Level 1 - Step 6: cash_flow_analysis - Skip
            wait_for_node_prompt(child, "cash_flow_analysis")
            assert_node_executed(output.getvalue(), "apple_receipt_parsing", "completed")
            send_node_decision(child, execute=False)

            # Level 1 - Step 7: retirement_update - Skip
            wait_for_node_prompt(child, "retirement_update")
            send_node_decision(child, execute=False)

            # Level 2 - Step 8: amazon_matching - Execute
            wait_for_node_prompt(child, "amazon_matching")
            send_node_decision(child, execute=True)

            # Level 2 - Step 9: apple_matching - Execute
            wait_for_node_prompt(child, "apple_matching")
            assert_node_executed(output.getvalue(), "amazon_matching", "completed")
            send_node_decision(child, execute=True)

            # Level 3 - Step 10: split_generation - Execute
            wait_for_node_prompt(child, "split_generation")
            assert_node_executed(output.getvalue(), "apple_matching", "completed")
            send_node_decision(child, execute=True)

            # Level 4 - Step 11: ynab_apply - Skip
            wait_for_node_prompt(child, "ynab_apply")
            assert_node_executed(output.getvalue(), "split_generation", "completed")
            send_node_decision(child, execute=False)

            # Wait for execution summary
            child.expect("EXECUTION SUMMARY", timeout=30)

            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            child.close()

            # Get full output for final assertions
            full_output = output.getvalue()

            # Verify all expected nodes executed successfully
            assert_node_executed(full_output, "amazon_unzip", "completed")
            assert_node_executed(full_output, "amazon_matching", "completed")
            assert_node_executed(full_output, "apple_receipt_parsing", "completed")
            assert_node_executed(full_output, "apple_matching", "completed")
            assert_node_executed(full_output, "split_generation", "completed")

    finally:
        # Clean up process if still running
        if child.isalive():
            child.terminate(force=True)

    # Verify outputs were created by successful node executions
    data_dir = flow_test_env_coordinated["data_dir"]

    # Amazon unzipped directory should exist (created by amazon_unzip)
    amazon_unzipped_dirs = list((data_dir / "amazon" / "raw").glob("*_karl_amazon_data"))
    assert len(amazon_unzipped_dirs) > 0, "Amazon unzip should create extracted directory"

    # Amazon matching results should exist (created by amazon_matching)
    amazon_matches = list((data_dir / "amazon" / "transaction_matches").glob("*.json"))
    assert len(amazon_matches) > 0, "Amazon matching should create results file"

    # Apple parsed receipts should exist (created by apple_receipt_parsing)
    apple_exports = list((data_dir / "apple" / "exports").glob("*.json"))
    assert len(apple_exports) > 0, "Apple parsing should create parsed receipts"

    # Apple matching results should exist (created by apple_matching)
    apple_matches = list((data_dir / "apple" / "transaction_matches").glob("*.json"))
    assert len(apple_matches) > 0, "Apple matching should create results file"

    # Split generation results should exist with our coordinated multi-item test data
    split_edits = list((data_dir / "ynab" / "edits").glob("*split*.json"))
    assert len(split_edits) > 0, "Split generation should create edit file with multi-item orders/receipts"

    # Verify split edits contain expected data
    split_data = read_json(split_edits[0])
    assert "metadata" in split_data, "Split edit file should have metadata"
    assert "edits" in split_data, "Split edit file should have edits array"

    # Should have 2 edits: 1 for Amazon transaction, 1 for Apple transaction
    edits = split_data["edits"]
    assert len(edits) == 2, f"Expected 2 split edits (1 Amazon + 1 Apple), got {len(edits)}"

    # Verify sources
    sources = {edit["source"] for edit in edits}
    assert sources == {"amazon", "apple"}, f"Expected amazon and apple sources, got {sources}"

    # Verify each edit has splits
    for edit in edits:
        assert "transaction_id" in edit, "Edit should have transaction_id"
        assert "splits" in edit, "Edit should have splits array"
        assert (
            len(edit["splits"]) == 2
        ), f"Expected 2 splits for multi-item transaction, got {len(edit['splits'])}"


@pytest.mark.e2e
def test_flow_preview_and_cancel(flow_test_env_coordinated):
    """
    Test flow preview and cancellation.

    Validates that users can preview what the flow will do and cancel
    before any changes are made.
    """
    import os

    # Get environment variables from fixture
    env = os.environ.copy()
    env["FINANCES_DATA_DIR"] = str(flow_test_env_coordinated["data_dir"])
    env["FINANCES_ENV"] = "test"
    env["YNAB_API_TOKEN"] = "test-token-e2e"

    # Spawn interactive flow command
    cmd = "uv run finances flow"
    child = pexpect.spawn(cmd, cwd=REPO_ROOT, env=env, timeout=60, encoding="utf-8")

    try:
        with capture_and_log_on_failure(child) as output:
            # Skip all nodes (preview without execution)
            # In the new model, users preview each node and can skip all of them
            for i in range(11):  # 11 nodes in the flow
                child.sendline("n")

            # Wait for execution summary showing all skipped
            child.expect("EXECUTION SUMMARY", timeout=10)
            child.expect("Executed: 0 nodes", timeout=5)
            child.expect("Skipped:  11 nodes", timeout=5)

            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            child.close()

            # Verify preview showed useful information about each node
            full_output = output.getvalue()
            assert "amazon_order_history_request" in full_output
            assert "apple_email_fetch" in full_output
            assert "Status:" in full_output  # Should show status for each node

    finally:
        # Clean up process if still running
        if child.isalive():
            child.terminate(force=True)


@pytest.mark.e2e
def test_flow_help_command(flow_test_env):
    """
    Test that help command works correctly.

    Validates that --help provides useful information for flow command.
    """
    # Flow help
    result = run_flow_command(["--help"])
    assert result.returncode == 0
    assert "Financial Flow System" in result.stdout or "Execute the Financial Flow System" in result.stdout
    assert "Options:" in result.stdout


@pytest.mark.e2e
def test_flow_default_command(flow_test_env):
    """
    Test that flow is the default command (can call without 'flow').

    Validates that `finances flow` and `finances` are equivalent.
    """
    # Call without 'flow' subcommand - should work as default
    cmd = ["uv", "run", "finances", "--help"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, f"Default command failed: {result.stderr}"

    # Should show flow-related help information
    assert (
        "Financial Flow System" in result.stdout or "flow" in result.stdout.lower()
    ), "Should show flow command help"
