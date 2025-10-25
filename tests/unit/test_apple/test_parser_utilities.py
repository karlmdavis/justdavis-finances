"""Unit tests for Apple parser selector utilities."""

import pytest
from bs4 import BeautifulSoup

from finances.apple.parser import AppleReceiptParser


class TestSelectorUtilities:
    """Test selector utility methods with size validation."""

    def test_select_large_container_accepts_200_chars(self):
        """Large container selector allows up to 200 characters."""
        html = f"<div class='container'>{'x' * 200}</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_large_container(soup, "div.container")
        assert result is not None
        assert len(result) == 200

    def test_select_large_container_rejects_201_chars(self):
        """Large container selector throws on >200 characters."""
        html = f"<div class='container'>{'x' * 201}</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match=r"captured 201 chars.*likely matched a container"):
            parser._select_large_container(soup, "div.container")

    def test_select_small_container_accepts_80_chars(self):
        """Small container selector allows up to 80 characters."""
        html = f"<td class='label'>{'x' * 80}</td>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_small_container(soup, "td.label")
        assert result is not None
        assert len(result) == 80

    def test_select_small_container_rejects_81_chars(self):
        """Small container selector throws on >80 characters."""
        html = f"<td class='label'>{'x' * 81}</td>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match=r"captured 81 chars.*exceeded small container limit"):
            parser._select_small_container(soup, "td.label")

    def test_select_value_accepts_80_chars(self):
        """Value selector allows up to 80 characters."""
        html = f"<span class='value'>{'$' + '9' * 79}</span>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_value(soup, "span.value")
        assert result is not None
        assert len(result) == 80

    def test_select_value_rejects_81_chars(self):
        """Value selector throws on >80 characters."""
        html = f"<span class='value'>{'$' + '9' * 80}</span>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match=r"captured 81 chars.*exceeded value limit"):
            parser._select_value(soup, "span.value")

    def test_select_value_returns_none_when_not_found(self):
        """Value selector returns None when element not found."""
        html = "<div>no matching element</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_value(soup, "span.missing")
        assert result is None
