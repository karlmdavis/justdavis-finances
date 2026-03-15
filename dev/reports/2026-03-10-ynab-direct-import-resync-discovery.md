# YNAB Direct Import Re-Sync Discovery

**Date:** 2026-03-10
**Session context:** Debugging session investigating unexpected YNAB transactions after
a `bank_data_reconcile_apply` run on 2026-03-09.

---

## Summary

When transactions are created in YNAB on an account that has Direct Import (live bank
connection) enabled, and those transactions are dated **before** the account's Starting
Balance entry, YNAB's backend appears to proactively reach back and pull matching
historical data from the bank.
Those bank-imported transactions then appear in YNAB with YNAB-format import IDs
(`YNAB:-AMOUNT:DATE:N`) and show up in the next `ynab_sync` as new transactions — even
though neither the user nor the tool explicitly created them.

---

## Investigation Trigger

After a `bank_data_reconcile_apply` session, a large batch of January–February 2024
Chase Credit Card transactions appeared in YNAB that the user had not intentionally
applied.
The initial hypothesis was that the apply workflow had applied transactions without user
approval, or had applied them after the user pressed Ctrl+C.

---

## Evidence Collected

1. **Apply log shows 2024-01-03 batch as "skipped."**
   The apply log entry for the 2024-01-03 Chase batch recorded `status: skipped`.
   The UUIDs our tool uses as import IDs (`bank_data_reconcile:...`) were absent from the
   YNAB transaction cache.

2. **YNAB-format import IDs on the mystery transactions.**
   The transactions that appeared in YNAB carried import IDs matching the pattern
   `YNAB:-N:DATE:1` — the format YNAB uses for its own Direct Import–sourced transactions,
   not the UUID-based format our tool uses.

3. **Archive diff confirms timing.**
   The sentinel import IDs were absent in the `19-46-09_pre` snapshot and present in the
   `19-46-13_post` snapshot — they appeared during the `ynab_sync` immediately following
   the apply session, not during the apply session itself.

4. **Scope of newly appeared transactions.**
   All 54 proposed creates for January–February 2024 were already present in YNAB after
   the sync.
   Only 10 December 2024–January 2025 Amazon transactions were genuinely missing (the
   ones our tool correctly created).

5. **Account configuration.**
   The Chase Credit Card account has `direct_import_linked: true`.
   Its Starting Balance is dated **2024-02-03**.

6. **Date of the 4 transactions our tool created.**
   The 4 transactions the apply workflow actually created are dated **2024-01-01** and
   **2024-01-02** — 33 days before the Starting Balance date.

---

## Hypotheses Considered

### Hypothesis 1: Transactions applied before user approval
**Ruling:** Definitively ruled out.
The apply log records the 2024-01-03 batch as `skipped`.
Our UUID-based import IDs are absent from the YNAB cache.
There is no mechanism in the apply code to create transactions without logging them.

### Hypothesis 2: Transactions applied after Ctrl+C
**Ruling:** Definitively ruled out.
The Ctrl+C was pressed during the **2024-01-04** batch prompt, not the 2024-01-03 batch.
Even if a partial write had occurred, the UUID-based import IDs would be present in YNAB,
which they are not.

### Hypothesis 3: ynab_sync delta-sync / server_knowledge quirk
**Ruling:** Plausible but incomplete.
A delta sync could surface previously unseen transactions if `server_knowledge` advanced.
However, this hypothesis alone does not explain why the new transactions carry
YNAB-format import IDs (`YNAB:-N:DATE:1`) rather than pre-existing import IDs from a
prior sync window.

### Hypothesis 4: Creating pre-Starting-Balance transactions triggers YNAB Direct Import re-sync
**Ruling:** Best fit for all evidence.
When our tool created 4 transactions dated 2024-01-01 and 2024-01-02 on the Chase Credit
Card account (Starting Balance: 2024-02-03, Direct Import enabled), YNAB's backend
appears to have interpreted those pre-Starting-Balance creates as a signal to reach back
and pull matching historical data from the bank.
This explains:

- Why the new transactions carry YNAB-format import IDs (they came from the bank, not
  from our tool).
- Why there was a timing delay (the re-sync completed between the apply session and the
  next `ynab_sync`).
- Why the new transactions cover a coherent date range (the full Jan–Feb 2024 history
  the bank had on file).

---

## Root Cause Assessment

**Hypothesis 4 is the strongest match** and is treated as the working explanation.
Hypotheses 1 and 2 are definitively ruled out.
Hypothesis 3 may be a contributing factor (the delta sync surfaced what YNAB's backend
had already fetched), but it is not the root cause.

---

## Implications

### The apply workflow is correct
No premature application occurred.
The tool's apply-log and UUID-based import ID design provide clear evidence of what was
and was not applied.

### Creating pre-Starting-Balance transactions has two side effects

**Side effect 1: YNAB Direct Import may proactively pull historical bank data.**
If you backfill transactions dated before an account's Starting Balance and that account
has Direct Import enabled, YNAB may automatically fetch matching historical records from
the bank.
**Mitigation:** After any apply session that creates pre-Starting-Balance transactions,
run `ynab_sync` before re-running `bank_data_reconcile`.
Transactions that appeared via YNAB Direct Import should be treated as
already-reconciled rather than missing, to avoid creating duplicates.

**Side effect 2: The Starting Balance entry becomes inaccurate.**
Once pre-Starting-Balance transactions exist, the Starting Balance entry's date and
amount no longer correctly represent the account's opening state.
**Mitigation:** Adjust the Starting Balance entry's date (move it earlier) and amount
(recalculate to reflect the true balance at the new start date) after adding historical
data.

### Immediate action for this account
The 4 transactions our tool created (dated 2024-01-01 and 2024-01-02) now sit before
the 2024-02-03 Starting Balance in YNAB.
The Starting Balance entry's date and amount should be adjusted to reflect the true
account balance at 2024-01-01 or the earliest transaction date present.
