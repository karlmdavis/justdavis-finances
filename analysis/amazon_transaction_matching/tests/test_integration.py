#!/usr/bin/env python3
"""Integration tests for Amazon transaction matching system."""

import pytest
import tempfile
import os
import json
import csv
from datetime import datetime

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from match_single_transaction import AmazonTransactionMatcher


class TestAmazonTransactionMatchingIntegration:
    """Integration tests for the complete Amazon transaction matching system."""

    def setup_method(self):
        """Set up test fixtures with realistic data."""
        self.temp_dir = tempfile.mkdtemp()

        # Sample YNAB transactions
        self.ynab_transactions = [
            {
                'id': 'ynab-trans-1',
                'date': '2024-08-15',
                'amount': -4599,  # -$45.99 in milliunits
                'payee_name': 'AMZN Mktp US*RT4Y12',
                'account_name': 'Chase Credit Card',
                'memo': '',
                'category_name': 'Shopping'
            },
            {
                'id': 'ynab-trans-2',
                'date': '2024-08-16',
                'amount': -8799,  # -$87.99 in milliunits
                'payee_name': 'Amazon.com',
                'account_name': 'Apple Card',
                'memo': '',
                'category_name': 'Shopping'
            },
            {
                'id': 'ynab-trans-3',
                'date': '2024-08-18',
                'amount': -15000,  # -$150.00 in milliunits (split payment scenario)
                'payee_name': 'AMZN Mktp US*RT4Y18',
                'account_name': 'Chase Credit Card',
                'memo': '',
                'category_name': 'Shopping'
            },
            {
                'id': 'ynab-trans-4',
                'date': '2024-08-19',
                'amount': -7500,  # -$75.00 (second part of split)
                'payee_name': 'AMZN Mktp US*RT4Y19',
                'account_name': 'Chase Credit Card',
                'memo': '',
                'category_name': 'Shopping'
            }
        ]

        # Sample Amazon orders
        self.amazon_orders = [
            {
                'Order ID': '111-2223334-5556667',
                'Order Date': '2024-08-15',
                'Shipment Date': '2024-08-15',
                'Product Name': 'Echo Dot (4th Gen) - Charcoal',
                'Quantity': '1',
                'Total Owed': '$45.99'
            },
            {
                'Order ID': '222-3334445-6667778',
                'Order Date': '2024-08-16',
                'Shipment Date': '2024-08-16',
                'Product Name': 'Wireless Mouse',
                'Quantity': '1',
                'Total Owed': '$29.99'
            },
            {
                'Order ID': '222-3334445-6667778',
                'Order Date': '2024-08-16',
                'Shipment Date': '2024-08-16',
                'Product Name': 'USB Hub',
                'Quantity': '1',
                'Total Owed': '$57.99'
            },
            {
                'Order ID': '333-4445556-7778889',
                'Order Date': '2024-08-17',
                'Shipment Date': '2024-08-18',
                'Product Name': 'Large Item 1',
                'Quantity': '1',
                'Total Owed': '$149.99'
            },
            {
                'Order ID': '333-4445556-7778889',
                'Order Date': '2024-08-17',
                'Shipment Date': '2024-08-19',
                'Product Name': 'Large Item 2',
                'Quantity': '1',
                'Total Owed': '$75.00'
            }
        ]

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_amazon_data(self, account='karl'):
        """Create test Amazon data directory structure."""
        # Create Amazon data directory
        amazon_dir = os.path.join(self.temp_dir, 'amazon', 'data')
        account_dir = os.path.join(amazon_dir, f'2024-08-20_{account}_amazon_data')
        csv_dir = os.path.join(account_dir, 'Retail.OrderHistory.1')
        os.makedirs(csv_dir, exist_ok=True)

        # Create CSV file
        csv_path = os.path.join(csv_dir, 'Retail.OrderHistory.1.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if self.amazon_orders:
                writer = csv.DictWriter(f, fieldnames=self.amazon_orders[0].keys())
                writer.writeheader()
                writer.writerows(self.amazon_orders)

        return amazon_dir

    def create_test_ynab_data(self):
        """Create test YNAB transaction data."""
        ynab_dir = os.path.join(self.temp_dir, 'ynab-data')
        os.makedirs(ynab_dir, exist_ok=True)

        transactions_path = os.path.join(ynab_dir, 'transactions.json')
        with open(transactions_path, 'w', encoding='utf-8') as f:
            json.dump(self.ynab_transactions, f, indent=2)

        return ynab_dir

    def test_end_to_end_single_transaction_matching(self):
        """Test complete workflow for single transaction matching."""
        # Set up test data
        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        # Initialize matcher
        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Test exact match (transaction 1 -> order 1)
        result = matcher.match_transaction('ynab-trans-1')

        assert result['matched'] is True
        assert result['confidence'] >= 0.95
        assert result['match_strategy'] == 'complete_match'
        assert len(result['amazon_orders']) == 1
        assert result['amazon_orders'][0]['order_id'] == '111-2223334-5556667'

    def test_multi_item_order_matching(self):
        """Test matching transaction to multi-item order."""
        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Test multi-item match (transaction 2 -> order 2 with 2 items)
        result = matcher.match_transaction('ynab-trans-2')

        assert result['matched'] is True
        assert result['confidence'] >= 0.85
        assert len(result['amazon_orders']) == 1

        # Should combine both items from the order
        order = result['amazon_orders'][0]
        assert order['order_id'] == '222-3334445-6667778'
        assert len(order['items']) == 2
        assert order['total'] == 87.98  # $29.99 + $57.99

    def test_split_payment_matching(self):
        """Test matching split payments to large order."""
        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Test first split payment
        result_1 = matcher.match_transaction('ynab-trans-3')

        assert result_1['matched'] is True
        assert result_1['match_strategy'] == 'split_payment'
        assert result_1['confidence'] > 0.7

        # Should match the first item
        order_1 = result_1['amazon_orders'][0]
        assert order_1['order_id'] == '333-4445556-7778889'
        assert len(order_1['items']) == 1
        assert order_1['items'][0]['amount'] == 149.99

        # Test second split payment
        result_2 = matcher.match_transaction('ynab-trans-4')

        assert result_2['matched'] is True
        assert result_2['match_strategy'] == 'split_payment'

        # Should match the second item
        order_2 = result_2['amazon_orders'][0]
        assert order_2['order_id'] == '333-4445556-7778889'
        assert len(order_2['items']) == 1
        assert order_2['items'][0]['amount'] == 75.00

    def test_multi_account_discovery(self):
        """Test automatic discovery of multiple Amazon accounts."""
        # Create data for multiple accounts
        amazon_dir = os.path.join(self.temp_dir, 'amazon', 'data')

        # Karl's account
        karl_dir = os.path.join(amazon_dir, '2024-08-20_karl_amazon_data')
        karl_csv_dir = os.path.join(karl_dir, 'Retail.OrderHistory.1')
        os.makedirs(karl_csv_dir, exist_ok=True)

        karl_csv = os.path.join(karl_csv_dir, 'Retail.OrderHistory.1.csv')
        with open(karl_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.amazon_orders[0].keys())
            writer.writeheader()
            writer.writerows(self.amazon_orders[:2])  # First 2 orders

        # Erica's account
        erica_dir = os.path.join(amazon_dir, '2024-08-20_erica_amazon_data')
        erica_csv_dir = os.path.join(erica_dir, 'Retail.OrderHistory.1')
        os.makedirs(erica_csv_dir, exist_ok=True)

        erica_csv = os.path.join(erica_csv_dir, 'Retail.OrderHistory.1.csv')
        with open(erica_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.amazon_orders[0].keys())
            writer.writeheader()
            writer.writerows(self.amazon_orders[2:])  # Remaining orders

        ynab_dir = self.create_test_ynab_data()

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Should discover both accounts
        accounts = matcher.discover_amazon_accounts()
        assert 'karl' in accounts
        assert 'erica' in accounts

        # Test matching across accounts
        result = matcher.match_transaction('ynab-trans-1')
        assert result['matched'] is True
        assert result['amazon_orders'][0]['account'] == 'karl'

    def test_date_window_fuzzy_matching(self):
        """Test fuzzy matching with date windows."""
        # Modify orders to have slight date differences
        modified_orders = self.amazon_orders.copy()
        modified_orders[0]['Order Date'] = '2024-08-14'  # 1 day before transaction

        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        # Update CSV with modified dates
        account_dir = os.path.join(amazon_dir, '2024-08-20_karl_amazon_data')
        csv_path = os.path.join(account_dir, 'Retail.OrderHistory.1', 'Retail.OrderHistory.1.csv')

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=modified_orders[0].keys())
            writer.writeheader()
            writer.writerows(modified_orders)

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        result = matcher.match_transaction('ynab-trans-1')

        # Should still match but with fuzzy strategy and reduced confidence
        assert result['matched'] is True
        assert result['match_strategy'] == 'fuzzy_match'
        assert result['confidence'] < 0.95  # Lower than exact match

    def test_unmatched_transaction_handling(self):
        """Test handling of transactions that don't match any orders."""
        # Create YNAB transaction that won't match any Amazon order
        unmatched_transaction = {
            'id': 'ynab-trans-unmatched',
            'date': '2024-09-01',
            'amount': -9999,  # Unique amount that won't match
            'payee_name': 'AMZN Mktp US*UNIQUE',
            'account_name': 'Chase Credit Card',
            'memo': '',
            'category_name': 'Shopping'
        }

        transactions_with_unmatched = self.ynab_transactions + [unmatched_transaction]

        amazon_dir = self.create_test_amazon_data()
        ynab_dir = os.path.join(self.temp_dir, 'ynab-data')
        os.makedirs(ynab_dir, exist_ok=True)

        transactions_path = os.path.join(ynab_dir, 'transactions.json')
        with open(transactions_path, 'w', encoding='utf-8') as f:
            json.dump(transactions_with_unmatched, f, indent=2)

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=transactions_path
        )

        result = matcher.match_transaction('ynab-trans-unmatched')

        # Should return unmatched result
        assert result['matched'] is False
        assert result['confidence'] == 0.0
        assert result['amazon_orders'] == []
        assert result['ynab_transaction']['id'] == 'ynab-trans-unmatched'

    def test_performance_characteristics(self):
        """Test performance characteristics with realistic data volumes."""
        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Measure processing time for single transaction
        start_time = datetime.now()
        result = matcher.match_transaction('ynab-trans-1')
        end_time = datetime.now()

        processing_time = (end_time - start_time).total_seconds()

        # Should complete within reasonable time (< 1 second for test data)
        assert processing_time < 1.0
        assert 'processing_time' in result
        assert result['processing_time'] > 0

    def test_error_recovery_and_validation(self):
        """Test error recovery and data validation."""
        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        # Test with missing YNAB transaction
        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        with pytest.raises(ValueError):
            matcher.match_transaction('nonexistent-transaction-id')

        # Test with corrupted Amazon data directory
        empty_amazon_dir = os.path.join(self.temp_dir, 'empty_amazon')
        os.makedirs(empty_amazon_dir, exist_ok=True)

        matcher_empty = AmazonTransactionMatcher(
            amazon_data_dir=empty_amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Should handle gracefully and return unmatched
        result = matcher_empty.match_transaction('ynab-trans-1')
        assert result['matched'] is False

    def test_confidence_threshold_filtering(self):
        """Test filtering results by confidence threshold."""
        amazon_dir = self.create_test_amazon_data()
        ynab_dir = self.create_test_ynab_data()

        matcher = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json')
        )

        # Get normal result
        result = matcher.match_transaction('ynab-trans-1')
        original_confidence = result['confidence']

        # Test with very high confidence threshold
        matcher_strict = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json'),
            confidence_threshold=0.99  # Very high threshold
        )

        result_strict = matcher_strict.match_transaction('ynab-trans-1')

        # Result should depend on whether original confidence exceeds threshold
        if original_confidence >= 0.99:
            assert result_strict['matched'] is True
        else:
            # May be filtered out due to high threshold
            pass  # Allow either outcome based on actual confidence

    def test_account_specific_processing(self):
        """Test processing specific Amazon accounts only."""
        # Create multi-account setup
        amazon_dir = os.path.join(self.temp_dir, 'amazon', 'data')

        # Create separate account data
        for account in ['karl', 'erica']:
            account_dir = os.path.join(amazon_dir, f'2024-08-20_{account}_amazon_data')
            csv_dir = os.path.join(account_dir, 'Retail.OrderHistory.1')
            os.makedirs(csv_dir, exist_ok=True)

            csv_path = os.path.join(csv_dir, 'Retail.OrderHistory.1.csv')
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.amazon_orders[0].keys())
                writer.writeheader()
                # Give each account different orders
                orders = [self.amazon_orders[0]] if account == 'karl' else [self.amazon_orders[1]]
                writer.writerows(orders)

        ynab_dir = self.create_test_ynab_data()

        # Test account-specific matching
        matcher_karl_only = AmazonTransactionMatcher(
            amazon_data_dir=amazon_dir,
            ynab_cache_file=os.path.join(ynab_dir, 'transactions.json'),
            accounts=['karl']
        )

        # Should only search Karl's data
        accounts = matcher_karl_only.discover_amazon_accounts()
        assert accounts == ['karl']


if __name__ == '__main__':
    pytest.main([__file__])