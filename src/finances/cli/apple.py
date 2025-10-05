#!/usr/bin/env python3
"""
Apple CLI - Transaction Matching Commands

Professional command-line interface for Apple transaction matching.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import click

from ..apple import AppleMatcher, AppleReceiptParser, fetch_apple_receipts_cli
from ..core.config import get_config
from ..core.json_utils import format_json, write_json


@click.group()
def apple() -> None:
    """Apple transaction matching commands."""
    pass


@apple.command()
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--apple-ids", multiple=True, help="Specific Apple IDs to process")
@click.option("--output-dir", help="Override output directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def match(
    ctx: click.Context, start: str, end: str, apple_ids: tuple, output_dir: Optional[str], verbose: bool
) -> None:
    """
    Match YNAB transactions to Apple receipts in a date range.

    Examples:
      finances apple match --start 2024-07-01 --end 2024-07-31
      finances apple match --start 2024-07-01 --end 2024-07-31 --apple-ids karl@example.com erica@example.com
    """
    config = get_config()

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "apple" / "transaction_matches"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Apple Transaction Matching")
        click.echo(f"Date range: {start} to {end}")
        click.echo(f"Apple IDs: {list(apple_ids) if apple_ids else 'all'}")
        click.echo(f"Output: {output_path}")
        click.echo()

    try:
        # Initialize matcher
        AppleMatcher()

        # Load Apple receipt data
        apple_data_dir = config.data_dir / "apple" / "exports"

        if verbose:
            click.echo(f"Loading Apple receipt data from: {apple_data_dir}")

        # This would integrate with the existing data loading logic
        # For now, we'll show the structure
        click.echo("🔍 Processing Apple transaction matching...")
        click.echo("⚠️  Full implementation requires integration with existing batch processing logic")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_apple_matching_results.json"

        # Placeholder result structure
        result = {
            "metadata": {
                "start_date": start,
                "end_date": end,
                "apple_ids": list(apple_ids) if apple_ids else "all",
                "timestamp": timestamp,
            },
            "summary": {
                "total_transactions": 0,
                "matched_transactions": 0,
                "match_rate": 0.0,
                "average_confidence": 0.0,
            },
            "matches": [],
        }

        # Write result file
        write_json(output_file, result)

        click.echo(f"✅ Results saved to: {output_file}")

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
    config = get_config()

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
        # Initialize matcher
        AppleMatcher()

        # Load Apple receipt data
        config.data_dir / "apple" / "exports"

        click.echo("🔍 Searching for matching Apple receipts...")
        click.echo("⚠️  Full implementation requires integration with existing single transaction logic")

        # Placeholder result
        result: dict[str, Any] = {
            "transaction": ynab_transaction,
            "matches": [],
            "best_match": None,
            "message": "CLI implementation in progress",
        }

        # Display result
        if result.get("best_match"):
            click.echo("✅ Match found!")
            click.echo(f"Confidence: {result['best_match']['confidence']}")
        else:
            click.echo("❌ No matches found")

        # Output JSON for programmatic use
        click.echo("\nJSON Result:")
        click.echo(format_json(result))

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
    ctx: click.Context, days_back: int, max_emails: Optional[int], output_dir: Optional[str], verbose: bool
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
def parse_receipts(ctx: click.Context, input_dir: str, output_dir: Optional[str], verbose: bool) -> None:
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
