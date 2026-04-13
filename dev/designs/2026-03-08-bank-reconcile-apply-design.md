# Bank Reconcile Apply — Design

**Status**: Approved
**Created**: 2026-03-08

## Overview

Two improvements to the bank account reconciliation system:

1. **Matching fix**: use `merchant` field (when available) instead of `description` for
   fuzzy payee scoring, resolving most `flag_discrepancy` ambiguous cases.
2. **Apply node**: new interactive flow node that walks through reconciliation operations
   and calls `ynab create transaction` for approved creates.

## 1. Matching Algorithm Fix

### Problem

`find_matches()` in `src/finances/bank_accounts/matching.py` compares `bank_tx.description`
(verbose OFX field, e.g. `"STARBUCKS 800-782-7282 UTAH AVE S 98134 WA USA"`) against YNAB
`payee_name` (short, e.g. `"Starbucks"`).
SequenceMatcher scores ~0.25 — below the 0.8 threshold — making same-day same-amount pairs
ambiguous even when payees clearly identify the correct match.

### Solution

Apple Card OFX provides a clean `merchant` field that closely matches YNAB Direct Import
payee names (verified: 20/20 matched pairs show `merchant` ≈ YNAB `payee_name`).
When `bank_tx.merchant` is populated, use it instead of `description` for fuzzy comparison.

```python
# In find_matches(), fuzzy scoring block:
bank_desc = normalize_description(
    bank_tx.merchant if bank_tx.merchant else bank_tx.description
)
```

`description` continues to be stored in the bank transaction and used as `--memo` when
creating YNAB transactions; it is not the right input for payee name matching.

### Expected impact

Most of the 28 `flag_discrepancy` cases should resolve to `fuzzy` matches.

## 2. Apply Node

### Architecture

```
bank_data_reconcile  →  bank_data_reconcile_apply
  (operations.json)        (interactive prompt + ynab CLI)
                                   ↓
                      data/bank_accounts/reconciliation_apply/
                        {timestamp}_apply_log.ndjson
```

### Flow Position

- **Node ID**: `bank_data_reconcile_apply`
- **Depends on**: `bank_data_reconcile`
- **Output dir**: `data/bank_accounts/reconciliation_apply/`

### Operation Display

**create_transaction:**
```
─── [apple-card] 2024-03-15  -$12.99 ───────────────────────────────
  Payee : Spotify
  Memo  : SPOTIFY USA 8888812345 NY USA
  CMD   : ynab create transaction --account-id 7fec0007-... \
            --amount -12990 --date 2024-03-15 \
            --payee-name "Spotify" --memo "SPOTIFY USA ..." \
            --cleared reconciled --import-id "bank:apple-card:2024-03-15:-12990:a3f9b2c1"
Apply? [y/N]
```

**flag_discrepancy:**
```
─── [apple-card] 2024-06-28  -$25.00  ⚠ AMBIGUOUS ──────────────────
  Bank  : Starbucks
  YNAB candidates:
    1. Inst for Jh Nursing  (2024-06-28  -$25.00)
    2. Starbucks             (2024-06-28  -$25.00)
  Cannot auto-apply — resolve manually in YNAB.
Acknowledge? [A]
```

### YNAB CLI Invocation

```
ynab create transaction
  --account-id  {op["account_id"]}
  --amount      {bank_tx["amount_milliunits"]}
  --date        {bank_tx["posted_date"]}
  --payee-name  {bank_tx.get("merchant") or bank_tx["description"]}
  --memo        {bank_tx["description"]}
  --cleared     reconciled
  --import-id   bank:{slug}:{posted_date}:{amount_milliunits}:{sha256(description)[:8]}
```

`--import-id` is stable per bank transaction → idempotent apply (safe to re-run).

### NDJSON Log Format

One JSON object per line, written immediately on each decision:

```json
{"timestamp":"...","op_type":"create_transaction","action":"applied",
 "account_slug":"apple-card","posted_date":"2024-03-15","amount_milliunits":-12990,
 "payee_name":"Spotify","import_id":"bank:apple-card:2024-03-15:-12990:a3f9b2c1",
 "ynab_exit_code":0}
{"timestamp":"...","op_type":"create_transaction","action":"skipped",
 "account_slug":"chase-checking","posted_date":"2023-12-29","amount_milliunits":-3000,
 "payee_name":"Non-Chase Atm Fee-With","import_id":"bank:chase-checking:..."}
{"timestamp":"...","op_type":"flag_discrepancy","action":"acknowledged",
 "account_slug":"apple-card","posted_date":"2024-06-28","amount_milliunits":-25000,
 "candidates":["Inst for Jh Nursing","Starbucks"]}
```

### Idempotency

`--import-id` format: `bank:{slug}:{posted_date}:{amount_milliunits}:{sha256(description)[:8]}`

The YNAB API rejects duplicate `import-id` values, so re-running apply on the same
reconciliation file will not create duplicate transactions.
After the user runs `ynab_sync` + `bank_data_reconcile` again, applied transactions will
be matched and will no longer appear as `create_transaction` operations.

### Payee Name Resolution

- Apple Card: use `bank_tx.merchant` (clean, matches YNAB Direct Import format)
- Other accounts: use `bank_tx.description` (no `merchant` field available)

### Cleared/Approved Status

- `--cleared reconciled`: these transactions are confirmed present in the bank statement
- `--approved false`: leaves categorization to be done in YNAB before entering the budget

## 3. Ordering

Operations are sorted chronologically by `posted_date` across all accounts.
This matches natural review order and ensures the oldest gaps (historical pre-YNAB period)
are addressed first, with more recent in-range creates following.
