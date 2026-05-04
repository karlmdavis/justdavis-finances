#!/usr/bin/env python3
"""
Cash Flow Analysis Module

Professional cash flow analysis with trend detection, statistical modeling,
and comprehensive dashboard generation.
"""

import matplotlib
import pandas as pd

matplotlib.use("Agg")  # Use non-interactive backend
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from ..core.config import get_config
from ..ynab.loader import load_accounts, load_transactions


class WindowStats(TypedDict):
    """Linear-regression trend statistics for one date-windowed view of the balance series."""

    slope: float
    intercept: float
    r_value: float
    p_value: float
    std_err: float
    monthly_trend: float
    yearly_trend: float
    direction: Literal["positive", "negative", "flat"]
    fit_quality: float
    trend_line: np.ndarray
    window_index: pd.Index
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    n_days: int


class TrendStats(TypedDict):
    """Three windowed regressions; any slot may be None when its window can't be computed."""

    overall: WindowStats | None
    thirteen_months: WindowStats | None
    six_months: WindowStats | None


@dataclass
class CashFlowConfig:
    """Configuration for cash flow analysis."""

    # Account selection
    cash_accounts: list[str]
    start_date: str

    # Analysis parameters
    short_ma_window: int = 7
    medium_ma_window: int = 30
    long_ma_window: int = 90

    # Output configuration
    figure_size: tuple[int, int] = (16, 12)
    dpi: int = 150
    output_format: str = "png"

    @classmethod
    def default(cls) -> "CashFlowConfig":
        """Create default configuration."""
        return cls(
            cash_accounts=[
                "Chase Checking",
                "Chase Credit Card",
                "Apple Card",
                "Apple Cash",
                "Apple Savings",
            ],
            start_date="2024-05-01",  # Exclude unreliable data before May 2024
        )


class CashFlowAnalyzer:
    """
    Professional cash flow analyzer with advanced statistical modeling.

    Features:
    - Multi-timeframe moving averages for noise reduction
    - Trend analysis with statistical confidence
    - Monthly aggregation and burn rate calculation
    - Account composition tracking over time
    - Comprehensive dashboard generation with 6 panels
    """

    def __init__(self, config: CashFlowConfig | None = None):
        """Initialize analyzer with configuration."""
        self.config = config or CashFlowConfig.default()
        self.df: pd.DataFrame | None = None
        self.monthly_df: pd.DataFrame | None = None
        self.trend_stats: TrendStats | None = None

    def load_data(self, ynab_cache_dir: Path | None = None) -> None:
        """Load YNAB data from cache directory."""
        # Load typed domain models via shared loaders
        accounts = load_accounts(ynab_cache_dir)
        transactions = load_transactions(ynab_cache_dir)

        # Filter accounts: by configured name, excluding closed accounts.
        # Note: on_budget is NOT filtered here — credit cards tracked as off-budget in YNAB
        # still carry real debt and must be included in the net balance calculation.
        cash_account_models = [a for a in accounts if a.name in self.config.cash_accounts and not a.closed]

        # Get current balances (convert milliunits → dollars at the pandas DataFrame boundary)
        current_balances = {a.name: a.balance.to_milliunits() / 1000 for a in cash_account_models}

        # Filter transactions: by included account name, start date, and exclude deleted.
        # Use current_balances keys (not self.config.cash_accounts) so that closed accounts
        # — already excluded from current_balances — don't have their historical transactions
        # included in the backwards walk starting from a $0 anchor.
        cash_transactions = [
            t
            for t in transactions
            if t.account_name in current_balances and str(t.date) >= self.config.start_date and not t.deleted
        ]
        cash_transactions.sort(key=lambda x: str(x.date))

        if not cash_transactions:
            raise ValueError(f"No transactions found for cash accounts after {self.config.start_date}")

        # Calculate daily balances by working backwards from current balances
        daily_balances: defaultdict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
        end_date = max(str(t.date) for t in cash_transactions)

        # Start with current balances
        for account, balance in current_balances.items():
            daily_balances[end_date][account] = balance

        # Work backwards through transactions
        for transaction in reversed(cash_transactions):
            tx_date = str(transaction.date)
            tx_account = transaction.account_name
            tx_amount = transaction.amount.to_milliunits() / 1000  # Convert to dollars at pandas boundary

            # Initialize this date with balances from future date if needed
            if tx_date not in daily_balances:
                future_dates = [d for d in daily_balances if d > tx_date]
                if future_dates:
                    next_date = min(future_dates)
                    for acc in current_balances:
                        daily_balances[tx_date][acc] = daily_balances[next_date][acc]

            # Subtract transaction amount (working backwards)
            daily_balances[tx_date][tx_account] -= tx_amount

        # Create complete time series
        all_dates = sorted(daily_balances.keys())
        date_range = pd.date_range(start=all_dates[0], end=all_dates[-1], freq="D")

        complete_balances = {}
        last_balances: dict[str, float] = dict.fromkeys(current_balances, 0.0)

        for date_str in date_range.strftime("%Y-%m-%d"):
            if date_str in daily_balances:
                for acct_name in current_balances:
                    if acct_name in daily_balances[date_str]:
                        last_balances[acct_name] = float(daily_balances[date_str][acct_name])
            complete_balances[date_str] = last_balances.copy()

        # Convert to DataFrame
        df_data = []
        for date_key, acct_balances in sorted(complete_balances.items()):
            total = sum(acct_balances.values())
            df_data.append({"Date": pd.to_datetime(date_key), "Total": total, **acct_balances})

        self.df = pd.DataFrame(df_data)
        self.df.set_index("Date", inplace=True)

        # Calculate derived metrics
        self._calculate_moving_averages()
        self._calculate_monthly_aggregates()
        self._calculate_trend_statistics()

    def _calculate_moving_averages(self) -> None:
        """Calculate multiple moving averages for trend smoothing."""
        if self.df is None:
            raise RuntimeError("Data not loaded. Call load_data() first.")

        self.df["MA_7"] = self.df["Total"].rolling(window=self.config.short_ma_window, min_periods=1).mean()
        self.df["MA_30"] = self.df["Total"].rolling(window=self.config.medium_ma_window, min_periods=1).mean()
        self.df["MA_90"] = self.df["Total"].rolling(window=self.config.long_ma_window, min_periods=1).mean()

        # Calculate daily changes
        self.df["Daily_Change"] = self.df["Total"].diff()

    def _calculate_monthly_aggregates(self) -> None:
        """Calculate monthly summary statistics."""
        if self.df is None:
            raise RuntimeError("Data not loaded. Call load_data() first.")

        self.monthly_df = self.df.resample("ME").agg(
            {"Total": ["mean", "min", "max", "last"], "Daily_Change": "sum"}
        )
        self.monthly_df.columns = ["Mean_Balance", "Min_Balance", "Max_Balance", "End_Balance", "Net_Change"]

    def _calculate_trend_for_window(self, df_window: pd.DataFrame) -> WindowStats | None:
        """Run a linear regression on a date-sliced view of the balance series."""
        if len(df_window) < 2:
            return None

        x = np.arange(len(df_window))
        y = df_window["Total"].values
        if np.all(y == y[0]):
            # Constant series: slope is 0, r_value is undefined and scipy would warn.
            slope, intercept, r_value, p_value, std_err = 0.0, float(y[0]), 0.0, 1.0, 0.0
        else:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            if np.isnan(r_value):
                # Belt-and-suspenders: a degenerate non-constant case that still produced NaN.
                r_value = 0.0

        direction: Literal["positive", "negative", "flat"]
        if slope > 0:
            direction = "positive"
        elif slope < 0:
            direction = "negative"
        else:
            direction = "flat"

        result: WindowStats = {
            "slope": slope,
            "intercept": intercept,
            "r_value": r_value,
            "p_value": p_value,
            "std_err": std_err,
            # Average Gregorian month/year (365.25 days/yr ÷ 12 = 30.4375 days/mo).
            "monthly_trend": slope * 30.4375,
            "yearly_trend": slope * 365.25,
            "direction": direction,
            # R² (coefficient of determination): fraction of variance explained.
            "fit_quality": r_value**2,
            "trend_line": slope * x + intercept,
            "window_index": df_window.index,
            "window_start": df_window.index[0],
            "window_end": df_window.index[-1],
            "n_days": len(df_window),
        }
        return result

    def _calculate_trend_statistics(self) -> None:
        """Calculate three windowed trend regressions: overall, last 13 months, last 6 months.

        Sub-windows are skipped (None) when their cutoff predates the dataset, since
        the resulting slice would equal the overall window and would be a duplicate.
        """
        if self.df is None:
            raise RuntimeError("Data not loaded. Call load_data() first.")

        df = self.df
        end = df.index.max()
        earliest = df.index.min()

        def windowed(months: int) -> WindowStats | None:
            cutoff = end - pd.DateOffset(months=months)
            if cutoff <= earliest:
                return None
            return self._calculate_trend_for_window(df[df.index >= cutoff])

        self.trend_stats = {
            "overall": self._calculate_trend_for_window(df),
            "thirteen_months": windowed(13),
            "six_months": windowed(6),
        }

    def generate_dashboard(self, output_dir: Path | None = None) -> Path:
        """
        Generate comprehensive 6-panel cash flow dashboard.

        Returns:
            Path to generated dashboard image.
        """
        if self.df is None or self.monthly_df is None or self.trend_stats is None:
            raise RuntimeError("Data not loaded or processed. Call load_data() first.")

        if output_dir is None:
            config = get_config()
            output_dir = config.data_dir / "cash_flow" / "charts"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Create figure with 6 panels
        plt.figure(figsize=self.config.figure_size)

        # Panel 1: Main plot with moving averages
        self._create_main_trend_panel(plt.subplot(3, 2, 1))

        # Panel 2: Monthly net cash flow bar chart
        self._create_monthly_flow_panel(plt.subplot(3, 2, 2))

        # Panel 3: Monthly volatility range
        self._create_volatility_panel(plt.subplot(3, 2, 3))

        # Panel 4: Cash flow velocity
        self._create_velocity_panel(plt.subplot(3, 2, 4))

        # Panel 5: Account composition
        self._create_composition_panel(plt.subplot(3, 2, 5))

        # Panel 6: Statistical summary
        self._create_statistics_panel(plt.subplot(3, 2, 6))

        plt.suptitle("Comprehensive Cash Flow Analysis Dashboard", fontsize=14, fontweight="bold", y=0.98)
        plt.tight_layout()

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = output_dir / f"{timestamp}_cash_flow_dashboard.{self.config.output_format}"

        plt.savefig(output_file, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        return output_file

    def _create_main_trend_panel(self, ax: Any) -> None:
        """Create main trend panel with moving averages and three windowed trend lines."""
        if self.df is None:
            raise RuntimeError("df must not be None")
        if self.trend_stats is None:
            raise RuntimeError("trend_stats must not be None")
        ax.plot(
            self.df.index, self.df["Total"], alpha=0.3, color="gray", linewidth=0.5, label="Daily Balance"
        )
        ax.plot(self.df.index, self.df["MA_7"], color="#2E86AB", linewidth=1.5, label="7-Day MA")
        ax.plot(self.df.index, self.df["MA_30"], color="#A23B72", linewidth=2, label="30-Day MA")
        ax.plot(self.df.index, self.df["MA_90"], color="#F18F01", linewidth=2.5, label="90-Day MA")

        trend_lines: list[tuple[WindowStats | None, str, float, str]] = [
            (self.trend_stats["overall"], "red", 0.6, "Overall trend"),
            (self.trend_stats["thirteen_months"], "darkorange", 0.85, "13-mo trend"),
            (self.trend_stats["six_months"], "purple", 0.95, "6-mo trend"),
        ]
        for window, color, alpha, label in trend_lines:
            if window is None:
                continue
            ax.plot(
                window["window_index"],
                window["trend_line"],
                color=color,
                linestyle="--",
                alpha=alpha,
                linewidth=1.2,
                label=label,
            )

        ax.set_title("Cash Flow with Moving Averages", fontsize=12, fontweight="bold")
        ax.set_ylabel("Balance ($)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x/1000:.0f}k"))

    def _create_monthly_flow_panel(self, ax: Any) -> None:
        """Create monthly cash flow bar chart."""
        if self.monthly_df is None:
            raise RuntimeError("monthly_df must not be None")
        monthly_burn_rate = self.monthly_df["Net_Change"].mean()
        colors = ["green" if x > 0 else "red" for x in self.monthly_df["Net_Change"]]

        ax.bar(self.monthly_df.index, self.monthly_df["Net_Change"], color=colors, alpha=0.7)
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.axhline(
            y=monthly_burn_rate,
            color="blue",
            linestyle="--",
            alpha=0.7,
            label=f"Avg: ${monthly_burn_rate:,.0f}/mo",
        )

        ax.set_title("Monthly Net Cash Flow", fontsize=12, fontweight="bold")
        ax.set_ylabel("Net Change ($)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x/1000:.0f}k"))

    def _create_volatility_panel(self, ax: Any) -> None:
        """Create monthly volatility range panel."""
        if self.monthly_df is None:
            raise RuntimeError("monthly_df must not be None")
        ax.fill_between(
            self.monthly_df.index,
            self.monthly_df["Min_Balance"],
            self.monthly_df["Max_Balance"],
            alpha=0.3,
            color="#2E86AB",
            label="Monthly Range",
        )
        ax.plot(
            self.monthly_df.index,
            self.monthly_df["Mean_Balance"],
            color="#2E86AB",
            linewidth=2,
            label="Monthly Average",
        )
        ax.plot(
            self.monthly_df.index,
            self.monthly_df["End_Balance"],
            color="#A23B72",
            linewidth=1,
            linestyle="--",
            label="Month-End Balance",
        )

        ax.set_title("Monthly Balance Range (Volatility)", fontsize=12, fontweight="bold")
        ax.set_ylabel("Balance ($)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x/1000:.0f}k"))

    def _create_velocity_panel(self, ax: Any) -> None:
        """Create cash flow velocity panel."""
        if self.df is None:
            raise RuntimeError("df must not be None")
        rolling_change = self.df["Total"].diff().rolling(window=30, min_periods=1).sum()

        ax.plot(self.df.index, rolling_change, color="#6A994E", linewidth=1.5)
        ax.fill_between(
            self.df.index,
            0,
            rolling_change,
            where=(rolling_change >= 0),
            color="green",
            alpha=0.3,
            label="Positive Flow",
        )
        ax.fill_between(
            self.df.index,
            0,
            rolling_change,
            where=(rolling_change < 0),
            color="red",
            alpha=0.3,
            label="Negative Flow",
        )
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)

        ax.set_title("30-Day Rolling Cash Flow Velocity", fontsize=12, fontweight="bold")
        ax.set_ylabel("30-Day Change ($)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x/1000:.0f}k"))

    def _create_composition_panel(self, ax: Any) -> None:
        """Create account composition panel."""
        if self.df is None:
            raise RuntimeError("df must not be None")
        # Separate positive and negative accounts
        positive_accounts = []
        negative_accounts = []

        for acc in self.config.cash_accounts:
            if acc in self.df.columns:
                if self.df[acc].mean() >= 0:
                    positive_accounts.append(acc)
                else:
                    negative_accounts.append(acc)

        # Plot positive accounts stacked
        if positive_accounts:
            ax.stackplot(
                self.df.index,
                *[self.df[acc] if acc in self.df.columns else 0 for acc in positive_accounts],
                labels=positive_accounts,
                alpha=0.7,
            )

        # Plot negative accounts separately
        for acc in negative_accounts:
            if acc in self.df.columns:
                ax.plot(self.df.index, self.df[acc], linewidth=1.5, label=acc)

        ax.axhline(y=0, color="red", linestyle="--", alpha=0.5)
        ax.set_title("Account Composition Over Time", fontsize=12, fontweight="bold")
        ax.set_ylabel("Balance ($)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x/1000:.0f}k"))

    def _format_trend_section(self) -> str:
        """Format the TREND ANALYSIS block of the statistics panel for three windows."""
        if self.trend_stats is None:
            raise RuntimeError("trend_stats must not be None")

        windows: list[tuple[WindowStats | None, str]] = [
            (self.trend_stats["overall"], "Overall"),
            (self.trend_stats["thirteen_months"], "Last 13 months"),
            (self.trend_stats["six_months"], "Last 6 months"),
        ]

        lines = ["TREND ANALYSIS:"]
        for window, label in windows:
            if window is None:
                lines.append(f"{label}:")
                lines.append("  • Insufficient data")
                continue
            start_str = window["window_start"].strftime("%Y-%m-%d")
            end_str = window["window_end"].strftime("%Y-%m-%d")
            if window["direction"] == "positive":
                arrow = "↗ Growing"
            elif window["direction"] == "negative":
                arrow = "↘ Declining"
            else:
                arrow = "→ Flat"
            fit_quality_pct = window["fit_quality"] * 100
            lines.append(f"{label} ({start_str} to {end_str}, {window['n_days']} days):")
            lines.append(
                f"  • Monthly: ${window['monthly_trend']:,.0f}/mo  {arrow}  "
                f"(fit quality: {fit_quality_pct:.1f}%)"
            )
            lines.append(f"  • Yearly:  ${window['yearly_trend']:,.0f}/yr")
        return "\n".join(lines)

    def _create_statistics_panel(self, ax: Any) -> None:
        """Create statistical summary panel."""
        if self.df is None:
            raise RuntimeError("df must not be None")
        if self.monthly_df is None:
            raise RuntimeError("monthly_df must not be None")
        if self.trend_stats is None:
            raise RuntimeError("trend_stats must not be None")
        ax.axis("off")

        # Calculate statistics
        current_total = self.df["Total"].iloc[-1]
        avg_balance = self.df["Total"].mean()
        std_balance = self.df["Total"].std()
        min_balance = self.df["Total"].min()
        max_balance = self.df["Total"].max()
        days_positive: int = int((self.df["Daily_Change"] > 0).sum())
        days_negative: int = int((self.df["Daily_Change"] < 0).sum())
        avg_daily_change = self.df["Daily_Change"].mean()
        monthly_burn_rate = self.monthly_df["Net_Change"].mean()

        min_date = pd.to_datetime(self.df["Total"].idxmin()).strftime("%Y-%m-%d")
        max_date = pd.to_datetime(self.df["Total"].idxmax()).strftime("%Y-%m-%d")

        trend_section = self._format_trend_section()

        stats_text = f"""
FINANCIAL HEALTH METRICS (Since {self.config.start_date})
{'='*40}

CURRENT STATUS:
• Current Balance: ${current_total:,.0f}
• 30-Day Average: ${self.df['Total'].tail(30).mean():,.0f}
• 90-Day Average: ${self.df['Total'].tail(90).mean():,.0f}

HISTORICAL ANALYSIS:
• Average Balance: ${avg_balance:,.0f}
• Standard Deviation: ${std_balance:,.0f}
• Minimum: ${min_balance:,.0f} ({min_date})
• Maximum: ${max_balance:,.0f} ({max_date})

CASH FLOW PATTERNS:
• Days with Positive Flow: {days_positive} ({days_positive/len(self.df)*100:.1f}%)
• Days with Negative Flow: {days_negative} ({days_negative/len(self.df)*100:.1f}%)
• Average Daily Change: ${avg_daily_change:,.0f}
• Monthly Burn Rate: ${monthly_burn_rate:,.0f}

{trend_section}

VOLATILITY METRICS:
• Coefficient of Variation: {(std_balance/avg_balance)*100:.1f}%
• Monthly Volatility: ${self.monthly_df['Max_Balance'].mean() - self.monthly_df['Min_Balance'].mean():,.0f}
"""

        ax.text(
            0.05,
            0.95,
            stats_text,
            transform=ax.transAxes,
            fontsize=9,
            fontfamily="monospace",
            verticalalignment="top",
            bbox={"boxstyle": "round,pad=1", "facecolor": "lightgray", "alpha": 0.8},
        )

    def get_summary_statistics(self) -> dict:
        """Get summary statistics for programmatic use."""
        if self.df is None or self.trend_stats is None:
            raise RuntimeError("Data not loaded or processed. Call load_data() first.")
        if self.monthly_df is None:
            raise RuntimeError("monthly_df must not be None")

        current_total = self.df["Total"].iloc[-1]
        monthly_burn_rate = self.monthly_df["Net_Change"].mean()

        def _window_summary(window: WindowStats | None) -> dict | None:
            if window is None:
                return None
            return {
                "monthly_trend": window["monthly_trend"],
                "yearly_trend": window["yearly_trend"],
                "direction": window["direction"],
                "fit_quality": window["fit_quality"],
                "window_start": window["window_start"].strftime("%Y-%m-%d"),
                "window_end": window["window_end"].strftime("%Y-%m-%d"),
                "n_days": window["n_days"],
            }

        return {
            "current_balance": current_total,
            "monthly_burn_rate": monthly_burn_rate,
            "trends": {
                "overall": _window_summary(self.trend_stats["overall"]),
                "thirteen_months": _window_summary(self.trend_stats["thirteen_months"]),
                "six_months": _window_summary(self.trend_stats["six_months"]),
            },
            "volatility": self.df["Total"].std(),
            "data_start_date": self.config.start_date,
            "analysis_date": datetime.now().isoformat(),
        }
