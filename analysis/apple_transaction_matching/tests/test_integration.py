#!/usr/bin/env python3
"""Integration tests for Apple transaction matching system."""

import pytest
import tempfile
import os
import json

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from match_single_transaction import AppleTransactionMatcher


class TestAppleTransactionMatchingIntegration:
    """Integration tests for the complete Apple transaction matching system."""

    def setup_method(self):
        """Set up test fixtures with realistic data."""
        self.temp_dir = tempfile.mkdtemp()

        # Sample YNAB transactions
        self.ynab_transactions = [
            {
                'id': 'ynab-apple-1',
                'date': '2024-08-15',
                'amount': -32970,  # -$32.97 in milliunits
                'payee_name': 'APPLE.COM/BILL',
                'account_name': 'Apple Card',
                'memo': '',
                'category_name': 'Software',
                'approved': False
            },
            {
                'id': 'ynab-apple-2',
                'date': '2024-08-17',  # 1 day after receipt
                'amount': -21960,  # -$21.96 in milliunits
                'payee_name': 'Apple Services',
                'account_name': 'Chase Credit Card',
                'memo': '',
                'category_name': 'Entertainment',
                'approved': False
            },
            {
                'id': 'ynab-apple-3',
                'date': '2024-08-20',
                'amount': -9990,  # -$9.99 - no matching receipt
                'payee_name': 'APPLE.COM/BILL',
                'account_name': 'Apple Card',
                'memo': '',
                'category_name': 'Software',
                'approved': False
            },
            {
                'id': 'ynab-non-apple',
                'date': '2024-08-15',
                'amount': -4599,  # Non-Apple transaction
                'payee_name': 'Amazon.com',
                'account_name': 'Chase Credit Card',
                'memo': '',
                'category_name': 'Shopping',
                'approved': False
            }
        ]

        # Sample Apple receipts
        self.apple_receipts_karl = [
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
            }
        ]

        self.apple_receipts_erica = [
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

    def create_test_apple_data(self):
        """Create test Apple receipt data directory structure."""
        # Create apple/exports structure
        apple_dir = os.path.join(self.temp_dir, 'apple')
        exports_dir = os.path.join(apple_dir, 'exports')
        os.makedirs(exports_dir, exist_ok=True)

        # Create Karl's receipt directory
        karl_dir = os.path.join(exports_dir, '***REMOVED***')
        os.makedirs(karl_dir, exist_ok=True)
        karl_file = os.path.join(karl_dir, '2024-08-20_apple_receipts.json')
        with open(karl_file, 'w', encoding='utf-8') as f:
            json.dump(self.apple_receipts_karl, f, indent=2)

        # Create Erica's receipt directory
        erica_dir = os.path.join(exports_dir, 'erica_apple@***REMOVED***')
        os.makedirs(erica_dir, exist_ok=True)
        erica_file = os.path.join(erica_dir, '2024-08-21_apple_receipts.json')
        with open(erica_file, 'w', encoding='utf-8') as f:
            json.dump(self.apple_receipts_erica, f, indent=2)

        return apple_dir

    def create_test_ynab_data(self):
        """Create test YNAB transaction data."""
        ynab_dir = os.path.join(self.temp_dir, 'ynab-data')
        os.makedirs(ynab_dir, exist_ok=True)

        transactions_path = os.path.join(ynab_dir, 'transactions.json')
        with open(transactions_path, 'w', encoding='utf-8') as f:
            json.dump(self.ynab_transactions, f, indent=2)

        return ynab_dir

    def test_end_to_end_exact_match(self):
        """Test complete workflow for exact date/amount match."""
        # Set up test data
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        # Initialize matcher
        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Test exact match (transaction 1 -> Karl's receipt)
        result = matcher.match_transaction('ynab-apple-1')

        assert result['matched'] is True
        assert result['confidence'] == 1.0
        assert result['match_strategy'] == 'exact_match'
        assert len(result['apple_receipts']) == 1

        receipt = result['apple_receipts'][0]
        assert receipt['order_id'] == 'ML7PQ2XYZ'
        assert receipt['apple_id'] == '***REMOVED***'
        assert receipt['total'] == 32.97

    def test_date_window_matching(self):
        """Test matching transaction within date window."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Test date window match (transaction 2 -> Erica's receipt, 1 day difference)
        result = matcher.match_transaction('ynab-apple-2')

        assert result['matched'] is True
        assert result['match_strategy'] == 'date_window_match'
        assert 0.85 <= result['confidence'] <= 0.95  # High confidence for 1-day difference

        receipt = result['apple_receipts'][0]
        assert receipt['order_id'] == 'ABCDEF123'
        assert receipt['apple_id'] == 'erica_apple@***REMOVED***'
        assert len(receipt['items']) == 3  # Multi-item receipt

    def test_multi_apple_id_discovery(self):
        """Test automatic discovery of multiple Apple IDs."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Should discover both Apple accounts
        accounts = matcher.discover_apple_accounts()
        assert len(accounts) == 2
        assert '***REMOVED***' in accounts
        assert 'erica_apple@***REMOVED***' in accounts

        # Should load receipts from both accounts
        all_receipts = matcher.load_all_receipts()
        assert len(all_receipts) == 2

        apple_ids = [receipt['apple_id'] for receipt in all_receipts]
        assert '***REMOVED***' in apple_ids
        assert 'erica_apple@***REMOVED***' in apple_ids

    def test_unmatched_transaction_handling(self):
        """Test handling of transactions with no matching receipts."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Test unmatched transaction (different amount, no matching receipt)
        result = matcher.match_transaction('ynab-apple-3')

        assert result['matched'] is False
        assert result['confidence'] == 0.0
        assert result['apple_receipts'] == []
        assert result['ynab_transaction']['id'] == 'ynab-apple-3'

    def test_non_apple_transaction_filtering(self):
        """Test that non-Apple transactions are properly filtered."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Should filter Apple transactions only
        apple_transactions = matcher.filter_apple_transactions()
        assert len(apple_transactions) == 3  # 3 Apple transactions out of 4 total

        payee_names = [t['payee_name'] for t in apple_transactions]
        assert 'Amazon.com' not in payee_names
        assert any('APPLE' in name.upper() for name in payee_names)

    def test_batch_processing_workflow(self):
        """Test batch processing of multiple transactions."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Process all Apple transactions
        results = []
        apple_transactions = matcher.filter_apple_transactions()

        for transaction in apple_transactions:
            result = matcher.match_transaction(transaction['id'])
            results.append(result)

        # Should have results for all 3 Apple transactions
        assert len(results) == 3

        # Check match success rate
        matched_results = [r for r in results if r['matched']]
        assert len(matched_results) == 2  # 2 out of 3 should match

        # Verify specific matches
        transaction_1_result = next(r for r in results if r['ynab_transaction']['id'] == 'ynab-apple-1')
        assert transaction_1_result['matched'] is True
        assert transaction_1_result['confidence'] == 1.0

        transaction_2_result = next(r for r in results if r['ynab_transaction']['id'] == 'ynab-apple-2')
        assert transaction_2_result['matched'] is True
        assert transaction_2_result['confidence'] < 1.0  # Date window match

    def test_confidence_threshold_filtering(self):
        """Test filtering results by confidence threshold."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        # Create matcher with high confidence threshold
        matcher_strict = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json'),
            confidence_threshold=0.95
        )

        # Exact match should pass threshold
        exact_result = matcher_strict.match_transaction('ynab-apple-1')
        assert exact_result['matched'] is True
        assert exact_result['confidence'] >= 0.95

        # Date window match might not pass strict threshold
        window_result = matcher_strict.match_transaction('ynab-apple-2')
        # Result depends on actual confidence score for 1-day difference

    def test_account_specific_processing(self):
        """Test processing specific Apple accounts only."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        # Test Karl's account only
        matcher_karl = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json'),
            accounts=['***REMOVED***']
        )

        receipts_karl = matcher_karl.load_all_receipts()
        assert len(receipts_karl) == 1
        assert receipts_karl[0]['apple_id'] == '***REMOVED***'

        # Test Erica's account only
        matcher_erica = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json'),
            accounts=['erica_apple@***REMOVED***']
        )

        receipts_erica = matcher_erica.load_all_receipts()
        assert len(receipts_erica) == 1
        assert receipts_erica[0]['apple_id'] == 'erica_apple@***REMOVED***'

    def test_zero_cost_items_preservation(self):
        """Test that zero-cost items are preserved in match results."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Match transaction with Erica's multi-item receipt (includes free TestFlight)
        result = matcher.match_transaction('ynab-apple-2')

        assert result['matched'] is True
        receipt = result['apple_receipts'][0]

        # Should preserve all items including free ones
        assert len(receipt['items']) == 3

        item_costs = [item['cost'] for item in receipt['items']]
        assert 0.00 in item_costs  # Free TestFlight
        assert 4.99 in item_costs  # Productivity App
        assert 14.99 in item_costs  # Game Add-on

        item_titles = [item['title'] for item in receipt['items']]
        assert 'TestFlight' in item_titles

    def test_error_recovery_missing_data(self):
        """Test error recovery with missing data files."""
        # Create incomplete Apple data structure
        apple_dir = os.path.join(self.temp_dir, 'apple')
        os.makedirs(apple_dir, exist_ok=True)
        # Exports directory exists but is empty

        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Should handle gracefully
        accounts = matcher.discover_apple_accounts()
        assert len(accounts) == 0

        receipts = matcher.load_all_receipts()
        assert len(receipts) == 0

        # Matching should return unmatched results
        result = matcher.match_transaction('ynab-apple-1')
        assert result['matched'] is False

    def test_invalid_transaction_id_handling(self):
        """Test handling of invalid transaction IDs."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Should raise appropriate error for non-existent transaction
        with pytest.raises(ValueError):
            matcher.match_transaction('nonexistent-transaction-id')

    def test_performance_characteristics(self):
        """Test performance characteristics with realistic data."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Measure processing time
        import time
        start_time = time.time()

        result = matcher.match_transaction('ynab-apple-1')

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete quickly (< 0.1 seconds for test data)
        assert processing_time < 0.1
        assert 'processing_time' in result
        assert result['processing_time'] > 0

    def test_date_range_filtering_integration(self):
        """Test integration with date range filtering."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        # Create matcher with date filtering
        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json'),
            start_date='2024-08-16'  # Only include receipts from Aug 16 onward
        )

        # Should only load Erica's receipt (Aug 16), not Karl's (Aug 15)
        receipts = matcher.load_all_receipts()
        assert len(receipts) == 1
        assert receipts[0]['apple_id'] == 'erica_apple@***REMOVED***'

        # Karl's transaction should not match (receipt filtered out)
        result_karl = matcher.match_transaction('ynab-apple-1')
        assert result_karl['matched'] is False

        # Erica's transaction should still match
        result_erica = matcher.match_transaction('ynab-apple-2')
        assert result_erica['matched'] is True

    def test_tax_and_subtotal_preservation(self):
        """Test that tax and subtotal information is preserved."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        result = matcher.match_transaction('ynab-apple-1')

        assert result['matched'] is True
        receipt = result['apple_receipts'][0]

        # Tax and subtotal should be preserved
        assert receipt['subtotal'] == 29.99
        assert receipt['tax'] == 2.98
        assert receipt['total'] == 32.97

    def test_result_structure_validation(self):
        """Test that match results have correct structure."""
        apple_dir = self.create_test_apple_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AppleTransactionMatcher(
            apple_exports_dir=apple_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        result = matcher.match_transaction('ynab-apple-1')

        # Verify required top-level fields
        required_fields = [
            'ynab_transaction', 'matched', 'apple_receipts',
            'confidence', 'match_strategy', 'processing_time'
        ]

        for field in required_fields:
            assert field in result

        # Verify YNAB transaction structure
        ynab_tx = result['ynab_transaction']
        assert 'id' in ynab_tx
        assert 'date' in ynab_tx
        assert 'amount' in ynab_tx
        assert 'payee_name' in ynab_tx

        # Verify Apple receipt structure (if matched)
        if result['matched']:
            receipt = result['apple_receipts'][0]
            assert 'order_id' in receipt
            assert 'receipt_date' in receipt
            assert 'apple_id' in receipt
            assert 'total' in receipt
            assert 'items' in receipt


if __name__ == '__main__':
    pytest.main([__file__])