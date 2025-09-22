#!/usr/bin/env python3
"""Tests for YNAB split calculation module."""

import pytest
from finances.ynab import (
    calculate_amazon_splits,
    calculate_apple_splits,
    calculate_generic_splits,
    validate_split_calculation,
    sort_splits_for_stability,
    create_split_summary,
    SplitCalculationError,
)


class TestAmazonSplitCalculation:
    """Test Amazon transaction split calculation."""

    @pytest.mark.ynab
    def test_single_item_no_split(self):
        """Test single item returns memo update only."""
        transaction_amount = -1999  # $19.99 expense
        items = [
            {
                'name': 'Kindle Book: Project Hail Mary',
                'amount': 1999,
                'quantity': 1,
                'unit_price': 1999
            }
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        assert len(splits) == 1
        assert splits[0]['amount'] == transaction_amount
        assert splits[0]['memo'] == "Kindle Book: Project Hail Mary (1x @ $19.99)"

    @pytest.mark.ynab
    def test_multiple_items_split(self):
        """Test multiple items creates proper splits."""
        transaction_amount = -8990  # $89.90 expense
        items = [
            {
                'name': 'Echo Dot (4th Gen) - Charcoal',
                'amount': 4599,  # $45.99
                'quantity': 1,
                'unit_price': 4599
            },
            {
                'name': 'USB-C Cable 6ft - 2 Pack',
                'amount': 2350,  # $23.50
                'quantity': 2,
                'unit_price': 1175
            },
            {
                'name': 'Charging Stand',
                'amount': 2041,  # $20.41
                'quantity': 1,
                'unit_price': 2041
            }
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        assert len(splits) == 3

        # Check individual split amounts (negative for expenses)
        assert splits[0]['amount'] == -4599
        assert splits[1]['amount'] == -2350
        assert splits[2]['amount'] == -2041

        # Check memos include quantity and price info
        assert "1x @ $45.99" in splits[0]['memo']
        assert "2x @ $11.75" in splits[1]['memo']
        assert "1x @ $20.41" in splits[2]['memo']

        # Check total equals original transaction
        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount

    @pytest.mark.ynab
    def test_amount_mismatch_error(self):
        """Test error when item amounts don't match transaction total."""
        transaction_amount = -5000  # $50.00
        items = [
            {
                'name': 'Test Item',
                'amount': 3000,  # Only $30.00
                'quantity': 1,
                'unit_price': 3000
            }
        ]

        with pytest.raises(SplitCalculationError, match="Amount mismatch"):
            calculate_amazon_splits(transaction_amount, items)

    @pytest.mark.ynab
    def test_tax_allocation(self):
        """Test proper tax allocation across items."""
        transaction_amount = -10650  # $106.50 including tax
        items = [
            {
                'name': 'Item 1',
                'amount': 5000,  # $50.00 pre-tax
                'quantity': 1,
                'unit_price': 5000
            },
            {
                'name': 'Item 2',
                'amount': 5000,  # $50.00 pre-tax
                'quantity': 1,
                'unit_price': 5000
            }
        ]
        tax_amount = 650  # $6.50 tax

        splits = calculate_amazon_splits(transaction_amount, items, tax_amount=tax_amount)

        # Tax should be allocated proportionally
        assert len(splits) == 2
        assert splits[0]['amount'] == -5325  # $50.00 + $3.25 tax
        assert splits[1]['amount'] == -5325  # $50.00 + $3.25 tax

        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount


class TestAppleSplitCalculation:
    """Test Apple transaction split calculation."""

    @pytest.mark.ynab
    def test_single_app_purchase(self):
        """Test single app purchase."""
        transaction_amount = -2999  # $29.99
        receipt_data = {
            'items': [
                {
                    'title': 'Procreate',
                    'cost': 29.99
                }
            ],
            'apple_id': 'test@example.com'
        }

        splits = calculate_apple_splits(transaction_amount, receipt_data)

        assert len(splits) == 1
        assert splits[0]['amount'] == transaction_amount
        assert 'Procreate' in splits[0]['memo']
        assert 'test@example.com' in splits[0]['memo']

    @pytest.mark.ynab
    def test_multiple_app_purchases(self):
        """Test multiple app purchases with different costs."""
        transaction_amount = -7996  # $79.96
        receipt_data = {
            'items': [
                {
                    'title': 'Final Cut Pro',
                    'cost': 299.99
                },
                {
                    'title': 'Logic Pro',
                    'cost': 199.99
                },
                {
                    'title': 'Compressor',
                    'cost': 49.99
                },
                {
                    'title': 'Motion',
                    'cost': 49.99
                }
            ],
            'apple_id': 'test@example.com'
        }

        splits = calculate_apple_splits(transaction_amount, receipt_data)

        assert len(splits) == 4

        # Check amounts match costs (converted to negative milliunits)
        expected_amounts = [-29999, -19999, -4999, -4999]
        actual_amounts = [split['amount'] for split in splits]
        assert actual_amounts == expected_amounts

    @pytest.mark.ynab
    def test_subscription_handling(self):
        """Test handling of subscription renewals."""
        transaction_amount = -999  # $9.99
        receipt_data = {
            'items': [
                {
                    'title': 'Apple Music (Monthly)',
                    'cost': 9.99,
                    'subscription': True
                }
            ],
            'apple_id': 'test@example.com'
        }

        splits = calculate_apple_splits(transaction_amount, receipt_data)

        assert len(splits) == 1
        assert 'subscription' in splits[0]['memo'].lower() or 'monthly' in splits[0]['memo'].lower()


class TestGenericSplitCalculation:
    """Test generic split calculation for other vendors."""

    @pytest.mark.ynab
    def test_even_split(self):
        """Test even split across categories."""
        transaction_amount = -6000  # $60.00
        categories = ['Groceries', 'Household', 'Personal Care']

        splits = calculate_generic_splits(transaction_amount, categories)

        assert len(splits) == 3
        # Should split evenly: $20.00 each
        for split in splits:
            assert split['amount'] == -2000

        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount

    @pytest.mark.ynab
    def test_weighted_split(self):
        """Test weighted split with custom amounts."""
        transaction_amount = -10000  # $100.00
        split_config = [
            {'category': 'Groceries', 'amount': 6000},      # $60.00
            {'category': 'Household', 'amount': 2500},      # $25.00
            {'category': 'Personal Care', 'amount': 1500},  # $15.00
        ]

        splits = calculate_generic_splits(transaction_amount, split_config, weighted=True)

        assert len(splits) == 3
        assert splits[0]['amount'] == -6000
        assert splits[1]['amount'] == -2500
        assert splits[2]['amount'] == -1500

        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount


class TestSplitValidation:
    """Test split calculation validation."""

    @pytest.mark.ynab
    def test_validate_split_calculation(self):
        """Test split validation function."""
        splits = [
            {'amount': -2000, 'memo': 'Item 1'},
            {'amount': -3000, 'memo': 'Item 2'},
        ]

        # Valid split
        assert validate_split_calculation(splits, -5000) is True

        # Invalid split (doesn't sum to total)
        assert validate_split_calculation(splits, -6000) is False

        # With tolerance
        assert validate_split_calculation(splits, -5005, tolerance=10) is True

    @pytest.mark.ynab
    def test_split_sorting(self):
        """Test split sorting for consistent order."""
        splits = [
            {'amount': -1000, 'memo': 'B Item'},
            {'amount': -3000, 'memo': 'A Item'},
            {'amount': -2000, 'memo': 'C Item'},
        ]

        sorted_splits = sort_splits_for_stability(splits)

        # Should be sorted by amount (descending absolute value)
        amounts = [split['amount'] for split in sorted_splits]
        assert amounts == [-3000, -2000, -1000]

    @pytest.mark.ynab
    def test_split_summary(self):
        """Test split summary generation."""
        splits = [
            {'amount': -2000, 'memo': 'Item 1', 'category': 'Shopping'},
            {'amount': -3000, 'memo': 'Item 2', 'category': 'Electronics'},
        ]

        summary = create_split_summary(splits)

        assert summary['total_amount'] == -5000
        assert summary['split_count'] == 2
        assert len(summary['categories']) == 2
        assert 'Shopping' in summary['categories']
        assert 'Electronics' in summary['categories']


class TestSplitErrorHandling:
    """Test error handling in split calculations."""

    @pytest.mark.ynab
    def test_empty_items_error(self):
        """Test error with empty items list."""
        with pytest.raises(SplitCalculationError, match="No items provided"):
            calculate_amazon_splits(-1000, [])

    @pytest.mark.ynab
    def test_missing_required_fields(self):
        """Test error with missing required item fields."""
        items = [
            {
                'name': 'Test Item',
                # Missing amount field
                'quantity': 1,
            }
        ]

        with pytest.raises(SplitCalculationError, match="Missing required field"):
            calculate_amazon_splits(-1000, items)

    @pytest.mark.ynab
    def test_zero_transaction_amount(self):
        """Test handling of zero transaction amount."""
        with pytest.raises(SplitCalculationError, match="Transaction amount cannot be zero"):
            calculate_amazon_splits(0, [{'name': 'Test', 'amount': 100}])

    @pytest.mark.ynab
    def test_negative_item_amounts(self):
        """Test handling of negative item amounts."""
        items = [
            {
                'name': 'Refund Item',
                'amount': -1000,  # Negative amount
                'quantity': 1,
            }
        ]

        # Should handle refunds gracefully
        splits = calculate_amazon_splits(1000, items)  # Positive transaction for refund
        assert len(splits) == 1
        assert splits[0]['amount'] == 1000


@pytest.mark.ynab
def test_integration_with_fixtures(sample_ynab_transaction, sample_amazon_order):
    """Test split calculation with fixture data."""
    transaction_amount = sample_ynab_transaction['amount']
    items = sample_amazon_order['items']

    # Convert order format to items format expected by calculator
    formatted_items = []
    for item in items:
        formatted_items.append({
            'name': item['name'],
            'amount': item['amount'],
            'quantity': item['quantity'],
            'unit_price': item['amount'] // item['quantity']
        })

    splits = calculate_amazon_splits(transaction_amount, formatted_items)

    assert len(splits) >= 1
    total = sum(split['amount'] for split in splits)
    assert total == transaction_amount