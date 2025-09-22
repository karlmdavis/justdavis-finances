"""
Pytest Configuration and Shared Fixtures

Provides common test fixtures and configuration for the entire test suite.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List
from decimal import Decimal


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_path:
        yield Path(temp_path)


@pytest.fixture
def sample_ynab_transaction() -> Dict[str, Any]:
    """Sample YNAB transaction for testing."""
    return {
        'id': 'test-transaction-123',
        'date': '2024-08-15',
        'amount': -45990,  # -$45.99 in milliunits
        'payee_name': 'AMZN Mktp US*TEST123',
        'account_name': 'Chase Credit Card',
        'category_name': 'Shopping',
        'memo': 'Test transaction',
        'subtransactions': []
    }


@pytest.fixture
def sample_amazon_order() -> Dict[str, Any]:
    """Sample Amazon order for testing."""
    return {
        'order_id': '111-2223334-5556667',
        'order_date': '2024-08-15',
        'ship_date': '2024-08-15',
        'total': 4599,  # $45.99 in cents
        'items': [
            {
                'name': 'Test Product',
                'quantity': 1,
                'amount': 4599,
                'asin': 'TEST123456'
            }
        ]
    }


@pytest.fixture
def sample_apple_receipt() -> Dict[str, Any]:
    """Sample Apple receipt for testing."""
    return {
        'order_id': 'ML7PQ2XYZ',
        'receipt_date': '2024-08-15',
        'apple_id': 'test@example.com',
        'subtotal': 29.99,
        'tax': 2.98,
        'total': 32.97,
        'items': [
            {
                'title': 'Test App',
                'cost': 29.99
            }
        ]
    }


@pytest.fixture
def currency_test_cases() -> List[Dict[str, Any]]:
    """Test cases for currency conversion functions."""
    return [
        {'input': '$45.99', 'cents': 4599, 'milliunits': 45990},
        {'input': '$0.00', 'cents': 0, 'milliunits': 0},
        {'input': '$1.00', 'cents': 100, 'milliunits': 1000},
        {'input': '$999.99', 'cents': 99999, 'milliunits': 999990},
    ]


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    # Ensure tests don't use production data
    monkeypatch.setenv('FINANCES_ENV', 'test')
    monkeypatch.setenv('FINANCES_DATA_DIR', '/tmp/test_finances_data')

    # Mock sensitive environment variables
    monkeypatch.setenv('YNAB_API_TOKEN', 'test-token')
    monkeypatch.setenv('EMAIL_PASSWORD', 'test-password')


# Test markers for categorizing tests
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for complete workflows"
    )
    config.addinivalue_line(
        "markers", "currency: Tests for currency handling and precision"
    )
    config.addinivalue_line(
        "markers", "amazon: Tests for Amazon transaction matching"
    )
    config.addinivalue_line(
        "markers", "apple: Tests for Apple receipt processing"
    )
    config.addinivalue_line(
        "markers", "ynab: Tests for YNAB integration"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take significant time to run"
    )