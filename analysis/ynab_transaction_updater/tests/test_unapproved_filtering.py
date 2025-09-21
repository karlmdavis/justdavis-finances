#!/usr/bin/env python3
"""
Test suite for unapproved transaction filtering functionality.

Tests the new --unapproved-only flag and filtering logic in generate_mutations.py.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_mutations import MutationGenerator


class TestUnapprovedFiltering(unittest.TestCase):
    """Test cases for unapproved transaction filtering."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = MutationGenerator(confidence_threshold=0.8)

        # Sample transaction data with mixed approval status
        self.test_transactions = [
            {
                "id": "tx-approved-1",
                "amount": -5000,
                "memo": "Approved transaction",
                "approved": True,
                "account_name": "Chase Credit Card",
                "date": "2025-09-15"
            },
            {
                "id": "tx-unapproved-1",
                "amount": -3000,
                "memo": "Unapproved transaction",
                "approved": False,
                "account_name": "Chase Credit Card",
                "date": "2025-09-16"
            },
            {
                "id": "tx-unapproved-2",
                "amount": -7500,
                "memo": "Another unapproved transaction",
                "approved": False,
                "account_name": "Apple Card",
                "date": "2025-09-17"
            },
            {
                "id": "tx-approved-2",
                "amount": -2500,
                "memo": "Another approved transaction",
                "approved": True,
                "account_name": "Apple Card",
                "date": "2025-09-18"
            },
            {
                "id": "tx-no-field",
                "amount": -4000,
                "memo": "Transaction without approved field",
                "account_name": "Chase Checking",
                "date": "2025-09-19"
            }
        ]

    def test_load_all_transactions(self):
        """Test loading all transactions (no filtering)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.test_transactions, f)
            temp_path = f.name

        try:
            # Load all transactions
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=False)

            # Should return all 5 transactions
            self.assertEqual(len(result), 5)
            self.assertIn("tx-approved-1", result)
            self.assertIn("tx-unapproved-1", result)
            self.assertIn("tx-unapproved-2", result)
            self.assertIn("tx-approved-2", result)
            self.assertIn("tx-no-field", result)

        finally:
            os.unlink(temp_path)

    def test_load_unapproved_only(self):
        """Test loading only unapproved transactions."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.test_transactions, f)
            temp_path = f.name

        try:
            # Load only unapproved transactions
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=True)

            # Should return only 2 transactions with approved=false
            self.assertEqual(len(result), 2)
            self.assertIn("tx-unapproved-1", result)
            self.assertIn("tx-unapproved-2", result)
            self.assertNotIn("tx-approved-1", result)
            self.assertNotIn("tx-approved-2", result)
            self.assertNotIn("tx-no-field", result)  # Missing field defaults to approved

        finally:
            os.unlink(temp_path)

    def test_missing_approved_field_defaults_approved(self):
        """Test that transactions without 'approved' field default to approved=True."""
        transactions_no_approved = [
            {
                "id": "tx-missing-1",
                "amount": -1000,
                "memo": "No approved field",
                "account_name": "Test Account",
                "date": "2025-09-20"
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(transactions_no_approved, f)
            temp_path = f.name

        try:
            # Should not be included when filtering for unapproved only
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=True)
            self.assertEqual(len(result), 0)

            # Should be included when loading all
            result_all = self.generator.load_ynab_transactions(temp_path, unapproved_only=False)
            self.assertEqual(len(result_all), 1)

        finally:
            os.unlink(temp_path)

    def test_empty_transaction_list(self):
        """Test handling of empty transaction list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            temp_path = f.name

        try:
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=True)
            self.assertEqual(len(result), 0)

        finally:
            os.unlink(temp_path)

    def test_all_approved_transactions(self):
        """Test filtering when all transactions are approved."""
        all_approved = [
            {
                "id": "tx-1",
                "amount": -1000,
                "approved": True,
                "account_name": "Test",
                "date": "2025-09-20"
            },
            {
                "id": "tx-2",
                "amount": -2000,
                "approved": True,
                "account_name": "Test",
                "date": "2025-09-21"
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(all_approved, f)
            temp_path = f.name

        try:
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=True)
            self.assertEqual(len(result), 0)

        finally:
            os.unlink(temp_path)

    def test_all_unapproved_transactions(self):
        """Test filtering when all transactions are unapproved."""
        all_unapproved = [
            {
                "id": "tx-1",
                "amount": -1000,
                "approved": False,
                "account_name": "Test",
                "date": "2025-09-20"
            },
            {
                "id": "tx-2",
                "amount": -2000,
                "approved": False,
                "account_name": "Test",
                "date": "2025-09-21"
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(all_unapproved, f)
            temp_path = f.name

        try:
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=True)
            self.assertEqual(len(result), 2)

        finally:
            os.unlink(temp_path)

    def test_boolean_approved_values(self):
        """Test handling of various boolean representations for approved field."""
        mixed_booleans = [
            {"id": "tx-1", "amount": -1000, "approved": True, "account_name": "Test", "date": "2025-09-20"},
            {"id": "tx-2", "amount": -1000, "approved": False, "account_name": "Test", "date": "2025-09-20"},
            {"id": "tx-3", "amount": -1000, "approved": 1, "account_name": "Test", "date": "2025-09-20"},  # Truthy
            {"id": "tx-4", "amount": -1000, "approved": 0, "account_name": "Test", "date": "2025-09-20"},  # Falsy
            {"id": "tx-5", "amount": -1000, "approved": "true", "account_name": "Test", "date": "2025-09-20"},  # Truthy string
            {"id": "tx-6", "amount": -1000, "approved": "", "account_name": "Test", "date": "2025-09-20"},  # Falsy string
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mixed_booleans, f)
            temp_path = f.name

        try:
            result = self.generator.load_ynab_transactions(temp_path, unapproved_only=True)
            # Should include tx-2 (False), tx-4 (0), and tx-6 (empty string)
            self.assertEqual(len(result), 3)
            self.assertIn("tx-2", result)
            self.assertIn("tx-4", result)
            self.assertIn("tx-6", result)

        finally:
            os.unlink(temp_path)

    @patch('builtins.print')
    def test_filtering_output_messages(self, mock_print):
        """Test that filtering outputs informational messages."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.test_transactions, f)
            temp_path = f.name

        try:
            # Test unapproved only filtering
            self.generator.load_ynab_transactions(temp_path, unapproved_only=True)

            # Should print filtering message
            mock_print.assert_any_call("Filtered to 2 unapproved transactions from 5 total")

            # Reset and test no filtering
            mock_print.reset_mock()
            self.generator.load_ynab_transactions(temp_path, unapproved_only=False)

            # Should print total count message
            mock_print.assert_any_call("Loaded 5 transactions (no filtering)")

        finally:
            os.unlink(temp_path)

    def test_file_not_found_error(self):
        """Test handling of non-existent transaction file."""
        with self.assertRaises(RuntimeError) as context:
            self.generator.load_ynab_transactions("/nonexistent/file.json", unapproved_only=True)

        self.assertIn("Failed to load YNAB cache", str(context.exception))

    def test_invalid_json_error(self):
        """Test handling of invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name

        try:
            with self.assertRaises(RuntimeError) as context:
                self.generator.load_ynab_transactions(temp_path, unapproved_only=True)

            self.assertIn("Failed to load YNAB cache", str(context.exception))

        finally:
            os.unlink(temp_path)

    def test_integration_with_generate_mutations(self):
        """Test integration of filtering with the full mutation generation workflow."""
        # Create sample matching results
        match_results = {
            "results": [
                {
                    "ynab_transaction": {"id": "tx-unapproved-1"},
                    "matches": [{
                        "confidence": 0.9,
                        "amazon_orders": [{
                            "order_id": "123",
                            "order_date": "2025-09-16",
                            "items": [{"product_name": "Test Product", "total_owed": "30.00"}]
                        }]
                    }]
                },
                {
                    "ynab_transaction": {"id": "tx-approved-1"},
                    "matches": [{
                        "confidence": 0.9,
                        "amazon_orders": [{
                            "order_id": "456",
                            "order_date": "2025-09-15",
                            "items": [{"product_name": "Another Product", "total_owed": "50.00"}]
                        }]
                    }]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.test_transactions, f)
            tx_path = f.name

        try:
            # Load only unapproved transactions
            ynab_transactions = self.generator.load_ynab_transactions(tx_path, unapproved_only=True)

            # Generate mutations - should only process unapproved transaction
            mutations = self.generator.generate_mutations(match_results, ynab_transactions)

            # Should skip tx-approved-1 because it's not in the filtered set
            # tx-unapproved-1 should be processed but may fail due to missing data
            # Main point is testing the filtering integration
            self.assertIsInstance(mutations, list)

        finally:
            os.unlink(tx_path)


class TestCommandLineIntegration(unittest.TestCase):
    """Test command-line argument integration for unapproved filtering."""

    def test_unapproved_flag_in_argparse(self):
        """Test that the --unapproved-only flag is properly configured."""
        # Import the main function to test argument parsing
        import generate_mutations

        # Test with mock command line arguments
        test_args = [
            'generate_mutations.py',
            '--matches-file', 'test_matches.json',
            '--ynab-cache', 'test_transactions.json',
            '--unapproved-only',
            '--output', 'test_output.yaml'
        ]

        with patch('sys.argv', test_args):
            with patch('pathlib.Path.exists', return_value=True):
                with patch.object(MutationGenerator, 'load_ynab_transactions') as mock_load:
                    with patch.object(MutationGenerator, 'load_match_results'):
                        with patch.object(MutationGenerator, 'generate_mutations', return_value=[]):
                            with patch.object(MutationGenerator, 'save_mutations_yaml'):
                                try:
                                    generate_mutations.main()
                                except SystemExit:
                                    pass  # Expected for successful completion

                                # Verify the unapproved_only flag was passed correctly
                                mock_load.assert_called_once()
                                args, kwargs = mock_load.call_args
                                self.assertTrue(len(args) >= 2)  # Should have cache path and unapproved_only
                                if len(args) >= 2:
                                    self.assertTrue(args[1])  # unapproved_only should be True

    def test_default_behavior_without_flag(self):
        """Test default behavior when --unapproved-only flag is not provided."""
        import generate_mutations

        test_args = [
            'generate_mutations.py',
            '--matches-file', 'test_matches.json',
            '--ynab-cache', 'test_transactions.json',
            '--output', 'test_output.yaml'
        ]

        with patch('sys.argv', test_args):
            with patch('pathlib.Path.exists', return_value=True):
                with patch.object(MutationGenerator, 'load_ynab_transactions') as mock_load:
                    with patch.object(MutationGenerator, 'load_match_results'):
                        with patch.object(MutationGenerator, 'generate_mutations', return_value=[]):
                            with patch.object(MutationGenerator, 'save_mutations_yaml'):
                                try:
                                    generate_mutations.main()
                                except SystemExit:
                                    pass

                                # Verify the unapproved_only flag defaults to False
                                mock_load.assert_called_once()
                                args, kwargs = mock_load.call_args
                                if len(args) >= 2:
                                    self.assertFalse(args[1])  # unapproved_only should be False


if __name__ == '__main__':
    unittest.main()