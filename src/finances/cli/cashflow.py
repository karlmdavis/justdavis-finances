#!/usr/bin/env python3
"""
Cash Flow CLI - Financial Analysis Commands

Professional command-line interface for cash flow analysis and reporting.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import click

from ..analysis import CashFlowAnalyzer, CashFlowConfig
from ..core.config import get_config


@click.group()
def cashflow() -> None:
    """Cash flow analysis and reporting commands."""
    pass


@cashflow.command()
@click.option("--start", help="Start date (YYYY-MM-DD), defaults to 6 months ago")
@click.option("--end", help="End date (YYYY-MM-DD), defaults to today")
@click.option("--accounts", multiple=True, help="Specific accounts to analyze")
@click.option("--exclude-before", help="Exclude data before date (YYYY-MM-DD)")
@click.option("--output-dir", help="Override output directory")
@click.option(
    "--format", type=click.Choice(["png", "pdf", "svg"]), default="png", help="Output format (default: png)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def analyze(
    ctx: click.Context,
    start: str | None,
    end: str | None,
    accounts: tuple,
    exclude_before: str | None,
    output_dir: str | None,
    format: str,
    verbose: bool,
) -> None:
    """
    Generate comprehensive cash flow analysis dashboard.

    Examples:
      finances cashflow analyze
      finances cashflow analyze --start 2024-01-01 --end 2024-12-31
      finances cashflow analyze --accounts "Chase Checking" "Chase Credit Card"
      finances cashflow analyze --exclude-before 2024-05-01 --format pdf
    """
    config = get_config()

    # Set default date range
    if not end:
        end_date = date.today()
        end = end_date.strftime("%Y-%m-%d")
    else:
        end_date = date.fromisoformat(end)

    if not start:
        start_date = end_date - timedelta(days=180)  # 6 months
        start = start_date.strftime("%Y-%m-%d")
    else:
        start_date = date.fromisoformat(start)

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "cash_flow" / "charts"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Cash Flow Analysis")
        click.echo(f"Date range: {start} to {end}")
        click.echo(f"Accounts: {list(accounts) if accounts else 'all primary accounts'}")
        if exclude_before:
            click.echo(f"Excluding data before: {exclude_before}")
        click.echo(f"Output format: {format}")
        click.echo(f"Output directory: {output_path}")
        click.echo()

    try:
        # Create analyzer configuration
        analyzer_config = CashFlowConfig(
            cash_accounts=list(accounts) if accounts else CashFlowConfig.default().cash_accounts,
            start_date=exclude_before if exclude_before else CashFlowConfig.default().start_date,
            output_format=format,
        )

        # Initialize analyzer
        analyzer = CashFlowAnalyzer(analyzer_config)

        # Load YNAB data
        ynab_cache_dir = config.data_dir / "ynab" / "cache"

        if verbose:
            click.echo(f"Loading YNAB data from: {ynab_cache_dir}")
            click.echo(f"Analyzing accounts: {analyzer_config.cash_accounts}")
            click.echo(f"Start date: {analyzer_config.start_date}")

        click.echo("[ANALYSIS] Loading and processing cash flow data...")
        analyzer.load_data(ynab_cache_dir)

        click.echo("[DASHBOARD] Generating comprehensive dashboard...")
        output_file = analyzer.generate_dashboard(output_path)

        # Get summary statistics
        stats = analyzer.get_summary_statistics()

        click.echo(f"\n✅ Dashboard saved to: {output_file}")

        # Display key insights
        click.echo("\n[INSIGHTS] Key Statistics:")
        click.echo(f"   Current Balance: ${stats['current_balance']:,.0f}")
        click.echo(f"   Monthly Trend: ${stats['monthly_trend']:,.0f}/month ({stats['trend_direction']})")
        click.echo(f"   Monthly Burn Rate: ${stats['monthly_burn_rate']:,.0f}")
        click.echo(f"   Trend Confidence: {stats['trend_confidence']*100:.1f}%")
        click.echo(f"   Volatility: ${stats['volatility']:,.0f}")

        if verbose:
            click.echo(f"\n📅 Analysis Period: {stats['data_start_date']} to present")
            click.echo(f"   Yearly Projection: ${stats['yearly_trend']:,.0f}/year")

    except Exception as e:
        click.echo(f"❌ Error during analysis: {e}", err=True)
        raise click.ClickException(str(e)) from e


@cashflow.command()
@click.option(
    "--period",
    type=click.Choice(["daily", "weekly", "monthly"]),
    default="monthly",
    help="Reporting period (default: monthly)",
)
@click.option("--start", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (YYYY-MM-DD)")
@click.option("--categories", multiple=True, help="Specific categories to report")
@click.option("--output-dir", help="Override output directory")
@click.option(
    "--format",
    type=click.Choice(["json", "csv", "xlsx"]),
    default="json",
    help="Output format (default: json)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def report(
    ctx: click.Context,
    period: str,
    start: str | None,
    end: str | None,
    categories: tuple,
    output_dir: str | None,
    format: str,
    verbose: bool,
) -> None:
    """
    Generate structured cash flow reports.

    Examples:
      finances cashflow report --period monthly
      finances cashflow report --period weekly --start 2024-07-01 --end 2024-07-31
      finances cashflow report --categories "Groceries" "Gas" --format csv
    """
    config = get_config()

    # Determine output directory
    output_path = Path(output_dir) if output_dir else config.data_dir / "cash_flow" / "data"

    output_path.mkdir(parents=True, exist_ok=True)

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Cash Flow Report Generation")
        click.echo(f"Period: {period}")
        if start:
            click.echo(f"Start date: {start}")
        if end:
            click.echo(f"End date: {end}")
        click.echo(f"Categories: {list(categories) if categories else 'all'}")
        click.echo(f"Output format: {format}")
        click.echo(f"Output directory: {output_path}")
        click.echo()

    try:
        click.echo("📋 Generating cash flow report...")
        click.echo("⚠️  Full implementation requires migration of existing analysis logic")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_{period}_cashflow_report.{format}"

        # Placeholder report structure
        report_sections = [
            f"{period.title()} income/expense breakdown",
            "Category-wise spending analysis",
            "Account balance changes",
            "Trend indicators",
            "Variance from historical averages",
        ]

        click.echo("\n[REPORT] Sections:")
        for section in report_sections:
            click.echo(f"  • {section}")

        click.echo(f"\n✅ Report would be saved to: {output_file}")

    except Exception as e:
        click.echo(f"❌ Error generating report: {e}", err=True)
        raise click.ClickException(str(e)) from e


@cashflow.command()
@click.option("--lookback-days", type=int, default=90, help="Days to analyze for trend (default: 90)")
@click.option(
    "--confidence-level", type=float, default=0.95, help="Statistical confidence level (default: 0.95)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def forecast(ctx: click.Context, lookback_days: int, confidence_level: float, verbose: bool) -> None:
    """
    Generate cash flow forecasts based on historical trends.

    Example:
      finances cashflow forecast --lookback-days 180 --confidence-level 0.90
    """
    get_config()

    if verbose or ctx.obj.get("verbose", False):
        click.echo("Cash Flow Forecasting")
        click.echo(f"Lookback period: {lookback_days} days")
        click.echo(f"Confidence level: {confidence_level}")
        click.echo()

    try:
        click.echo("🔮 Generating cash flow forecast...")
        click.echo("⚠️  Full implementation requires migration of existing analysis logic")

        # Forecast components
        forecast_metrics = [
            "30-day cash flow projection",
            "60-day cash flow projection",
            "90-day cash flow projection",
            "Confidence intervals",
            "Trend strength indicators",
            "Seasonality adjustments",
            "Risk assessment",
        ]

        click.echo("\n🎯 Forecast Metrics:")
        for metric in forecast_metrics:
            click.echo(f"  • {metric}")

        click.echo("\n[FORECAST] Summary:")
        click.echo("   30-day projection: $X,XXX ± $XXX")
        click.echo("   60-day projection: $X,XXX ± $XXX")
        click.echo("   90-day projection: $X,XXX ± $XXX")
        click.echo("   Trend confidence: XX%")

    except Exception as e:
        click.echo(f"❌ Error generating forecast: {e}", err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cashflow()
