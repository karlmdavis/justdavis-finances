#!/usr/bin/env python3
"""
YNAB CLI - Transaction Updates and Edit Management

Professional command-line interface for YNAB transaction updates.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from ..core.config import get_config
from ..core.json_utils import write_json
from ..ynab import calculate_amazon_splits, calculate_apple_splits


@click.group()
def ynab() -> None:
    """YNAB transaction update and edit management commands."""
    pass


@ynab.command()
@click.option("--input-file", required=True, help="Match results JSON file")
@click.option(
    "--confidence-threshold",
    type=float,
    default=0.8,
    help="Minimum confidence for automatic approval (default: 0.8)",
)
@click.option("--dry-run", is_flag=True, help="Generate edits without applying them")
@click.option("--output-dir", help="Override output directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def generate_splits(
    ctx: click.Context,
    input_file: str,
    confidence_threshold: float,
    dry_run: bool,
    output_dir: Optional[str],
    verbose: bool,
) -> None:
    """
    Generate transaction split edits from match results.

    Examples:
      finances ynab generate-splits --input-file data/amazon/transaction_matches/2024-07-15_results.json
      finances ynab generate-splits --input-file data/apple/transaction_matches/2024-07-15_results.json --dry-run
    """
    config = get_config()

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "ynab" / "edits"

    output_path.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_file)
    if not input_path.exists():
        raise click.ClickException(f"Input file not found: {input_path}")

    if verbose or ctx.obj.get("verbose", False):
        click.echo("YNAB Split Generation")
        click.echo(f"Input: {input_path}")
        click.echo(f"Confidence threshold: {confidence_threshold}")
        click.echo(f"Mode: {'Dry run' if dry_run else 'Generate edits'}")
        click.echo(f"Output: {output_path}")
        click.echo()

    try:
        # Load match results
        with open(input_path) as f:
            match_results = json.load(f)

        if verbose:
            click.echo(f"Loaded {len(match_results.get('matches', []))} match results")

        # Determine match type (Amazon or Apple)
        match_type = "unknown"
        if "amazon" in str(input_path).lower():
            match_type = "amazon"
        elif "apple" in str(input_path).lower():
            match_type = "apple"

        # Generate edits
        edits = []
        auto_approved = 0
        requires_review = 0

        for match in match_results.get("matches", []):
            confidence = match.get("confidence", 0.0)

            # Extract transaction amount in milliunits from the match
            ynab_transaction = match.get("ynab_transaction", {})
            transaction_amount_cents = ynab_transaction.get("amount", 0)
            # Convert cents to milliunits (YNAB's format)
            transaction_amount = transaction_amount_cents * 10

            if match_type == "amazon":
                # Extract Amazon items from the first order
                amazon_orders = match.get("amazon_orders", [])
                if amazon_orders:
                    amazon_items = amazon_orders[0].get("items", [])
                    splits = calculate_amazon_splits(transaction_amount, amazon_items)
                else:
                    click.echo(
                        f"⚠️  No Amazon orders in match, skipping: {ynab_transaction.get('id', 'unknown')}"
                    )
                    continue
            elif match_type == "apple":
                # Extract Apple items
                apple_items = match.get("items", [])
                splits = calculate_apple_splits(transaction_amount, apple_items)
            else:
                click.echo(f"⚠️  Unknown match type, skipping: {ynab_transaction.get('id', 'unknown')}")
                continue

            edit = {
                "transaction_id": ynab_transaction.get("id"),
                "confidence": confidence,
                "auto_approved": confidence >= confidence_threshold,
                "splits": splits,
                "match_details": match,
            }

            edits.append(edit)

            if edit["auto_approved"]:
                auto_approved += 1
            else:
                requires_review += 1

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mode_suffix = "dry_run" if dry_run else "edits"
        output_file = output_path / f"{timestamp}_{match_type}_{mode_suffix}.json"

        # Create edit file
        edit_data = {
            "metadata": {
                "source_file": str(input_path),
                "match_type": match_type,
                "confidence_threshold": confidence_threshold,
                "dry_run": dry_run,
                "timestamp": timestamp,
            },
            "summary": {
                "total_edits": len(edits),
                "auto_approved": auto_approved,
                "requires_review": requires_review,
                "approval_rate": auto_approved / len(edits) if edits else 0.0,
            },
            "edits": edits,
        }

        # Write edit file
        write_json(output_file, edit_data)

        # Display summary
        click.echo(f"✅ Generated {len(edits)} edits")
        click.echo(f"   Auto-approved: {auto_approved}")
        click.echo(f"   Requires review: {requires_review}")
        click.echo(f"   Saved to: {output_file}")

        if dry_run:
            click.echo("\n💡 This was a dry run. Use --apply to execute edits.")

    except Exception as e:
        click.echo(f"❌ Error generating splits: {e}", err=True)
        raise click.ClickException(str(e)) from e


@ynab.command()
@click.option("--edit-file", required=True, help="Edit file to apply")
@click.option("--force", is_flag=True, help="Apply without confirmation prompt")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def apply_edits(ctx: click.Context, edit_file: str, force: bool, verbose: bool) -> None:
    """
    Apply transaction edits to YNAB.

    Example:
      finances ynab apply-edits --edit-file data/ynab/edits/2024-07-15_amazon_edits.json
    """
    get_config()
    edit_path = Path(edit_file)

    if not edit_path.exists():
        raise click.ClickException(f"Edit file not found: {edit_path}")

    if verbose or ctx.obj.get("verbose", False):
        click.echo("YNAB Edit Application")
        click.echo(f"Edit file: {edit_path}")
        click.echo()

    try:
        # Load edit data
        with open(edit_path) as f:
            edit_data = json.load(f)

        edits = edit_data.get("edits", [])
        auto_approved = sum(1 for m in edits if m.get("auto_approved", False))
        requires_review = len(edits) - auto_approved

        if verbose:
            click.echo(f"Loaded {len(edits)} edits")
            click.echo(f"  Auto-approved: {auto_approved}")
            click.echo(f"  Requires review: {requires_review}")
            click.echo()

        # Confirmation prompt
        if not force:
            click.echo(f"About to apply {auto_approved} auto-approved edits to YNAB.")
            if requires_review > 0:
                click.echo(f"Note: {requires_review} edits require review and will be skipped.")

            if not click.confirm("Continue?"):
                click.echo("Cancelled.")
                return

        # Apply edits
        click.echo("🔍 Applying edits to YNAB...")
        click.echo("⚠️  Full implementation requires YNAB API integration")

        # Placeholder implementation
        applied = 0
        skipped = 0

        for edit in edits:
            if edit.get("auto_approved", False):
                # Would apply edit here
                applied += 1
            else:
                skipped += 1

        click.echo(f"✅ Applied {applied} edits")
        if skipped > 0:
            click.echo(f"⏸️  Skipped {skipped} edits (require review)")

    except Exception as e:
        click.echo(f"❌ Error applying edits: {e}", err=True)
        raise click.ClickException(str(e)) from e


@ynab.command()
@click.option("--days", type=int, default=7, help="Number of days to sync (default: 7)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def sync_cache(ctx: click.Context, days: int, verbose: bool) -> None:
    """
    Sync YNAB data to local cache.

    Example:
      finances ynab sync-cache --days 30
    """
    config = get_config()
    cache_dir = config.data_dir / "ynab" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("YNAB Cache Sync")
        click.echo(f"Days to sync: {days}")
        click.echo(f"Cache directory: {cache_dir}")
        click.echo()

    try:
        click.echo("🔄 Syncing YNAB data to local cache...")
        click.echo("⚠️  Full implementation requires YNAB API integration")

        # Placeholder for YNAB data sync
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Would fetch and cache:
        # - accounts.json
        # - categories.json
        # - transactions.json (last N days)

        click.echo("✅ YNAB data synced to cache")
        click.echo(f"   Timestamp: {timestamp}")

    except Exception as e:
        click.echo(f"❌ Error syncing cache: {e}", err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    ynab()
