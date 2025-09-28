#!/usr/bin/env python3
"""
Retirement CLI - Balance Tracking Commands

Professional command-line interface for retirement account balance management.
"""

import click
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any
from decimal import Decimal

from ..retirement import RetirementTracker
from ..core.config import get_config
from ..core.currency import format_cents


@click.group()
def retirement():
    """Retirement account balance tracking commands."""
    pass


@retirement.command()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def list_accounts(ctx: click.Context, verbose: bool) -> None:
    """
    List all tracked retirement accounts with their latest balances.

    Shows active retirement accounts, their types, providers, and most recent
    balance information including last update date and current balance.

    Example:
      finances retirement list-accounts
    """
    config = get_config()
    tracker = RetirementTracker(config.data_dir)

    if verbose or ctx.obj.get('verbose', False):
        click.echo("Retirement Account Listing")
        click.echo(f"Data directory: {config.data_dir / 'retirement'}")
        click.echo()

    active_accounts = tracker.get_active_accounts()

    if not active_accounts:
        click.echo("No active retirement accounts found.")
        click.echo("Run 'finances retirement configure' to set up accounts.")
        return

    click.echo("Active Retirement Accounts:")
    click.echo("=" * 50)

    for account in active_accounts:
        click.echo(f"\n[ACCOUNT] {account.name}")
        click.echo(f"   Type: {account.account_type}")
        click.echo(f"   Provider: {account.provider}")

        if account.ynab_account_name:
            click.echo(f"   YNAB Account: {account.ynab_account_name}")

        # Get latest balance
        last_balance = tracker.get_last_balance(account.name)
        if last_balance:
            click.echo(f"   Last Updated: {last_balance.date}")
            click.echo(f"   Current Balance: {format_cents(last_balance.balance_cents)}")

            if last_balance.adjustment_cents and last_balance.adjustment_cents != 0:
                adjustment_sign = "+" if last_balance.adjustment_cents > 0 else ""
                click.echo(f"   Last Adjustment: {adjustment_sign}{format_cents(last_balance.adjustment_cents)}")
        else:
            click.echo(f"   Status: No balance history")

    click.echo(f"\nTotal accounts: {len(active_accounts)}")


@retirement.command()
@click.option('--interactive/--non-interactive', default=True,
              help='Interactive mode with prompts (default) or non-interactive')
@click.option('--account', multiple=True, help='Specific accounts to update')
@click.option('--date', help='Balance date (YYYY-MM-DD, default: today)')
@click.option('--output-file', help='Save YNAB transactions to file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def update(ctx: click.Context, interactive: bool, account: tuple, date: Optional[str],
           output_file: Optional[str], verbose: bool) -> None:
    """
    Update retirement account balances interactively.

    Prompts for new balance information for each tracked retirement account.
    Calculates adjustments and generates YNAB transactions for balance changes.
    Supports both interactive prompting and batch updates.

    Examples:
      finances retirement update
      finances retirement update --account karl_401k --account erica_403b
      finances retirement update --date 2024-07-31 --output-file ynab_updates.yaml
    """
    config = get_config()
    tracker = RetirementTracker(config.data_dir)

    # Parse date
    update_date = None
    if date:
        try:
            update_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise click.ClickException(f"Invalid date format: {date}. Use YYYY-MM-DD")
    else:
        update_date = date.today()

    if verbose or ctx.obj.get('verbose', False):
        click.echo("Retirement Account Balance Update")
        click.echo(f"Update date: {update_date}")
        click.echo(f"Mode: {'Interactive' if interactive else 'Non-interactive'}")
        click.echo()

    # Get accounts to update
    if account:
        # Filter to specified accounts
        all_accounts = tracker.get_active_accounts()
        accounts_to_update = [acc for acc in all_accounts if acc.name in account]

        if len(accounts_to_update) != len(account):
            missing = set(account) - {acc.name for acc in accounts_to_update}
            raise click.ClickException(f"Unknown accounts: {', '.join(missing)}")
    else:
        accounts_to_update = tracker.get_active_accounts()

    if not accounts_to_update:
        click.echo("No accounts to update.")
        return

    # Collect updates
    updates = {}

    if interactive:
        click.echo("Retirement Account Balance Updates")
        click.echo("Enter new balances (or press Enter to skip account)")
        click.echo()

        for account_obj in accounts_to_update:
            # Show current info
            last_balance = tracker.get_last_balance(account_obj.name)

            click.echo(f"[ACCOUNT] {account_obj.name} ({account_obj.account_type})")
            click.echo(f"   Provider: {account_obj.provider}")

            if last_balance:
                click.echo(f"   Last Balance: {format_cents(last_balance.balance_cents)} (on {last_balance.date})")
            else:
                click.echo(f"   Last Balance: No previous balance")

            # Prompt for new balance
            while True:
                try:
                    balance_input = click.prompt(
                        f"   New Balance",
                        default="",
                        show_default=False,
                        type=str
                    )

                    if not balance_input.strip():
                        click.echo("   Skipped.\n")
                        break

                    # Parse balance - handle both $123.45 and 123.45 formats
                    balance_str = balance_input.strip().replace('$', '').replace(',', '')
                    balance_decimal = Decimal(balance_str)
                    balance_cents = int(balance_decimal * 100)

                    # Prompt for notes
                    notes = click.prompt(
                        f"   Notes (optional)",
                        default="",
                        show_default=False,
                        type=str
                    )

                    updates[account_obj.name] = {
                        "balance_cents": balance_cents,
                        "date": update_date,
                        "notes": notes.strip() if notes.strip() else None
                    }

                    # Show preview
                    if last_balance:
                        adjustment_cents = balance_cents - last_balance.balance_cents
                        adjustment_sign = "+" if adjustment_cents > 0 else ""
                        click.echo(f"   Adjustment: {adjustment_sign}{format_cents(adjustment_cents)}")

                    click.echo("   ✅ Added.\n")
                    break

                except (ValueError, TypeError) as e:
                    click.echo(f"   ❌ Invalid balance format. Please enter a number (e.g., 123456.78)")

    else:
        # Non-interactive mode - would read from file or require parameters
        click.echo("⚠️  Non-interactive mode requires additional implementation")
        click.echo("For now, use interactive mode: finances retirement update")
        return

    if not updates:
        click.echo("No updates to process.")
        return

    # Show summary before processing
    click.echo("Summary of Updates:")
    click.echo("=" * 30)
    total_adjustment = 0

    for account_name, update_data in updates.items():
        last_balance = tracker.get_last_balance(account_name)
        previous_cents = last_balance.balance_cents if last_balance else 0
        adjustment_cents = update_data["balance_cents"] - previous_cents
        total_adjustment += adjustment_cents

        click.echo(f"{account_name}:")
        click.echo(f"  New Balance: {format_cents(update_data['balance_cents'])}")
        if adjustment_cents != 0:
            adjustment_sign = "+" if adjustment_cents > 0 else ""
            click.echo(f"  Adjustment: {adjustment_sign}{format_cents(adjustment_cents)}")

    click.echo(f"\nTotal Net Adjustment: {format_cents(total_adjustment)}")

    # Confirm before processing
    if interactive:
        click.echo()
        if not click.confirm("Process these updates?"):
            click.echo("Updates cancelled.")
            return

    try:
        # Process updates
        update_result = tracker.update_session(updates)

        click.echo("\n✅ Updates processed successfully!")
        click.echo(f"Accounts updated: {len(update_result.accounts_updated)}")
        click.echo(f"Total adjustment: {format_cents(update_result.total_adjustment_cents)}")

        # Show YNAB transactions
        if update_result.ynab_transactions_created:
            click.echo(f"\nYNAB Transactions Generated ({len(update_result.ynab_transactions_created)}):")

            for transaction in update_result.ynab_transactions_created:
                click.echo(f"  📝 {transaction['account_name']}")
                click.echo(f"     Amount: {format_cents(transaction['amount_milliunits'] // 10)}")
                click.echo(f"     Memo: {transaction['memo']}")

            # Save to file if requested
            if output_file:
                output_path = Path(output_file)
                ynab_data = {
                    "retirement_update": {
                        "date": update_result.date,
                        "transactions": update_result.ynab_transactions_created
                    }
                }

                with open(output_path, 'w') as f:
                    yaml.dump(ynab_data, f, default_flow_style=False, sort_keys=True)

                click.echo(f"\n💾 YNAB transactions saved to: {output_path}")
                click.echo("Use 'finances ynab apply-mutations' to apply these transactions")

        else:
            click.echo("\nNo YNAB transactions needed (no balance changes).")

    except Exception as e:
        click.echo(f"❌ Error processing updates: {e}", err=True)
        raise click.ClickException(str(e))


@retirement.command()
@click.option('--account', help='Specific account to show history for')
@click.option('--limit', default=10, help='Number of recent entries to show (default: 10)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def history(ctx: click.Context, account: Optional[str], limit: int, verbose: bool) -> None:
    """
    Show balance history for retirement accounts.

    Displays recent balance updates and adjustments for tracked retirement accounts.
    Can show history for all accounts or filter to a specific account.

    Examples:
      finances retirement history
      finances retirement history --account karl_401k
      finances retirement history --limit 5
    """
    config = get_config()
    tracker = RetirementTracker(config.data_dir)

    if verbose or ctx.obj.get('verbose', False):
        click.echo("Retirement Account Balance History")
        click.echo(f"Limit: {limit} entries per account")
        if account:
            click.echo(f"Account filter: {account}")
        click.echo()

    # Determine accounts to show
    if account:
        if account not in tracker.accounts:
            raise click.ClickException(f"Unknown account: {account}")
        accounts_to_show = [account]
    else:
        accounts_to_show = [acc.name for acc in tracker.get_active_accounts()]

    if not accounts_to_show:
        click.echo("No accounts to show history for.")
        return

    for account_name in accounts_to_show:
        if account_name not in tracker.balance_history:
            click.echo(f"[ACCOUNT] {account_name}: No balance history")
            continue

        entries = tracker.balance_history[account_name]
        if not entries:
            click.echo(f"[ACCOUNT] {account_name}: No balance history")
            continue

        # Sort by date (most recent first) and limit
        sorted_entries = sorted(entries, key=lambda x: x.date, reverse=True)[:limit]

        click.echo(f"[ACCOUNT] {account_name}:")

        for entry in sorted_entries:
            click.echo(f"   {entry.date}: {format_cents(entry.balance_cents)}")

            if entry.adjustment_cents and entry.adjustment_cents != 0:
                adjustment_sign = "+" if entry.adjustment_cents > 0 else ""
                click.echo(f"      Adjustment: {adjustment_sign}{format_cents(entry.adjustment_cents)}")

            if entry.notes:
                click.echo(f"      Notes: {entry.notes}")

        click.echo()


if __name__ == '__main__':
    retirement()