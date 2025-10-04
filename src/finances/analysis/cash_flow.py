#!/usr/bin/env python3
"""
Cash Flow Analysis Module

Professional cash flow analysis with trend detection, statistical modeling,
and comprehensive dashboard generation.
"""

import json

import matplotlib
import pandas as pd

matplotlib.use("Agg")  # Use non-interactive backend
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from ..core.config import get_config


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

    def __init__(self, config: Optional[CashFlowConfig] = None):
        """Initialize analyzer with configuration."""
        self.config = config or CashFlowConfig.default()
        self.df: Optional[pd.DataFrame] = None
        self.monthly_df: Optional[pd.DataFrame] = None
        self.trend_stats: Optional[dict] = None

    def load_data(self, ynab_cache_dir: Optional[Path] = None) -> None:
        """Load YNAB data from cache directory."""
        if ynab_cache_dir is None:
            config = get_config()
            ynab_cache_dir = config.data_dir / "ynab" / "cache"

        # Load account and transaction data
        accounts_file = ynab_cache_dir / "accounts.json"
        transactions_file = ynab_cache_dir / "transactions.json"

        if not accounts_file.exists() or not transactions_file.exists():
            raise FileNotFoundError(
                f"YNAB data not found in {ynab_cache_dir}. " "Run 'finances ynab sync-cache' first."
            )

        with open(accounts_file) as f:
            accounts_data = json.load(f)

        with open(transactions_file) as f:
            transactions = json.load(f)

        # Get current balances (convert from milliunits to dollars)
        current_balances = {}
        for account in accounts_data["accounts"]:
            if account["name"] in self.config.cash_accounts:
                current_balances[account["name"]] = account["balance"] / 1000

        # Filter and sort transactions
        cash_transactions = [
            t
            for t in transactions
            if t.get("account_name") in self.config.cash_accounts and t["date"] >= self.config.start_date
        ]
        cash_transactions.sort(key=lambda x: x["date"])

        if not cash_transactions:
            raise ValueError(f"No transactions found for cash accounts after {self.config.start_date}")

        # Calculate daily balances by working backwards from current balances
        daily_balances = defaultdict(lambda: defaultdict(float))
        end_date = max(t["date"] for t in cash_transactions)

        # Start with current balances
        for account, balance in current_balances.items():
            daily_balances[end_date][account] = balance

        # Work backwards through transactions
        for transaction in reversed(cash_transactions):
            date = transaction["date"]
            account = transaction["account_name"]
            amount = transaction["amount"] / 1000  # Convert to dollars

            # Initialize this date with balances from future date if needed
            if date not in daily_balances:
                future_dates = [d for d in daily_balances if d > date]
                if future_dates:
                    next_date = min(future_dates)
                    for acc in self.config.cash_accounts:
                        daily_balances[date][acc] = daily_balances[next_date][acc]

            # Subtract transaction amount (working backwards)
            daily_balances[date][account] -= amount

        # Create complete time series
        all_dates = sorted(daily_balances.keys())
        date_range = pd.date_range(start=all_dates[0], end=all_dates[-1], freq="D")

        complete_balances = {}
        last_balances = dict.fromkeys(self.config.cash_accounts, 0)

        for date_str in date_range.strftime("%Y-%m-%d"):
            if date_str in daily_balances:
                for account in self.config.cash_accounts:
                    if account in daily_balances[date_str]:
                        last_balances[account] = daily_balances[date_str][account]
            complete_balances[date_str] = last_balances.copy()

        # Convert to DataFrame
        df_data = []
        for date, accounts in sorted(complete_balances.items()):
            total = sum(accounts.values())
            df_data.append({"Date": pd.to_datetime(date), "Total": total, **accounts})

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

    def _calculate_trend_statistics(self) -> None:
        """Calculate trend line and statistical measures."""
        if self.df is None:
            raise RuntimeError("Data not loaded. Call load_data() first.")

        x = np.arange(len(self.df))
        y = self.df["Total"].values

        # Check if we have enough data points for statistical analysis
        if len(x) < 2:
            # Not enough data for regression - use default values
            slope = intercept = r_value = p_value = std_err = 0.0
        else:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        self.trend_stats = {
            "slope": slope,
            "intercept": intercept,
            "r_value": r_value,
            "p_value": p_value,
            "std_err": std_err,
            "trend_line": slope * x + intercept,
            "daily_trend": slope,
            "monthly_trend": slope * 30,
            "yearly_trend": slope * 365,
        }

    def generate_dashboard(self, output_dir: Optional[Path] = None) -> Path:
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

    def _create_main_trend_panel(self, ax) -> None:
        """Create main trend panel with moving averages."""
        ax.plot(
            self.df.index, self.df["Total"], alpha=0.3, color="gray", linewidth=0.5, label="Daily Balance"
        )
        ax.plot(self.df.index, self.df["MA_7"], color="#2E86AB", linewidth=1.5, label="7-Day MA")
        ax.plot(self.df.index, self.df["MA_30"], color="#A23B72", linewidth=2, label="30-Day MA")
        ax.plot(self.df.index, self.df["MA_90"], color="#F18F01", linewidth=2.5, label="90-Day MA")
        ax.plot(
            self.df.index, self.trend_stats["trend_line"], "r--", alpha=0.7, linewidth=1, label="Trend Line"
        )

        ax.set_title("Cash Flow with Moving Averages", fontsize=12, fontweight="bold")
        ax.set_ylabel("Balance ($)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x/1000:.0f}k"))

    def _create_monthly_flow_panel(self, ax) -> None:
        """Create monthly cash flow bar chart."""
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

    def _create_volatility_panel(self, ax) -> None:
        """Create monthly volatility range panel."""
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

    def _create_velocity_panel(self, ax) -> None:
        """Create cash flow velocity panel."""
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

    def _create_composition_panel(self, ax) -> None:
        """Create account composition panel."""
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

    def _create_statistics_panel(self, ax) -> None:
        """Create statistical summary panel."""
        ax.axis("off")

        # Calculate statistics
        current_total = self.df["Total"].iloc[-1]
        avg_balance = self.df["Total"].mean()
        std_balance = self.df["Total"].std()
        min_balance = self.df["Total"].min()
        max_balance = self.df["Total"].max()
        days_positive = (self.df["Daily_Change"] > 0).sum()
        days_negative = (self.df["Daily_Change"] < 0).sum()
        avg_daily_change = self.df["Daily_Change"].mean()
        monthly_burn_rate = self.monthly_df["Net_Change"].mean()

        # Trend statistics
        slope = self.trend_stats["slope"]
        r_value = self.trend_stats["r_value"]
        monthly_trend = self.trend_stats["monthly_trend"]
        yearly_trend = self.trend_stats["yearly_trend"]

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
• Minimum: ${min_balance:,.0f} ({self.df['Total'].idxmin().strftime('%Y-%m-%d')})
• Maximum: ${max_balance:,.0f} ({self.df['Total'].idxmax().strftime('%Y-%m-%d')})

CASH FLOW PATTERNS:
• Days with Positive Flow: {days_positive} ({days_positive/len(self.df)*100:.1f}%)
• Days with Negative Flow: {days_negative} ({days_negative/len(self.df)*100:.1f}%)
• Average Daily Change: ${avg_daily_change:,.0f}
• Monthly Burn Rate: ${monthly_burn_rate:,.0f}

TREND ANALYSIS:
• Daily Trend: ${slope:,.2f}/day
• Monthly Projection: ${monthly_trend:,.0f}/month
• Yearly Projection: ${yearly_trend:,.0f}/year
• Trend Direction: {'↗ Growing' if slope > 0 else '↘ Declining'}
• Trend Confidence: {abs(r_value)*100:.1f}%

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

        current_total = self.df["Total"].iloc[-1]
        monthly_burn_rate = self.monthly_df["Net_Change"].mean()

        return {
            "current_balance": current_total,
            "monthly_trend": self.trend_stats["monthly_trend"],
            "yearly_trend": self.trend_stats["yearly_trend"],
            "monthly_burn_rate": monthly_burn_rate,
            "trend_direction": "positive" if self.trend_stats["slope"] > 0 else "negative",
            "trend_confidence": abs(self.trend_stats["r_value"]),
            "volatility": self.df["Total"].std(),
            "data_start_date": self.config.start_date,
            "analysis_date": datetime.now().isoformat(),
        }
