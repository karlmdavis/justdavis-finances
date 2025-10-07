#!/usr/bin/env python3
"""
Apple CLI - Transaction Matching Commands

Professional command-line interface for Apple transaction matching.
"""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..apple import AppleMatcher, AppleReceiptParser, fetch_apple_receipts_cli, normalize_apple_receipt_data
from ..core.config import get_config
from ..core.json_utils import format_json, write_json, write_json_with_defaults


@click.group()
def apple() -> None:
    """Apple transaction matching commands."""
    pass


@apple.command()
@click.option("--start", help="Start date (YYYY-MM-DD) - optional, defaults to all transactions")
@click.option("--end", help="End date (YYYY-MM-DD) - optional, defaults to all transactions")
@click.option("--apple-ids", multiple=True, help="Specific Apple IDs to process")
@click.option("--output-dir", help="Override output directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def match(
    ctx: click.Context,
    start: str | None,
    end: str | None,
    apple_ids: tuple,
    output_dir: str | None,
    verbose: bool,
) -> None:
    """
    Match YNAB transactions to Apple receipts.

    Date range is optional. If not provided, all Apple transactions will be matched.

    Examples:
      finances apple match
      finances apple match --start 2024-07-01 --end 2024-07-31
      finances apple match --start 2024-07-01 --end 2024-07-31 --apple-ids karl@example.com
    """
    config = get_config()

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "apple" / "transaction_matches"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Apple Transaction Matching")
        if start and end:
            click.echo(f"Date range: {start} to {end}")
        else:
            click.echo("Date range: all transactions")
        click.echo(f"Apple IDs: {list(apple_ids) if apple_ids else 'all'}")
        click.echo(f"Output: {output_path}")
        click.echo()

    try:
        # Load Apple receipt data and YNAB transactions
        import pandas as pd

        from ..apple import batch_match_transactions, load_apple_receipts
        from ..ynab import filter_transactions, load_ynab_transactions

        ynab_cache_dir = config.data_dir / "ynab" / "cache"

        if verbose:
            click.echo(f"Loading Apple receipt data from: {config.data_dir / 'apple' / 'exports'}")
            click.echo(f"Loading YNAB data from: {ynab_cache_dir}")

        # Load Apple receipts - loader will auto-discover latest export directory
        apple_receipts = load_apple_receipts()

        # Filter by Apple ID if specified
        if apple_ids:
            apple_receipts = [r for r in apple_receipts if r.get("apple_id") in apple_ids]

        # Normalize and convert to DataFrame (handles date parsing and invalid data)
        apple_receipts_df = normalize_apple_receipt_data(apple_receipts)

        # Load and filter YNAB transactions
        all_transactions = load_ynab_transactions(ynab_cache_dir)
        transactions = filter_transactions(all_transactions, start_date=start, end_date=end, payee="Apple")

        # Convert to DataFrame
        transactions_df = pd.DataFrame(transactions)

        if verbose:
            click.echo(f"Loaded {len(apple_receipts_df)} Apple receipts")
            click.echo(f"Found {len(transactions_df)} Apple transactions in date range")

        click.echo("🔍 Processing Apple transaction matching...")

        # Initialize matcher and match transactions
        matcher = AppleMatcher()
        match_results = batch_match_transactions(transactions_df, apple_receipts_df, matcher)

        # Calculate summary statistics
        matched_count = sum(1 for result in match_results if result.receipts)
        total_confidence = sum(result.confidence for result in match_results if result.receipts)
        match_rate = matched_count / len(match_results) if match_results else 0.0
        avg_confidence = total_confidence / matched_count if matched_count > 0 else 0.0

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_apple_matching_results.json"

        # Convert results to JSON-serializable format
        matches = []
        for result in match_results:
            # Convert dataclass instances to dicts
            transaction_dict = (
                asdict(result.transaction) if hasattr(result.transaction, "__dict__") else result.transaction
            )
            receipts_list = [asdict(r) if hasattr(r, "__dict__") else r for r in result.receipts]

            match_dict: dict[str, Any] = {
                "transaction": transaction_dict,
                "receipts": receipts_list,
                "confidence": result.confidence,
                "strategy": result.strategy_used or result.match_method,
            }
            matches.append(match_dict)

        # Build result structure
        output_result = {
            "metadata": {
                "start_date": start,
                "end_date": end,
                "apple_ids": list(apple_ids) if apple_ids else "all",
                "timestamp": timestamp,
            },
            "summary": {
                "total_transactions": len(match_results),
                "matched_transactions": matched_count,
                "match_rate": match_rate,
                "average_confidence": avg_confidence,
            },
            "matches": matches,
        }

        # Write result file (use write_json_with_defaults to handle date objects)
        write_json_with_defaults(output_file, output_result, default=str)

        # Display summary
        click.echo(f"✅ Matched {matched_count} of {len(match_results)} transactions ({match_rate*100:.1f}%)")
        click.echo(f"   Average confidence: {avg_confidence*100:.1f}%")
        click.echo(f"   Results saved to: {output_file}")

    except Exception as e:
        click.echo(f"❌ Error during matching: {e}", err=True)
        raise click.ClickException(str(e)) from e


@apple.command()
@click.option("--transaction-id", required=True, help="YNAB transaction ID")
@click.option("--date", required=True, help="Transaction date (YYYY-MM-DD)")
@click.option("--amount", required=True, type=int, help="Transaction amount in milliunits")
@click.option("--payee-name", required=True, help="Transaction payee name")
@click.option("--account-name", required=True, help="Account name")
@click.option("--apple-ids", multiple=True, help="Apple IDs to search")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def match_single(
    ctx: click.Context,
    transaction_id: str,
    date: str,
    amount: int,
    payee_name: str,
    account_name: str,
    apple_ids: tuple,
    verbose: bool,
) -> None:
    """
    Match a single YNAB transaction to Apple receipts.

    Example:
      finances apple match-single --transaction-id "abc123" --date "2024-07-07"
        --amount -227320 --payee-name "Apple Store" --account-name "Chase Credit Card"
    """
    get_config()

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Single Apple Transaction Matching")
        click.echo(f"Transaction ID: {transaction_id}")
        click.echo(f"Date: {date}")
        click.echo(f"Amount: {amount} milliunits")
        click.echo(f"Payee: {payee_name}")
        click.echo(f"Account: {account_name}")
        click.echo()

    # Create transaction object
    ynab_transaction = {
        "id": transaction_id,
        "date": date,
        "amount": amount,
        "payee_name": payee_name,
        "account_name": account_name,
    }

    try:
        # Load Apple receipt data

        from ..apple import load_apple_receipts

        # Load receipts - loader will auto-discover latest export directory
        apple_receipts = load_apple_receipts()

        # Filter by Apple ID if specified
        if apple_ids:
            apple_receipts = [r for r in apple_receipts if r.get("apple_id") in apple_ids]

        # Normalize and convert to DataFrame (handles date parsing and invalid data)
        apple_receipts_df = normalize_apple_receipt_data(apple_receipts)

        if verbose:
            click.echo(f"Loaded {len(apple_receipts_df)} Apple receipts")

        click.echo("🔍 Searching for matching Apple receipts...")

        # Initialize matcher and match the transaction
        matcher = AppleMatcher()
        match_result = matcher.match_single_transaction(ynab_transaction, apple_receipts_df)

        # Display result
        if match_result.receipts:
            click.echo("\n✅ Match found!")
            click.echo(f"   Confidence: {match_result.confidence*100:.1f}%")
            click.echo(f"   Strategy: {match_result.strategy_used or match_result.match_method}")
            click.echo(f"   Receipts matched: {len(match_result.receipts)}")

            for i, receipt in enumerate(match_result.receipts[:3], 1):  # Show first 3
                click.echo(f"   {i}. Order ID: {getattr(receipt, 'order_id', 'N/A')}")
                click.echo(f"      Date: {getattr(receipt, 'date', 'N/A')}")
                total = getattr(receipt, "total_amount", 0)
                click.echo(f"      Total: ${total/100:.2f}")
        else:
            click.echo("\n❌ No matches found")

        # Output JSON for programmatic use
        if verbose:
            # Convert dataclass to dict
            transaction_dict = (
                asdict(match_result.transaction)
                if hasattr(match_result.transaction, "__dict__")
                else match_result.transaction
            )
            receipts_list = [asdict(r) if hasattr(r, "__dict__") else r for r in match_result.receipts]

            result_dict: dict[str, Any] = {
                "transaction": transaction_dict,
                "receipts": receipts_list,
                "confidence": match_result.confidence,
                "strategy": match_result.strategy_used or match_result.match_method,
            }
            click.echo("\nJSON Result:")
            click.echo(format_json(result_dict, default=str))

    except Exception as e:
        click.echo(f"❌ Error during matching: {e}", err=True)
        raise click.ClickException(str(e)) from e


@apple.command()
@click.option("--days-back", default=90, help="Number of days to search back (default: 90)")
@click.option("--max-emails", type=int, help="Maximum number of emails to fetch")
@click.option("--output-dir", help="Override output directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def fetch_emails(
    ctx: click.Context, days_back: int, max_emails: int | None, output_dir: str | None, verbose: bool
) -> None:
    """
    Fetch Apple receipt emails from IMAP server.

    Example:
      finances apple fetch-emails --days-back 30 --max-emails 100
    """
    config = get_config()

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "apple" / "emails"

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Apple Email Fetching")
        click.echo(f"Days back: {days_back}")
        click.echo(f"Max emails: {max_emails or 'unlimited'}")
        click.echo(f"Output directory: {output_path}")
        click.echo()

    try:
        # Check email configuration
        if not config.email.username or not config.email.password:
            click.echo("❌ Email credentials not configured", err=True)
            click.echo("Set EMAIL_USERNAME and EMAIL_PASSWORD environment variables", err=True)
            raise click.ClickException("Email configuration required")

        click.echo("📧 Fetching Apple receipt emails...")

        # Call the fetch function
        fetch_apple_receipts_cli(days_back=days_back, output_dir=output_path, max_emails=max_emails)

        click.echo("✅ Email fetch completed")

    except Exception as e:
        click.echo(f"❌ Error fetching emails: {e}", err=True)
        raise click.ClickException(str(e)) from e


@apple.command()
@click.option("--input-dir", required=True, help="Directory containing email files")
@click.option("--output-dir", help="Override output directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def parse_receipts(ctx: click.Context, input_dir: str, output_dir: str | None, verbose: bool) -> None:
    """
    Parse Apple receipt emails to extract purchase data.

    Example:
      finances apple parse-receipts --input-dir data/apple/emails/
    """
    config = get_config()

    input_path = Path(input_dir)
    if not input_path.exists():
        raise click.ClickException(f"Input directory not found: {input_path}")

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "apple" / "exports"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Apple Receipt Parsing")
        click.echo(f"Input directory: {input_path}")
        click.echo(f"Output directory: {output_path}")
        click.echo()

    try:
        parser = AppleReceiptParser()

        # Find HTML files to parse
        html_files = list(input_path.glob("*-formatted-simple.html"))

        if not html_files:
            click.echo("⚠️  No HTML receipt files found")
            return

        click.echo(f"📄 Found {len(html_files)} receipt files to parse")

        parsed_receipts = []
        successful_parses = 0
        failed_parses = 0

        for html_file in html_files:
            try:
                # Extract base name
                base_name = html_file.name.replace("-formatted-simple.html", "")

                # Parse receipt
                receipt = parser.parse_receipt(base_name, input_path)

                if receipt.order_id or receipt.total or receipt.items:
                    parsed_receipts.append(receipt.to_dict())
                    successful_parses += 1

                    if verbose:
                        click.echo(
                            f"  ✅ {base_name}: {receipt.order_id or 'Unknown ID'} - ${receipt.total or 0:.2f}"
                        )
                else:
                    failed_parses += 1
                    if verbose:
                        click.echo(f"  ❌ {base_name}: Failed to extract data")

            except Exception as e:
                # PERF203: try-except in loop necessary for robust HTML parsing
                failed_parses += 1
                if verbose:
                    click.echo(f"  ❌ {html_file.name}: {e}")

        # Save parsed receipts
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_apple_receipts_export.json"

        export_data = {
            "metadata": {
                "export_date": timestamp,
                "total_files_processed": len(html_files),
                "successful_parses": successful_parses,
                "failed_parses": failed_parses,
                "success_rate": successful_parses / len(html_files) if html_files else 0,
            },
            "receipts": parsed_receipts,
        }

        write_json(output_file, export_data)

        click.echo("✅ Parsing completed")
        click.echo(f"   Successful: {successful_parses}")
        click.echo(f"   Failed: {failed_parses}")
        click.echo(f"   Success rate: {export_data['metadata']['success_rate']*100:.1f}%")  # type: ignore[index]
        click.echo(f"   Results saved to: {output_file}")

    except Exception as e:
        click.echo(f"❌ Error parsing receipts: {e}", err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    apple()
