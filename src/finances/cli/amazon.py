#!/usr/bin/env python3
"""
Amazon CLI - Transaction Matching Commands

Professional command-line interface for Amazon transaction matching.
"""

import click
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from ..amazon import SimplifiedMatcher
from ..amazon.unzipper import extract_amazon_zip_files
from ..core.config import get_config
from ..core.json_utils import write_json, format_json


@click.group()
def amazon():
    """Amazon transaction matching commands."""
    pass


@amazon.command()
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--accounts', multiple=True, help='Specific Amazon accounts to process')
@click.option('--disable-split', is_flag=True, help='Disable split payment matching')
@click.option('--output-dir', help='Override output directory')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def match(ctx: click.Context, start: str, end: str, accounts: tuple,
          disable_split: bool, output_dir: Optional[str], verbose: bool) -> None:
    """
    Match YNAB transactions to Amazon orders in a date range.

    Examples:
      finances amazon match --start 2024-07-01 --end 2024-07-31
      finances amazon match --start 2024-07-01 --end 2024-07-31 --accounts karl erica
    """
    config = get_config()

    # Determine output directory
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = config.data_dir / "amazon" / "transaction_matches"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"Amazon Transaction Matching")
        click.echo(f"Date range: {start} to {end}")
        click.echo(f"Accounts: {list(accounts) if accounts else 'all'}")
        click.echo(f"Split payments: {'disabled' if disable_split else 'enabled'}")
        click.echo(f"Output: {output_path}")
        click.echo()

    try:
        # Initialize matcher
        split_cache_file = None if disable_split else str(config.cache_dir / "amazon_split_cache.json")
        matcher = SimplifiedMatcher(split_cache_file=split_cache_file)

        # Load Amazon data for specified accounts
        amazon_data_dir = config.data_dir / "amazon" / "raw"

        if verbose:
            click.echo(f"Loading Amazon data from: {amazon_data_dir}")

        # This would integrate with the existing data loading logic
        # For now, we'll show the structure
        click.echo("🔍 Processing Amazon transaction matching...")
        click.echo("⚠️  Full implementation requires integration with existing batch processing logic")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_amazon_matching_results.json"

        # Placeholder result structure
        result = {
            "metadata": {
                "start_date": start,
                "end_date": end,
                "accounts": list(accounts) if accounts else "all",
                "split_payments_enabled": not disable_split,
                "timestamp": timestamp
            },
            "summary": {
                "total_transactions": 0,
                "matched_transactions": 0,
                "match_rate": 0.0,
                "average_confidence": 0.0
            },
            "matches": []
        }

        # Write result file
        write_json(output_file, result)

        click.echo(f"✅ Results saved to: {output_file}")

    except Exception as e:
        click.echo(f"❌ Error during matching: {e}", err=True)
        raise click.ClickException(str(e))


@amazon.command()
@click.option('--transaction-id', required=True, help='YNAB transaction ID')
@click.option('--date', required=True, help='Transaction date (YYYY-MM-DD)')
@click.option('--amount', required=True, type=int, help='Transaction amount in milliunits')
@click.option('--payee-name', required=True, help='Transaction payee name')
@click.option('--account-name', required=True, help='Account name')
@click.option('--accounts', multiple=True, help='Amazon accounts to search')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def match_single(ctx: click.Context, transaction_id: str, date: str, amount: int,
                payee_name: str, account_name: str, accounts: tuple, verbose: bool) -> None:
    """
    Match a single YNAB transaction to Amazon orders.

    Example:
      finances amazon match-single --transaction-id "abc123" --date "2024-07-07"
        --amount -227320 --payee-name "Amazon.com" --account-name "Chase Credit Card"
    """
    config = get_config()

    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"Single Amazon Transaction Matching")
        click.echo(f"Transaction ID: {transaction_id}")
        click.echo(f"Date: {date}")
        click.echo(f"Amount: {amount} milliunits")
        click.echo(f"Payee: {payee_name}")
        click.echo(f"Account: {account_name}")
        click.echo()

    # Create transaction object
    ynab_transaction = {
        'id': transaction_id,
        'date': date,
        'amount': amount,
        'payee_name': payee_name,
        'account_name': account_name
    }

    try:
        # Initialize matcher
        matcher = SimplifiedMatcher()

        # Load Amazon data
        amazon_data_dir = config.data_dir / "amazon" / "raw"

        click.echo("🔍 Searching for matching Amazon orders...")
        click.echo("⚠️  Full implementation requires integration with existing single transaction logic")

        # Placeholder result
        result = {
            "transaction": ynab_transaction,
            "matches": [],
            "best_match": None,
            "message": "CLI implementation in progress"
        }

        # Display result
        if result.get('best_match'):
            click.echo("✅ Match found!")
            click.echo(f"Confidence: {result['best_match']['confidence']}")
        else:
            click.echo("❌ No matches found")

        # Output JSON for programmatic use
        click.echo("\nJSON Result:")
        click.echo(format_json(result))

    except Exception as e:
        click.echo(f"❌ Error during matching: {e}", err=True)
        raise click.ClickException(str(e))


@amazon.command()
@click.option('--download-dir', required=True, help='Directory containing downloaded ZIP files')
@click.option('--accounts', multiple=True, help='Filter by specific account names (karl, erica)')
@click.option('--output-dir', help='Override output directory (default: data/amazon/raw)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def unzip(ctx: click.Context, download_dir: str, accounts: tuple,
          output_dir: Optional[str], verbose: bool) -> None:
    """
    Extract Amazon order history ZIP files to structured directories.

    Downloads Amazon order history as ZIP files and extracts them to organized
    directory structure for downstream processing. Each ZIP file is extracted to
    a timestamped directory named with the detected account.

    Examples:
      finances amazon unzip --download-dir ~/Downloads
      finances amazon unzip --download-dir ~/Downloads --accounts karl erica
      finances amazon unzip --download-dir ~/Downloads --output-dir data/amazon/raw
    """
    config = get_config()

    # Determine output directory
    if output_dir:
        raw_data_path = Path(output_dir)
    else:
        raw_data_path = config.data_dir / "amazon" / "raw"

    download_path = Path(download_dir)

    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"Amazon Order History Unzip")
        click.echo(f"Download directory: {download_path}")
        click.echo(f"Output directory: {raw_data_path}")
        click.echo(f"Account filter: {list(accounts) if accounts else 'all'}")
        click.echo()

    # Validate download directory
    if not download_path.exists():
        raise click.ClickException(f"Download directory does not exist: {download_path}")

    try:
        # Extract ZIP files
        account_filter = list(accounts) if accounts else None
        result = extract_amazon_zip_files(download_path, raw_data_path, account_filter)

        # Display results
        if result['success']:
            click.echo(f"✅ {result['message']}")

            if result['files_processed'] > 0:
                click.echo(f"\nExtractions completed:")
                for extraction in result['extractions']:
                    click.echo(f"  📁 {extraction['output_directory']}")
                    click.echo(f"     Account: {extraction['account_name']}")
                    click.echo(f"     Files: {extraction['files_extracted']} ({len(extraction['csv_files'])} CSV)")

        else:
            click.echo(f"⚠️  {result['message']}")

            # Show successful extractions
            if result['extractions']:
                click.echo(f"\nSuccessful extractions:")
                for extraction in result['extractions']:
                    click.echo(f"  ✅ {extraction['output_directory']}")

            # Show errors
            if result['errors']:
                click.echo(f"\nErrors encountered:")
                for error in result['errors']:
                    click.echo(f"  ❌ {error['zip_file']}: {error['error']}")

        # Show summary
        click.echo(f"\nSummary:")
        click.echo(f"  Files processed: {result['files_processed']}")
        if result['files_failed'] > 0:
            click.echo(f"  Files failed: {result['files_failed']}")

        # Output JSON for programmatic use
        if verbose:
            click.echo("\nDetailed Results (JSON):")
            click.echo(format_json(result))

    except Exception as e:
        click.echo(f"❌ Error during unzip: {e}", err=True)
        raise click.ClickException(str(e))


if __name__ == '__main__':
    amazon()