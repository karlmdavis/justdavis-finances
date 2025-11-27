"""
Comprehensive integration tests for Apple parser using realistic HTML samples.

Tests ALL fields for each sample and reports comprehensive failure list.
Uses realistic HTML structure with sanitized test data.
"""

from pathlib import Path

import pytest

from finances.apple.parser import AppleReceiptParser
from tests.fixtures.apple.modern_format_samples import MODERN_SAMPLES
from tests.fixtures.apple.table_format_samples import TABLE_SAMPLES


class TestAppleParserComprehensive:
    """Comprehensive parser tests with realistic HTML samples and full field validation."""

    @pytest.mark.parametrize("sample", TABLE_SAMPLES)
    def test_table_format_parsing(self, sample):
        """Test table_format (2020-era) receipt parsing with ALL field validation."""
        # Arrange
        html_path = Path("tests/fixtures/apple/html") / sample["html_filename"]
        expected = sample["expected"]
        failures = []

        # Act
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        parser = AppleReceiptParser()
        receipt = parser.parse_html_content(html_content)

        # Assert ALL fields and collect failures
        if receipt.format_detected != expected["format_detected"]:
            failures.append(
                f"format_detected: expected '{expected['format_detected']}', "
                f"got '{receipt.format_detected}'"
            )

        if receipt.apple_id != expected["apple_id"]:
            failures.append(f"apple_id: expected '{expected['apple_id']}', " f"got '{receipt.apple_id}'")

        if receipt.receipt_date != expected["receipt_date"]:
            failures.append(
                f"receipt_date: expected {expected['receipt_date']}, " f"got {receipt.receipt_date}"
            )

        if receipt.order_id != expected["order_id"]:
            failures.append(f"order_id: expected '{expected['order_id']}', " f"got '{receipt.order_id}'")

        if receipt.document_number != expected["document_number"]:
            failures.append(
                f"document_number: expected '{expected['document_number']}', "
                f"got '{receipt.document_number}'"
            )

        if receipt.subtotal != expected["subtotal"]:
            failures.append(f"subtotal: expected {expected['subtotal']}, " f"got {receipt.subtotal}")

        if receipt.tax != expected["tax"]:
            failures.append(f"tax: expected {expected['tax']}, got {receipt.tax}")

        if receipt.total != expected["total"]:
            failures.append(f"total: expected {expected['total']}, got {receipt.total}")

        if len(receipt.items) != len(expected["items"]):
            failures.append(f"items length: expected {len(expected['items'])}, " f"got {len(receipt.items)}")
        else:
            # Check each item
            for i, (actual_item, expected_item) in enumerate(
                zip(receipt.items, expected["items"], strict=False)
            ):
                if expected_item["title"] not in actual_item.title:
                    failures.append(
                        f"items[{i}].title: expected to contain "
                        f"'{expected_item['title']}', got '{actual_item.title}'"
                    )

                if actual_item.cost != expected_item["cost"]:
                    failures.append(
                        f"items[{i}].cost: expected {expected_item['cost']}, " f"got {actual_item.cost}"
                    )

                if actual_item.quantity != expected_item["quantity"]:
                    failures.append(
                        f"items[{i}].quantity: expected {expected_item['quantity']}, "
                        f"got {actual_item.quantity}"
                    )

                if actual_item.subscription != expected_item["subscription"]:
                    failures.append(
                        f"items[{i}].subscription: expected {expected_item['subscription']}, "
                        f"got {actual_item.subscription}"
                    )

        # Report ALL failures at once
        if failures:
            failure_report = "\n".join([f"  - {f}" for f in failures])
            pytest.fail(
                f"\n{len(failures)} field(s) failed for {sample['html_filename']}:\n" f"{failure_report}"
            )

    @pytest.mark.parametrize("sample", MODERN_SAMPLES)
    def test_modern_format_parsing(self, sample):
        """Test modern_format (2025+) receipt parsing with ALL field validation."""
        # Arrange
        html_path = Path("tests/fixtures/apple/html") / sample["html_filename"]
        expected = sample["expected"]
        failures = []

        # Act
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        parser = AppleReceiptParser()
        receipt = parser.parse_html_content(html_content)

        # Assert ALL fields and collect failures (same as table_format test)
        if receipt.format_detected != expected["format_detected"]:
            failures.append(
                f"format_detected: expected '{expected['format_detected']}', "
                f"got '{receipt.format_detected}'"
            )

        if receipt.apple_id != expected["apple_id"]:
            failures.append(f"apple_id: expected '{expected['apple_id']}', " f"got '{receipt.apple_id}'")

        if receipt.receipt_date != expected["receipt_date"]:
            failures.append(
                f"receipt_date: expected {expected['receipt_date']}, " f"got {receipt.receipt_date}"
            )

        if receipt.order_id != expected["order_id"]:
            failures.append(f"order_id: expected '{expected['order_id']}', " f"got '{receipt.order_id}'")

        if receipt.document_number != expected["document_number"]:
            failures.append(
                f"document_number: expected '{expected['document_number']}', "
                f"got '{receipt.document_number}'"
            )

        if receipt.subtotal != expected["subtotal"]:
            failures.append(f"subtotal: expected {expected['subtotal']}, " f"got {receipt.subtotal}")

        if receipt.tax != expected["tax"]:
            failures.append(f"tax: expected {expected['tax']}, got {receipt.tax}")

        if receipt.total != expected["total"]:
            failures.append(f"total: expected {expected['total']}, got {receipt.total}")

        if len(receipt.items) != len(expected["items"]):
            failures.append(f"items length: expected {len(expected['items'])}, " f"got {len(receipt.items)}")
        else:
            # Check each item
            for i, (actual_item, expected_item) in enumerate(
                zip(receipt.items, expected["items"], strict=False)
            ):
                if expected_item["title"] not in actual_item.title:
                    failures.append(
                        f"items[{i}].title: expected to contain "
                        f"'{expected_item['title']}', got '{actual_item.title}'"
                    )

                if actual_item.cost != expected_item["cost"]:
                    failures.append(
                        f"items[{i}].cost: expected {expected_item['cost']}, " f"got {actual_item.cost}"
                    )

                if actual_item.quantity != expected_item["quantity"]:
                    failures.append(
                        f"items[{i}].quantity: expected {expected_item['quantity']}, "
                        f"got {actual_item.quantity}"
                    )

                if actual_item.subscription != expected_item["subscription"]:
                    failures.append(
                        f"items[{i}].subscription: expected {expected_item['subscription']}, "
                        f"got {actual_item.subscription}"
                    )

        # Report ALL failures at once
        if failures:
            failure_report = "\n".join([f"  - {f}" for f in failures])
            pytest.fail(
                f"\n{len(failures)} field(s) failed for {sample['html_filename']}:\n" f"{failure_report}"
            )
