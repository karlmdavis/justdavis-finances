#!/usr/bin/env python3
"""
Mutation Executor for YNAB Transaction Updater.

Executes approved mutations via YNAB CLI with complete safety features.
Implements the Phase 3 logic from the specification.

Usage:
    python execute_mutations.py \\
        --mutations approved_mutations.yaml \\
        --delete-log deleted_transactions.ndjson \\
        --dry-run  # Remove for actual execution
"""

import json
import yaml
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from .currency_utils import milliunits_to_cents, cents_to_dollars_str
except ImportError:
    from currency_utils import milliunits_to_cents, cents_to_dollars_str


class MutationExecutor:
    """Executes approved mutations via YNAB CLI."""

    def __init__(self, dry_run: bool = True):
        """
        Initialize mutation executor.

        Args:
            dry_run: If True, use --dry-run flag for simulation only
        """
        self.dry_run = dry_run
        self.executed_count = 0
        self.error_count = 0
        self.delete_log_entries = []

    def load_approved_mutations(self, mutations_path: str) -> Dict[str, Any]:
        """
        Load approved mutations from YAML file.

        Args:
            mutations_path: Path to approved mutations YAML file

        Returns:
            Approved mutations data structure
        """
        try:
            with open(mutations_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load approved mutations: {e}")

    def load_current_ynab_cache(self, ynab_cache_path: str = "ynab-data/transactions.json") -> Dict[str, Dict[str, Any]]:
        """
        Load current YNAB transaction cache for pre-condition verification.

        Args:
            ynab_cache_path: Path to YNAB transactions cache

        Returns:
            Dictionary mapping transaction ID to current transaction data
        """
        try:
            with open(ynab_cache_path, 'r') as f:
                transactions = json.load(f)
            return {tx['id']: tx for tx in transactions}
        except Exception as e:
            raise RuntimeError(f"Failed to load YNAB cache: {e}")

    def execute_mutations(
        self,
        mutations_data: Dict[str, Any],
        delete_log_path: str,
        ynab_cache_path: str = "ynab-data/transactions.json"
    ) -> Tuple[int, int]:
        """
        Execute all approved mutations.

        Args:
            mutations_data: Loaded approved mutations data
            delete_log_path: Path to NDJSON delete log file
            ynab_cache_path: Path to YNAB cache for verification

        Returns:
            Tuple of (executed_count, error_count)
        """
        mutations = mutations_data.get('mutations', [])
        current_transactions = self.load_current_ynab_cache(ynab_cache_path)

        print(f"Executing {len(mutations)} approved mutations...")
        if self.dry_run:
            print("DRY RUN MODE - No actual changes will be made")
        print("="*60)

        # Create delete log file
        Path(delete_log_path).parent.mkdir(parents=True, exist_ok=True)

        for i, mutation in enumerate(mutations, 1):
            print(f"\nMutation {i}/{len(mutations)}: {mutation['transaction_id']}")
            print("-" * 40)

            try:
                success = self._execute_single_mutation(mutation, current_transactions, delete_log_path)
                if success:
                    self.executed_count += 1
                    print("✓ Success")
                else:
                    self.error_count += 1
                    print("✗ Failed")

            except Exception as e:
                print(f"✗ Error: {e}")
                self.error_count += 1

        # Write delete log
        if self.delete_log_entries:
            self._write_delete_log(delete_log_path)

        return self.executed_count, self.error_count

    def _execute_single_mutation(
        self,
        mutation: Dict[str, Any],
        current_transactions: Dict[str, Dict[str, Any]],
        delete_log_path: str
    ) -> bool:
        """
        Execute a single mutation with pre-condition verification.

        Args:
            mutation: Single mutation to execute
            current_transactions: Current transaction state for verification
            delete_log_path: Path to delete log

        Returns:
            True if successful, False otherwise
        """
        transaction_id = mutation['transaction_id']

        # Pre-condition verification
        if not self._verify_preconditions(mutation, current_transactions):
            return False

        # Execute based on action type
        action = mutation['action']

        if action == 'split':
            return self._execute_split_transaction(mutation, current_transactions[transaction_id], delete_log_path)
        elif action == 'update_memo':
            return self._execute_memo_update(mutation, current_transactions[transaction_id])
        else:
            print(f"Unknown action: {action}")
            return False

    def _verify_preconditions(
        self,
        mutation: Dict[str, Any],
        current_transactions: Dict[str, Dict[str, Any]]
    ) -> bool:
        """
        Verify pre-conditions before executing mutation.

        Args:
            mutation: Mutation to verify
            current_transactions: Current transaction state

        Returns:
            True if all pre-conditions pass
        """
        transaction_id = mutation['transaction_id']
        original = mutation['original']

        # Check transaction exists
        current_tx = current_transactions.get(transaction_id)
        if not current_tx:
            print(f"Pre-condition failed: Transaction {transaction_id} not found")
            return False

        # Check amount unchanged
        if current_tx['amount'] != original['amount']:
            print(f"Pre-condition failed: Amount changed from {original['amount']} to {current_tx['amount']}")
            return False

        # Check not already split (unless force flag)
        if current_tx.get('subtransactions'):
            print(f"Pre-condition failed: Transaction already has {len(current_tx['subtransactions'])} subtransactions")
            return False

        # Check confidence threshold (already filtered, but double-check)
        confidence = mutation.get('confidence', 0)
        if confidence < 0.8:  # Should match generator threshold
            print(f"Pre-condition failed: Confidence {confidence} below threshold")
            return False

        print("✓ Pre-conditions verified")
        return True

    def _execute_split_transaction(
        self,
        mutation: Dict[str, Any],
        current_transaction: Dict[str, Any],
        delete_log_path: str
    ) -> bool:
        """
        Execute transaction split via YNAB CLI.

        Args:
            mutation: Split mutation to execute
            current_transaction: Current transaction data
            delete_log_path: Path to delete log

        Returns:
            True if successful
        """
        transaction_id = mutation['transaction_id']
        splits = mutation.get('splits', [])

        if not splits:
            print("No splits defined")
            return False

        # Log original transaction for recovery
        self._log_transaction_deletion(current_transaction, delete_log_path)

        # Build YNAB CLI command
        cmd = self._build_split_command(transaction_id, splits, delete_log_path)

        # Execute command
        return self._execute_ynab_command(cmd, f"split transaction {transaction_id}")

    def _execute_memo_update(
        self,
        mutation: Dict[str, Any],
        current_transaction: Dict[str, Any]
    ) -> bool:
        """
        Execute memo update via YNAB CLI.

        Args:
            mutation: Memo update mutation
            current_transaction: Current transaction data

        Returns:
            True if successful
        """
        transaction_id = mutation['transaction_id']
        new_memo = mutation.get('new_memo', '')

        # Build YNAB CLI command
        cmd = [
            'ynab', 'update', 'transaction',
            '--id', transaction_id,
            '--memo', new_memo
        ]

        if self.dry_run:
            cmd.append('--dry-run')

        # Execute command
        return self._execute_ynab_command(cmd, f"update memo for {transaction_id}")

    def _build_split_command(
        self,
        transaction_id: str,
        splits: List[Dict[str, Any]],
        delete_log_path: str
    ) -> List[str]:
        """
        Build YNAB CLI command for transaction splitting.

        Args:
            transaction_id: Transaction ID to split
            splits: List of split specifications
            delete_log_path: Path to delete log

        Returns:
            YNAB CLI command as list of strings
        """
        cmd = [
            'ynab', 'update', 'transaction',
            '--id', transaction_id,
            '--allow-delete-and-recreate',
            '--delete-log', delete_log_path
        ]

        # Add split specifications
        for split in splits:
            amount = split['amount']
            memo = split['memo']
            category_id = split.get('category_id', '')

            # Format: amount:MILLIUNITS,category-id:UUID,memo:TEXT
            split_spec = f"amount:{amount}"
            if category_id:
                split_spec += f",category-id:{category_id}"
            split_spec += f",memo:{memo}"

            cmd.extend(['--split', split_spec])

        if self.dry_run:
            cmd.append('--dry-run')

        return cmd

    def _execute_ynab_command(self, cmd: List[str], description: str) -> bool:
        """
        Execute YNAB CLI command with error handling.

        Args:
            cmd: Command as list of strings
            description: Human-readable description for logging

        Returns:
            True if command succeeded
        """
        try:
            print(f"Executing: {description}")
            if self.dry_run:
                print(f"Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            if result.returncode == 0:
                if result.stdout.strip():
                    print(f"Output: {result.stdout.strip()}")
                return True
            else:
                print(f"Command failed (exit code {result.returncode})")
                if result.stderr.strip():
                    print(f"Error: {result.stderr.strip()}")
                return False

        except subprocess.TimeoutExpired:
            print("Command timed out after 30 seconds")
            return False
        except Exception as e:
            print(f"Command execution error: {e}")
            return False

    def _log_transaction_deletion(self, transaction: Dict[str, Any], delete_log_path: str):
        """
        Log transaction data before deletion for recovery.

        Args:
            transaction: Transaction data to log
            delete_log_path: Path to delete log file
        """
        log_entry = {
            'timestamp': datetime.now().isoformat() + 'Z',
            'action': 'delete_for_recreate',
            'transaction_id': transaction['id'],
            'budget_id': 'last-used',  # YNAB CLI uses this
            'command': f"ynab update transaction --id {transaction['id']} --allow-delete-and-recreate",
            'original_data': transaction
        }

        self.delete_log_entries.append(log_entry)

    def _write_delete_log(self, delete_log_path: str):
        """
        Write accumulated delete log entries to NDJSON file.

        Args:
            delete_log_path: Path to delete log file
        """
        try:
            with open(delete_log_path, 'w') as f:
                for entry in self.delete_log_entries:
                    f.write(json.dumps(entry) + '\n')

            print(f"\nDelete log written to: {delete_log_path}")
            print(f"Logged {len(self.delete_log_entries)} transaction deletions")

        except Exception as e:
            print(f"Error writing delete log: {e}")

    def generate_summary_report(self, mutations_data: Dict[str, Any]) -> str:
        """
        Generate execution summary report.

        Args:
            mutations_data: Original mutations data

        Returns:
            Summary report as string
        """
        total_mutations = len(mutations_data.get('mutations', []))
        success_rate = (self.executed_count / total_mutations * 100) if total_mutations > 0 else 0

        report = f"""
YNAB Transaction Updater - Execution Summary
{"="*50}

Mode: {"DRY RUN" if self.dry_run else "LIVE EXECUTION"}
Total mutations: {total_mutations}
Successfully executed: {self.executed_count}
Errors: {self.error_count}
Success rate: {success_rate:.1f}%

Generated at: {datetime.now().isoformat()}
"""

        if self.error_count > 0:
            report += f"\nNote: {self.error_count} mutations failed. Check output for details."

        if self.dry_run:
            report += "\n\nDRY RUN - No actual changes were made to YNAB."
            report += "\nRe-run without --dry-run to apply changes."

        return report


def main():
    """Command-line interface for mutation execution."""
    parser = argparse.ArgumentParser(description='Execute approved YNAB transaction mutations')
    parser.add_argument('--mutations', required=True, help='Path to approved mutations YAML file')
    parser.add_argument('--delete-log', required=True, help='Path to NDJSON delete log file')
    parser.add_argument('--ynab-cache', default='ynab-data/transactions.json',
                        help='Path to YNAB cache for verification')
    parser.add_argument('--dry-run', action='store_true', help='Simulate execution without making changes')

    args = parser.parse_args()

    # Validate input file
    if not Path(args.mutations).exists():
        print(f"Error: File not found: {args.mutations}")
        return 1

    if not Path(args.ynab_cache).exists():
        print(f"Error: YNAB cache not found: {args.ynab_cache}")
        print("Run: ynab --output json list transactions > ynab-data/transactions.json")
        return 1

    try:
        executor = MutationExecutor(dry_run=args.dry_run)

        # Load mutations
        print("Loading approved mutations...")
        mutations_data = executor.load_approved_mutations(args.mutations)
        mutation_count = len(mutations_data.get('mutations', []))
        print(f"Loaded {mutation_count} approved mutations")

        if mutation_count == 0:
            print("No mutations to execute.")
            return 0

        # Execute mutations
        executed, errors = executor.execute_mutations(mutations_data, args.delete_log, args.ynab_cache)

        # Generate summary
        print("\n" + executor.generate_summary_report(mutations_data))

        return 0 if errors == 0 else 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())