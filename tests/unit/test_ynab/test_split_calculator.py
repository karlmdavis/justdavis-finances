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
        transaction_amount = -19990  # $19.99 expense in milliunits
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
        assert splits[0]['memo'] == "Kindle Book: Project Hail Mary"

    @pytest.mark.ynab
    def test_multiple_items_split(self):
        """Test multiple items creates proper splits."""
        transaction_amount = -89900  # $89.90 expense in milliunits
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

        # Check individual split amounts (negative milliunits for expenses)
        assert splits[0]['amount'] == -45990  # $45.99
        assert splits[1]['amount'] == -23500  # $23.50
        assert splits[2]['amount'] == -20410  # $20.41

        # Check memos include quantity and price info
        # Check memos (quantity shown only if > 1)
        assert splits[0]['memo'] == 'Echo Dot (4th Gen) - Charcoal'
        assert splits[1]['memo'] == 'USB-C Cable 6ft - 2 Pack (qty: 2)'
        assert splits[2]['memo'] == 'Charging Stand'

        # Check total equals original transaction
        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount

    @pytest.mark.ynab
    def test_amount_mismatch_error(self):
        """Test error when item amounts don't match transaction total."""
        transaction_amount = -50000  # $50.00 in milliunits
        items = [
            {
                'name': 'Test Item',
                'amount': 3000,  # Only $30.00
                'quantity': 1,
                'unit_price': 3000
            }
        ]

        with pytest.raises(SplitCalculationError, match="doesn't match transaction"):
            calculate_amazon_splits(transaction_amount, items)

    @pytest.mark.ynab
    def test_tax_allocation(self):
        """Test proper tax allocation across items."""
        transaction_amount = -106500  # $106.50 including tax in milliunits
        items = [
            {
                'name': 'Item 1',
                'amount': 5325,  # $53.25 with tax included (cents)
                'quantity': 1,
                'unit_price': 5325
            },
            {
                'name': 'Item 2',
                'amount': 5325,  # $53.25 with tax included (cents)
                'quantity': 1,
                'unit_price': 5325
            }
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        # Tax should be allocated proportionally (already included in amounts)
        assert len(splits) == 2
        assert splits[0]['amount'] == -53250  # $53.25 in milliunits
        assert splits[1]['amount'] == -53250  # $53.25 in milliunits

        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount


class TestAppleSplitCalculation:
    """Test Apple transaction split calculation."""

    @pytest.mark.ynab
    def test_single_app_purchase(self):
        """Test single app purchase."""
        transaction_amount = -29990  # $29.99 in milliunits
        # Transform Apple receipt format to what split calculator expects
        items = [
            {
                'name': 'Procreate',
                'price': 2999  # $29.99 in cents
            }
        ]

        splits = calculate_apple_splits(transaction_amount, items)

        assert len(splits) == 1
        assert splits[0]['amount'] == transaction_amount
        assert 'Procreate' in splits[0]['memo']
        # Memo should contain the item title
        assert splits[0]['memo'] == 'Procreate'

    @pytest.mark.ynab
    def test_multiple_app_purchases(self):
        """Test multiple app purchases with different costs."""
        transaction_amount = -599960  # $599.96 in milliunits (299.99+199.99+49.99+49.99)
        # Transform Apple receipt format to what split calculator expects
        items = [
            {
                'name': 'Final Cut Pro',
                'price': 29999  # $299.99 in cents
            },
            {
                'name': 'Logic Pro',
                'price': 19999  # $199.99 in cents
            },
            {
                'name': 'Compressor',
                'price': 4999  # $49.99 in cents
            },
            {
                'name': 'Motion',
                'price': 4999  # $49.99 in cents
            }
        ]

        splits = calculate_apple_splits(transaction_amount, items)

        assert len(splits) == 4

        # Check amounts match costs (converted to negative milliunits)
        expected_amounts = [-299990, -199990, -49990, -49990]  # Correct milliunits
        actual_amounts = [split['amount'] for split in splits]
        assert actual_amounts == expected_amounts

    @pytest.mark.ynab
    def test_subscription_handling(self):
        """Test handling of subscription renewals."""
        transaction_amount = -9990  # $9.99 in milliunits
        # Transform Apple receipt format to what split calculator expects
        items = [
            {
                'name': 'Apple Music (Monthly)',
                'price': 999  # $9.99 in cents
            }
        ]

        splits = calculate_apple_splits(transaction_amount, items)

        assert len(splits) == 1
        assert 'subscription' in splits[0]['memo'].lower() or 'monthly' in splits[0]['memo'].lower()


class TestGenericSplitCalculation:
    """Test generic split calculation for other vendors."""

    @pytest.mark.ynab
    def test_even_split(self):
        """Test even split across categories."""
        transaction_amount = -60000  # $60.00 in milliunits
        items = [
            {'name': 'Groceries', 'amount': 2000},      # $20.00 in cents
            {'name': 'Household', 'amount': 2000},      # $20.00 in cents
            {'name': 'Personal Care', 'amount': 2000}   # $20.00 in cents
        ]

        splits = calculate_generic_splits(transaction_amount, items)

        assert len(splits) == 3
        # Should split evenly: $20.00 each in milliunits
        for split in splits:
            assert split['amount'] == -20000

        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount

    @pytest.mark.ynab
    def test_weighted_split(self):
        """Test weighted split with custom amounts."""
        transaction_amount = -100000  # $100.00 in milliunits
        items = [
            {'name': 'Groceries', 'amount': 6000},         # $60.00 in cents
            {'name': 'Household', 'amount': 2500},         # $25.00 in cents
            {'name': 'Personal Care', 'amount': 1500},     # $15.00 in cents
        ]

        splits = calculate_generic_splits(transaction_amount, items)

        assert len(splits) == 3
        assert splits[0]['amount'] == -60000   # $60.00 in milliunits
        assert splits[1]['amount'] == -25000   # $25.00 in milliunits
        assert splits[2]['amount'] == -15000   # $15.00 in milliunits

        total = sum(split['amount'] for split in splits)
        assert total == transaction_amount


class TestSplitValidation:
    """Test split calculation validation."""

    @pytest.mark.ynab
    def test_validate_split_calculation(self):
        """Test split validation function."""
        splits = [
            {'amount': -20000, 'memo': 'Item 1'},  # $20.00 in milliunits
            {'amount': -30000, 'memo': 'Item 2'},  # $30.00 in milliunits
        ]

        # Valid split
        is_valid, _ = validate_split_calculation(splits, -50000)
        assert is_valid is True

        # Invalid split (doesn't sum to total)
        is_valid, _ = validate_split_calculation(splits, -60000)
        assert is_valid is False

        # With tolerance
        is_valid, _ = validate_split_calculation(splits, -50050, tolerance=100)
        assert is_valid is True

    @pytest.mark.ynab
    def test_split_sorting(self):
        """Test split sorting for consistent order."""
        splits = [
            {'amount': -10000, 'memo': 'B Item'},  # $10.00 in milliunits
            {'amount': -30000, 'memo': 'A Item'},  # $30.00 in milliunits
            {'amount': -20000, 'memo': 'C Item'},  # $20.00 in milliunits
        ]

        sorted_splits = sort_splits_for_stability(splits)

        # Should be sorted by amount (descending absolute value)
        amounts = [split['amount'] for split in sorted_splits]
        assert amounts == [-30000, -20000, -10000]

    @pytest.mark.ynab
    def test_split_summary(self):
        """Test split summary generation."""
        splits = [
            {'amount': -20000, 'memo': 'Item 1', 'category': 'Shopping'},      # $20.00 in milliunits
            {'amount': -30000, 'memo': 'Item 2', 'category': 'Electronics'},   # $30.00 in milliunits
        ]

        summary = create_split_summary(splits)

        assert summary['total_amount'] == -50000
        assert summary['split_count'] == 2


class TestSplitErrorHandling:
    """Test error handling in split calculations."""

    @pytest.mark.ynab
    def test_empty_items_error(self):
        """Test handling of empty items list."""
        # Empty items list should return empty splits list, which then fails validation
        with pytest.raises(SplitCalculationError, match="doesn't match transaction"):
            calculate_amazon_splits(-10000, [])

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

        # Missing 'amount' field will cause KeyError
        with pytest.raises(KeyError):
            calculate_amazon_splits(-10000, items)

    @pytest.mark.ynab
    def test_zero_transaction_amount(self):
        """Test handling of zero transaction amount."""
        # Zero transaction amount with non-zero items will fail validation
        with pytest.raises(SplitCalculationError, match="doesn't match transaction"):
            calculate_amazon_splits(0, [{'name': 'Test', 'amount': 100}])

    @pytest.mark.ynab
    def test_negative_item_amounts(self):
        """Test handling of negative item amounts."""
        items = [
            {
                'name': 'Refund Item',
                'amount': -1000,  # -$10.00 in cents (refund)
                'quantity': 1,
            }
        ]

        # Should handle refunds gracefully
        splits = calculate_amazon_splits(10000, items)  # $10.00 positive transaction for refund in milliunits
        assert len(splits) == 1
        assert splits[0]['amount'] == 10000  # Positive milliunits for refund


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