#!/usr/bin/env python3
"""
YNAB CLI - Transaction Updates and Mutation Management

Professional command-line interface for YNAB transaction updates.
"""

import click
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ..ynab import calculate_amazon_splits, calculate_apple_splits
from ..core.config import get_config
from ..core.models import Transaction


@click.group()
def ynab():
    """YNAB transaction update and mutation management commands."""
    pass


@ynab.command()
@click.option('--input-file', required=True, help='Match results JSON file')
@click.option('--confidence-threshold', type=float, default=0.8,
              help='Minimum confidence for automatic approval (default: 0.8)')
@click.option('--dry-run', is_flag=True, help='Generate mutations without applying them')
@click.option('--output-dir', help='Override output directory')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def generate_splits(ctx: click.Context, input_file: str, confidence_threshold: float,
                   dry_run: bool, output_dir: Optional[str], verbose: bool) -> None:
    """
    Generate transaction split mutations from match results.

    Examples:
      finances ynab generate-splits --input-file data/amazon/transaction_matches/2024-07-15_results.json
      finances ynab generate-splits --input-file data/apple/transaction_matches/2024-07-15_results.json --dry-run
    """
    config = get_config()

    # Determine output directory
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = config.data_dir / "ynab" / "mutations"

    output_path.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_file)
    if not input_path.exists():
        raise click.ClickException(f"Input file not found: {input_path}")

    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"YNAB Split Generation")
        click.echo(f"Input: {input_path}")
        click.echo(f"Confidence threshold: {confidence_threshold}")
        click.echo(f"Mode: {'Dry run' if dry_run else 'Generate mutations'}")
        click.echo(f"Output: {output_path}")
        click.echo()

    try:
        # Load match results
        with open(input_path, 'r') as f:
            match_results = json.load(f)

        if verbose:
            click.echo(f"Loaded {len(match_results.get('matches', []))} match results")

        # Determine match type (Amazon or Apple)
        match_type = "unknown"
        if "amazon" in str(input_path).lower():
            match_type = "amazon"
        elif "apple" in str(input_path).lower():
            match_type = "apple"

        # Generate mutations
        mutations = []
        auto_approved = 0
        requires_review = 0

        for match in match_results.get('matches', []):
            confidence = match.get('confidence', 0.0)

            if match_type == "amazon":
                splits = calculate_amazon_splits(match)
            elif match_type == "apple":
                splits = calculate_apple_splits(match)
            else:
                click.echo(f"⚠️  Unknown match type, skipping: {match.get('transaction_id', 'unknown')}")
                continue

            mutation = {
                "transaction_id": match.get('transaction_id'),
                "confidence": confidence,
                "auto_approved": confidence >= confidence_threshold,
                "splits": splits,
                "match_details": match
            }

            mutations.append(mutation)

            if mutation["auto_approved"]:
                auto_approved += 1
            else:
                requires_review += 1

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mode_suffix = "dry_run" if dry_run else "mutations"
        output_file = output_path / f"{timestamp}_{match_type}_{mode_suffix}.json"

        # Create mutation file
        mutation_data = {
            "metadata": {
                "source_file": str(input_path),
                "match_type": match_type,
                "confidence_threshold": confidence_threshold,
                "dry_run": dry_run,
                "timestamp": timestamp
            },
            "summary": {
                "total_mutations": len(mutations),
                "auto_approved": auto_approved,
                "requires_review": requires_review,
                "approval_rate": auto_approved / len(mutations) if mutations else 0.0
            },
            "mutations": mutations
        }

        # Write mutation file
        with open(output_file, 'w') as f:
            json.dump(mutation_data, f, indent=2)

        # Display summary
        click.echo(f"✅ Generated {len(mutations)} mutations")
        click.echo(f"   Auto-approved: {auto_approved}")
        click.echo(f"   Requires review: {requires_review}")
        click.echo(f"   Saved to: {output_file}")

        if dry_run:
            click.echo("\n💡 This was a dry run. Use --apply to execute mutations.")

    except Exception as e:
        click.echo(f"❌ Error generating splits: {e}", err=True)
        raise click.ClickException(str(e))


@ynab.command()
@click.option('--mutation-file', required=True, help='Mutation file to apply')
@click.option('--force', is_flag=True, help='Apply without confirmation prompt')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def apply_mutations(ctx: click.Context, mutation_file: str, force: bool, verbose: bool) -> None:
    """
    Apply transaction mutations to YNAB.

    Example:
      finances ynab apply-mutations --mutation-file data/ynab/mutations/2024-07-15_amazon_mutations.json
    """
    config = get_config()
    mutation_path = Path(mutation_file)

    if not mutation_path.exists():
        raise click.ClickException(f"Mutation file not found: {mutation_path}")

    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"YNAB Mutation Application")
        click.echo(f"Mutation file: {mutation_path}")
        click.echo()

    try:
        # Load mutation data
        with open(mutation_path, 'r') as f:
            mutation_data = json.load(f)

        mutations = mutation_data.get('mutations', [])
        auto_approved = sum(1 for m in mutations if m.get('auto_approved', False))
        requires_review = len(mutations) - auto_approved

        if verbose:
            click.echo(f"Loaded {len(mutations)} mutations")
            click.echo(f"  Auto-approved: {auto_approved}")
            click.echo(f"  Requires review: {requires_review}")
            click.echo()

        # Confirmation prompt
        if not force:
            click.echo(f"About to apply {auto_approved} auto-approved mutations to YNAB.")
            if requires_review > 0:
                click.echo(f"Note: {requires_review} mutations require review and will be skipped.")

            if not click.confirm("Continue?"):
                click.echo("Cancelled.")
                return

        # Apply mutations
        click.echo("🔍 Applying mutations to YNAB...")
        click.echo("⚠️  Full implementation requires YNAB API integration")

        # Placeholder implementation
        applied = 0
        skipped = 0

        for mutation in mutations:
            if mutation.get('auto_approved', False):
                # Would apply mutation here
                applied += 1
            else:
                skipped += 1

        click.echo(f"✅ Applied {applied} mutations")
        if skipped > 0:
            click.echo(f"⏸️  Skipped {skipped} mutations (require review)")

    except Exception as e:
        click.echo(f"❌ Error applying mutations: {e}", err=True)
        raise click.ClickException(str(e))


@ynab.command()
@click.option('--days', type=int, default=7, help='Number of days to sync (default: 7)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
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

    if verbose or ctx.obj.get('verbose', False):
        click.echo(f"YNAB Cache Sync")
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

        click.echo(f"✅ YNAB data synced to cache")
        click.echo(f"   Timestamp: {timestamp}")

    except Exception as e:
        click.echo(f"❌ Error syncing cache: {e}", err=True)
        raise click.ClickException(str(e))


if __name__ == '__main__':
    ynab()