#!/usr/bin/env python3
"""
Amazon CLI - Transaction Matching Commands

Professional command-line interface for Amazon transaction matching.
"""

from datetime import datetime
from pathlib import Path

import click

from ..amazon import SimplifiedMatcher
from ..amazon.unzipper import extract_amazon_zip_files
from ..core.config import get_config
from ..core.json_utils import format_json, write_json


@click.group()
def amazon() -> None:
    """Amazon transaction matching commands."""
    pass


@amazon.command()
@click.option("--start", help="Start date (YYYY-MM-DD) - optional, defaults to all transactions")
@click.option("--end", help="End date (YYYY-MM-DD) - optional, defaults to all transactions")
@click.option("--accounts", multiple=True, help="Specific Amazon accounts to process")
@click.option("--disable-split", is_flag=True, help="Disable split payment matching")
@click.option("--output-dir", help="Override output directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def match(
    ctx: click.Context,
    start: str | None,
    end: str | None,
    accounts: tuple,
    disable_split: bool,
    output_dir: str | None,
    verbose: bool,
) -> None:
    """
    Match YNAB transactions to Amazon orders.

    Date range is optional. If not provided, all Amazon transactions will be matched.

    Examples:
      finances amazon match
      finances amazon match --start 2024-07-01 --end 2024-07-31
      finances amazon match --start 2024-07-01 --end 2024-07-31 --accounts karl erica
    """
    config = get_config()

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "amazon" / "transaction_matches"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Amazon Transaction Matching")
        if start and end:
            click.echo(f"Date range: {start} to {end}")
        else:
            click.echo("Date range: all transactions")
        click.echo(f"Accounts: {list(accounts) if accounts else 'all'}")
        click.echo(f"Split payments: {'disabled' if disable_split else 'enabled'}")
        click.echo(f"Output: {output_path}")
        click.echo()

    try:
        # Initialize matcher
        split_cache_file = None if disable_split else str(config.cache_dir / "amazon_split_cache.json")
        matcher = SimplifiedMatcher(split_cache_file=split_cache_file)

        # Load Amazon data for specified accounts
        from ..amazon import load_amazon_data
        from ..ynab import filter_transactions, load_ynab_transactions

        amazon_data_dir = config.data_dir / "amazon" / "raw"
        ynab_cache_dir = config.data_dir / "ynab" / "cache"

        if verbose:
            click.echo(f"Loading Amazon data from: {amazon_data_dir}")
            click.echo(f"Loading YNAB data from: {ynab_cache_dir}")

        # Load Amazon account data
        account_data = load_amazon_data(amazon_data_dir, accounts)

        # Load and filter YNAB transactions
        all_transactions = load_ynab_transactions(ynab_cache_dir)
        transactions = filter_transactions(all_transactions, start_date=start, end_date=end, payee="Amazon")

        if verbose:
            click.echo(f"Loaded {len(account_data)} Amazon accounts")
            click.echo(f"Found {len(transactions)} Amazon transactions in date range")

        click.echo("🔍 Processing Amazon transaction matching...")

        # Match transactions
        matches = []
        matched_count = 0
        total_confidence = 0.0

        for tx in transactions:
            match_result = matcher.match_transaction(tx, account_data)

            # Add to matches if we found any matches
            if match_result.get("best_match"):
                matched_count += 1
                total_confidence += match_result["best_match"].get("confidence", 0.0)

            matches.append(match_result)

        # Calculate summary statistics
        match_rate = matched_count / len(transactions) if transactions else 0.0
        avg_confidence = total_confidence / matched_count if matched_count > 0 else 0.0

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_amazon_matching_results.json"

        # Build result structure
        result = {
            "metadata": {
                "start_date": start,
                "end_date": end,
                "accounts": list(accounts) if accounts else "all",
                "split_payments_enabled": not disable_split,
                "timestamp": timestamp,
            },
            "summary": {
                "total_transactions": len(transactions),
                "matched_transactions": matched_count,
                "match_rate": match_rate,
                "average_confidence": avg_confidence,
            },
            "matches": matches,
        }

        # Write result file
        write_json(output_file, result)

        # Display summary
        click.echo(f"✅ Matched {matched_count} of {len(transactions)} transactions ({match_rate*100:.1f}%)")
        click.echo(f"   Average confidence: {avg_confidence*100:.1f}%")
        click.echo(f"   Results saved to: {output_file}")

    except Exception as e:
        click.echo(f"❌ Error during matching: {e}", err=True)
        raise click.ClickException(str(e)) from e


@amazon.command()
@click.option("--transaction-id", required=True, help="YNAB transaction ID")
@click.option("--date", required=True, help="Transaction date (YYYY-MM-DD)")
@click.option("--amount", required=True, type=int, help="Transaction amount in milliunits")
@click.option("--payee-name", required=True, help="Transaction payee name")
@click.option("--account-name", required=True, help="Account name")
@click.option("--accounts", multiple=True, help="Amazon accounts to search")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def match_single(
    ctx: click.Context,
    transaction_id: str,
    date: str,
    amount: int,
    payee_name: str,
    account_name: str,
    accounts: tuple,
    verbose: bool,
) -> None:
    """
    Match a single YNAB transaction to Amazon orders.

    Example:
      finances amazon match-single --transaction-id "abc123" --date "2024-07-07"
        --amount -227320 --payee-name "Amazon.com" --account-name "Chase Credit Card"
    """
    config = get_config()

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Single Amazon Transaction Matching")
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
        matcher = SimplifiedMatcher()

        # Load Amazon data
        from ..amazon import load_amazon_data

        amazon_data_dir = config.data_dir / "amazon" / "raw"
        account_data = load_amazon_data(amazon_data_dir, accounts)

        if verbose:
            click.echo(f"Loaded {len(account_data)} Amazon accounts")

        click.echo("🔍 Searching for matching Amazon orders...")

        # Match the transaction
        result = matcher.match_transaction(ynab_transaction, account_data)

        # Display result
        if result.get("best_match"):
            best = result["best_match"]
            click.echo("\n✅ Match found!")
            click.echo(f"   Confidence: {best.get('confidence', 0.0)*100:.1f}%")
            click.echo(f"   Match type: {best.get('match_type', 'unknown')}")
            click.echo(f"   Order ID: {best.get('order_id', 'N/A')}")
            click.echo(f"   Order date: {best.get('order_date', 'N/A')}")
            click.echo(f"   Total: ${best.get('order_total_cents', 0)/100:.2f}")
        else:
            click.echo("\n❌ No matches found")

        # Show all matches if multiple found
        if verbose and len(result.get("matches", [])) > 1:
            click.echo(f"\nFound {len(result['matches'])} potential matches:")
            for i, match in enumerate(result["matches"][:5], 1):  # Show top 5
                click.echo(
                    f"  {i}. Order {match.get('order_id', 'N/A')} - "
                    f"Confidence: {match.get('confidence', 0.0)*100:.1f}%"
                )

        # Output JSON for programmatic use
        if verbose:
            click.echo("\nJSON Result:")
            click.echo(format_json(result))

    except Exception as e:
        click.echo(f"❌ Error during matching: {e}", err=True)
        raise click.ClickException(str(e)) from e


@amazon.command()
@click.option("--download-dir", required=True, help="Directory containing downloaded ZIP files")
@click.option("--accounts", multiple=True, help="Filter by specific account names (karl, erica)")
@click.option("--output-dir", help="Override output directory (default: data/amazon/raw)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def unzip(
    ctx: click.Context, download_dir: str, accounts: tuple, output_dir: str | None, verbose: bool
) -> None:
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
    raw_data_path = Path(output_dir) if output_dir else config.data_dir / "amazon" / "raw"

    download_path = Path(download_dir)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Amazon Order History Unzip")
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
        if result["success"]:
            click.echo(f"✅ {result['message']}")

            if result["files_processed"] > 0:
                click.echo("\nExtractions completed:")
                for extraction in result["extractions"]:
                    click.echo(f"  📁 {extraction['output_directory']}")
                    click.echo(f"     Account: {extraction['account_name']}")
                    click.echo(
                        f"     Files: {extraction['files_extracted']} ({len(extraction['csv_files'])} CSV)"
                    )

        else:
            click.echo(f"⚠️  {result['message']}")

            # Show successful extractions
            if result["extractions"]:
                click.echo("\nSuccessful extractions:")
                for extraction in result["extractions"]:
                    click.echo(f"  ✅ {extraction['output_directory']}")

            # Show errors
            if result["errors"]:
                click.echo("\nErrors encountered:")
                for error in result["errors"]:
                    click.echo(f"  ❌ {error['zip_file']}: {error['error']}")

        # Show summary
        click.echo("\nSummary:")
        click.echo(f"  Files processed: {result['files_processed']}")
        if result["files_failed"] > 0:
            click.echo(f"  Files failed: {result['files_failed']}")

        # Output JSON for programmatic use
        if verbose:
            click.echo("\nDetailed Results (JSON):")
            click.echo(format_json(result))

    except Exception as e:
        click.echo(f"❌ Error during unzip: {e}", err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    amazon()
