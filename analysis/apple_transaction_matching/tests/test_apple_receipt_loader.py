#!/usr/bin/env python3
"""Tests for Apple receipt loader module."""

import pytest
import tempfile
import os
import json

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apple_receipt_loader import AppleReceiptLoader


class TestAppleReceiptLoader:
    """Test cases for AppleReceiptLoader functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Sample receipt data
        self.sample_receipts = [
            {
                "order_id": "ML7PQ2XYZ",
                "receipt_date": "2024-08-15",
                "apple_id": "***REMOVED***",
                "subtotal": 29.99,
                "tax": 2.98,
                "total": 32.97,
                "items": [
                    {
                        "title": "Logic Pro",
                        "cost": 29.99
                    }
                ]
            },
            {
                "order_id": "ABCDEF123",
                "receipt_date": "2024-08-16",
                "apple_id": "erica_apple@***REMOVED***",
                "subtotal": 19.98,
                "tax": 1.98,
                "total": 21.96,
                "items": [
                    {
                        "title": "TestFlight",
                        "cost": 0.00
                    },
                    {
                        "title": "Productivity App",
                        "cost": 4.99
                    },
                    {
                        "title": "Game Add-on",
                        "cost": 14.99
                    }
                ]
            }
        ]

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_receipt_file(self, receipts, filename="test_receipts.json"):
        """Create a test Apple receipt JSON file."""
        filepath = os.path.join(self.temp_dir, filename)

        # Create directory structure
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(receipts, f, indent=2)

        return filepath

    def create_apple_exports_structure(self):
        """Create typical Apple exports directory structure."""
        # Create apple/exports structure
        apple_dir = os.path.join(self.temp_dir, 'apple')
        exports_dir = os.path.join(apple_dir, 'exports')
        os.makedirs(exports_dir, exist_ok=True)

        # Create multiple Apple ID directories
        karl_dir = os.path.join(exports_dir, '***REMOVED***')
        erica_dir = os.path.join(exports_dir, 'erica_apple@***REMOVED***')
        os.makedirs(karl_dir, exist_ok=True)
        os.makedirs(erica_dir, exist_ok=True)

        # Create receipt files for each account
        karl_receipts = [self.sample_receipts[0]]  # Karl's receipt
        erica_receipts = [self.sample_receipts[1]]  # Erica's receipt

        karl_file = os.path.join(karl_dir, '2024-08-20_apple_receipts.json')
        erica_file = os.path.join(erica_dir, '2024-08-21_apple_receipts.json')

        with open(karl_file, 'w', encoding='utf-8') as f:
            json.dump(karl_receipts, f, indent=2)

        with open(erica_file, 'w', encoding='utf-8') as f:
            json.dump(erica_receipts, f, indent=2)

        return apple_dir

    def test_load_single_receipt_file(self):
        """Test loading receipts from a single JSON file."""
        receipt_file = self.create_test_receipt_file(self.sample_receipts)

        loader = AppleReceiptLoader([receipt_file])
        receipts = loader.load_receipts()

        assert len(receipts) == 2
        assert receipts[0]['order_id'] == 'ML7PQ2XYZ'
        assert receipts[1]['order_id'] == 'ABCDEF123'

    def test_auto_discover_apple_exports(self):
        """Test automatic discovery of Apple export directories."""
        apple_dir = self.create_apple_exports_structure()

        loader = AppleReceiptLoader(apple_exports_dir=apple_dir)
        receipts = loader.load_receipts()

        assert len(receipts) == 2

        # Should have receipts from both accounts
        apple_ids = [receipt['apple_id'] for receipt in receipts]
        assert '***REMOVED***' in apple_ids
        assert 'erica_apple@***REMOVED***' in apple_ids

    def test_discover_apple_accounts(self):
        """Test discovery of Apple account directories."""
        apple_dir = self.create_apple_exports_structure()

        loader = AppleReceiptLoader(apple_exports_dir=apple_dir)
        accounts = loader.discover_apple_accounts()

        assert len(accounts) == 2
        assert '***REMOVED***' in accounts
        assert 'erica_apple@***REMOVED***' in accounts

    def test_load_most_recent_receipts_per_account(self):
        """Test loading most recent receipt file per account."""
        apple_dir = self.create_apple_exports_structure()

        # Create additional older receipt file for Karl
        karl_dir = os.path.join(apple_dir, 'exports', '***REMOVED***')
        older_file = os.path.join(karl_dir, '2024-08-10_apple_receipts.json')

        older_receipts = [{
            "order_id": "OLD123",
            "receipt_date": "2024-08-10",
            "apple_id": "***REMOVED***",
            "total": 9.99,
            "items": [{"title": "Old App", "cost": 9.99}]
        }]

        with open(older_file, 'w', encoding='utf-8') as f:
            json.dump(older_receipts, f, indent=2)

        loader = AppleReceiptLoader(apple_exports_dir=apple_dir)
        receipts = loader.load_receipts()

        # Should only load most recent file per account
        karl_receipts = [r for r in receipts if r['apple_id'] == '***REMOVED***']
        assert len(karl_receipts) == 1
        assert karl_receipts[0]['order_id'] == 'ML7PQ2XYZ'  # From newer file

    def test_receipt_data_validation(self):
        """Test validation of receipt data structure."""
        # Valid receipts should load
        valid_file = self.create_test_receipt_file(self.sample_receipts)
        loader = AppleReceiptLoader([valid_file])
        receipts = loader.load_receipts()
        assert len(receipts) == 2

        # Invalid receipts should be filtered out
        invalid_receipts = [
            {
                # Missing required fields
                "order_id": "INVALID1",
                "apple_id": "test@example.com"
                # Missing receipt_date, total, items
            },
            {
                # Valid receipt
                "order_id": "VALID1",
                "receipt_date": "2024-08-20",
                "apple_id": "test@example.com",
                "total": 9.99,
                "items": [{"title": "Valid App", "cost": 9.99}]
            }
        ]

        invalid_file = self.create_test_receipt_file(invalid_receipts, "invalid.json")
        loader_invalid = AppleReceiptLoader([invalid_file])
        receipts_filtered = loader_invalid.load_receipts()

        # Should only load valid receipt
        assert len(receipts_filtered) == 1
        assert receipts_filtered[0]['order_id'] == 'VALID1'

    def test_load_receipts_with_date_filtering(self):
        """Test loading receipts with date range filtering."""
        receipt_file = self.create_test_receipt_file(self.sample_receipts)

        # Filter to only receipts on or after 2024-08-16
        loader = AppleReceiptLoader([receipt_file], start_date='2024-08-16')
        receipts = loader.load_receipts()

        assert len(receipts) == 1
        assert receipts[0]['receipt_date'] == '2024-08-16'

        # Filter to only receipts before 2024-08-16
        loader_before = AppleReceiptLoader([receipt_file], end_date='2024-08-15')
        receipts_before = loader_before.load_receipts()

        assert len(receipts_before) == 1
        assert receipts_before[0]['receipt_date'] == '2024-08-15'

    def test_empty_directory_handling(self):
        """Test handling of empty or non-existent directories."""
        empty_dir = os.path.join(self.temp_dir, 'empty_apple')
        os.makedirs(empty_dir, exist_ok=True)

        loader = AppleReceiptLoader(apple_exports_dir=empty_dir)
        receipts = loader.load_receipts()

        assert len(receipts) == 0

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON files."""
        # Create file with invalid JSON
        malformed_file = os.path.join(self.temp_dir, 'malformed.json')
        with open(malformed_file, 'w', encoding='utf-8') as f:
            f.write('{ invalid json content }')

        loader = AppleReceiptLoader([malformed_file])
        receipts = loader.load_receipts()

        # Should handle gracefully and return empty list
        assert len(receipts) == 0

    def test_receipt_normalization(self):
        """Test that receipts are properly normalized during loading."""
        receipt_file = self.create_test_receipt_file(self.sample_receipts)

        loader = AppleReceiptLoader([receipt_file])
        receipts = loader.load_receipts()

        # Check that all expected fields are present
        for receipt in receipts:
            assert 'order_id' in receipt
            assert 'receipt_date' in receipt
            assert 'apple_id' in receipt
            assert 'total' in receipt
            assert 'items' in receipt
            assert isinstance(receipt['items'], list)

            # Check item structure
            for item in receipt['items']:
                assert 'title' in item
                assert 'cost' in item
                assert isinstance(item['cost'], (int, float))

    def test_multiple_file_sources(self):
        """Test loading from multiple explicit file sources."""
        # Create separate files
        file1 = self.create_test_receipt_file([self.sample_receipts[0]], "file1.json")
        file2 = self.create_test_receipt_file([self.sample_receipts[1]], "file2.json")

        loader = AppleReceiptLoader([file1, file2])
        receipts = loader.load_receipts()

        assert len(receipts) == 2

        # Should have receipts from both files
        order_ids = [receipt['order_id'] for receipt in receipts]
        assert 'ML7PQ2XYZ' in order_ids
        assert 'ABCDEF123' in order_ids

    def test_account_specific_loading(self):
        """Test loading receipts for specific Apple accounts only."""
        apple_dir = self.create_apple_exports_structure()

        # Load only Karl's receipts
        loader_karl = AppleReceiptLoader(
            apple_exports_dir=apple_dir,
            accounts=['***REMOVED***']
        )
        karl_receipts = loader_karl.load_receipts()

        assert len(karl_receipts) == 1
        assert karl_receipts[0]['apple_id'] == '***REMOVED***'

        # Load only Erica's receipts
        loader_erica = AppleReceiptLoader(
            apple_exports_dir=apple_dir,
            accounts=['erica_apple@***REMOVED***']
        )
        erica_receipts = loader_erica.load_receipts()

        assert len(erica_receipts) == 1
        assert erica_receipts[0]['apple_id'] == 'erica_apple@***REMOVED***'

    def test_receipt_sorting(self):
        """Test that receipts are sorted by date."""
        # Create receipts in non-chronological order
        unsorted_receipts = [
            {
                "order_id": "ORDER3",
                "receipt_date": "2024-08-20",
                "apple_id": "test@example.com",
                "total": 30.00,
                "items": []
            },
            {
                "order_id": "ORDER1",
                "receipt_date": "2024-08-15",
                "apple_id": "test@example.com",
                "total": 10.00,
                "items": []
            },
            {
                "order_id": "ORDER2",
                "receipt_date": "2024-08-18",
                "apple_id": "test@example.com",
                "total": 20.00,
                "items": []
            }
        ]

        receipt_file = self.create_test_receipt_file(unsorted_receipts)
        loader = AppleReceiptLoader([receipt_file])
        receipts = loader.load_receipts()

        # Should be sorted by date
        assert len(receipts) == 3
        assert receipts[0]['receipt_date'] == '2024-08-15'
        assert receipts[1]['receipt_date'] == '2024-08-18'
        assert receipts[2]['receipt_date'] == '2024-08-20'

    def test_duplicate_receipt_handling(self):
        """Test handling of duplicate receipts across files."""
        # Create duplicate receipt in different files
        duplicate_receipt = self.sample_receipts[0]  # Same order_id

        file1 = self.create_test_receipt_file([duplicate_receipt], "file1.json")
        file2 = self.create_test_receipt_file([duplicate_receipt], "file2.json")

        loader = AppleReceiptLoader([file1, file2])
        receipts = loader.load_receipts()

        # Should deduplicate based on order_id
        assert len(receipts) == 1
        assert receipts[0]['order_id'] == 'ML7PQ2XYZ'

    def test_receipt_statistics_generation(self):
        """Test generation of loading statistics."""
        apple_dir = self.create_apple_exports_structure()

        loader = AppleReceiptLoader(apple_exports_dir=apple_dir)
        receipts = loader.load_receipts()
        stats = loader.get_loading_statistics()

        assert 'total_receipts' in stats
        assert 'accounts_found' in stats
        assert 'files_processed' in stats
        assert 'date_range' in stats

        assert stats['total_receipts'] == 2
        assert stats['accounts_found'] == 2
        assert stats['files_processed'] == 2

    def test_file_pattern_matching(self):
        """Test that only receipt files matching expected patterns are loaded."""
        apple_dir = self.create_apple_exports_structure()

        # Create non-receipt file that should be ignored
        karl_dir = os.path.join(apple_dir, 'exports', '***REMOVED***')
        non_receipt_file = os.path.join(karl_dir, 'not_a_receipt.txt')

        with open(non_receipt_file, 'w') as f:
            f.write('This is not a receipt file')

        loader = AppleReceiptLoader(apple_exports_dir=apple_dir)
        receipts = loader.load_receipts()

        # Should still load only receipt JSON files
        assert len(receipts) == 2


if __name__ == '__main__':
    pytest.main([__file__])