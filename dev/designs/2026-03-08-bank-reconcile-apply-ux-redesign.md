# Bank Reconcile Apply — UX Redesign

**Status**: Approved
**Created**: 2026-03-08
**Supersedes**: `2026-03-08-bank-reconcile-apply-design.md` (apply node section only)

## Overview

Redesign of the `bank_data_reconcile_apply` interactive UI to:

1. Group operations account-by-account rather than globally chronological.
2. Within each account, batch operations by (type, date) for bulk review.
3. Use `ynab create transaction --file -` for batch creates (one API call per batch).
4. Allow splitting any create batch into individual operations with `s`.

## Flow

```
For each account (in config order):
  Show account summary (creates + flags counts + date ranges)
  If nothing pending: print "Nothing pending." and continue (no prompt)
  Prompt: Process this account? [Y/n]
    n → log all ops as skipped, next account

  Walk (date, type) batches chronologically:
    CREATE batch → Apply batch? [y/N/s]  (single item: [y/N])
      y → ynab create transaction --file - (batch), log each tx
      N → log each tx as skipped
      s → review individually (y/N per item), return to batch list
    FLAG batch → Acknowledge? [A/n]
      A → log each flag as acknowledged
      n → log each flag as skipped
```

## Account Summary Display

```
Account: apple-card
  Creates : 12 across 4 days  (2024-03-15 – 2024-06-20)
  Flags   :  3                (2024-05-01 – 2024-06-28)
Process this account? [Y/n]

Account: chase-checking
  Nothing pending.
```

## Batch Displays

**CREATE batch:**
```
  ─── 2024-03-15  CREATE  3 transactions  -$42.97 total ──────────
    1. Spotify          -$12.99   SPOTIFY USA 8888812345 NY USA
    2. Starbucks         -$6.50   STARBUCKS UTAH AVE S WA USA
    3. Netflix          -$23.48   NETFLIX.COM
  CMD   : ynab create transaction --file - (3 transactions)
  Apply batch? [y/N/s]
```

**Individual item (after s):**
```
    ─── 2024-03-15  -$12.99 ─────────────────────────────────
      Payee : Spotify
      Memo  : SPOTIFY USA 8888812345 NY USA
      CMD   : ynab create transaction --account-id ... \
                --amount -12990 --date 2024-03-15 \
                --payee-name "Spotify" --memo "..." \
                --cleared reconciled \
                --import-id "bank:apple-card:2024-03-15:-12990:a3f9b2c1"
    Apply? [y/N]
```
After last item in batch: print `[Returning to batch view]`.

**FLAG batch:**
```
  ─── 2024-06-28  FLAG  2 ambiguous ──────────────────────────────
    1. Bank: -$25.00  Starbucks
       Candidate Matching Transactions in YNAB:
         a. Inst for Jh Nursing   2024-06-28  -$25.00
         b. Starbucks             2024-06-28  -$25.00
    2. Bank: -$18.00  Trader Joe's
       Candidate Matching Transactions in YNAB:
         a. Trader Joe's          2024-06-28  -$18.00
         b. Whole Foods           2024-06-28  -$19.00
  Acknowledge? [A/n]
```

## API Invocation

**Batch apply** (one API call per batch):
```
ynab create transaction --file -
```
Input: JSON array on stdin — one object per transaction with fields:
`account_id`, `date`, `amount`, `payee_name`, `memo`, `cleared`, `import_id`.

**Individual apply** (after split `y`):
```
ynab create transaction --account-id UUID --amount N --date YYYY-MM-DD \
  --payee-name NAME --memo MEMO --cleared reconciled --import-id ID
```

**Error handling**: if `--file` exits non-zero, log all txs in batch as `action="failed"`,
print the error output, continue to next batch.

## NDJSON Log Format

One line per transaction, written after the API call completes.
New field: `included_in_batch: bool`.

```json
{"timestamp":"...","op_type":"create_transaction","action":"applied",
 "account_slug":"apple-card","posted_date":"2024-03-15","amount_milliunits":-12990,
 "payee_name":"Spotify","import_id":"bank:apple-card:2024-03-15:-12990:a3f9b2c1",
 "ynab_exit_code":0,"included_in_batch":true}
```

Actions: `applied` | `skipped` | `failed` (creates); `acknowledged` | `skipped` (flags).

## Idempotency

`import_id` format unchanged: `bank:{slug}:{posted_date}:{amount_milliunits}:{sha256(description)[:8]}`

Re-running apply on the same reconciliation file is safe — YNAB rejects duplicate
import IDs.
