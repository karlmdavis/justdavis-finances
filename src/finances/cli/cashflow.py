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
from ..core.currency import format_cents


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
        click.echo(f"   Current Balance: {format_cents(int(stats['current_balance'] * 100))}")
        click.echo(
            f"   Monthly Trend: {format_cents(int(stats['monthly_trend'] * 100))}/month ({stats['trend_direction']})"
        )
        click.echo(f"   Monthly Burn Rate: {format_cents(int(stats['monthly_burn_rate'] * 100))}")
        click.echo(f"   Trend Confidence: {stats['trend_confidence']*100:.1f}%")
        click.echo(f"   Volatility: {format_cents(int(stats['volatility'] * 100))}")

        if verbose:
            click.echo(f"\n📅 Analysis Period: {stats['data_start_date']} to present")
            click.echo(f"   Yearly Projection: {format_cents(int(stats['yearly_trend'] * 100))}/year")

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
        # Use existing analyzer to get data
        from ..analysis import CashFlowAnalyzer, CashFlowConfig

        analyzer_config = CashFlowConfig.default()
        analyzer = CashFlowAnalyzer(analyzer_config)

        # Load YNAB data
        ynab_cache_dir = config.data_dir / "ynab" / "cache"
        analyzer.load_data(ynab_cache_dir)

        click.echo("📋 Generating cash flow report...")

        # Get summary statistics
        stats = analyzer.get_summary_statistics()

        # Generate output filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_path / f"{timestamp}_{period}_cashflow_report.{format}"

        # Build report data
        report_data = {
            "metadata": {
                "generated_at": timestamp,
                "period": period,
                "start_date": start or stats.get("data_start_date", "N/A"),
                "end_date": end or datetime.now().strftime("%Y-%m-%d"),
                "categories": list(categories) if categories else "all",
            },
            "summary": stats,
            "sections": {
                "income_expense": {
                    "current_balance": stats["current_balance"],
                    "monthly_trend": stats["monthly_trend"],
                    "yearly_trend": stats["yearly_trend"],
                },
                "trends": {
                    "direction": stats["trend_direction"],
                    "confidence": stats["trend_confidence"],
                    "volatility": stats["volatility"],
                },
                "projections": {
                    "monthly_burn_rate": stats["monthly_burn_rate"],
                },
            },
        }

        # Write to file based on format
        if format == "json":
            from ..core.json_utils import write_json

            write_json(output_file, report_data)
        elif format == "csv":
            import csv

            with open(output_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])
                for key, value in stats.items():
                    writer.writerow([key, value])
        elif format == "xlsx":
            # XLSX requires openpyxl - provide fallback to JSON
            click.echo("⚠️  XLSX format not yet supported, using JSON instead")
            output_file = output_file.with_suffix(".json")
            from ..core.json_utils import write_json

            write_json(output_file, report_data)

        click.echo(f"✅ Report saved to: {output_file}")

        # Display key metrics
        click.echo("\n[SUMMARY] Key Metrics:")
        click.echo(f"   Current Balance: {format_cents(int(stats['current_balance'] * 100))}")
        click.echo(f"   Monthly Trend: {format_cents(int(stats['monthly_trend'] * 100))}/month")
        click.echo(f"   Yearly Trend: {format_cents(int(stats['yearly_trend'] * 100))}/year")

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
        # Use existing analyzer to get trend data
        from ..analysis import CashFlowAnalyzer, CashFlowConfig

        config = get_config()
        analyzer_config = CashFlowConfig.default()
        analyzer = CashFlowAnalyzer(analyzer_config)

        # Load YNAB data
        ynab_cache_dir = config.data_dir / "ynab" / "cache"
        analyzer.load_data(ynab_cache_dir)

        click.echo("🔮 Generating cash flow forecast...")

        # Get current statistics
        stats = analyzer.get_summary_statistics()

        # Calculate projections based on monthly trend
        current_balance = stats["current_balance"]
        monthly_trend = stats["monthly_trend"]
        volatility = stats["volatility"]
        confidence = stats["trend_confidence"]

        # Simple linear projections with confidence intervals
        # Confidence interval = volatility * (1 - confidence)
        margin = volatility * (1 - confidence)

        projections = {
            "30_day": {
                "days": 30,
                "projected_balance": current_balance + monthly_trend,
                "lower_bound": current_balance + monthly_trend - margin,
                "upper_bound": current_balance + monthly_trend + margin,
                "change": monthly_trend,
            },
            "60_day": {
                "days": 60,
                "projected_balance": current_balance + (monthly_trend * 2),
                "lower_bound": current_balance + (monthly_trend * 2) - (margin * 1.5),
                "upper_bound": current_balance + (monthly_trend * 2) + (margin * 1.5),
                "change": monthly_trend * 2,
            },
            "90_day": {
                "days": 90,
                "projected_balance": current_balance + (monthly_trend * 3),
                "lower_bound": current_balance + (monthly_trend * 3) - (margin * 2),
                "upper_bound": current_balance + (monthly_trend * 3) + (margin * 2),
                "change": monthly_trend * 3,
            },
        }

        click.echo("\n🎯 Forecast Summary:")
        click.echo(f"   Current Balance: {format_cents(int(current_balance * 100))}")
        click.echo(
            f"   Monthly Trend: {format_cents(int(monthly_trend * 100))}/month ({stats['trend_direction']})"
        )
        click.echo(f"   Trend Confidence: {confidence*100:.1f}%")
        click.echo(f"   Volatility: {format_cents(int(volatility * 100))}")
        click.echo()

        for projection in projections.values():
            click.echo(f"   {projection['days']}-day projection:")
            click.echo(f"      Balance: {format_cents(int(projection['projected_balance'] * 100))}")
            click.echo(
                f"      Range: {format_cents(int(projection['lower_bound'] * 100))} - {format_cents(int(projection['upper_bound'] * 100))}"
            )
            click.echo(f"      Change: {format_cents(int(projection['change'] * 100))}")

        # Display risk assessment
        risk_level = "LOW" if confidence > 0.8 else "MEDIUM" if confidence > 0.5 else "HIGH"
        click.echo(f"\n   Risk Assessment: {risk_level}")
        click.echo(f"      Based on trend confidence of {confidence*100:.1f}%")

    except Exception as e:
        click.echo(f"❌ Error generating forecast: {e}", err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cashflow()
