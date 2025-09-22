#!/usr/bin/env python3
"""Integration tests for YNAB Transaction Updater."""

import unittest
import tempfile
import json
import yaml
import uuid
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_mutations import MutationGenerator
from review_mutations import MutationReviewer
from execute_mutations import MutationExecutor


class TestIntegrationWorkflow(unittest.TestCase):
    """Test the complete workflow integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_complete_amazon_workflow(self):
        """Test complete workflow with Amazon data."""
        # Create synthetic Amazon matching results
        amazon_results = self._create_amazon_match_results()
        match_file = self.temp_path / "amazon_matches.json"
        with open(match_file, 'w') as f:
            json.dump(amazon_results, f)

        # Create synthetic YNAB transactions
        ynab_transactions = self._create_ynab_transactions()
        ynab_file = self.temp_path / "transactions.json"
        with open(ynab_file, 'w') as f:
            json.dump(ynab_transactions, f)

        # Phase 1: Generate mutations
        generator = MutationGenerator(confidence_threshold=0.8)
        ynab_tx_dict = generator.load_ynab_transactions(str(ynab_file))
        match_data = generator.load_match_results(str(match_file))

        mutations = generator.generate_mutations(match_data, ynab_tx_dict)

        # Verify mutations generated
        self.assertGreater(len(mutations), 0)

        # Save mutations YAML
        mutations_file = self.temp_path / "mutations.yaml"
        generator.save_mutations_yaml(mutations, str(mutations_file), str(match_file))

        # Phase 2: Review mutations (batch mode)
        reviewer = MutationReviewer()
        mutations_data = reviewer.load_mutations(str(mutations_file))

        # Auto-approve high confidence
        approved_ids = reviewer.review_mutations_batch(mutations_data, auto_approve_confidence=0.9)

        # Save approval file
        approval_file = self.temp_path / "approved.yaml"
        reviewer.save_approval_file(mutations_data, approved_ids, str(approval_file), str(mutations_file))

        # Phase 3: Execute mutations (dry-run)
        executor = MutationExecutor(dry_run=True)
        approved_data = executor.load_approved_mutations(str(approval_file))

        delete_log = self.temp_path / "delete.ndjson"

        # This would normally need real YNAB cache, but in dry-run mode
        # we can simulate with our test data
        executed, errors = executor.execute_mutations(approved_data, str(delete_log), str(ynab_file))

        # Verify no errors in dry-run
        self.assertEqual(errors, 0)

    def test_apple_workflow_with_tax(self):
        """Test complete workflow with Apple data including tax."""
        # Create synthetic Apple matching results
        apple_results = self._create_apple_match_results()
        match_file = self.temp_path / "apple_matches.json"
        with open(match_file, 'w') as f:
            json.dump(apple_results, f)

        # Create corresponding YNAB transactions
        ynab_transactions = self._create_apple_ynab_transactions()
        ynab_file = self.temp_path / "transactions.json"
        with open(ynab_file, 'w') as f:
            json.dump(ynab_transactions, f)

        # Generate mutations
        generator = MutationGenerator(confidence_threshold=0.8)
        ynab_tx_dict = generator.load_ynab_transactions(str(ynab_file))
        match_data = generator.load_match_results(str(match_file))

        mutations = generator.generate_mutations(match_data, ynab_tx_dict)

        # Verify Apple mutations handle tax
        self.assertGreater(len(mutations), 0)

        apple_mutation = next((m for m in mutations if m['source'] == 'apple'), None)
        self.assertIsNotNone(apple_mutation)

        if apple_mutation['action'] == 'split':
            # Verify tax is included in memos
            for split in apple_mutation['splits']:
                self.assertIn('(incl. tax)', split['memo'])

    def _create_amazon_match_results(self):
        """Create synthetic Amazon matching results."""
        tx_id = "915a3595-0424-45a0-b5f9-f5cf4a03c986"  # Fixed UUID for test consistency
        return {
            "date_range": {"start": "2025-09-01", "end": "2025-09-30"},
            "results": [
                {
                    "ynab_transaction": {
                        "id": tx_id,
                        "date": "2025-09-15",
                        "amount": "89.90",
                        "payee_name": "Amazon.com",
                        "account_name": "Chase Credit Card"
                    },
                    "matches": [
                        {
                            "account": "karl",
                            "amazon_orders": [
                                {
                                    "order_id": "111-2223334-5556667",
                                    "items": [
                                        {
                                            "name": "Echo Dot (4th Gen) - Charcoal",
                                            "amount": 4599,
                                            "quantity": 1,
                                            "unit_price": 4599
                                        },
                                        {
                                            "name": "USB-C Cable 6ft - 2 Pack",
                                            "amount": 2350,
                                            "quantity": 1,
                                            "unit_price": 2350
                                        },
                                        {
                                            "name": "Phone Case Clear",
                                            "amount": 1599,
                                            "quantity": 1,
                                            "unit_price": 1599
                                        },
                                        {
                                            "name": "Screen Protector",
                                            "amount": 1442,
                                            "quantity": 1,
                                            "unit_price": 1442
                                        }
                                    ],
                                    "order_date": "2025-09-14",
                                    "total": 8990
                                }
                            ],
                            "confidence": 0.95,
                            "match_method": "complete"
                        }
                    ]
                }
            ]
        }

    def _create_apple_match_results(self):
        """Create synthetic Apple matching results."""
        tx_id = "f57b6948-9b9b-4d8e-8e49-1640f0522c50"  # Fixed UUID for test consistency
        return {
            "date_range": {"start": "2025-09-01", "end": "2025-09-30"},
            "results": [
                {
                    "ynab_transaction": {
                        "id": tx_id,
                        "date": "2025-09-16",
                        "amount": 32.97,
                        "payee_name": "Apple Services",
                        "account_name": "Apple Card"
                    },
                    "matched": True,
                    "apple_receipts": [
                        {
                            "order_id": "ML7PQ2XYZ",
                            "date": "2025-09-16",
                            "apple_id": "karl@example.com",
                            "subtotal": 29.98,
                            "tax": 2.99,
                            "items": [
                                {"title": "Logic Pro", "cost": 19.99},
                                {"title": "Final Cut Pro", "cost": 9.99}
                            ]
                        }
                    ],
                    "match_confidence": 1.0,
                    "match_strategy": "exact_match"
                }
            ]
        }

    def _create_ynab_transactions(self):
        """Create synthetic YNAB transactions for Amazon test."""
        tx_id = "915a3595-0424-45a0-b5f9-f5cf4a03c986"  # Fixed UUID for test consistency
        return [
            {
                "id": tx_id,
                "date": "2025-09-15",
                "amount": -89900,  # milliunits
                "memo": "AMZN Mktp US*RT4Y12",
                "payee_name": "Amazon.com",
                "account_name": "Chase Credit Card",
                "category_name": "Shopping",
                "subtransactions": []
            }
        ]

    def _create_apple_ynab_transactions(self):
        """Create synthetic YNAB transactions for Apple test."""
        tx_id = "f57b6948-9b9b-4d8e-8e49-1640f0522c50"  # Fixed UUID for test consistency
        return [
            {
                "id": tx_id,
                "date": "2025-09-16",
                "amount": -32970,  # milliunits
                "memo": "Apple Services",
                "payee_name": "Apple Services",
                "account_name": "Apple Card",
                "category_name": "Software",
                "subtransactions": []
            }
        ]


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""

    def test_missing_files_error_handling(self):
        """Test graceful handling of missing files."""
        generator = MutationGenerator()

        with self.assertRaises(RuntimeError):
            generator.load_ynab_transactions("nonexistent.json")

        with self.assertRaises(RuntimeError):
            generator.load_match_results("nonexistent.json")

    def test_invalid_json_error_handling(self):
        """Test handling of invalid JSON files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            invalid_file = f.name

        generator = MutationGenerator()

        with self.assertRaises(RuntimeError):
            generator.load_ynab_transactions(invalid_file)

        # Clean up
        Path(invalid_file).unlink()

    def test_low_confidence_filtering(self):
        """Test that low confidence matches are filtered out."""
        generator = MutationGenerator(confidence_threshold=0.8)

        # Create match result with low confidence
        match_result = {
            "ynab_transaction": {"id": "test-id"},
            "matches": [{"confidence": 0.5}]  # Below threshold
        }

        ynab_transactions = {"test-id": {"id": "test-id", "amount": -1000}}

        mutation = generator._process_match_result(match_result, ynab_transactions)
        self.assertIsNone(mutation)  # Should be filtered out


class TestDryRunValidation(unittest.TestCase):
    """Test dry-run mode validation."""

    def test_dry_run_command_building(self):
        """Test that dry-run commands are built correctly."""
        executor = MutationExecutor(dry_run=True)

        cmd = executor._build_split_command(
            "test-id",
            [
                {"amount": -2000, "memo": "Item 1"},
                {"amount": -3000, "memo": "Item 2"}
            ],
            "delete.log"
        )

        # Should include --dry-run flag
        self.assertIn("--dry-run", cmd)
        self.assertIn("--allow-delete-and-recreate", cmd)


if __name__ == '__main__':
    unittest.main()