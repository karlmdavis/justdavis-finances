#!/usr/bin/env python3
"""
Retirement CLI - YNAB-Based Balance Updates

Professional command-line interface for retirement account balance management
using YNAB as the single source of truth.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import click

from ..core.config import get_config
from ..core.currency import format_cents
from ..ynab.retirement import YnabRetirementService


@click.group()
def retirement() -> None:
    """Retirement account balance tracking commands."""
    pass


@retirement.command()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def list(ctx: click.Context, verbose: bool) -> None:
    """
    List all retirement accounts from YNAB with their current balances.

    Auto-discovers retirement accounts by filtering YNAB accounts for:
    - type: "otherAsset"
    - on_budget: false

    Example:
      finances retirement list
    """
    config = get_config()
    service = YnabRetirementService(config.data_dir)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Retirement Account Discovery")
        click.echo(f"YNAB cache: {config.data_dir / 'ynab' / 'cache'}")
        click.echo()

    # Discover accounts from YNAB
    accounts = service.discover_retirement_accounts()

    if not accounts:
        click.echo("No retirement accounts found in YNAB.")
        click.echo(
            "Retirement accounts are identified as off-budget assets (type: otherAsset, on_budget: false)"
        )
        return

    click.echo("Retirement Accounts (from YNAB):")
    click.echo("=" * 60)

    total_balance = 0
    for account in accounts:
        click.echo(f"\n{account.name}")
        click.echo(f"  Provider: {account.provider}")
        click.echo(f"  Type: {account.account_type}")
        click.echo(f"  Current Balance: {format_cents(account.balance_cents)}")

        if account.cleared_balance_cents != account.balance_cents:
            click.echo(f"  Cleared Balance: {format_cents(account.cleared_balance_cents)}")

        if account.last_reconciled_at:
            reconciled_date = account.last_reconciled_at.split("T")[0]
            click.echo(f"  Last Reconciled: {reconciled_date}")

        total_balance += account.balance_cents

    click.echo(f"\n{'-' * 60}")
    click.echo(f"Total: {len(accounts)} accounts, {format_cents(total_balance)}")


@retirement.command()
@click.option(
    "--interactive/--non-interactive",
    default=True,
    help="Interactive mode with prompts (default) or non-interactive",
)
@click.option("--date", help="Balance date (YYYY-MM-DD, default: today)")
@click.option("--output-file", help="Save YNAB edits to specific file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def update(
    ctx: click.Context, interactive: bool, date_str: Optional[str], output_file: Optional[str], verbose: bool
) -> None:
    """
    Update retirement account balances and generate YNAB adjustment transactions.

    Prompts for new balance information for each discovered retirement account.
    Generates YNAB reconciliation transactions that follow the standard edit workflow.

    Examples:
      finances retirement update
      finances retirement update --date 2024-07-31
      finances retirement update --output-file custom_retirement_edits.yaml
    """
    config = get_config()
    service = YnabRetirementService(config.data_dir)

    # Parse date
    update_date = None
    if date_str:
        try:
            update_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise click.ClickException(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
    else:
        update_date = date.today()

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Retirement Account Balance Update")
        click.echo(f"Update date: {update_date}")
        click.echo(f"Mode: {'Interactive' if interactive else 'Non-interactive'}")
        click.echo()

    # Discover accounts from YNAB
    accounts = service.discover_retirement_accounts()

    if not accounts:
        click.echo("No retirement accounts found in YNAB.")
        return

    # Collect balance updates
    adjustments = []

    if interactive:
        click.echo("Retirement Account Balance Updates")
        click.echo("Enter new balances (or press Enter to skip account)")
        click.echo()

        for account in accounts:
            click.echo(f"\n[ACCOUNT] {account.name}")
            click.echo(f"  Provider: {account.provider}")
            click.echo(f"  Type: {account.account_type}")
            click.echo(f"  Current Balance: {format_cents(account.balance_cents)}")

            # Prompt for new balance
            while True:
                try:
                    balance_input = click.prompt("  New Balance", default="", show_default=False, type=str)

                    if not balance_input.strip():
                        click.echo("  Skipped.\n")
                        break

                    # Parse balance - handle both $123.45 and 123.45 formats
                    balance_str = balance_input.strip().replace("$", "").replace(",", "")
                    balance_decimal = Decimal(balance_str)
                    new_balance_cents = int(balance_decimal * 100)

                    # Generate adjustment
                    mutation = service.generate_balance_adjustment(account, new_balance_cents, update_date)

                    if mutation:
                        adjustments.append(mutation)
                        adjustment_cents = mutation["metadata"]["adjustment_cents"]
                        adjustment_sign = "+" if adjustment_cents > 0 else ""
                        click.echo(f"  Adjustment: {adjustment_sign}{format_cents(adjustment_cents)}")
                        click.echo("  ✅ Added.\n")
                    else:
                        click.echo("  No change needed.\n")

                    break

                except (ValueError, TypeError):
                    click.echo("  ❌ Invalid balance format. Please enter a number (e.g., 123456.78)")

    else:
        # Non-interactive mode would need to read from a file or accept parameters
        click.echo("⚠️  Non-interactive mode requires additional implementation")
        click.echo("For now, use interactive mode: finances retirement update")
        return

    if not adjustments:
        click.echo("\nNo balance adjustments to process.")
        return

    # Show summary before creating edits
    click.echo("\nSummary of Adjustments:")
    click.echo("=" * 40)

    total_adjustment = 0
    for adj in adjustments:
        account_name = adj["account_name"]
        adjustment_cents = adj["metadata"]["adjustment_cents"]
        adjustment_sign = "+" if adjustment_cents > 0 else ""
        total_adjustment += adjustment_cents

        click.echo(f"{account_name}:")
        click.echo(f"  {adjustment_sign}{format_cents(adjustment_cents)}")

    click.echo(f"\nTotal Net Adjustment: {format_cents(total_adjustment)}")

    # Confirm before creating edits
    if interactive:
        click.echo()
        if not click.confirm("Generate YNAB edit file for these adjustments?"):
            click.echo("Cancelled.")
            return

    try:
        # Create edits file
        if output_file:
            # If custom output specified, we need to handle that
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # For now, use the service method and then rename/move
            edits_file = service.create_retirement_edits(adjustments)
            if edits_file and output_file:
                import shutil

                shutil.move(str(edits_file), str(output_path))
                edits_file = output_path
        else:
            edits_file = service.create_retirement_edits(adjustments)

        if edits_file:
            click.echo(f"\n✅ YNAB edits file created: {edits_file}")
            click.echo("\nNext steps:")
            click.echo(f"1. Review the edits: cat {edits_file}")
            click.echo(f"2. Apply to YNAB: finances ynab apply-edits --edit-file {edits_file}")
        else:
            click.echo("\n❌ Failed to create edits file")

    except Exception as e:
        click.echo(f"\n❌ Error creating edits: {e}", err=True)
        raise click.ClickException(str(e))


if __name__ == "__main__":
    retirement()
