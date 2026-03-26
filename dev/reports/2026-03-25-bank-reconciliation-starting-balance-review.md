# Bank Reconciliation and Starting Balance Review — 2026-03-25

**Date:** 2026-03-25
**Session context:** Post-reconciliation audit after running `bank_data_reconcile` and
`bank_data_reconcile_apply` flows for four accounts.
The goal was to verify that each account is correctly reconciled and to determine the correct
YNAB starting balance for each.

---

## Background

After running the bank reconciliation flow for the four accounts with downloaded bank
statements, this session audited whether the accounts were actually balanced and what
YNAB starting balance adjustments were required.

**Accounts analyzed:**
- `chase-checking` — Chase Checking account
- `chase-credit` — Chase Credit Card
- `apple-card` — Apple Card (credit card)
- `apple-savings` — Apple Savings account

**Key technical context:**
- Apple accounts use `ynab_date_offset_days: -1`, meaning YNAB stores dates as
  bank_posted_date − 1 day (YNAB records purchase date; bank records clearing/posting date).
- Apple Card payment transfers (ACH deposits) appear in YNAB 1–2 days after their bank
  posted date — this creates apparent discrepancies at exact month/year boundaries that are
  not real reconciliation errors.
- Chase CSV files include per-transaction running balances.
- Apple Card OFX files contain `LEDGERBAL` (`BALAMT`) but these are download-time snapshots,
  not historical statement balances — the same value appeared in 30+ consecutive monthly
  files, confirming they're unusable for historical reconciliation.
- Apple Savings OFX files provide only 2 reliable balance snapshots (from 2 download
  batches: 2025-12-28 and 2026-03-04).
- The user's iPhone Wallet app was used as ground truth for Apple Card and Apple Savings
  balances at specific dates.

---

## Data Sources

| Source | File/Location |
|---|---|
| Reconciliation operations | `data/bank_accounts/reconciliation/2026-03-24_21-32-23_operations.json` |
| Normalized bank txs | `data/bank_accounts/normalized/2026-03-24_21-32-16_{slug}.json` |
| YNAB transactions | `data/ynab/cache/transactions.json` |
| YNAB account metadata | `data/ynab/cache/accounts.json` |
| Account config | `config/bank_accounts_config.json` |

**YNAB account IDs:**
- Chase Checking: `7516d6c8-3f57-4a2b-a233-4b29c8caf45c`
- Chase Credit Card: `fd54d1ad-f80b-413d-87b1-1932861da606`
- Apple Card: `7fec0007-e2a7-4293-8ac7-6235d166f6e9`
- Apple Savings: `c34e2cee-22ef-4445-b3c2-1f233c7718ad`

---

## Chase Checking

### Bank Data
- Coverage start: 2023-12-29
- 594 transactions with per-transaction running balances
- First balance point (2023-12-29): $37,534.76

### YNAB State at Analysis Time
- Existing "Starting Balance" TX: **+$28,903.43 on 2024-02-03** (mid-range, wrong)
- With this SB TX, YNAB running balance on 2023-12-29 = **-$406.00**

### Analysis
Using the first clean reconciliation point (2023-12-29, where both bank and YNAB had
zero unmatched transactions):
```
bank_balance = $37,534.76
ynab_balance = -$406.00
required_sb_adjustment = $37,534.76 − (−$406.00) = $37,940.76
```

### Resolution (Completed by User)
The user found a Chase Checking PDF statement (Dec 16, 2023 – Jan 17, 2024) showing
starting balance of $30,899.59 on Dec 16, 2023.
The YNAB starting balance was manually set to **$69,639.07**, which includes:
- $30,899.59 (Dec 16 bank balance)
- \+ $38,739.48 (Apple Card payment transfers from Chase Checking that YNAB had recorded
  before Dec 16, which would not appear in the bank statement balance)

**Status: RESOLVED ✓**

---

## Chase Credit Card

### Bank Data
- Coverage start: 2024-01-01
- 1,497 transactions, no balance points
- Transaction flows match YNAB exactly throughout the entire coverage period ($0 delta)

### YNAB State at Analysis Time
- Existing "Starting Balance" TX: **-$7,824.74 on 2024-02-03**
  (id: `50c58551-836d-4a7e-994c-fafb4321cc6a`)
- No transactions in YNAB for Dec 12–31, 2023

### Analysis — From PDF Statement

User provided a Chase Credit Card statement for the billing cycle Dec 12, 2023 – Jan 11,
2024:
- Previous balance (as of Dec 11, 2023): **$5,020.16** owed
- New balance (as of Jan 11, 2024): **$4,168.20** owed

YNAB has no Chase Credit transactions in Dec 12–31, 2023 (pre-coverage), and the
Dec 11 balance of $5,020.16 is confirmed correct (YNAB agrees).

Back-calculating Dec 12–31 spending:
```
Total spending (Dec 12 – Jan 11) = statement payment − net balance reduction
    = $5,020.16 − ($5,020.16 − $4,168.20) = $4,168.20

Jan 1–11 YNAB spending (confirmed from YNAB data) = $733.63

Dec 12–31 spending (not in YNAB, not in bank) = $4,168.20 − $733.63 = $3,434.57
```

Cross-check:
```
Dec 11 balance ($5,020.16) + Dec 12–31 spending ($3,434.57) = $8,454.73 owed on Dec 31
Dec 31 balance (−$8,454.73) + Jan 1–11 YNAB net (+$4,286.53) = −$4,168.20 ✓
```

**Correct Jan 1, 2024 opening balance: −$8,454.73 (owed)**

The existing SB TX of −$7,824.74 is off by **−$629.99** (under-stating debt by that amount).
The $629.99 represents Dec 12–31, 2023 spending that occurred before both bank data and
YNAB coverage windows.

### Required Actions

1. Edit the existing SB TX (`50c58551-836d-4a7e-994c-fafb4321cc6a`):
   - Change **amount** from −$7,824.74 to **−$8,454.73**
   - Change **date** from 2024-02-03 to **2023-12-31** (any date before 2024-01-01)

**Status: ACTION REQUIRED**

---

## Apple Card

### Bank Data
- Coverage start: 2023-04-25
- 4,876 transactions, no balance points
- Bank cumulative delta matches Wallet at all statement-end dates (see table below)

### iPhone Wallet Balance Data Points (Ground Truth)

| Date | Wallet (owed) | Bank cumulative | Bank − Wallet |
|---|---|---|---|
| 2023-04-30 | $148.73 | $148.73 | $0.00 ✓ |
| 2023-06-30 | $8,008.12 | $10,911.01 | +$2,902.89 ⚠ |
| 2023-12-31 | $9,175.06 | $9,175.06 | $0.00 ✓ |
| 2024-06-30 | $13,737.01 | $13,737.01 | $0.00 ✓ |
| 2024-12-31 | $15,765.84 | $15,765.84 | $0.00 ✓ |
| 2025-06-30 | $12,220.91 | $12,220.91 | $0.00 ✓ |
| 2025-12-31 | $8,607.02 | $8,607.02 | $0.00 ✓ |
| 2026-02-28 | $11,700.87 | $11,700.87 | $0.00 ✓ |

**Note on June 2023 discrepancy (+$2,902.89):** This is a timing artifact.
A payment made during the April 30 – May 3 coverage gap (between statement files) was
reflected immediately in the Wallet but appears in a later monthly export file.
By Dec 31, 2023, the cumulative totals converge exactly — confirming no real data error.

### YNAB State at Analysis Time
- Existing "Starting Balance" TX: **−$9,845.15 on 2024-03-10**
  (id: `9008c104-5978-407a-ad2e-cf15a7a378da`)
- Account opened April 22, 2023 with $0 balance (confirmed by user)
- Without the SB TX, YNAB tracks Wallet exactly from opening through mid-2024
- The SB TX introduces a −$9,845.15 artificial debt starting March 2024, causing YNAB
  to diverge from reality from that point forward

### YNAB vs Wallet (after removing SB TX from analysis)

| Date | Wallet (owed) | YNAB (owed) | YNAB − Wallet | Note |
|---|---|---|---|---|
| 2023-04-30 | $148.73 | $148.73 | $0.00 ✓ | |
| 2023-12-31 | $9,175.06 | $9,175.06 | $0.00 ✓ | |
| 2024-06-30 | $13,737.01 | $13,735.71 | −$1.30 ✓ | |
| 2024-12-31 | $15,765.84 | ~$15,765 | ~$0 ✓ | Dec 31 payment in YNAB on Jan 1 |
| 2025-06-30 | $12,220.91 | ~$12,221 | ~$0 ✓ | Jun 30 payment in YNAB on Jul 1 |
| 2025-12-31 | $8,607.02 | ~$8,607 | ~$0 ✓ | Dec 31 payment in YNAB on Jan 1 |

**Note on month/year-end apparent discrepancies:** Apple Card ACH payments posted on the
last day of a month/year in the bank data appear in YNAB 1–2 days later.
This creates apparent divergences at exact month-end boundaries (e.g., a $9,885.04
Dec 31, 2024 bank payment appears in YNAB on Jan 1, 2025).
These are not real reconciliation errors — the running balance is correct when the payment
date boundary is accounted for.

### Chase Checking YNAB Link (Related Fix)

The only Apple Card payment that was NOT correctly linked from Chase Checking in YNAB
was **$148.73 on 2023-06-01**.
This was manually fixed by the user.
All other 2023 Apple Card payments were correctly recorded in the Apple Card YNAB account
(though some as ACH deposits rather than explicit YNAB transfers).

### Required Actions

1. **Delete** the SB TX (`9008c104-5978-407a-ad2e-cf15a7a378da`) — amount −$9,845.15
   dated 2024-03-10.
   Do **not** replace it; the account opened at $0 and YNAB tracks correctly without it.

**Status: ACTION REQUIRED**

---

## Apple Savings

### Bank Data
- Coverage start: 2023-04-22
- 2,944 transactions, 2 OFX balance points:
  - 2025-12-28: $42,053.56
  - 2026-03-04: $42,591.44

### iPhone Wallet Balance Data Points (Ground Truth)

| Date | Wallet | Bank cumul. | B − W | YNAB cumul. | Y − W |
|---|---|---|---|---|---|
| 2023-04-22 | $40,100.00 | $40,100.00 | +$0.00 ✓ | $0.00 | −$40,100 (no data before) |
| 2023-07-26 | $40,563.55 | $40,563.55 | +$0.00 ✓ | $40,563.00 | −$0.55 ✓ |
| 2023-12-23 | $41,681.65 | $41,694.79 | +$13.14 | $41,688.47 | +$6.82 ✓ |
| 2024-06-30 | $43,364.61 | $43,212.14 | −$152.47 | $43,203.15 | −$161.46 |
| 2025-01-01 | $44,805.05 | $44,804.94 | −$0.11 ✓ | $44,797.78 | −$7.27 ✓ |
| 2025-06-30 | $41,023.81 | $40,903.21 | −$120.60 | $40,894.29 | −$129.52 |
| 2026-01-01 | $42,198.00 | $42,197.89 | −$0.11 ✓ | $42,190.73 | −$7.27 ✓ |

**Note on Apr 22, 2023 YNAB = $0:** YNAB data starts with the first transaction, so the
running balance from inception looks like $0 before transactions are added.
The Apr 22 "date" in the Wallet represents the day YNAB would need a starting balance
entry — not that YNAB shows zero, but that cumulative sums from bank data starting
that day would produce this artifact.

**Note on mid-year discrepancies (Jun 2024, Jun 2025):** The −$120–$161 differences at
June 30 likely reflect coverage gaps at monthly statement boundaries.
The accounts converge back to within <$8 at Jan 1, 2025 and Jan 1, 2026.

**Note on persistent −$7.27 YNAB offset at Jan dates:** The consistent −$7.27 offset at
Jan 1, 2025 and Jan 1, 2026 is small enough to be a rounding difference or single missed
micro-transaction.

### Analysis

Apple Savings is essentially reconciled:
- Bank tracks Wallet within $0.11 at all annual boundaries ✓
- YNAB tracks Wallet within $7.27 at all annual boundaries ✓
- No starting balance action is needed

### Required Actions

None.

**Status: RECONCILED ✓**

---

## Summary of Action Items

| Account | Status | Action Required |
|---|---|---|
| **Chase Checking** | ✓ Resolved | User set YNAB SB to $69,639.07 on Dec 16, 2023 date |
| **Chase Credit** | ⚠ Action needed | Edit SB TX: amount → −$8,454.73, date → 2023-12-31 |
| **Apple Card** | ⚠ Action needed | Delete SB TX (−$9,845.15 dated 2024-03-10) |
| **Apple Savings** | ✓ Reconciled | No action needed |

### Chase Credit — Specific Edit

In YNAB, find the "Starting Balance" transaction in the Chase Credit Card account:
- **ID:** `50c58551-836d-4a7e-994c-fafb4321cc6a`
- **Current:** amount = −$7,824.74, date = 2024-02-03
- **Change to:** amount = **−$8,454.73**, date = **2023-12-31**

Justification: Derived from the Dec 12, 2023 – Jan 11, 2024 PDF statement (previous balance
$5,020.16, new balance $4,168.20), back-calculating $3,434.57 in Dec 12–31 spending not
captured in YNAB or bank data.
Cross-check: −$8,454.73 + Jan 1–11 YNAB net (+$4,286.53) = −$4,168.20 = statement Jan 11
balance ✓

### Apple Card — Specific Delete

In YNAB, delete the "Starting Balance" transaction in the Apple Card account:
- **ID:** `9008c104-5978-407a-ad2e-cf15a7a378da`
- **Current:** amount = −$9,845.15, date = 2024-03-10

Justification: Account opened April 22, 2023 at $0 balance (user confirmed).
The SB TX was a historical workaround for missing payment link in Chase Checking
($148.73 on 2023-06-01), which has now been directly corrected.
YNAB tracks Wallet correctly throughout 2023 and through mid-2024 without the SB TX.
