#!/usr/bin/env python3
"""
Enhanced cash flow analysis with smoothing and trend analysis.
Common techniques for personal finance visualization.
"""

import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime
from collections import defaultdict
from scipy import stats

# Load data
with open('ynab-data/accounts.json', 'r') as f:
    accounts_data = json.load(f)

with open('ynab-data/transactions.json', 'r') as f:
    transactions = json.load(f)

# Define cash/liquid accounts
cash_accounts = [
    'Chase Checking',
    'Chase Credit Card', 
    'Apple Card',
    'Apple Cash',
    'Apple Savings'
]

# Get current balances
current_balances = {}
for account in accounts_data['accounts']:
    if account['name'] in cash_accounts:
        current_balances[account['name']] = account['balance'] / 1000

# Filter and sort transactions (exclude unreliable data before May 2024)
START_DATE = '2024-05-01'
cash_transactions = [t for t in transactions 
                    if t.get('account_name') in cash_accounts 
                    and t['date'] >= START_DATE]
cash_transactions.sort(key=lambda x: x['date'])

# Calculate daily balances
daily_balances = defaultdict(lambda: defaultdict(float))
end_date = max(t['date'] for t in cash_transactions)

for account, balance in current_balances.items():
    daily_balances[end_date][account] = balance

for transaction in reversed(cash_transactions):
    date = transaction['date']
    account = transaction['account_name']
    amount = transaction['amount'] / 1000
    
    if date not in daily_balances:
        future_dates = [d for d in daily_balances.keys() if d > date]
        if future_dates:
            next_date = min(future_dates)
            for acc in cash_accounts:
                daily_balances[date][acc] = daily_balances[next_date][acc]
    
    daily_balances[date][account] -= amount

# Create complete time series
all_dates = sorted(daily_balances.keys())
date_range = pd.date_range(start=all_dates[0], end=all_dates[-1], freq='D')

complete_balances = {}
last_balances = {acc: 0 for acc in cash_accounts}

for date_str in date_range.strftime('%Y-%m-%d'):
    if date_str in daily_balances:
        for account in cash_accounts:
            if account in daily_balances[date_str]:
                last_balances[account] = daily_balances[date_str][account]
    complete_balances[date_str] = last_balances.copy()

# Convert to DataFrame
df_data = []
for date, accounts in sorted(complete_balances.items()):
    total = sum(accounts.values())
    df_data.append({
        'Date': pd.to_datetime(date),
        'Total': total,
        **accounts
    })

df = pd.DataFrame(df_data)
df.set_index('Date', inplace=True)

# Calculate moving averages
df['MA_7'] = df['Total'].rolling(window=7, min_periods=1).mean()
df['MA_30'] = df['Total'].rolling(window=30, min_periods=1).mean()
df['MA_90'] = df['Total'].rolling(window=90, min_periods=1).mean()

# Calculate daily changes
df['Daily_Change'] = df['Total'].diff()

# Calculate monthly aggregates
monthly_df = df.resample('ME').agg({
    'Total': ['mean', 'min', 'max', 'last'],
    'Daily_Change': 'sum'
})
monthly_df.columns = ['Mean_Balance', 'Min_Balance', 'Max_Balance', 'End_Balance', 'Net_Change']

# Calculate trend line
x = np.arange(len(df))
y = df['Total'].values
slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
trend_line = slope * x + intercept

# Monthly burn rate (negative = spending more than earning)
monthly_burn_rate = monthly_df['Net_Change'].mean()

# Create comprehensive dashboard
fig = plt.figure(figsize=(16, 12))

# 1. Main plot with moving averages
ax1 = plt.subplot(3, 2, 1)
ax1.plot(df.index, df['Total'], alpha=0.3, color='gray', linewidth=0.5, label='Daily Balance')
ax1.plot(df.index, df['MA_7'], color='#2E86AB', linewidth=1.5, label='7-Day MA')
ax1.plot(df.index, df['MA_30'], color='#A23B72', linewidth=2, label='30-Day MA')
ax1.plot(df.index, df['MA_90'], color='#F18F01', linewidth=2.5, label='90-Day MA')
ax1.plot(df.index, trend_line, 'r--', alpha=0.7, linewidth=1, label='Trend Line')
ax1.set_title('Cash Flow with Moving Averages', fontsize=12, fontweight='bold')
ax1.set_ylabel('Balance ($)', fontsize=10)
ax1.legend(loc='best', fontsize=8)
ax1.grid(True, alpha=0.3)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# 2. Monthly net cash flow (bar chart)
ax2 = plt.subplot(3, 2, 2)
colors = ['green' if x > 0 else 'red' for x in monthly_df['Net_Change']]
bars = ax2.bar(monthly_df.index, monthly_df['Net_Change'], color=colors, alpha=0.7)
ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax2.set_title('Monthly Net Cash Flow', fontsize=12, fontweight='bold')
ax2.set_ylabel('Net Change ($)', fontsize=10)
ax2.grid(True, alpha=0.3, axis='y')
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# Add average line
ax2.axhline(y=monthly_burn_rate, color='blue', linestyle='--', alpha=0.7, 
            label=f'Avg: ${monthly_burn_rate:,.0f}/mo')
ax2.legend(loc='best', fontsize=8)

# 3. Monthly range plot (shows volatility)
ax3 = plt.subplot(3, 2, 3)
ax3.fill_between(monthly_df.index, monthly_df['Min_Balance'], monthly_df['Max_Balance'], 
                 alpha=0.3, color='#2E86AB', label='Monthly Range')
ax3.plot(monthly_df.index, monthly_df['Mean_Balance'], color='#2E86AB', 
         linewidth=2, label='Monthly Average')
ax3.plot(monthly_df.index, monthly_df['End_Balance'], color='#A23B72', 
         linewidth=1, linestyle='--', label='Month-End Balance')
ax3.set_title('Monthly Balance Range (Volatility)', fontsize=12, fontweight='bold')
ax3.set_ylabel('Balance ($)', fontsize=10)
ax3.legend(loc='best', fontsize=8)
ax3.grid(True, alpha=0.3)
ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# 4. Cash flow velocity (rolling 30-day change)
ax4 = plt.subplot(3, 2, 4)
rolling_change = df['Total'].diff().rolling(window=30, min_periods=1).sum()
ax4.plot(df.index, rolling_change, color='#6A994E', linewidth=1.5)
ax4.fill_between(df.index, 0, rolling_change, 
                 where=(rolling_change >= 0), color='green', alpha=0.3, label='Positive Flow')
ax4.fill_between(df.index, 0, rolling_change, 
                 where=(rolling_change < 0), color='red', alpha=0.3, label='Negative Flow')
ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax4.set_title('30-Day Rolling Cash Flow Velocity', fontsize=12, fontweight='bold')
ax4.set_ylabel('30-Day Change ($)', fontsize=10)
ax4.legend(loc='best', fontsize=8)
ax4.grid(True, alpha=0.3)
ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# 5. Account composition over time (stacked area)
ax5 = plt.subplot(3, 2, 5)
# Separate positive and negative accounts
positive_accounts = []
negative_accounts = []
for acc in cash_accounts:
    if acc in df.columns:
        if df[acc].mean() >= 0:
            positive_accounts.append(acc)
        else:
            negative_accounts.append(acc)

# Plot positive accounts stacked
if positive_accounts:
    ax5.stackplot(df.index, 
                  *[df[acc] if acc in df.columns else 0 for acc in positive_accounts],
                  labels=positive_accounts, alpha=0.7)

# Plot negative accounts separately
for acc in negative_accounts:
    if acc in df.columns:
        ax5.plot(df.index, df[acc], linewidth=1.5, label=acc)

ax5.axhline(y=0, color='red', linestyle='--', alpha=0.5)
ax5.set_title('Account Composition Over Time', fontsize=12, fontweight='bold')
ax5.set_ylabel('Balance ($)', fontsize=10)
ax5.legend(loc='best', fontsize=8)
ax5.grid(True, alpha=0.3)
ax5.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# 6. Statistical summary box
ax6 = plt.subplot(3, 2, 6)
ax6.axis('off')

# Calculate statistics
current_total = df['Total'].iloc[-1]
avg_balance = df['Total'].mean()
std_balance = df['Total'].std()
min_balance = df['Total'].min()
max_balance = df['Total'].max()
days_positive = (df['Daily_Change'] > 0).sum()
days_negative = (df['Daily_Change'] < 0).sum()
avg_daily_change = df['Daily_Change'].mean()

# Calculate trend
days_elapsed = len(df)
daily_trend = slope
monthly_trend = slope * 30
yearly_trend = slope * 365

stats_text = f"""
📊 FINANCIAL HEALTH METRICS (Since May 2024)
{'='*40}

CURRENT STATUS:
• Current Balance: ${current_total:,.0f}
• 30-Day Average: ${df['Total'].tail(30).mean():,.0f}
• 90-Day Average: ${df['Total'].tail(90).mean():,.0f}

HISTORICAL ANALYSIS:
• Average Balance: ${avg_balance:,.0f}
• Standard Deviation: ${std_balance:,.0f}
• Minimum: ${min_balance:,.0f} ({df['Total'].idxmin().strftime('%Y-%m-%d')})
• Maximum: ${max_balance:,.0f} ({df['Total'].idxmax().strftime('%Y-%m-%d')})

CASH FLOW PATTERNS:
• Days with Positive Flow: {days_positive} ({days_positive/len(df)*100:.1f}%)
• Days with Negative Flow: {days_negative} ({days_negative/len(df)*100:.1f}%)
• Average Daily Change: ${avg_daily_change:,.0f}
• Monthly Burn Rate: ${monthly_burn_rate:,.0f}

TREND ANALYSIS:
• Daily Trend: ${daily_trend:,.2f}/day
• Monthly Projection: ${monthly_trend:,.0f}/month
• Yearly Projection: ${yearly_trend:,.0f}/year
• Trend Direction: {'📈 Growing' if slope > 0 else '📉 Declining'}
• Trend Confidence: {abs(r_value)*100:.1f}%

VOLATILITY METRICS:
• Coefficient of Variation: {(std_balance/avg_balance)*100:.1f}%
• Monthly Volatility: ${monthly_df['Max_Balance'].mean() - monthly_df['Min_Balance'].mean():,.0f}
"""

ax6.text(0.05, 0.95, stats_text, transform=ax6.transAxes, fontsize=9,
         fontfamily='monospace', verticalalignment='top',
         bbox=dict(boxstyle='round,pad=1', facecolor='lightgray', alpha=0.8))

plt.suptitle('Comprehensive Cash Flow Analysis Dashboard', fontsize=14, fontweight='bold', y=0.98)
plt.tight_layout()

# Create analysis directory if it doesn't exist
os.makedirs('results', exist_ok=True)

# Generate timestamped filename
timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
output_filename = f'results/{timestamp}_cash_flow_analysis.png'

plt.savefig(output_filename, dpi=150, bbox_inches='tight')
# plt.show()  # Comment out for non-interactive mode

print(f"Analysis complete! Dashboard saved as '{output_filename}'")
print(f"\nKey Insights:")
print(f"• Current trend: ${monthly_trend:,.0f}/month")
print(f"• Your cash flow is {'POSITIVE' if monthly_burn_rate > 0 else 'NEGATIVE'} on average")
print(f"• 30-day moving average smooths daily noise and shows clearer trends")